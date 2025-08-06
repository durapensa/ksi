# Declarative Agent-Composition Architecture

## Executive Summary

This document outlines the architectural enhancement for making KSI agent spawning fully **declarative** rather than code-driven. The key insight is that composition metadata should drive KSI context injection, not hardcoded agent type mappings.

## Problem Statement

The current implementation has architectural issues:

1. **Default agents shouldn't be KSI-aware** - breaks experimental control
2. **Hardcoded logic violates separation of concerns** - agent types hardcoded in composition system
3. **Loose coupling** - no explicit declaration of KSI-awareness in compositions

## Solution: Composition-Metadata Driven Architecture

### Core Principle
**Compositions self-declare their capabilities through metadata, eliminating hardcoded mappings.**

### Enhanced Metadata Schema
```yaml
# Standard metadata fields for all compositions
metadata:
  ksi_aware: boolean           # Triggers KSI context resolution
  suitable_for: [agent_types]  # Which agent types can use this
  required_capabilities: []    # What the agent must support
  provides_capabilities: []    # What this composition adds
  experiment_safe: boolean     # Safe for controlled studies
  use_cases: []               # Documented use cases
```

### Example Compositions

#### Pure Experimental Agent
```yaml
# claude_agent_default.yaml - Clean, no KSI
name: claude_agent_default
metadata:
  ksi_aware: false
  experiment_safe: true
  description: "Pure Claude agent for controlled experiments"
  suitable_for: [default, conversationalist, creative, researcher]
  use_cases: [baseline_testing, multi_agent_naive]
```

#### KSI-Aware Developer Agent
```yaml
# ksi_developer_agent.yaml - Full daemon knowledge
name: ksi_developer_agent
metadata:
  ksi_aware: true
  experiment_safe: false
  description: "KSI system developer with full daemon knowledge"
  suitable_for: [ksi_developer, tool_tester, system_admin]
  required_capabilities: [daemon_interaction, event_client]
  provides_capabilities: [system_commands, event_discovery]
extends: claude_agent_default
components:
  - name: ksi_context
    source: components/daemon_commands.md
    vars:
      daemon_commands: "{{daemon_commands}}"
```

## Implementation Strategy

### 1. Metadata-Driven KSI Resolution
```python
def _should_resolve_ksi_context(composition: Composition) -> bool:
    """Check composition metadata, not hardcoded agent types."""
    return composition.metadata.get("ksi_aware", False)

def _resolve_ksi_context_variables(variables: Dict[str, Any], composition: Composition) -> None:
    """Only resolve KSI variables for compositions that declare ksi_aware: true."""
    if not _should_resolve_ksi_context(composition):
        logger.debug(f"Skipping KSI resolution for non-KSI composition: {composition.name}")
        return
    # ... existing KSI resolution logic
```

### 2. Enhanced Discovery System
```python
# In composition:discover handler
def filter_by_metadata(compositions: List[Dict], metadata_filter: Dict) -> List[Dict]:
    """Filter compositions by metadata criteria."""
    filtered = []
    for comp in compositions:
        metadata = comp.get("metadata", {})
        if all(metadata.get(key) == value for key, value in metadata_filter.items()):
            filtered.append(comp)
    return filtered
```

### 3. Dynamic Agent Spawning
```python
# Agent service becomes query-driven
suitable_compositions = await event_emitter("composition:discover", {
    "metadata_filter": {
        "ksi_aware": wants_ksi_context,
        "suitable_for": agent_type
    }
})

# Or use intelligent selection
selected = await event_emitter("composition:select", {
    "agent_id": agent_id,
    "role": agent_type,
    "context": {"spawn_request": True},
    "requirements": {"ksi_aware": wants_ksi_context}
})
```

## Architectural Benefits

### ✅ Experimental Control
```python
# Spawn pure agent for baseline
spawn_result = await spawn_agent("researcher", ksi_context=False)
# Gets claude_agent_default (ksi_aware: false)

# Spawn KSI-aware agent for comparison  
spawn_result = await spawn_agent("researcher", ksi_context=True)
# Gets ksi_research_agent (ksi_aware: true)
```

### ✅ Introspectable System
```bash
# Discover all KSI-aware compositions
ksi-cli send composition:discover --metadata_filter '{"ksi_aware": true}'

# Find compositions suitable for researchers
ksi-cli send composition:discover --metadata_filter '{"suitable_for": ["researcher"]}'
```

### ✅ Zero Code Changes for New Compositions
Adding `ksi_security_agent.yaml` with `ksi_aware: true` immediately enables KSI context resolution without touching Python code.

### ✅ Clean Separation of Concerns
- **Composition system**: Handles metadata-driven KSI resolution
- **Agent service**: Queries for suitable compositions
- **Discovery system**: Filters by metadata criteria
- **No hardcoded mappings**: All configuration is declarative

## Implementation Tasks

### Phase 1: Metadata-Driven KSI Resolution
1. **Enhance composition metadata schema** with ksi_aware field
2. **Modify KSI context resolution** to check composition.metadata.ksi_aware
3. **Update existing compositions** to declare ksi_aware status
4. **Create KSI-aware variants** (ksi_developer_agent.yaml, etc.)

### Phase 2: Enhanced Discovery
1. **Add metadata filtering** to composition:discover
2. **Enhance composition:select** to consider metadata requirements
3. **Update agent spawning** to query for suitable compositions
4. **Add validation** for ksi_aware compositions

### Phase 3: Documentation & Testing
1. **Document composition metadata schema**
2. **Create composition authoring guide**
3. **Test experimental control scenarios**
4. **Validate performance impact**

## Migration Strategy

### Backward Compatibility
- Existing compositions without `ksi_aware` default to `false`
- Current agent spawning continues to work
- Gradual migration to metadata-driven approach

### Rollout Plan
1. **Phase 1**: Add metadata support, keep existing behavior
2. **Phase 2**: Create KSI-aware composition variants
3. **Phase 3**: Update agent spawning to query metadata
4. **Phase 4**: Remove hardcoded logic, full declarative system

## Success Metrics

- **Zero hardcoded agent type mappings** in Python code
- **All KSI context injection** driven by composition metadata
- **Successful experimental control** (pure vs KSI-aware agents)
- **Dynamic discovery** of suitable compositions by metadata
- **Clean separation** between agent service and composition system

---

*This architecture makes KSI truly **configuration-driven** rather than **code-driven**, enabling flexible experimentation and clean system boundaries.*