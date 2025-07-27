# Agent System Prompt Fix

## Problem
The agent service is not extracting and using the `system_prompt` from the rendered component manifest. When a component like `json_strict` is rendered, the manifest contains the system prompt in `components[1].inline.system_prompt`, but this is never sent to the agent.

## Root Cause
In `handle_spawn_agent`, the manifest data is properly created using `render_component_to_agent_manifest`, but:
1. The system_prompt is nested in the manifest structure
2. The agent service only sends an initial message if an `interaction_prompt` is provided at spawn time
3. The system_prompt from the component is never extracted or used

## Solution
Add elegant system_prompt extraction after manifest creation:

```python
# In handle_spawn_agent, after manifest_data is created (around line 830)

# Extract system_prompt from manifest if present
system_prompt = None
if manifest_data and 'components' in manifest_data:
    for component in manifest_data.get('components', []):
        if component.get('name') == 'generated_content':
            inline_data = component.get('inline', {})
            system_prompt = inline_data.get('system_prompt')
            if system_prompt:
                logger.debug(f"Extracted system_prompt from manifest for agent {agent_id}")
                break

# Store system_prompt in agent info for initial context
if system_prompt:
    agent_info['system_prompt'] = system_prompt
```

Then modify the initial prompt sending logic (around line 1059):

```python
# Send initial context - either system_prompt, interaction_prompt, or both
initial_content = None
interaction_prompt = data.get("prompt")

# Determine what to send as initial context
if system_prompt and interaction_prompt:
    # Combine system prompt with interaction
    initial_content = f"{system_prompt}\n\n{interaction_prompt}"
elif system_prompt:
    # Just system prompt from component
    initial_content = system_prompt
elif interaction_prompt:
    # Just interaction prompt from spawn request
    initial_content = interaction_prompt

if initial_content and event_emitter:
    logger.info(f"Sending initial context to agent {agent_id}")
    
    # Send as direct message instead of using composition:agent_context
    initial_result = await event_emitter("agent:send_message", {
        "agent_id": agent_id,
        "message": {
            "role": "system" if system_prompt and not interaction_prompt else "user",
            "content": initial_content
        }
    }, propagate_agent_context(context))
```

## Benefits
1. **No code duplication** - Uses existing `render_component_to_agent_manifest` utility
2. **Elegant extraction** - Simple loop to find the system_prompt in the manifest structure
3. **Flexible combination** - Handles system_prompt only, interaction_prompt only, or both
4. **Proper role assignment** - Uses "system" role for pure system prompts

## Testing
After this fix:
1. Components with embedded instructions will work properly
2. Agents will receive their behavioral overrides
3. JSON emission patterns can be implemented in components