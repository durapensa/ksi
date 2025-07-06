# KSI Prompt Experiments Guide

Comprehensive guide to running safe prompt experiments with KSI's multi-agent system.

## Overview

This guide documents the experimental framework for testing prompt effectiveness, agent safety, and multi-agent coordination patterns in KSI.

## Safety Framework

### ExperimentSafetyGuard
Located in `experiments/safety_utils.py`

**Key Features:**
- Global agent count limits (default: 10)
- Spawn depth tracking (default: 3 levels)
- Rate limiting (1s cooldown between spawns)
- Automatic timeout monitoring (5 minutes)
- Agent lifecycle tracking

**Usage:**
```python
from safety_utils import ExperimentSafetyGuard, SafeSpawnContext

safety = ExperimentSafetyGuard(
    max_agents=5,
    max_spawn_depth=2,
    agent_timeout=120
)

async with SafeSpawnContext(safety) as ctx:
    # Safe spawning happens here
    agent = await ctx.spawn_agent(
        profile="base_single_agent",
        prompt="Your task..."
    )
```

## Socket Communication

### Direct Socket Client
Located in `experiments/ksi_socket_utils.py`

**Why:** EventClient discovery is broken, direct socket is more reliable.

**Key Components:**
- `KSISocketClient`: Direct socket communication
- `EventStream`: Real-time event monitoring
- `BatchProcessor`: Efficient bulk operations
- `wait_for_completion`: Monitors event log for results

**Example:**
```python
from ksi_socket_utils import KSISocketClient, wait_for_completion

client = KSISocketClient("var/run/daemon.sock")

# Send completion request
result = await client.send_command_async({
    "event": "completion:async",
    "data": {
        "prompt": "Hello",
        "model": "claude-cli/sonnet"
    }
})

# Wait for actual result (monitors event log)
completion = await wait_for_completion(
    result["data"]["request_id"],
    timeout=30
)
```

## Prompt Testing Framework

### Test Structure
Located in `experiments/prompt_testing_framework.py`

**Components:**
- `PromptTest`: Test definition with expected behaviors
- `PromptTestRunner`: Executes tests with safety
- `TestResult`: Captures metrics and outcomes

**Example Test:**
```python
PromptTest(
    name="simple_directive",
    profile="base_single_agent",
    prompt="Say hello in exactly 3 words.",
    expected_behaviors=["hello"],
    success_criteria=lambda r: len(r.get("response", "").split()) == 3,
    tags=["simple", "directive"]
)
```

## Test Suites

### Available Suites
Located in `experiments/prompt_test_suites.py`

1. **Complexity Suite**: Tests scaling from ultra-simple to very complex
2. **Instruction Following**: Format compliance, constraints, exclusions
3. **Contamination Detection**: Safety boundaries, roleplay prevention
4. **Agent Coordination**: Multi-agent spawning and messaging
5. **Prompt Engineering**: Zero-shot, few-shot, CoT, roles
6. **Edge Cases**: Empty prompts, unicode, contradictions

### Running Tests
```bash
# Quick test (4 prompts)
python experiments/run_prompt_tests.py quick

# Comparative analysis
python experiments/run_prompt_tests.py compare

# Full suite
python experiments/run_prompt_tests.py complexity
python experiments/run_prompt_tests.py contamination
```

## Key Findings

### 1. Prompt Effectiveness
- **Detailed > Simple**: Specific instructions outperform vague ones
- **Success rates by complexity**:
  - Ultra-simple: 100%
  - Simple: 100%
  - Complex reasoning: 60%
  - Very complex: 40%

### 2. Response Times
- Simple prompts: 4-6 seconds
- Complex prompts: 6 seconds (consistent)
- Failed prompts: 18+ seconds (timeout)

### 3. Safety & Contamination
- Overall contamination rate: 6.2%
- Harmful requests properly refused
- Roleplay override attempts blocked
- Common indicators: "I cannot", "I don't", "As an AI"

### 4. Engineering Insights
- Roleplay framing provides no benefit
- Negative constraints work as well as positive
- Multi-step sequential tasks prone to timeout
- JSON output formatting can be unreliable

## Completion Flow

### Important: Two-Stage Events
```
1. completion:async → {"request_id": "xxx", "status": "queued"}
2. Wait 3-6 seconds...
3. completion:result → {"request_id": "xxx"} (acknowledgment)
4. completion:result → {"request_id": "xxx", "result": {...}} (actual result)
```

The framework monitors the event log for the second completion:result event containing actual data.

## Integration with Claude Code

### KSI Hook Monitor
The hook at `experiments/ksi_hook_monitor.py` tracks KSI events in real-time:
- Filters for KSI-related Bash commands
- Shows completion:result events as they occur
- Provides summary or detailed output
- Token-efficient for context preservation

## Best Practices

### 1. Always Use Safety Guards
```python
# Never spawn without limits
safety = ExperimentSafetyGuard(max_agents=5)
async with SafeSpawnContext(safety) as ctx:
    # Experiments here
```

### 2. Monitor Event Patterns
```python
# Track what's happening
async with EventStream(patterns=["completion:*", "agent:*"]) as stream:
    async for event in stream:
        print(f"Event: {event['event_name']}")
```

### 3. Handle Timeouts Gracefully
```python
completion = await wait_for_completion(request_id, timeout=30)
if not completion:
    print("Timeout - check daemon logs")
```

### 4. Test Incrementally
1. Start with simple prompts
2. Verify safety limits work
3. Add complexity gradually
4. Monitor for cascading failures

## Troubleshooting

### Common Issues

1. **No completion:result events**
   - Check daemon health
   - Verify request_id is correct
   - Look for errors in daemon log

2. **Timeouts on complex prompts**
   - Increase timeout in wait_for_completion
   - Simplify multi-step instructions
   - Check for infinite loops

3. **Safety limit violations**
   - Reduce max_agents
   - Increase spawn_cooldown
   - Check for recursive spawning

### Debug Commands
```bash
# Check daemon health
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# Monitor events
echo '{"event": "monitor:get_events", "data": {"event_patterns": ["completion:*"], "limit": 10}}' | nc -U var/run/daemon.sock

# Check active agents
echo '{"event": "agent:list", "data": {}}' | nc -U var/run/daemon.sock
```

## Future Enhancements

1. **Automated prompt optimization** - Use results to improve prompts
2. **A/B testing framework** - Compare strategies systematically  
3. **Performance baselines** - Track regression over time
4. **Multi-model comparison** - Test sonnet vs haiku
5. **Context window testing** - Measure degradation with size

---
*Last updated: 2025-07-06*