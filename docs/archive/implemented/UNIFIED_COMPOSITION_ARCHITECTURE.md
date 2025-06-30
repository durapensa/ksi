# Unified Composition Architecture

## Overview

The Unified Composition Architecture treats everything in KSI as a declarative composition - from agent profiles to prompts to system configurations. This creates a consistent, modular, and extensible system for all configuration needs.

## Core Principles

1. **Everything is a Composition** - Agent profiles, prompts, and system configs all use the same YAML-based composition system
2. **Declarative Over Imperative** - Define what you want, not how to build it
3. **Composition Over Inheritance** - Mix and match components rather than deep inheritance trees
4. **Git-Friendly** - Small, focused files that work well with version control
5. **No Legacy Baggage** - Clean implementation without backward compatibility constraints

## Directory Structure

```
var/lib/
├── compositions/           # All composition definitions
│   ├── profiles/          # Agent profile compositions
│   │   ├── base/         # Base profiles to extend
│   │   └── agents/       # Specific agent profiles
│   ├── prompts/          # Prompt compositions
│   │   ├── components/   # Reusable prompt fragments
│   │   └── templates/    # Complete prompt templates
│   └── system/           # System-level compositions (future)
├── fragments/            # Shared text/config fragments
└── schemas/              # YAML schemas for validation
```

## Composition Format

### Base Structure

```yaml
# Required metadata
name: "composition_name"
type: "profile|prompt|system"    # Composition type
version: "1.0.0"                 # Semantic versioning
description: "What this does"
author: "author_id"

# Optional inheritance
extends: "base_composition"      # Single inheritance
mixins: ["mixin1", "mixin2"]    # Multiple mixins

# Component assembly
components:
  - name: "component_id"
    source: "path/to/file.md"    # File reference
    vars:                        # Variable substitution
      key: "value"
    condition: "{{expr}}"        # Conditional inclusion
    
  - name: "inline_component"
    inline:                      # Inline content
      key: value
      nested:
        data: here
        
  - name: "nested_composition"
    composition: "other_comp"    # Composition reference
    vars:
      override: "value"

# Variable definitions
variables:
  var_name:
    type: "string|number|boolean|array|object"
    default: "default_value"
    required: false
    description: "What this variable does"

# Metadata for discovery
metadata:
  tags: ["tag1", "tag2"]
  capabilities: ["capability1"]
  use_cases: ["use_case1"]
```

### Profile Composition Example

```yaml
name: "software_developer_profile"
type: "profile"
version: "1.0.0"
description: "Profile for software development agents"
extends: "base_agent_profile"

components:
  # Agent configuration
  - name: "agent_config"
    inline:
      model: "sonnet"
      capabilities: ["coding", "debugging", "architecture"]
      tools: ["Read", "Edit", "Bash", "Grep"]
      
  # Include prompt composition
  - name: "prompt"
    composition: "prompts/software_developer"
    vars:
      role_emphasis: "clean, maintainable code"
      
  # Daemon-specific settings
  - name: "daemon_config"
    inline:
      message_queue_size: 100
      priority: "normal"
      
variables:
  project_context:
    type: "string"
    description: "Specific project context for the developer"
    required: false
```

### Prompt Composition Example

```yaml
name: "software_developer"
type: "prompt"
version: "1.0.0"
description: "Prompt template for software development"

components:
  - name: "identity"
    source: "fragments/system_identity.md"
    vars:
      role: "a Software Developer"
      mission: "write clean code and debug issues"
      
  - name: "capabilities"
    source: "fragments/capabilities.md"
    condition: "{{show_capabilities}}"
    
  - name: "tools"
    source: "fragments/tool_permissions.md"
    condition: "{{enable_tools}}"
    
  - name: "context"
    template: |
      ## Project Context
      {{project_context}}
    condition: "{{project_context}}"
```

## Composition Service API

### Events

```python
# Composition operations
"composition:compose"      # Compose any type
"composition:validate"     # Validate composition
"composition:discover"     # Find available compositions
"composition:resolve"      # Resolve all references

# Specialized composition
"composition:profile"      # Compose agent profile
"composition:prompt"       # Compose prompt

# Management
"composition:list"         # List compositions by type
"composition:get"          # Get composition definition
"composition:reload"       # Reload from disk
```

### Example Usage

```python
# Compose an agent profile
result = await emit_event("composition:profile", {
    "name": "software_developer_profile",
    "variables": {
        "project_context": "KSI daemon development"
    }
})

# Result includes:
# - Fully resolved agent configuration
# - Composed prompt template
# - All variables substituted
```

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create composition service plugin
2. Implement YAML parser with variable substitution
3. Build composition resolver (handles extends, mixins, components)
4. Add validation system

### Phase 2: Migration
1. Create var/lib directory structure
2. Convert existing JSON profiles to YAML compositions
3. Convert prompt compositions to new format
4. Update agent spawning to use composition service

### Phase 3: Integration
1. Remove old agent_profile_registry.py
2. Update agent_service.py to use compositions
3. Clean up legacy code paths
4. Update all interfaces to use new system

### Phase 4: Enhancement
1. Add composition inheritance
2. Implement mixin system
3. Add hot-reload capability
4. Build composition IDE/tools

## Benefits

1. **Consistency** - One system for all configuration
2. **Modularity** - Small, reusable components
3. **Flexibility** - Mix and match as needed
4. **Maintainability** - Clear structure, easy to understand
5. **Extensibility** - Easy to add new composition types
6. **Testability** - Validate compositions before use

## Migration Guide

### From JSON Profiles

Before:
```json
{
  "name": "developer",
  "role": "Software Developer",
  "model": "sonnet",
  "composition": "software_developer"
}
```

After:
```yaml
name: "developer_profile"
type: "profile"
extends: "base_agent_profile"

components:
  - name: "config"
    inline:
      model: "sonnet"
  - name: "prompt"
    composition: "prompts/software_developer"
```

### From Legacy Prompts

Before (embedded in JSON):
```json
{
  "system_prompt": "You are a developer..."
}
```

After (composition):
```yaml
components:
  - name: "identity"
    template: |
      You are a developer...
```

## Future Extensions

1. **System Compositions** - Declarative daemon configuration
2. **Network Compositions** - Multi-daemon cluster definitions
3. **Workflow Compositions** - Declarative agent workflows
4. **UI Compositions** - Declarative interface definitions

This architecture provides the foundation for KSI's vision of declarative, composable systems at every level.