# Quick Interface Fixes for Composition Migration

## Critical Changes Needed

### 1. orchestrate.py (Line ~195)
```python
# REMOVE the profile file creation:
def create_agent_profile(self, mode_name, agent_index):
    # DELETE ALL OF THIS - no more temp JSON files
    
# REPLACE with:
def get_composition_name(self, mode_name, agent_index):
    if mode_name == 'debate':
        return 'debater'  # Use existing debater.yaml
    elif mode_name == 'discussion':
        return 'base_agent'  # Use base for now
    elif mode_name == 'qa':
        role, _ = self.determine_agent_role(mode_name, agent_index)
        return 'questioner' if role == 'questioner' else 'responder'
    return 'base_agent'
```

### 2. orchestrate.py spawn_agents() (Line ~220)
```python
# CHANGE:
profile_name = self.create_agent_profile(mode, i)

# TO:
composition_name = self.get_composition_name(mode, i)

# CHANGE spawn_params:
spawn_params = {
    "composition": composition_name,  # Not profile_name!
    "task": initial_task,
    "context": context,
    "agent_id": agent_id
}
```

### 3. orchestrate_v3.py Similar Changes
- Remove create_profile_for_mode()
- Use composition names directly
- Update spawn_params to use "composition" not "profile_name"

### 4. chat_textual.py
- Keep profile loading for now (lower priority)
- Can be updated later to use composition service

## Testing Commands

```bash
# Test orchestrator with existing debater composition
python3 interfaces/orchestrate.py --mode debate --agents 2 --topic "AI safety"

# Verify no temp files created
ls var/lib/agent_profiles/temp_* 2>/dev/null || echo "Good: No temp files"
```

## Benefits
- No more temp file cleanup needed
- Uses existing composition system
- Maintains same functionality
- Cleaner architecture