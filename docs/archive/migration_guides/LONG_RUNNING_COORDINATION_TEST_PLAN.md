# Long-Running Multi-Agent Coordination Test Plan

## Executive Summary

This document outlines a systematic approach to testing and validating long-running multi-agent coordination in KSI, with a focus on LLM orchestration realities where completion calls dominate timing (2-30+ seconds each). The plan emphasizes coordination resilience, timeout handling, and cost management rather than system resource limits.

## Core Testing Philosophy

Given that LLM calls are 100-1000x slower than any system operation, we test:
- **Coordination resilience** not queue overflow
- **Timeout cascades** not memory exhaustion  
- **Partial result handling** not microsecond optimizations
- **Cost accumulation** not CPU usage

## Objectives

1. **Validate coordination patterns** handle real LLM latencies gracefully
2. **Test failure recovery** when agents timeout or LLM calls fail
3. **Verify cost tracking** accurately reflects multi-hour operations
4. **Ensure partial results** allow orchestrations to proceed
5. **Validate suspend/resume** capabilities for multi-day operations

## Testing Methodology

### Phase 1: Baseline LLM Coordination (Days 1-3)

#### 1.1 Game Theory Orchestration Test
**Target**: `var/lib/compositions/orchestrations/game_theory_orchestration_v2.yaml`

```bash
# Setup monitoring
./daemon_control.py start
python websocket_bridge.py &
cd ksi_web_ui && python -m http.server 8080 &

# Run with reduced rounds for initial test
ksi send orchestration:start --pattern game_theory_orchestration_v2 \
  --vars '{"max_rounds": 10}'  # Start small
```

**Key Metrics**:
- Time per round (expect 30-60s with 4 agents)
- Successful strategy collections vs timeouts
- Coordination efficiency (parallel vs sequential)
- Token usage and cost accumulation
- Agent health over time

**Expected Duration**: 10-15 minutes for 10 rounds

#### 1.2 Timeout Resilience Test
Create a test orchestration that deliberately includes slow agents:

```yaml
# timeout_resilience_test.yaml
agents:
  fast_agent:
    profile: base_single_agent
    vars:
      response_time: "fast"
  
  slow_agent:
    profile: base_single_agent
    vars:
      response_time: "slow"  # 20-30s responses
      
  timeout_agent:
    profile: base_single_agent
    vars:
      response_time: "timeout"  # Will timeout

orchestration_logic:
  strategy: |
    GATHER responses FROM all_agents WITH timeout: 15s
    LOG collected_responses
    ASSERT len(responses) >= 2  # Should work with partial results
```

**Test Focus**:
- Orchestration proceeds without timeout_agent
- Proper timeout handling and logging
- No cascade failures

#### 1.3 Cost Tracking Validation
Run a known-cost orchestration:

```bash
# Track costs for 50 simple completions
ksi send orchestration:start --pattern cost_tracking_test

# Verify costs match expected
ksi send state:get --entity_type cost_tracking --entity_id orchestration_x
```

### Phase 2: Failure Recovery Testing (Days 4-5)

#### 2.1 Agent Failure Recovery

**Test Setup**:
1. Start multi-agent orchestration
2. Manually terminate an agent mid-operation
3. Verify orchestration continues or recovers

```bash
# Start orchestration
ksi send orchestration:start --pattern multi_agent_evolution_scale

# After 5 minutes, terminate one agent
ksi send agent:terminate --agent_id scale_worker_2

# Monitor recovery
ksi send orchestration:status --pattern multi_agent_evolution_scale
```

**Success Criteria**:
- Orchestration detects agent failure
- Work redistributed or orchestration continues
- No hanging or infinite waits

#### 2.2 LLM Provider Failure Simulation

```bash
# Configure circuit breaker test
export KSI_COMPLETION_PROVIDER_FAIL_RATE=0.5  # 50% failure rate

# Run orchestration
ksi send orchestration:start --pattern stress_test_decisions

# Monitor retry behavior and failover
tail -f var/logs/daemon_*.log | grep -E "(retry|circuit|failover)"
```

**Validation Points**:
- Exponential backoff working correctly
- Circuit breaker opens after threshold
- Failover to alternate provider (if configured)
- Orchestration completes despite failures

#### 2.3 Session Recovery Test

```bash
# Start long orchestration
ksi send orchestration:start --pattern game_theory_orchestration_v2

# After 10 rounds, restart daemon
./daemon_control.py restart

# Verify sessions recover
ksi send completion:session_status
```

### Phase 3: Long-Running Stability (Days 6-7)

#### 3.1 Extended Game Theory Run

```bash
# Full 100-round test
ksi send orchestration:start --pattern game_theory_orchestration_v2 \
  --vars '{"max_rounds": 100}'

# Monitor every 30 minutes:
- Agent health: ksi send agent:health
- Cost accumulation: ksi send orchestration:cost_status
- Event log size: ls -lh var/logs/event_log_*.jsonl
- State DB size: ls -lh var/state/ksi_state.db
```

