# Phase 1 Critical Fixes Implementation

## 1. Capability Restrictions Fix

### Problem
Agents spawned with "base" capability cannot emit critical events like `agent:status`, `completion:async`, etc. The capability mappings are too restrictive and missing key events.

### Solution

```yaml
# var/lib/capabilities/capability_mappings.yaml

capabilities:
  base:
    events:
      # Core discovery and health
      - "system:health"
      - "system:help"
      - "system:discover"
      # Critical agent communication
      - "agent:status"  # ADDED: Agents must report status
      - "completion:async"  # ADDED: Agents must be able to communicate
      - "monitor:*"  # ADDED: Agents should be able to report to monitor
      # State access for context
      - "state:get"  # ADDED: Read-only state access
      - "state:entity:get"  # ADDED: Read entity state
      
  enhanced:
    includes: ["base"]
    events:
      - "state:set"
      - "state:entity:update"  # ADDED: Was missing entirely!
      - "state:entity:create"
      - "agent:send_message"
      - "routing:get_rules"  # Read routing but not modify
      
  routing_control:
    includes: ["enhanced"]
    events:
      - "routing:add_rule"
      - "routing:remove_rule"
      - "routing:update_rule"
      - "routing:clear_rules"
      
  composition:
    includes: ["enhanced"]
    events:
      - "composition:*"
      
  optimization:
    includes: ["enhanced"]
    events:
      - "optimization:*"
      - "evaluation:*"
```

### Implementation

```python
# ksi_daemon/capability_enforcer.py - Add validation

def validate_essential_events(self, capability_list: List[str]) -> List[str]:
    """Ensure agents have minimum viable event permissions."""
    essential_events = {
        "agent:status",  # Must report status
        "completion:async",  # Must communicate
        "monitor:log"  # Must log activity
    }
    
    # Always include essentials unless explicitly restricted
    if "restricted" not in capability_list:
        return list(set(capability_list) | essential_events)
    return capability_list
```

## 2. Transformer Reliability Fix

### Problem
The `agent_spawned_state_create` transformer may not fire reliably, leaving agents without state entities.

### Solution

```python
# ksi_daemon/agent/agent_service.py - Add verification

async def verify_agent_state_entity(agent_id: str, context: Dict) -> bool:
    """Verify agent state entity was created, create if missing."""
    # Check if state entity exists
    result = await event_emitter("state:entity:get", {
        "type": "agent",
        "id": agent_id
    }, context)
    
    result = extract_single_response(result)
    
    if not result or result.get("status") != "success":
        # State entity missing - create it directly
        logger.warning(f"Agent {agent_id} missing state entity, creating...")
        
        # Get agent info
        agent = agents.get(agent_id)
        if agent:
            await event_emitter("state:entity:create", {
                "type": "agent",
                "id": agent_id,
                "properties": {
                    "agent_id": agent_id,
                    "sandbox_uuid": agent.get("sandbox_uuid"),
                    "capabilities": agent.get("capabilities", []),
                    "permission_profile": agent.get("permission_profile", "standard"),
                    "status": "active",
                    "created_at": timestamp_utc()
                }
            }, context)
            return True
    return True

# Call after agent spawn
await verify_agent_state_entity(agent_id, context)
```

## 3. Event System Robustness

### Timestamp Fixes

```python
# ksi_daemon/optimization/optimization_service.py

# WRONG
"timestamp": timestamp_utc()  # Returns string, not timestamp object

# CORRECT
"timestamp": time.time()  # Numeric timestamp
"timestamp_iso": timestamp_utc()  # ISO string for display
```

### JSON Serialization Fixes

```python
# ksi_daemon/utils/serialization.py

import decimal
import datetime
import uuid

class RobustJSONEncoder(json.JSONEncoder):
    """Handle all common Python types that cause serialization errors."""
    
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

# Use throughout system
json.dumps(data, cls=RobustJSONEncoder)
```

### Timeout Prevention

```python
# ksi_daemon/event_handlers.py

async def safe_handler_wrapper(handler, data, context):
    """Wrap handlers with timeout and error handling."""
    try:
        # Add timeout to prevent hanging
        result = await asyncio.wait_for(
            handler(data, context),
            timeout=30.0  # 30 second timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Handler {handler.__name__} timed out")
        return error_response("Handler timeout", context=context)
    except Exception as e:
        logger.error(f"Handler {handler.__name__} error: {e}")
        return error_response(str(e), context=context)
```

## 4. llanguage Integration Preparation

### Create llanguage Bootstrap Component

```yaml
# components/llanguage/bootstrap/v1.yaml
name: llanguage_v1
type: llanguage_specification
description: Bootstrap language for LLM agent communication

primitives:
  GET: "Retrieve data via appropriate tool"
  SET: "Store data via appropriate tool"  
  CALL: "Invoke function/tool"
  EVAL: "Evaluate/classify/score"
  SPAWN: "Create agent/process"
  FLOW: "Control flow decision"

examples:
  - natural: "Optimize the component for efficiency"
    llanguage: "GET component | EVAL efficiency | CALL optimize | SET component"
    compressed: "OPT component"
    
interpretation_note: |
  LLMs interpret llanguage directly through comprehension.
  No code interpreter exists or should exist.
  Execution happens through natural tool selection based on understanding.
```

### Update Agent Components for llanguage

```yaml
# components/core/base_agent.md
---
component_type: core
name: base_agent
capabilities:
  - base
  - llanguage_comprehension  # NEW
---

You understand llanguage, a compressed protocol for agent coordination.

When you see llanguage expressions like "GET state | EVAL threshold | FLOW exceeded | CALL alert",
interpret them as instructions for tool use:
- GET: retrieve using appropriate tool
- SET: store using appropriate tool  
- CALL: invoke specified function
- EVAL: evaluate/classify/score
- SPAWN: create agent
- FLOW: conditional execution

Execute llanguage through natural tool selection, not code interpretation.
```

## Testing Checklist

- [ ] Spawn agent with base capability, verify can emit agent:status
- [ ] Spawn agent, verify state entity created
- [ ] Test optimization service with proper timestamps
- [ ] Test JSON serialization with complex objects
- [ ] Test handler timeouts
- [ ] Test llanguage comprehension with simple expression

## Rollout Plan

1. **Day 1**: Deploy capability fixes (highest priority)
2. **Day 2**: Deploy event system robustness fixes
3. **Day 3**: Verify transformer reliability
4. **Day 4**: Begin llanguage bootstrap testing
5. **Day 5-7**: Monitor and iterate

---

*Critical fixes for Phase 1 Baseline Dynamics*  
*Focus: Enable agents to communicate effectively*