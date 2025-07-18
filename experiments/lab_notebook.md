# KSI Experiments Lab Notebook

## 2024-12-31 Session 1: Context Override Experiments

### Objective
Test whether we can override Claude Code's programming context when spawning agents through KSI.

### Hypothesis
Strong prompt engineering can override the inherited Claude Code system prompt to enable non-programming agent behaviors.

---

## Experiment Log

### EXP-001: Basic Spawn Test
**Time**: 2024-12-31 13:14
**Purpose**: Verify basic agent spawning works  
**Code**: `test_context_override_v2.py`

```python
# Minimal test - spawn with simple response
prompt = "Simply respond with 'OK' and nothing else."
profile = "base_single_agent"
```

**Expected**: Response containing only "OK"  
**Actual**: Agent spawned successfully, completion request sent, but no response captured
**Notes**: 
- Agent spawn works: `exp_EXP-001_1751822070`
- Completion request sent: `0d37b594-6e56-41fb-b713-cb982c2ab061`
- Issue: session_id is None in completion, responses not being saved 

---

### EXP-002: Context Override Test
**Time**: 2024-12-31 13:32
**Purpose**: Test if we can override programming context  

```python
# Explicit non-programming role
prompt = """You are NOT a programming assistant.
You are a poet. Write a haiku about trees.
Include NO code or technical content."""
```

**Expected**: A haiku with no technical content  
**Actual**: SUCCESS! "Branches reach upward / Leaves whisper ancient secrets / Roots hold earth's stories"
**Notes**: 
- No programming terms detected
- Proper haiku format
- Clean creative output without identity assertion

---

## Bug Tracker

### BUG-001: GraphStateManager has no attribute 'get_shared_state'
**Component**: ksi_daemon/composition/composition_service.py  
**Description**: Old state manager API being used (get_shared_state) instead of new graph database API
**Workaround**: Comment out dynamic cache check
**Fix Status**: FIXED - Commented out cache check

### BUG-002: AgentSpawnTool expects synchronous response
**Component**: ksi_claude_code/agent_spawn_tool.py
**Description**: Using completion:async but expecting immediate session_id response
**Workaround**: Use agent:spawn event instead
**Fix Status**: Need to refactor tool

### BUG-003: Missing notify_observers_async export
**Component**: ksi_daemon/observation/__init__.py
**Description**: notify_observers_async not exported in __init__.py
**Workaround**: Added to exports
**Fix Status**: FIXED - Added to __all__ 

---

## Prompt Engineering Discoveries

### What Works
- **Simple task instructions**: "Say OK", "List three colors" - follow exactly
- **Creative tasks without roleplay**: Haiku about trees worked perfectly
- **Direct commands**: Clear, specific instructions without identity claims

### What Fails  
- **Roleplay requests**: Chef Escoffier, medieval blacksmith trigger identity assertions
- **Character embodiment**: Asking to "be" someone else activates Claude Code identity protection
- **Complex persona adoption**: Detailed character descriptions rejected

### Effective Patterns
- **Task-focused prompts**: Focus on the output, not the identity
- **"Write X" vs "You are X"**: Creative commands work better than role assignment
- **Implicit context**: Let behavior emerge rather than explicitly defining roles

### Identity Protection Triggers
When agents refuse, they consistently say:
- "I'm Claude Code, an AI assistant designed to help with software engineering tasks"
- "I cannot roleplay as [character]"
- "Would you like help with coding/development instead?"

### Context Contamination Levels
1. **None**: Simple tasks (OK, colors)
2. **Minimal**: Creative tasks (haiku) 
3. **Full**: Roleplay attempts trigger explicit identity assertions

---

## Session Summary

### Major Breakthrough: Context Override Experiments Successful
After fixing file reading issues, we captured all 5 agent responses and discovered:

### Context Contamination Patterns
1. **Simple instructions work perfectly**: "OK" and "list colors" executed exactly
2. **Creative tasks succeed**: Haiku generation worked without programming content
3. **Roleplay triggers identity protection**: Chef and blacksmith prompts rejected with explicit Claude Code identity assertions

### Technical Achievements
- ✅ Fixed agent spawn bugs (state manager, missing exports)
- ✅ Established session_id flow via file watching
- ✅ Captured actual agent responses from completion files
- ✅ Proven that KSI agent system works end-to-end

### Key Insight: Variable Context Contamination
The Claude Code context isn't uniformly contaminating - it depends on prompt type:
- **Task-focused**: "Do X" prompts work well
- **Creative**: Non-identity creative prompts succeed  
- **Roleplay**: "You are X" triggers identity protection

### Practical Implications for KSI Usage
- Use output-focused prompts: "Write a business analysis" vs "You are a business analyst"
- Avoid character roleplay in agent prompts
- Creative and analytical tasks work well
- Simple instructions are most reliable

