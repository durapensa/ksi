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
**Time**: [PENDING]  
**Purpose**: Test if we can override programming context  

```python
# Explicit non-programming role
prompt = """You are NOT a programming assistant.
You are a poet. Write a haiku about trees.
Include NO code or technical content."""
```

**Expected**: A haiku with no technical content  
**Actual**: [PENDING]  
**Notes**:

---

## Bug Tracker

### BUG-001: RelationalStateManager has no attribute 'get_shared_state'
**Component**: ksi_daemon/composition/composition_service.py  
**Description**: Old state manager API being used (get_shared_state) instead of new relational API
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
- [PENDING]

### What Fails  
- [PENDING]

### Effective Patterns
- [PENDING]

---

## Session Summary

### Key Findings
1. **Agent spawning works** - Successfully creates agents with profiles
2. **Completion requests work** - Claude CLI is invoked successfully  
3. **Session management broken** - session_id is None, responses not saved
4. **Migration incomplete** - Old KV state API references remain

### Critical Issue
The agent system creates agents but cannot properly route responses back because:
- Agents spawn without session_id
- Completion requests run with session_id=None  
- Response files aren't created without valid session_id

### Next Steps
1. Investigate how session_id should flow from agent spawn to completion
2. Check if we need to create initial conversation context
3. Consider using synchronous completion for initial prompts