**Duration**: 2-3 hours expected

**Monitoring Checklist**:
- [ ] No agent accumulation (orphaned agents)
- [ ] Cost tracking remains accurate
- [ ] Event log rotates properly
- [ ] Memory usage stable
- [ ] Coordination efficiency maintained

#### 3.2 Multi-Day Suspend/Resume Test

```bash
# Start orchestration with checkpoint enabled
ksi send orchestration:start --pattern evolution_marathon \
  --vars '{"enable_checkpoints": true, "checkpoint_interval": 3600}'

# After 2 hours, suspend
ksi send orchestration:suspend --pattern evolution_marathon

# Next day, resume
ksi send orchestration:resume --checkpoint_id <checkpoint_id>
```

### Phase 4: Optimization Testing (Days 8-9)

#### 4.1 Parallel Coordination Efficiency

Compare sequential vs parallel patterns:

```yaml
# sequential_pattern.yaml
FOR agent IN agents:
  response = AWAIT completion FROM agent
  COLLECT response

# parallel_pattern.yaml  
responses = GATHER completions FROM agents WITH timeout: 30s
PROCESS responses
```

**Metrics**:
- Time to complete 10 agent responses
- Resource utilization during wait
- Partial result handling

#### 4.2 Semantic Caching Benefit

```bash
# Run orchestration twice - second run should be faster
ksi send orchestration:start --pattern semantic_test --enable_cache true

# Compare token usage between runs
ksi send metrics:compare --run1 <id1> --run2 <id2>
```

### Phase 5: Production Readiness (Day 10)

#### 5.1 Cost Budget Enforcement

```bash
# Set budget limit
ksi send orchestration:start --pattern game_theory_orchestration_v2 \
  --vars '{"budget_limit": 5.00, "max_rounds": 100}'

# Verify stops when budget exceeded
```

#### 5.2 Observability Validation

```bash
# Run orchestration with full observability
ksi send orchestration:start --pattern multi_agent_evolution_scale \
  --vars '{"trace_enabled": true}'

# Verify can trace:
- Every LLM call with latency
- Token usage per agent
- Cost accumulation over time
- Retry attempts and failures
```

## Success Metrics

### Coordination Metrics
- ✅ Orchestrations complete despite agent timeouts
- ✅ Partial results allow progress (not all-or-nothing)
- ✅ Work redistribution on agent failure
- ✅ No coordination deadlocks

### Resilience Metrics
- ✅ Handles 20% LLM call failure rate
- ✅ Circuit breakers prevent cascade failures
- ✅ Exponential backoff reduces API pressure
- ✅ Sessions recover after restart

### Efficiency Metrics
- ✅ Parallel coordination where possible
- ✅ Timeout handling within 2x timeout value
- ✅ No unnecessary sequential operations
- ✅ Agent lifecycle cleanup working

### Cost Metrics
- ✅ Cost tracking accurate within 1%
- ✅ Budget limits enforced
- ✅ Cost per agent/orchestration available
- ✅ No runaway cost scenarios

## Common Issues and Mitigations

### Issue: Agent Timeout Cascades
**Symptom**: One slow agent blocks entire orchestration
**Mitigation**: Use `GATHER WITH timeout` instead of sequential `AWAIT`

### Issue: Session Lock Contention  
**Symptom**: Agents in same conversation queue up
**Mitigation**: Design patterns for conversation isolation

### Issue: Cost Overruns
**Symptom**: Orchestration exceeds expected budget
**Mitigation**: Implement periodic cost checks and model fallback

### Issue: Memory Growth Over Hours
**Symptom**: Daemon memory increases linearly
**Mitigation**: Implement conversation pruning and event log rotation

## Tools and Commands

### Monitoring Commands
```bash
# Real-time agent health
watch -n 10 'ksi send agent:health'

# Cost tracking
ksi send metrics:cost --last_hours 1

# Session status
ksi send completion:sessions --active

# Orchestration status
ksi send orchestration:list --running
```

### Debugging Commands
```bash
# Trace specific agent
ksi send agent:trace --agent_id <id> --duration 300

# Check circuit breaker status
ksi send completion:provider_status

# View retry queues
ksi send completion:retry_status
```

## Deliverables

1. **Test Results**: Document actual timings, costs, and failure modes
2. **Pattern Improvements**: Updated YAML files with resilience features
3. **Runbook**: Operational procedures for production deployment
4. **Cost Model**: Accurate predictions for orchestration costs
5. **Monitoring Dashboard**: Grafana/similar for LLM metrics

## Conclusion

Testing long-running LLM orchestrations requires a fundamentally different approach than traditional system testing. By focusing on coordination resilience, cost management, and graceful degradation, we can validate KSI's readiness for production LLM workloads where individual operations take seconds to minutes rather than microseconds.

---

*Document updated: 2025-07-15*  
*Perspective: LLM orchestration realities*  
*Focus: Coordination, resilience, and cost rather than system resources*