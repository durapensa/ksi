# Capability System Usage Guide

## Overview

The KSI Capability System provides a hierarchical, modular approach to defining agent permissions and knowledge. Capabilities are reusable components that can be combined to create sophisticated agent profiles with exactly the permissions and knowledge they need.

## Core Concepts

### Capability Definition
A capability is a YAML file that defines:
- **Permissions**: What events and tools an agent can access
- **Knowledge**: Instructions and examples for using those permissions
- **Inheritance**: Base capabilities that this capability extends
- **Validation**: Rules for validating the capability
- **Compatibility**: Compatible LLM models and versions

### Capability Hierarchy
```
base (fundamental operations)
├── orchestration (extends base)
├── pattern_discovery (extends base) 
├── agent_messaging (extends base)
└── decision_tracking (extends base)
```

## Usage

### 1. Loading Capabilities

```bash
# Load a capability with inheritance resolution
ksi send capability:load --name orchestration

# Load without inheritance resolution
ksi send capability:load --name orchestration --resolve_inheritance false
```

### 2. Listing Available Capabilities

```bash
# List all capabilities
ksi send capability:list
```

### 3. Resolving Profile Capabilities

```bash
# Get all capabilities for a profile
ksi send profile:resolve_capabilities --name "system/orchestrator"

# Get only permissions
ksi send profile:resolve_capabilities --name "system/orchestrator" --include_knowledge false

# Get only knowledge
ksi send profile:resolve_capabilities --name "system/orchestrator" --include_permissions false
```

### 4. Validating Capabilities

```bash
# Validate a capability definition
ksi send capability:validate --name orchestration
```

## Capability Structure

### Basic Capability Template

```yaml
name: capability_name
type: capability
version: 1.0.0
description: "Brief description of what this capability provides"
author: ksi
extends: base  # or null for base capabilities

metadata:
  tags:
    - tag1
    - tag2
  category: system
  priority: medium

permissions:
  events:
    - event:name
    - event:pattern:*
  claude_tools: []
  mcp_servers: []

knowledge:
  instructions: |
    ## Capability Instructions
    
    Detailed instructions on how to use this capability.
    
    Example event:
    {"event": "example:event", "data": {"key": "value"}}
    
  examples:
    - name: "Example usage"
      description: "Description of example"
      code: |
        {"event": "example:event", "data": {"param": "value"}}

validation:
  required_permissions:
    - event:name
  required_fields:
    - name
    - permissions

compatibility:
  provider_models:
    - claude-3-*
    - claude-4-*
  minimum_version: "1.0.0"
  requires_capabilities:
    - base
```

## Built-in Capabilities

### Base Capability
- **File**: `capabilities/base.yaml`
- **Purpose**: Fundamental agent operations
- **Permissions**: state:get, state:set, monitor:get_events, monitor:get_status
- **Use Cases**: All agents need these basic operations

### Orchestration Capability
- **File**: `capabilities/orchestration.yaml`  
- **Purpose**: Multi-agent orchestration and coordination
- **Permissions**: agent:spawn, agent:terminate, orchestration:*, composition:*
- **Use Cases**: Orchestrator agents, multi-agent systems

### Pattern Discovery Capability
- **File**: `capabilities/pattern_discovery.yaml`
- **Purpose**: Pattern discovery and adaptation
- **Permissions**: composition:discover, composition:fork, evaluation:prompt
- **Use Cases**: Intelligent pattern-aware agents

### Agent Messaging Capability
- **File**: `capabilities/agent_messaging.yaml`
- **Purpose**: Inter-agent communication
- **Permissions**: agent:send_message, agent:broadcast_message
- **Use Cases**: Collaborative agents, team coordination

### Decision Tracking Capability
- **File**: `capabilities/decision_tracking.yaml`
- **Purpose**: Decision tracking and analytics
- **Permissions**: orchestration:track, composition:track_decision
- **Use Cases**: Orchestrators, performance analysis

## Profile Integration

### Declaring Capabilities in Profiles

```yaml
# In profile YAML
name: my_profile
type: profile

metadata:
  capabilities:
    - orchestration
    - pattern_discovery

capabilities:
  orchestration: true
  pattern_discovery: true
```

### Profile Capability Resolution

