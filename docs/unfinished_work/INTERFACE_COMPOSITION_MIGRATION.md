# Interface Composition Migration Guide

## Overview

This document tracks the migration of KSI interfaces from direct JSON profile loading to the unified composition system.

## Migration Status

### chat_textual.py
- **Current**: Loads profiles from `var/lib/agent_profiles/{profile}.json`
- **Required**: Use composition system via agent:spawn or profile resolution
- **Changes Needed**:
  - Remove `load_profile()` method
  - Use composition service for profile data
  - Pass profile/composition name to agent:spawn

### orchestrate.py
- **Current**: Creates temporary JSON profiles in `var/lib/agent_profiles/`
- **Required**: Use compositions directly without temp files
- **Changes Needed**:
  - Remove `create_agent_profile()` method
  - Create compositions for orchestrator roles
  - Pass composition name to agent:spawn

### orchestrate_v3.py
- **Current**: Creates temporary JSON profiles in `var/tmp/agent_profiles/`
- **Required**: Use compositions directly
- **Changes Needed**:
  - Remove temp profile creation
  - Update `create_profile_for_mode()` to return composition name
  - Use existing or create new compositions

## Composition Templates Needed

### For Orchestrator Modes

1. **Debate Mode**
   ```yaml
   name: orchestrator_debate_participant
   template: base_agent
   model: sonnet
   variables:
     participant_number: "{{ participant_number }}"
     topic: "{{ topic }}"
   content: |
     You are participant {{ participant_number }} in a debate about: {{ topic }}
     
     Take a clear position and defend it with logic and evidence.
     Engage respectfully with other viewpoints.
   ```

2. **Discussion Mode**
   ```yaml
   name: orchestrator_discussion_participant
   template: base_agent
   model: sonnet
   variables:
     role: "{{ role }}"
     topic: "{{ topic }}"
   content: |
     You are the {{ role }} in a collaborative discussion about: {{ topic }}
     
     Share insights and build on others' ideas constructively.
   ```

3. **Q&A Mode**
   ```yaml
   name: orchestrator_qa_participant
   template: base_agent
   model: sonnet
   variables:
     role: "{{ role }}"  # questioner or responder
     topic: "{{ topic }}"
   content: |
     You are the {{ role }} in a Q&A session about: {{ topic }}
     {% if role == "questioner" %}
     Ask thoughtful, probing questions to explore the topic deeply.
     {% else %}
     Provide comprehensive, well-reasoned answers.
     {% endif %}
   ```

## Migration Steps

### Phase 1: Create Compositions
1. Create orchestrator compositions in `var/lib/compositions/profiles/`
2. Test compositions with manual agent:spawn
3. Verify variable substitution works correctly

### Phase 2: Update Interfaces
1. Modify orchestrate.py to use composition names
2. Modify orchestrate_v3.py similarly
3. Update chat_textual.py to resolve profiles via composition

### Phase 3: Cleanup
1. Remove temp profile creation code
2. Remove direct JSON file loading
3. Update documentation

## Code Examples

### Before (orchestrate.py)
```python
def create_agent_profile(self, mode_name, agent_index):
    profile = {
        'model': 'sonnet',
        'role': role,
        'composition': composition
    }
    profile_path = config.agent_profiles_dir / f'temp_{mode_name}_{agent_index}.json'
    with open(profile_path, 'w') as f:
        json.dump(profile, f, indent=2)
    return f'temp_{mode_name}_{agent_index}'
```

### After (orchestrate.py)
```python
def get_composition_name(self, mode_name, agent_index):
    role, _ = self.determine_agent_role(mode_name, agent_index)
    
    # Map to composition names
    composition_map = {
        'debate': 'orchestrator_debate_participant',
        'discussion': 'orchestrator_discussion_participant',
        'qa': 'orchestrator_qa_participant'
    }
    
    return composition_map.get(mode_name, 'base_agent')
```

### Agent Spawn Update
```python
# Before
spawn_params = {
    "profile_name": profile_name,  # temp JSON file
    "task": initial_task,
    "context": context
}

# After
spawn_params = {
    "composition": composition_name,  # composition reference
    "task": initial_task,
    "context": {
        "participant_number": i + 1,
        "topic": topic,
        "role": role
    }
}
```

## Benefits

1. **No Temp Files**: Eliminates temporary profile file management
2. **Reusability**: Compositions can be shared and versioned
3. **Consistency**: All agents use same composition system
4. **Flexibility**: Easy to modify behaviors without code changes
5. **Validation**: Composition system provides schema validation

## Testing

1. Verify orchestrator modes work with compositions
2. Test variable substitution in prompts
3. Ensure chat interface loads profiles correctly
4. Validate no temp files are created

---

This migration aligns all interfaces with the unified composition architecture, removing the last vestiges of direct JSON profile management.