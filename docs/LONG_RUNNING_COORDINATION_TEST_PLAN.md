# Long-Running Multi-Agent Coordination Test Plan

## Executive Summary

This document outlines a systematic approach to testing and validating long-running multi-agent coordination in KSI, with a focus on identifying and resolving bottlenecks that prevent sustained autonomous operation.

## Objectives

1. **Validate sustained multi-agent coordination** over extended periods (30+ minutes)
2. **Identify and fix coordination bottlenecks** in prompts and system internals
3. **Establish performance baselines** for production deployment
4. **Create debugging playbooks** for common failure modes
5. **Ensure graceful degradation** under stress conditions

## Testing Methodology

### Phase 1: Baseline Testing (Days 1-2)

#### 1.1 Game Theory Orchestration Test
**Target**: `var/lib/compositions/orchestrations/game_theory_orchestration_v2.yaml`

```bash
# Setup monitoring infrastructure
./daemon_control.py start
python websocket_bridge.py &
cd ksi_web_ui && python -m http.server 8080 &

# Run with default parameters
ksi send orchestration:start --pattern game_theory_orchestration_v2

# Expected runtime: 10-30 minutes for 100 rounds
```

**Key Metrics**:
- Time to spawn all agents
- Average response time per strategy request
- Rounds to equilibrium convergence
- Total events generated
- Memory/CPU usage over time

#### 1.2 Multi-Agent Evolution Scale Test
**Target**: `var/lib/compositions/orchestrations/multi_agent_evolution_scale.yaml`

```bash
# Run with 5 agents × 20 decisions
ksi send orchestration:start --pattern multi_agent_evolution_scale

# Expected runtime: 20-30 minutes
```

**Key Metrics**:
- Concurrent agent spawn success rate
- Decision generation throughput
- Pattern conflict detection
- Resource utilization scaling

#### 1.3 Stress Test Decisions
**Target**: `var/lib/compositions/orchestrations/stress_test_decisions.yaml`

```bash
# Run 1000 decisions in batches
ksi send orchestration:start --pattern stress_test_decisions

# Expected runtime: 15-30 minutes
```

**Key Metrics**:
- Event emission rate
- Decision tracking latency
- System stability under load
- Memory growth patterns

### Phase 2: Failure Mode Analysis (Days 3-4)

#### 2.1 Common Failure Patterns

**Agent Communication Failures**:
- **Symptom**: Agents not responding to directed events
- **Detection**: Watch for timeout patterns in visualization
- **Debug**: Check event routing rules and agent event handling

**Strategy Collection Timeouts**:
- **Symptom**: Orchestrator waiting indefinitely for responses
- **Detection**: Monitor `game:request_strategy` → `game:strategy_response` pairs
- **Debug**: Examine agent prompts for event emission instructions

**Equilibrium Calculation Hangs**:
- **Symptom**: Async completion requests never returning
- **Detection**: Track `completion:async` → `completion:result` timing
- **Debug**: Check completion handler and model response parsing

**Pattern Crystallization Overload**:
- **Symptom**: Decision tracking events overwhelming system
- **Detection**: Event queue growth, processing delays
- **Debug**: Batch decision tracking, implement rate limiting

**Agent Lifecycle Issues**:
- **Symptom**: Agents not terminating, orphaned processes
- **Detection**: Growing agent count in health checks
- **Debug**: Verify termination event handling

#### 2.2 Debugging Protocol

1. **Real-time Observation**:
   ```bash
   # Monitor event stream
   ksi --health discover  # Check system health
   
   # Watch specific event patterns
   tail -f var/logs/event_log.json | jq 'select(.event | contains("game:"))'
   
   # Check agent states
   ksi send agent:list
   ```

2. **Event Flow Tracing**:
   ```bash
   # Trace specific agent's events
   ksi send system:trace --agent_id <agent_id> --duration 60
   
   # Analyze event patterns
   python scripts/analyze_event_patterns.py --pattern game_theory
   ```

3. **Performance Profiling**:
   ```bash
   # CPU/Memory monitoring
   htop -p $(pgrep -f "ksi_daemon")
   
   # Event processing metrics
   ksi send system:metrics --component event_router
   ```

### Phase 3: Systematic Fixes (Days 5-7)

#### 3.1 Prompt Engineering Improvements

**Agent Response Reliability**:
```yaml
# Before: Vague instructions
initial_prompt: |
  Respond to strategy requests when asked.

# After: Explicit event handling
initial_prompt: |
  CRITICAL: You MUST respond to ALL events directed to you.
  
  When you receive {"event": "game:request_strategy", ...}:
  1. IMMEDIATELY emit a response event
  2. Use format: {"event": "game:strategy_response", "data": {"agent_id": "{{agent_id}}", "strategy": "...", "confidence": 0.8}}
  3. Include your actual agent_id from the environment
  4. Respond within 5 seconds or emit timeout acknowledgment
```

**Orchestrator Coordination**:
```yaml
# Add explicit timeout handling
initial_prompt: |
  Strategy collection protocol:
  1. Emit "game:request_strategy" to each agent
  2. Set 10-second timeout per agent
  3. If no response, emit "game:agent_timeout" and continue
  4. Never wait indefinitely - always progress
```

#### 3.2 System Internal Improvements

**Event Router Enhancements**:
```python
# Add timeout support for directed events
class EventRouter:
    async def route_with_timeout(self, event, timeout=10):
        """Route event with response timeout"""
        response_future = asyncio.Future()
        self.pending_responses[event['id']] = response_future
        
        try:
            await self.route(event)
            return await asyncio.wait_for(response_future, timeout)
        except asyncio.TimeoutError:
            del self.pending_responses[event['id']]
            return {"timeout": True, "event_id": event['id']}
```