When a profile is loaded, the system:
1. Extracts declared capabilities from both `metadata.capabilities` and `capabilities` sections
2. Loads each capability with inheritance resolution
3. Merges permissions from all capabilities (removes duplicates)
4. Merges knowledge from all capabilities
5. Validates that all required capabilities exist

## Events

### capability:load
Load and resolve a capability definition.

**Parameters:**
- `name` (required): Capability name
- `resolve_inheritance` (optional): Whether to resolve inheritance chain (default: true)

**Returns:**
- Capability definition with resolved permissions and knowledge

### capability:list
List all available capabilities.

**Returns:**
- Array of capability summaries with name, description, category, tags

### capability:validate
Validate a capability definition.

**Parameters:**
- `name` (required): Capability name

**Returns:**
- Validation result with errors and warnings

### profile:resolve_capabilities
Resolve all capabilities for a profile.

**Parameters:**
- `name` (required): Profile name
- `include_permissions` (optional): Include resolved permissions (default: true)
- `include_knowledge` (optional): Include resolved knowledge (default: true)

**Returns:**
- Profile capabilities with resolved permissions and knowledge

## Best Practices

### 1. Capability Design
- Keep capabilities focused and cohesive
- Use inheritance to avoid duplication
- Provide clear instructions and examples
- Include validation rules

### 2. Permission Management
- Grant minimal necessary permissions
- Use event patterns (e.g., `orchestration:*`) for related events
- Avoid overly broad permissions

### 3. Knowledge Organization
- Structure instructions with clear sections
- Provide concrete examples
- Include event format specifications
- Document common patterns

### 4. Inheritance Strategy
- Extend `base` for fundamental capabilities
- Create intermediate capabilities for common patterns
- Avoid deep inheritance chains (max 3-4 levels)

## Troubleshooting

### Common Issues

1. **Capability not found**: Check file exists in `var/lib/compositions/capabilities/`
2. **Inheritance resolution failed**: Verify parent capability exists and is valid
3. **Permission validation failed**: Check required permissions are granted
4. **Profile capability resolution empty**: Rebuild profile index with `profile:rebuild_index`

### Debugging Commands

```bash
# Check capability file exists
ls var/lib/compositions/capabilities/

# Validate capability
ksi send capability:validate --name capability_name

# Check profile indexing
ksi send profile:get_attributes --name "profile_name" --attributes '["capability"]'

# Rebuild index if needed
ksi send profile:rebuild_index
```

## Examples

### Creating a Custom Capability

```yaml
# var/lib/compositions/capabilities/data_analysis.yaml
name: data_analysis
type: capability
version: 1.0.0
description: "Data analysis and visualization capabilities"
author: ksi
extends: base

permissions:
  events:
    - data:load
    - data:transform
    - data:visualize
  claude_tools:
    - python
  mcp_servers:
    - data_analysis_server

knowledge:
  instructions: |
    ## Data Analysis Operations
    
    Load dataset:
    {"event": "data:load", "data": {"source": "dataset.csv"}}
    
    Transform data:
    {"event": "data:transform", "data": {"operation": "normalize"}}
    
    Create visualization:
    {"event": "data:visualize", "data": {"type": "scatter", "x": "feature1", "y": "feature2"}}
```

### Using in Profile

```yaml
# var/lib/compositions/profiles/domain/analysis/data_analyst.yaml
name: data_analyst
type: profile
extends: provider_base/claude_base

metadata:
  capabilities:
    - data_analysis
    - pattern_discovery

capabilities:
  data_analysis: true
  pattern_discovery: true
```

### Testing Integration

```bash
# Test capability loading
ksi send capability:load --name data_analysis

# Test profile resolution
ksi send profile:resolve_capabilities --name "domain/analysis/data_analyst"
```

## Future Enhancements

1. **Dynamic Capability Loading**: Load capabilities at runtime based on task requirements
2. **Capability Composition**: Combine multiple capabilities into custom capability sets
3. **Permission Enforcement**: Validate agent permissions at event dispatch time
4. **Capability Metrics**: Track capability usage and effectiveness
5. **Capability Marketplace**: Share and discover capabilities across systems

---

*Last Updated: 2025-07-16*
*Version: 1.0.0*