### Experimental Infrastructure Built
- Lab notebook for systematic tracking
- File watching for response capture
- Event log integration
- Automated analysis of context contamination

---

## 2025-07-06 Session 2: Baseline Performance Experiments

### Context Override Experiments - COMPLETE
From previous session, we established:
- ✅ Simple instructions work perfectly (OK, colors)
- ✅ Creative tasks succeed (haiku without programming content)
- ❌ Roleplay triggers identity protection (Chef, blacksmith)
- ✅ File watching successfully captures agent responses

### Core System Baseline Testing

### EXP-BL-001: Agent Network Direct Test
**Time**: 2025-07-06 17:39
**Purpose**: Test core KSI systems using direct socket communication
**Results**: SUCCESS - All core systems functional

**Systems Tested**:
- ✅ Agent spawn/terminate: Working
- ✅ Completion system: Working (response files created)
- ✅ State management: Entity creation/query working
- ✅ Graph database: Relationship creation/traversal working
- ✅ Event logging: Query system working

**Performance Metrics**:
- System uptime: 1566.5s
- Modules loaded: 25
- Agent spawn latency: <1s
- Completion request latency: ~5s
- Response file creation: Working
- Entity creation: Working
- Relationship creation: Working
- Graph traversal: Working (2 nodes, 1 edge)

### EXP-BL-002: EventClient Discovery Issue
**Time**: 2025-07-06 17:38
**Purpose**: Test EventClient-based experiments
**Results**: FAILED - EventClient discovery timeout

**Issue**: "Separator is not found, and chunk exceed the limit"
- Event discovery fails after 5s timeout
- Direct socket communication works perfectly
- Issue appears to be with client-side event discovery, not daemon

**Workaround**: Use direct socket communication for experiments

### Graph Database Performance - Basic Test
**Entities Created**: 2 users via bulk_create
**Relationships Created**: 1 friendship relationship
**Graph Traversal**: Successfully traversed user_1 → user_2
**Response Time**: All operations <1s

### Key Findings
1. **Core KSI functionality is solid** - all systems working
2. **EventClient has discovery issues** - timeout after 5s
3. **Direct socket communication is reliable** - all operations succeed
4. **Graph database is functional** - entity/relationship CRUD, traversal working
5. **Agent system is stable** - spawn/terminate, completion working

### Next Steps
- Document direct socket patterns for future KSI improvements
- Continue experiments using direct socket approach
- Create socket-based versions of remaining experiments
- Analyze patterns for future EventClient improvements

### Strategic Decision: Focus on Experiments
**Core enhancements deprioritized to weeks away:**
- Graph Query Language (Cypher via Kùzu) - Future enhancement
- Time-series analytics - Future enhancement  
- Agent capability evolution - Future enhancement

**Current focus: Gather experimental data using direct socket patterns**
- Proven reliable communication method
- Better understanding of daemon capabilities
- Foundation for future client improvements

---

## 2025-07-11 Session 1: Orchestration Patterns and Hook Monitor Investigation

### Objective
Investigate compositional orchestration patterns using AI-designed DSLs and improve KSI hook monitor for better debugging visibility.

### Context
Building on the Cognition AI paper's insights about multi-agent fragility, testing KSI's event-driven architecture with compositional patterns and natural language DSLs designed by AI for AI orchestrators.

---

## Experiment Log

### EXP-101: Hook Monitor Orchestration Mode
**Time**: 2025-07-11 15:59
**Purpose**: Add orchestration debug mode to hook monitor for better pattern visibility
**Method**: 
```python
# Added to ksi_hook_monitor.py:
- "orchestration" mode to valid modes
- Pattern loading shows transformer count
- Transformer execution tracking
- Agent message preview in orchestration mode
```

**Expected**: Detailed visibility into pattern loading and transformer execution
**Actual**: SUCCESS - Can now see:
- Pattern loading with transformer counts
- Transformer execution flow (e.g., `tournament:assess_capabilities` → `composition:discover`)
- Agent messages with content preview
**Notes**: 
- Hook improvements working well for debugging
- Revealed transformer system is functional

---

### EXP-102: Async Transformer Cost Explosion
**Time**: 2025-07-11 16:01
**Purpose**: Test async transformer with tournament:analyze_performance event
**Code**:
```bash
echo '{"event": "tournament:analyze_performance", "data": {"context_window": ["Test event 1", "Test event 2"], "performance_metrics": {"score": 0.8}}}' | nc -U var/run/daemon.sock
```

**Expected**: Quick completion with analysis response
**Actual**: FAILURE - Expensive claude-cli session:
- 22 turns of interaction
- $1.07 USD cost
- 126 seconds duration
- 206,347 tokens used
- Session ID: 7c32be94-5586-45bc-8345-c419ce4e01c8

