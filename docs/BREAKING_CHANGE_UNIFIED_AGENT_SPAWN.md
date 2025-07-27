# Breaking Change: Unified Agent Spawn

## Date: 2025-01-27

## Summary
Unified agent spawning to a single, cleaner path that always requires components and supports variables.

## Changes

### 1. Deprecated `agent:spawn_from_component`
This event is now **DEPRECATED** and will be removed. Use `agent:spawn` instead.

### 2. `agent:spawn` Now Requires Component
The `component` parameter is now **REQUIRED** for all agent spawns. There is no valid use case for spawning an agent without behavioral instructions.

### 3. `agent:spawn` Now Supports Variables
Added `variables` parameter to `agent:spawn` for template substitution in components.

### 4. Removed Dead Code
- Removed non-existent `composition:agent_context` event handling
- Removed fallback message logic that was never reached
- Removed `_in_memory_manifest_data` internal parameter

## Migration Guide

### Before:
```python
# Using spawn_from_component for variables
await event_emitter("agent:spawn_from_component", {
    "component": "components/agents/analyzer",
    "variables": {"role": "senior", "domain": "security"},
    "agent_id": "analyzer_001"
})

# Using regular spawn without variables
await event_emitter("agent:spawn", {
    "component": "components/agents/analyzer",
    "agent_id": "analyzer_002"
})
```

### After:
```python
# Single unified path with optional variables
await event_emitter("agent:spawn", {
    "component": "components/agents/analyzer",  # Now REQUIRED
    "variables": {"role": "senior", "domain": "security"},  # Now supported
    "agent_id": "analyzer_001"
})

# Without variables - same event
await event_emitter("agent:spawn", {
    "component": "components/agents/analyzer",
    "agent_id": "analyzer_002"
})
```

## Benefits

1. **Simpler API** - One way to spawn agents
2. **Consistent Features** - Variables always available
3. **Less Code** - Removed redundant paths and data passing
4. **Clearer Intent** - Components are always required

## Technical Details

### Removed Complexity
- No more pre-rendering manifests and passing as `_in_memory_manifest_data`
- No more separate code paths for with/without variables
- No more fallback messages for missing components

### Cleaner Flow
1. Receive spawn request with component + optional variables
2. Render manifest using `render_component_to_agent_manifest`
3. Extract system_prompt from manifest
4. Send initial context to agent
5. Done!

## Implementation Notes

The agent service now:
- Always calls `render_component_to_agent_manifest` directly in `handle_spawn_agent`
- Properly extracts and uses `system_prompt` from rendered manifests
- Sends system prompts with appropriate role ("system" vs "user")
- Combines system_prompt with interaction prompt when both are present

## Testing Results

Tested the unified spawn implementation:
- ✅ Basic spawn with required component works
- ✅ Spawn with variables successfully passes them to components
- ✅ Deprecated spawn_from_component still works with deprecation notice
- ✅ System prompts from components are properly extracted and sent to agents
- ✅ Missing component parameter correctly rejected

## Known Issues

1. **Agent behavioral overrides**: Some behavioral override components need CLAUDE.md removal to avoid confusion
2. **Dependency resolution**: Fixed ksi_json_reporter → mandatory_json references in persona components