**Completion System Resilience**:
```python
# Add retry logic for completion requests
async def handle_completion_async(self, event):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await self._call_completion_api(event)
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e), "retries_exhausted": True}
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

**Resource Management**:
```python
# Implement agent limits
class AgentManager:
    MAX_CONCURRENT_AGENTS = 50
    
    async def spawn_agent(self, profile, vars):
        if len(self.active_agents) >= self.MAX_CONCURRENT_AGENTS:
            # Queue or reject based on priority
            return {"error": "Agent limit reached", "limit": self.MAX_CONCURRENT_AGENTS}
```

### Phase 4: Validation & Benchmarking (Days 8-9)

#### 4.1 Success Criteria

**Stability Metrics**:
- ✓ Game theory orchestration completes 100 rounds without hanging
- ✓ Multi-agent scale test spawns 5+ agents successfully
- ✓ Stress test processes 1000+ decisions without crashes
- ✓ Memory usage remains stable (< 2GB growth)
- ✓ CPU usage averages < 70% on single core

**Performance Targets**:
- Agent spawn time: < 2 seconds per agent
- Event routing latency: < 50ms average
- Strategy response time: < 5 seconds per agent
- Completion request processing: < 10 seconds
- Decision tracking throughput: > 100/second

**Reliability Goals**:
- Zero agent orphans after orchestration
- < 1% event routing failures
- Graceful timeout handling (no hangs)
- Clean shutdown within 30 seconds

#### 4.2 Benchmark Suite

```yaml
# benchmark_config.yaml
benchmarks:
  - name: "agent_spawn_rate"
    test: "spawn 10 agents sequentially"
    target: "< 20 seconds total"
    
  - name: "concurrent_coordination"
    test: "5 agents exchanging 100 messages"
    target: "< 60 seconds total"
    
  - name: "decision_tracking_throughput"
    test: "emit 1000 decision events"
    target: "> 100 decisions/second"
    
  - name: "memory_stability"
    test: "run game_theory_orchestration 3x"
    target: "< 500MB growth total"
```

### Phase 5: Production Readiness (Day 10)

#### 5.1 Monitoring & Alerting

**Health Check Enhancements**:
```python
# Add coordination-specific health metrics
health_status = {
    "agents": {
        "active": len(active_agents),
        "stuck": len([a for a in active_agents if a.last_event_age > 60]),
        "orphaned": len(orphaned_agents)
    },
    "orchestrations": {
        "active": len(active_orchestrations),
        "average_runtime": avg_runtime,
        "completion_rate": completed / started
    },
    "event_flow": {
        "routing_latency_p99": p99_latency,
        "timeout_rate": timeouts / total_routed,
        "queue_depth": event_queue.qsize()
    }
}
```

**Alert Conditions**:
- Agent stuck for > 5 minutes
- Event queue depth > 1000
- Routing latency p99 > 1 second
- Memory usage > 80% of limit
- Orchestration runtime > 2x expected

#### 5.2 Operational Playbooks

**Stuck Agent Recovery**:
```bash
# 1. Identify stuck agents
ksi send agent:list | jq '.agents[] | select(.last_event_age > 300)'

# 2. Send recovery event
ksi send agent:recover --agent_id <stuck_id> --action restart

# 3. If unresponsive, force terminate
ksi send agent:terminate --agent_id <stuck_id> --force true
```

**Orchestration Timeout Recovery**:
```bash
# 1. Check orchestration state
ksi send orchestration:status --pattern <pattern_name>

# 2. Identify blocking operation
ksi send orchestration:debug --pattern <pattern_name> --show_blocking

# 3. Skip or retry operation
ksi send orchestration:skip_step --pattern <pattern_name> --step <step_id>
```

## Implementation Timeline

**Week 1**:
- Days 1-2: Baseline testing and metric collection
- Days 3-4: Failure mode analysis and documentation
- Day 5: Review and planning checkpoint

**Week 2**:
- Days 6-7: Implement prompt and system fixes
- Days 8-9: Validation testing and benchmarking
- Day 10: Production readiness assessment

## Deliverables

1. **Test Results Report**: Comprehensive analysis of all test runs
2. **Fixed Compositions**: Updated YAML files with improved prompts
3. **System Patches**: Code changes for resilience and performance
4. **Monitoring Dashboard**: Real-time coordination health metrics
5. **Operational Guide**: Playbooks for common issues
6. **Performance Baseline**: Documented benchmarks for future comparison

## Risk Mitigation

**Technical Risks**:
- **Architectural limitations**: May require event system refactoring
- **Model response variability**: Implement robust parsing and validation
- **Resource constraints**: Add configurable limits and quotas

**Operational Risks**:
- **Production incidents**: Implement gradual rollout with feature flags
- **Debugging complexity**: Enhance tracing and observability tools
- **Performance regression**: Establish CI/CD performance gates

## Success Metrics

The testing initiative will be considered successful when:
1. All three test orchestrations run to completion without manual intervention
2. System maintains stable performance over 1+ hour runs
3. Comprehensive debugging tools are available for production issues
4. Clear operational procedures exist for common failure modes
5. Performance baselines are established and documented

## Next Steps

1. **Immediate**: Start Phase 1 baseline testing
2. **This week**: Complete failure analysis and begin fixes
3. **Next week**: Validate fixes and establish production readiness
4. **Follow-up**: Implement safety guards based on learnings

---

*Document created: 2025-07-15*  
*Last updated: 2025-07-15*  
*Owner: KSI Development Team*