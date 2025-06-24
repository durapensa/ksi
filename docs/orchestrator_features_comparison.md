# Orchestrator Features: External vs Daemon Implementation

This document describes three key orchestration features present in the external orchestrators (`interfaces/orchestrate*.py`) that are missing from the daemon's internal orchestrator (`daemon/agent_orchestrator.py`).

## 1. Conversation Mode Management from YAML Compositions

### How it Works in External Orchestrators

The external orchestrators use a sophisticated system to load and manage conversation modes from YAML composition files located in `prompts/compositions/conversation_*.yaml`.

#### YAML Structure Example (`conversation_debate.yaml`):
```yaml
name: "conversation_debate"
version: "1.0"
description: "Composition for agents participating in debates"

components:
  - name: "debate_position_for"
    source: "components/conversation_patterns/debate_for.md"
    condition: "{{participant_number}} == 1"
    vars:
      topic: "{{topic}}"
      
  - name: "debate_position_against"
    source: "components/conversation_patterns/debate_against.md"
    condition: "{{participant_number}} == 2"
    vars:
      topic: "{{topic}}"

metadata:
  conversation_mode: "debate"
  min_agents: 2
  max_agents: 4
```

#### Key Features:
- **Automatic Discovery**: Scans `prompts/compositions/` for `conversation_*.yaml` files
- **Conditional Components**: Different prompts based on `participant_number`
- **Role-Specific Behaviors**: Includes specific component files (e.g., `debate_for.md`, `debate_against.md`)
- **Agent Validation**: Enforces min/max agent limits per mode
- **Mode Registry**: Builds a registry of available conversation modes at runtime

#### Implementation:
```python
class ConversationModeManager:
    def _load_conversation_modes(self):
        for comp_file in self.compositions_path.glob("conversation_*.yaml"):
            with open(comp_file) as f:
                composition = yaml.safe_load(f)
                mode_name = composition['metadata'].get('conversation_mode')
                self.modes[mode_name] = {
                    'composition': composition['name'],
                    'min_agents': metadata.get('min_agents', 2),
                    'max_agents': metadata.get('max_agents', 8),
                    'description': composition.get('description', '')
                }
```

### What's Missing in Daemon Version
The daemon's `agent_orchestrator.py` has no YAML-based mode management system. It only responds to hardcoded event types without any composition loading or mode configuration.

## 2. Dynamic Composition Discovery and Selection

### How it Works in orchestrate_v3.py

The v3 orchestrator implements intelligent composition discovery and selection using two key components:

#### Components:
1. **CompositionDiscovery**: Scans and indexes all available compositions
2. **CompositionSelector**: Intelligently selects the best composition based on context

#### Features:

**Automatic Discovery**:
```python
# Discovers all compositions with metadata
all_compositions = await self.discovery.get_all_compositions(include_metadata=True)

# Filters for conversation modes
for name, comp_info in all_compositions.items():
    mode_name = comp_info.metadata.get('conversation_mode')
    if mode_name:
        self.modes_cache[mode_name] = {
            'composition': name,
            'required_capabilities': comp_info.metadata.get('capabilities_required', []),
            'min_agents': comp_info.metadata.get('min_agents', 2),
            'max_agents': comp_info.metadata.get('max_agents', 8)
        }
```

**Intelligent Selection**:
- Matches compositions based on required capabilities
- Considers agent context and conversation requirements
- Provides fallback to basic modes if discovery fails
- Caches discovered modes for performance

**Benefits**:
- New conversation modes can be added without code changes
- Compositions are selected based on best fit for the context
- System adapts to available compositions dynamically
- Graceful degradation with fallback modes

### What's Missing in Daemon Version
The daemon has no composition discovery system. It cannot:
- Dynamically find new conversation modes
- Select compositions based on context
- Adapt to new composition files
- Provide intelligent fallbacks

## 3. Sophisticated Role Assignment by Mode

### How it Works in External Orchestrators

The orchestrators implement intelligent role assignment based on conversation mode and agent position.

#### Basic Version (orchestrate.py):
```python
role_assignments = {
    'debate': lambda i: ('debater', 'conversation_debate'),
    'teaching': lambda i: ('teacher' if i == 0 else 'student', 'conversation_teaching'),
    'brainstorm': lambda i: ('creative' if i < 2 else 'critic', 'conversation_brainstorm'),
}
```

#### Advanced Version (orchestrate_v3.py):
```python
role_mappings = {
    'debate': [
        ('proponent', ['argumentation', 'persuasion', 'research']),
        ('opponent', ['critical_thinking', 'counterargument', 'analysis']),
        ('moderator', ['summarization', 'fairness', 'time_management']),
        ('judge', ['evaluation', 'decision_making', 'objectivity'])
    ],
    'teaching': [
        ('teacher', ['explanation', 'patience', 'adaptation']),
        ('student', ['questioning', 'learning', 'comprehension']),
        ('assistant', ['support', 'clarification', 'examples'])
    ],
    'collaboration': [
        ('researcher', ['research', 'information_gathering', 'fact_checking']),
        ('analyst', ['analysis', 'pattern_recognition', 'synthesis']),
        ('strategist', ['planning', 'decision_making', 'optimization']),
        ('coordinator', ['organization', 'communication', 'delegation'])
    ]
}
```

#### Key Features:

1. **Position-Based Assignment**:
   - First agent in teaching mode → teacher
   - Second agent in teaching mode → student
   - Third+ agents get supporting roles

2. **Capability Mapping**:
   - Each role gets specific capabilities
   - Teacher: explanation, patience, adaptation
   - Student: questioning, learning, comprehension

3. **Mode-Specific Logic**:
   - Debate: proponent vs opponent with optional moderator/judge
   - Brainstorm: creators (first 2) vs critics (rest)
   - Analysis: data analyst + domain expert + synthesizer

4. **Scalable Patterns**:
   - Supports variable number of agents
   - Roles adapt based on total agent count
   - Graceful handling of extra agents

5. **Context Injection**:
   ```python
   context = json.dumps({
       'conversation_mode': mode,
       'topic': topic,
       'participant_number': i + 1,
       'agent_role': role,
       'capabilities': capabilities
   })
   ```

### What's Missing in Daemon Version

The daemon's `agent_orchestrator.py` only has basic event handling:
```python
elif event_type == "DEBATE_OPENING":
    debater_agent = self._find_agent_with_role("debater")
    if debater_agent:
        await self._route_to_agent(debater_agent.agent_id, data)
```

Missing features:
- No position-based role assignment
- No capability mapping per role
- No mode-aware role distribution
- No support for complex role hierarchies
- Limited to finding agents with pre-existing roles

## Summary

The external orchestrators provide a rich, flexible system for multi-agent conversations that the daemon's internal orchestrator lacks:

1. **YAML-based mode configuration** enables non-programmers to add conversation modes
2. **Dynamic discovery** allows the system to adapt to new compositions automatically
3. **Sophisticated role assignment** creates natural, purposeful agent interactions

These features make the external orchestrators powerful tools for complex multi-agent scenarios, while the daemon provides efficient infrastructure for basic agent coordination.