# Declarative Capability Integration with Existing MCP

## Current State (Already Implemented)

KSI **already has** dynamic event→tool generation:

```python
# In dynamic_server.py
async def _create_tool_for_event(self, event_name: str):
    # 1. Query system:help for event schema
    help_response = await self.ksi_client.send_event(
        "system:help",
        {"event": event_name, "format_style": "mcp"}
    )
    
    # 2. Generate MCP tool from event
    tool_name = f"ksi_{event_name.replace(':', '_')}"
    
    # 3. Return tool definition with schema
    return {
        "name": tool_name,
        "description": help_response.get("description"),
        "inputSchema": help_response.get("inputSchema")
    }
```

So Claude already gets tools like:
- `ksi_agent_spawn` → executes `agent:spawn`
- `ksi_message_publish` → executes `message:publish`
- `ksi_state_get` → executes `state:get`

## What's Missing: Clean Capability Mapping

The problem is determining **which events** an agent should have access to. Currently:

1. **Compositions** list explicit events (30+ lines)
2. **Permissions** also list tools (duplication)
3. **Agent service** gets confused about which to use
4. **MCP** queries permissions again

## Proposed Integration

### 1. Declarative Mapping (capability_mappings.yaml)

```yaml
capabilities:
  agent_messaging:
    description: "Inter-agent communication"
    events:
      - "message:subscribe"
      - "message:publish"
      - "message:unsubscribe"
      - "agent:send_message"
    
  spawn_agents:
    description: "Agent lifecycle management"
    requires: ["agent_messaging"]  # Dependencies
    events:
      - "agent:spawn"
      - "agent:terminate"
      - "agent:list"
```

### 2. Simplified Flow

```
Composition (3 lines of capabilities)
    ↓
Capability Resolver (expands to event list)
    ↓
Agent Service (stores allowed_events)
    ↓
MCP Server (generates tools from allowed_events) ← Already exists!
    ↓
Claude gets ksi_* tools
```

### 3. Integration Points

**Agent Service** (minimal change):
```python
# Current: Complex extraction from profile
# After: Simple capability resolution
resolver = get_capability_resolver()
resolved = resolver.resolve_capabilities_for_profile(
    profile.get("capabilities", {})
)
agent_info["allowed_events"] = resolved["allowed_events"]
```

**MCP Server** (no change needed!):
```python
# Already does this:
for event_name in allowed_tools:
    tool = await self._create_tool_for_event(event_name)
```

**Compositions** (massive simplification):
```yaml
# Before: List every event
allowed_tools:
  - "agent:spawn"
  - "agent:terminate"
  - "message:publish"
  ... 20 more lines

# After: Just capabilities
capabilities:
  spawn_agents: true
  agent_messaging: true
```

## Benefits of This Approach

1. **Leverages Existing Infrastructure**
   - MCP dynamic tool generation stays the same
   - Event discovery and help system unchanged
   - Just adds clean capability→event mapping

2. **Single Source of Truth**
   - `capability_mappings.yaml` defines groupings
   - No duplication between code/configs
   - Easy to audit and update

3. **Backward Compatible**
   - Can still support explicit `allowed_tools` lists
   - Gradual migration possible
   - No breaking changes

4. **Future Enhancements**
   - Hot-reload capability mappings
   - GUI for capability management
   - Auto-generate from event metadata

## Implementation Priority

1. **Phase 1**: Create capability_mappings.yaml
2. **Phase 2**: Add CapabilityResolver class
3. **Phase 3**: Update agent_service to use resolver
4. **Phase 4**: Migrate compositions to capability-based
5. **Phase 5**: Deprecate tool lists in permissions

The beauty is that 90% of the infrastructure already exists - we're just adding a clean mapping layer on top!

## ksi_client Integration (Future Task)

With the capability_resolver now in ksi_common and capability_enforcer in ksi_daemon, we need to add client-side methods for programmatic composition building:

**ksi_client enhancements needed:**
- `from ksi_common.capability_resolver import get_capability_resolver`
- Helper methods for discovering available capabilities
- Validation methods for capability combinations
- Composition building utilities that understand capability→event mappings

This will allow Claude to write Python code that manipulates compositions/permissions without needing to import from ksi_daemon directly.