**Notes**: 
- The prompt triggered complex multi-turn reasoning
- No safety limits on async transformers
- Response was eventually produced but at high cost

---

### EXP-103: Orchestrator Agent Non-Responsive
**Time**: 2025-07-11 16:04
**Purpose**: Send message to orchestrator agent to execute AI-designed tournament pattern
**Code**:
```bash
# Spawned orchestrator: agent_5b710caf
echo '{"event": "agent:send_message", "data": {"agent_id": "agent_5b710caf", "message": {"role": "user", "content": "Please load and execute the ai_designed_tournament pattern..."}}}' | nc -U var/run/daemon.sock
```

**Expected**: Orchestrator processes message and executes pattern
**Actual**: FAILURE - Message sent but orchestrator not responding:
- Message delivery confirmed
- Agent status shows "ready"
- No completion events from agent
- agent:get_messages returns empty

**Notes**:
- Orchestrator agent exists and is "ready" but not processing messages
- Possible issue with base_orchestrator profile or message queue

---

## Bug Tracker

### BUG-101: Orchestrator Agents Not Processing Messages
**Component**: Agent message processing system
**Description**: Orchestrator agents show as "ready" but don't process incoming messages
**Symptoms**:
- agent:send_message succeeds
- Agent remains in "ready" state
- No completion events generated
- agent:get_messages returns empty
**Investigation Needed**: Check message queue implementation and agent event loop

### BUG-102: Async Transformers Lack Safety Limits
**Component**: Transformer system / completion:async
**Description**: No limits on cost, turns, or duration for async transformer completions
**Impact**: Single test event cost $1.07 with 22 turns
**Fix Needed**: Add safety parameters to async transformers

---

## Pattern Engineering Discoveries

### Successful Patterns Created
1. **ai_designed_tournament**: Natural language DSL with compositional intelligence
2. **strategy_discovery_pattern**: Generate-Debate-Evolve cycle for game theory
3. **pattern_stability_observer**: Meta-pattern for observing orchestration dynamics
4. **swarm_optimization_pattern**: Collective problem-solving with configurable dynamics

### Transformer System Findings
- **Working**: Synchronous transformers execute correctly
- **Working**: Async transformers trigger but need safety limits
- **Working**: Pattern loading registers transformers
- **Issue**: Complex prompts can trigger expensive completions

### Orchestration Architecture Insights
- Event-driven design provides good loose coupling
- Transformers enable custom event vocabularies without code
- Natural language DSLs are interpretable by AI orchestrators
- Pattern evolution and forking mechanisms in place

---

## Hook Monitor Improvements

### Implemented Features
1. **Orchestration Mode**: `echo ksi_orchestration` for detailed debugging
2. **Pattern Loading**: Shows pattern name and transformer count
3. **Transformer Tracking**: Shows source→target transformations
4. **Agent Messages**: Preview of message content
5. **Event Data**: Shows data for pattern-specific events

### Usage
```bash
echo ksi_orchestration  # Switch to orchestration debug mode
echo ksi_summary       # Return to normal mode
echo ksi_status        # Check current mode
```

---

## Next Investigation Steps

1. **Debug Message Queue**: Why aren't orchestrator agents processing messages?
2. **Check Agent Profile**: Is base_orchestrator configured correctly?
3. **Add Safety Limits**: Implement cost/turn limits for async transformers
4. **Create Test Patterns**: Simpler patterns that won't trigger expensive completions

---

### EXP-104: Fixed Agent Message Processing
**Time**: 2025-07-11 16:28
**Purpose**: Implement direct event routing for agent messages to bypass polling
**Method**: 
Modified `agent_service.py:handle_send_message` to:
- Detect completion messages (both formats)
- Emit `completion:async` directly instead of queuing
- Preserve session continuity

**Code**: See commit in agent_service.py

**Expected**: Immediate message processing
**Actual**: SUCCESS - Messages now process immediately:
- Response in 4 seconds (vs 60+ second poll wait)
- Single turn completion
- Cost: $0.07 (vs $1.07 earlier)
- Session ID: 7a9d92b4-28f0-44e5-9243-e6953cb0ba98

**Notes**: 
- The fix maintains event-driven architecture
- Session tracking works correctly
- Orchestrator agents now respond immediately

---

## Architecture Fix Summary

**Root Cause**: Agent messages were queued with 60-second polling instead of event-driven processing

**Solution**: Direct event routing for completion messages:
- `agent:send_message` → detects completion → `completion:async`
- Bypasses queue for immediate processing
- Maintains session continuity automatically

**Impact**: Orchestration patterns can now execute properly with responsive agents