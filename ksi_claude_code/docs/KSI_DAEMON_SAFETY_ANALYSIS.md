# KSI Daemon Safety Analysis

Comprehensive analysis of existing safety features and recommendations for experiments.

## Executive Summary

KSI daemon has basic safety infrastructure but lacks comprehensive agent lifecycle management. Key gaps:
- No global agent count limits
- No spawn rate limiting  
- Incomplete circuit breaker implementation
- No cascade failure prevention

## Existing Safety Features

### 1. Agent Spawn Depth Tracking ✓
**Location**: `ksi_daemon/injection/injection_router.py:43-103`

The `InjectionCircuitBreaker` class provides:
- **Max depth**: 5 levels (hardcoded)
- Tracks parent-child relationships
- Blocks requests exceeding depth
- Maintains blocked request tracking

```python
class InjectionCircuitBreaker:
    MAX_DEPTH = 5  # Maximum injection depth
    
    def check_request_allowed(self, request_data):
        depth = self._calculate_depth(parent_id)
        if depth >= self.MAX_DEPTH:
            self.blocked_requests.add(request_id)
            return False, f"Max depth {self.MAX_DEPTH} exceeded"
```

### 2. Timeout Controls ✓
**Location**: `ksi_common/config.py:138-147`

Comprehensive timeout configuration:
- `completion_timeout_default`: 300s (5 minutes)
- `completion_timeout_min`: 60s (1 minute)
- `completion_timeout_max`: 1800s (30 minutes)
- `claude_timeout_attempts`: [300, 900, 1800] progressive
- `claude_progress_timeout`: 300s without progress
- `claude_max_workers`: 2 concurrent processes

### 3. Retry Management ✓
**Location**: `ksi_daemon/completion/retry_manager.py:23-33`

Exponential backoff retry policy:
- Max attempts: 3
- Initial delay: 1.0s
- Max delay: 60.0s
- Backoff multiplier: 2.0x
- Retryable errors: timeout, network_error, api_rate_limit, etc.

### 4. Event Queue Management ✓
**Location**: `ksi_common/config.py:94-98`

Basic queue limits:
- `event_write_queue_size`: 5000 events
- `event_batch_size`: 100 events/batch
- `event_flush_interval`: 1.0s

## Missing Safety Features

### 1. Global Agent Limits ❌
- **No limit** on total active agents
- System can spawn unlimited agents
- No memory/resource tracking per agent

### 2. Spawn Rate Limiting ❌
- Agents can spawn children rapidly
- No throttling on spawn requests
- No cooldown periods

### 3. Circuit Breaker Incomplete ❌
**Location**: `ksi_daemon/injection/injection_router.py`

Placeholders exist but not implemented:
- Token tracking (50k budget defined, not enforced)
- Time window tracking (3600s defined, not used)
- Risk score calculation (referenced but not implemented)

### 4. Agent Timeouts ❌
- No automatic agent termination
- Agents can run indefinitely
- No activity monitoring

### 5. Cascade Failure Prevention ❌
- Parent termination doesn't stop children
- No graceful shutdown propagation
- Orphaned agents continue running

### 6. Resource Quotas ❌
- No CPU/memory limits
- No disk usage tracking
- No network bandwidth limits

## EventClient Discovery Issues

### Root Cause
**Location**: `ksi_client/client.py:504-541`

The EventClient discovery expects:
```python
# Expected format
{"events": {"namespace": [event_list]}}

# Actual format
{"events": {"event:name": {details}}}
```

### Symptoms
- Discovery timeout after BOOTSTRAP_TIMEOUT (5s)
- EventClient falls back to bootstrap-only mode
- Dynamic namespace access fails

### Workaround
Direct socket communication is more reliable:
```python
# Instead of EventClient
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("var/run/daemon.sock")
```

## Missing Experimental Modules

### Not Found
- `prompts/composition_evolution.py`
- `prompts/fitness_evaluator.py`

These are referenced in `experiments/prompt_evolution_experiment.py` but don't exist. The experiment cannot run without implementing these modules.

## Recommendations for Safe Experiments

### 1. Implement Experiment-Level Safety

Create `experiments/safety_utils.py`:
```python
class ExperimentSafetyGuard:
    def __init__(self):
        self.max_agents = 10
        self.max_spawn_depth = 3
        self.max_children_per_agent = 5
        self.agent_timeout = 300  # 5 minutes
        self.spawn_cooldown = 1.0  # seconds between spawns
        
    async def check_spawn_allowed(self, parent_id=None):
        # Check total agents
        agents = await get_agent_list()
        if len(agents) >= self.max_agents:
            return False, "Max agent limit reached"
            
        # Check spawn depth
        if parent_id:
            depth = await calculate_depth(parent_id)
            if depth >= self.max_spawn_depth:
                return False, "Max spawn depth reached"
                
        return True, "Spawn allowed"
        
    async def monitor_agents(self):
        """Background task to kill old agents"""
        while True:
            agents = await get_agent_list()
            for agent in agents:
                if agent_age(agent) > self.agent_timeout:
                    await terminate_agent(agent['agent_id'])
            await asyncio.sleep(30)  # Check every 30s
```

### 2. Use Direct Socket Communication

Until EventClient is fixed, use socket directly:
```python
# experiments/ksi_socket_utils.py
def send_command(cmd):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("var/run/daemon.sock")
    sock.sendall(json.dumps(cmd).encode() + b'\n')
    
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
        try:
            json.loads(response.decode())
            break
        except:
            continue
    
    sock.close()
    return json.loads(response.decode())
```

### 3. Enhance Daemon vs Work Around?

**Recommendation**: Implement safety in experiments first, then migrate to daemon.

**Rationale**:
- Faster iteration in experiments
- Test different safety strategies
- Migrate proven patterns to daemon
- Keeps daemon stable during experimentation

**Future Daemon Enhancements**:
1. Global agent registry with limits
2. Spawn rate limiting
3. Complete circuit breaker implementation
4. Agent lifecycle hooks
5. Resource quota enforcement

### 4. Safe Experiment Patterns

```python
async def safe_multi_agent_experiment():
    """Example of safe multi-agent pattern"""
    safety = ExperimentSafetyGuard()
    
    # Start monitoring
    monitor_task = asyncio.create_task(safety.monitor_agents())
    
    try:
        # Spawn coordinator with limits
        allowed, reason = await safety.check_spawn_allowed()
        if not allowed:
            print(f"Spawn blocked: {reason}")
            return
            
        coordinator = await spawn_agent(
            profile="base_multi_agent",
            prompt="Coordinate research. Spawn MAX 3 agents.",
            metadata={"safety_limits": safety.to_dict()}
        )
        
        # Monitor spawned children
        await asyncio.sleep(1)  # Let spawns happen
        
        # Check limits weren't exceeded
        agents = await get_agent_list()
        assert len(agents) <= safety.max_agents
        
    finally:
        # Cleanup
        monitor_task.cancel()
        await cleanup_all_agents()
```

## Next Steps

1. **Immediate**: Create `experiments/safety_utils.py`
2. **Short-term**: Run baseline experiments with safety guards
3. **Medium-term**: Document effective patterns
4. **Long-term**: Migrate proven safety to daemon

---
*Generated: 2025-07-06*