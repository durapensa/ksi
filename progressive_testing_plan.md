# Progressive Testing Plan: Simple to Complex

## Phase 1: Basic JSON Extraction (✅ WORKING)

### Test 1.1: Single Agent JSON Emission
**Status**: ✅ Verified working
```bash
# Simple valid JSON test
./ksi send orchestration:start --pattern test_json_extraction_simple
```
**Expected**: Agent emits valid JSON, events extracted, feedback received

### Test 1.2: Malformed JSON Detection
**Status**: ⏳ Next to test
```bash
# Test malformed JSON patterns  
./ksi send orchestration:start --pattern test_json_malformed
```
**Expected**: Agent attempts malformed JSON, receives helpful error feedback

### Test 1.3: JSON Feedback Loop
**Status**: ⏳ Pending
```bash
# Agent receives feedback and corrects JSON
python test_json_feedback.py
```
**Expected**: Agent learns from feedback and corrects JSON format

## Phase 2: MIPRO Optimization Patterns

### Test 2.1: Simple MIPRO Demo
**Status**: ✅ Verified working
```bash
./ksi send orchestration:start --pattern mipro_simple_demo
```
**Expected**: Prompt optimization with JSON event tracking

### Test 2.2: Full MIPRO Orchestration  
**Status**: ⏳ Pending comprehensive test
```bash
./ksi send orchestration:start --pattern mipro_bayesian_optimization
# Monitor with: python monitor_orchestration.py orch_[id]
```
**Expected**: 3-stage optimization with multiple agent coordination

## Phase 3: Multi-Agent Coordination

### Test 3.1: Simple Agent Spawning
**Status**: ⏳ Design needed
- Orchestrator spawns 2-3 simple agents
- Each agent performs basic task (emit state:set event)
- Orchestrator collects results
- All agents terminated cleanly

### Test 3.2: Agent Communication Chain
**Status**: ⏳ Design needed  
- Agent A spawns Agent B
- Agent A sends message to Agent B via agent:send_message
- Agent B processes and responds
- Agent A collects response and terminates Agent B

### Test 3.3: Parallel Agent Processing
**Status**: ⏳ Design needed
- Orchestrator spawns 5 agents in parallel
- Each agent processes different part of task
- Orchestrator waits for all completions (orchestration:await)
- Results aggregated and analyzed

## Phase 4: Complex Orchestration Patterns

### Test 4.1: Adaptive Agent Management
**Status**: ⏳ Design needed
- Orchestrator monitors agent performance
- Spawn additional agents if tasks are slow
- Terminate under-performing agents
- Dynamic workload balancing

### Test 4.2: Hierarchical Agent Structure
**Status**: ⏳ Design needed
- Level 1: Master orchestrator
- Level 2: 3 sub-orchestrators (different specializations)
- Level 3: Each sub-orchestrator manages 2-3 worker agents
- Cross-level communication and coordination

### Test 4.3: Failure Recovery Patterns
**Status**: ⏳ Design needed
- Orchestrator spawns agents with intentional failure scenarios
- Test timeout handling (agents that don't respond)
- Test error propagation (agents that fail)
- Test graceful degradation (continue with partial results)

## Phase 5: Advanced Coordination

### Test 5.1: Real-time Agent Negotiation
**Status**: ⏳ Advanced design needed
- Multiple agents negotiate task assignment
- Use orchestration:coordinate for consensus
- Dynamic task redistribution based on agent capabilities
- Measure coordination efficiency

### Test 5.2: Self-Organizing Agent Network
**Status**: ⏳ Research phase
- Agents discover and connect to each other
- Form task-specific coalitions
- Self-healing when agents fail
- Emergent coordination patterns

### Test 5.3: Resource-Constrained Orchestration
**Status**: ⏳ Research phase
- Limited agent spawn budget
- Cost-aware task allocation
- Performance vs. resource trade-offs
- Optimization under constraints

## Success Criteria

### Phase 1-2 (Basic/MIPRO)
- [ ] JSON events extracted reliably (>95% success rate)
- [ ] Malformed JSON receives helpful feedback
- [ ] MIPRO shows measurable prompt improvement (>20%)
- [ ] Response times reasonable (<2 minutes for simple tests)

### Phase 3 (Multi-Agent)
- [ ] Agents spawn and terminate cleanly
- [ ] Cross-agent communication works reliably  
- [ ] Orchestrator can coordinate 5+ agents
- [ ] No resource leaks (all agents properly cleaned up)

### Phase 4 (Complex Patterns)
- [ ] Dynamic agent management works
- [ ] Hierarchical coordination successful
- [ ] Failure scenarios handled gracefully
- [ ] System recovers from partial failures

### Phase 5 (Advanced)
- [ ] Complex negotiation patterns work
- [ ] Self-organization emerges
- [ ] System scales to 20+ concurrent agents
- [ ] Resource optimization measurable

## Testing Infrastructure

### Monitoring Tools
- `monitor_orchestration.py` - Patient polling with subprocess tracking
- Response log analysis scripts
- Event extraction verification
- Performance metric collection

### Safety Measures
- Maximum agent spawn limits
- Timeout enforcement
- Resource monitoring
- Graceful cleanup procedures

### Metrics Collection
- Success/failure rates
- Response times
- Resource utilization
- Coordination efficiency
- Cost tracking

## Current Focus

**Immediate Next Steps**:
1. Complete Phase 1 testing (malformed JSON)
2. Verify Phase 2 MIPRO patterns work end-to-end
3. Design and implement Phase 3.1 simple spawning test
4. Create monitoring dashboards for complex tests

**Success Definition**: Each phase must achieve >90% success rate before advancing to next phase.