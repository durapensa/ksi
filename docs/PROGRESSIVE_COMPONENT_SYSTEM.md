# Progressive Component System

A Docker-inspired approach to component composition in KSI, enabling simple markdown files to progressively enhance into complex compositional structures.

## Overview

The Progressive Component System allows components to remain simple markdown files by default while supporting optional frontmatter for advanced composition features. This creates a natural progression from simple content to complex hierarchical compositions.

## Design Principles

1. **Progressive Enhancement**: Start simple, add complexity only when needed
2. **Backward Compatibility**: Existing markdown components work unchanged
3. **Auto-Detection**: System automatically detects component type
4. **Recursive Composition**: Components can compose other components
5. **Unified Model**: Same composition rules apply at all levels

## Component Types

### 1. Simple Markdown (Default)
Pure content files with no composition features:
```markdown
# My Component

This is just content. No variables, no mixins, no complexity.
```

### 2. Enhanced Markdown (With Frontmatter)
Markdown files with YAML frontmatter for composition:
```markdown
---
extends: components/base_instruction.md
mixins:
  - components/{{style}}_personality.md
  - components/common/error_handling.md
variables:
  style:
    type: string
    default: professional
    allowed_values: [professional, casual, technical]
  error_mode:
    type: string
    default: verbose
---
# {{title|Default Title}}

Enhanced content that can use variables and mix in other components.

{{base_content}}
```

### 3. Full YAML Components (Maximum Power)
Complete composition definitions (future enhancement):
```yaml
name: complex_orchestrator_instruction
type: component
version: 1.0.0
extends: components/orchestration_base
mixins:
  - components/error_handling/{{error_mode}}.md
  - components/capabilities/{{capability_level}}.yaml
variables:
  error_mode:
    type: string
    default: standard
  capability_level:
    type: string
    default: advanced
conditions:
  - condition: "capability_level == 'basic'"
    mixins:
      - components/basic_limits.md
content: |
  # Advanced Orchestrator Instructions
  
  {{base_content}}
  
  ## Your specific capabilities:
  {{capability_instructions}}
```

## Implementation Phases

### Phase 1: Auto-Detection (Current)
- Modify `composition:get_component` to detect and parse frontmatter
- Return structured data including metadata and content
- Maintain backward compatibility with simple markdown

### Phase 2: Enhanced Creation
- Update `composition:create_component` to validate frontmatter
- Check that referenced mixins exist
- Validate variable definitions
- Store metadata appropriately

### Phase 3: Rendering Support ✅ COMPLETED
- Implement recursive mixin resolution
- Apply variable substitution at render time
- Handle circular dependency detection
- Support conditional mixins
- Performance testing with deep inheritance (up to 10 levels)

### Phase 4: KSI System Integration
- Event-driven component updates and notifications
- Orchestration pattern generation from component hierarchies
- Component-based agent spawning and profile management
- Integration with existing KSI monitoring and state systems
- Component versioning and lifecycle management

### Phase 5: Full YAML Components (Future)
- Allow `.yaml` component files
- Support all composition features
- Enhanced component discovery and validation
- Component marketplace and sharing

## Usage Examples

### Creating Components

**Simple Component**:
```bash
ksi send composition:create_component \
  --name "tips/quick_tip" \
  --content "# Quick Tip\n\nAlways verify before proceeding"
```

**Enhanced Component**:
```bash
ksi send composition:create_component \
  --name "instructions/adaptive" \
  --content "---
mixins:
  - components/base.md
variables:
  mode: casual
---
# Adaptive Instructions

Content for {{mode}} mode."
```

### Using Components in Profiles

```yaml
# Profile using progressive components
name: smart_agent
type: profile
mixins:
  # Simple markdown component
  - fragments/components/basic_instruction.md
  # Enhanced component with variables
  - fragments/components/adaptive_instruction.md
variables:
  mode: technical
  style: professional
```

### Component Inheritance Chains

```
base_instruction.md (simple)
    ↓
error_handling.md (enhanced, adds mixins)
    ↓
orchestrator_instruction.md (enhanced, adds more variables)
    ↓
specialized_orchestrator.yaml (full composition)
```

## Benefits

1. **Simplicity**: Most components remain simple markdown files
2. **Power**: Complex scenarios supported without forcing complexity
3. **Discoverability**: Frontmatter makes component capabilities explicit
4. **Reusability**: Components can be mixed and matched at any level
5. **Evolution**: Natural progression from simple to complex
6. **Maintainability**: Changes to base components propagate automatically

## Testing Strategy

### Phase 1 Tests
1. Create simple markdown component, verify unchanged behavior
2. Create enhanced markdown with frontmatter, verify parsing
3. Test retrieval of both types, verify correct structure returned
4. Test malformed frontmatter handling

### Phase 2 Tests
1. Create component with invalid mixins, verify error
2. Create component with circular dependencies, verify detection
3. Test variable validation

### Phase 3 Tests ✅ COMPLETED
1. Test recursive mixin resolution
2. Test variable substitution in mixed components
3. Test conditional mixin application
4. Performance test deep inheritance chains

### Phase 4 Tests
1. Test event-driven component updates
2. Test orchestration pattern generation
3. Test component-based agent spawning
4. Test monitoring integration
5. Test component lifecycle management

## Migration Path

1. Existing markdown components continue working unchanged
2. Components can be progressively enhanced by adding frontmatter
3. No breaking changes to existing composition system
4. Optional migration tool to analyze and suggest enhancements

## Future Considerations

### Component Marketplace
- Share components across KSI instances
- Version management for components
- Dependency resolution

### Visual Component Editor
- GUI for composing components
- Drag-and-drop mixin management
- Real-time preview with variable substitution

### Component Analytics
- Track which components are used most
- Identify common patterns for extraction
- Suggest refactoring opportunities

## Phase 4: KSI System Integration

### Event-Driven Component Updates
Components can respond to KSI events and trigger updates:

```yaml
# components/adaptive_agent_profile.md
---
extends: base_agent_profile
event_subscriptions:
  - pattern: "agent:context_update"
    variable_mappings:
      context: "{{event.data.context}}"
      capabilities: "{{event.data.capabilities}}"
  - pattern: "orchestration:vars_changed"
    variable_mappings:
      environment: "{{event.data.environment}}"
variables:
  context: "default"
  capabilities: "[]"
  environment: "development"
---
# Dynamic Agent Profile

Your context: {{context}}
Your capabilities: {{capabilities}}
Environment: {{environment}}
```

### Orchestration Pattern Generation
Generate orchestration patterns from component hierarchies:

```bash
# Generate orchestration from component
ksi send composition:generate_orchestration \
  --component "components/complex_workflow" \
  --pattern_name "workflow_orchestration"

# Use component as orchestration template
ksi send orchestration:start \
  --component "components/multi_step_process" \
  --vars '{"priority": "high", "deadline": "2024-12-31"}'
```

### Component-Based Agent Spawning
Spawn agents directly from components:

```bash
# Spawn agent using component as profile
ksi send agent:spawn_from_component \
  --component "components/specialized_analyst" \
  --vars '{"domain": "financial", "depth": "detailed"}'

# Create temporary profile from component
ksi send composition:component_to_profile \
  --component "components/task_executor" \
  --profile_name "temp_executor_profile"
```

### Integration Points

1. **Composition Service Extension**
   - Add `composition:render_component` event handler
   - Implement `composition:component_to_profile` for agent spawning
   - Add `composition:generate_orchestration` for pattern creation

2. **Agent Service Integration**
   - Add `agent:spawn_from_component` event handler
   - Support component-based profile resolution
   - Dynamic profile updates from component changes

3. **Orchestration Service Integration**
   - Pattern generation from component hierarchies
   - Component-based orchestration templates
   - Dynamic orchestration variable injection

4. **Monitoring Integration**
   - Component usage tracking
   - Performance metrics for component rendering
   - Component dependency analysis

### Component Lifecycle Management
Track component versions and usage:

```bash
# Version components
ksi send composition:version_component \
  --component "components/critical_instruction" \
  --version "1.2.0" \
  --changelog "Added error handling"

# Track component usage
ksi send composition:track_usage \
  --component "components/base_agent" \
  --usage_context "agent_spawn" \
  --metadata '{"agent_id": "agent_123"}'

# Component dependency analysis
ksi send composition:analyze_dependencies \
  --component "components/complex_workflow"
```

## Implementation Notes

### Frontmatter Parsing
Use existing YAML parsing with clear separation:
```python
if content.startswith('---\n'):
    # Find closing ---
    end = content.find('\n---\n', 4)
    if end > 0:
        frontmatter = yaml.safe_load(content[4:end])
        body = content[end+5:]  # Skip closing --- and newline
        return {
            "type": "enhanced",
            "metadata": frontmatter,
            "content": body
        }
```

### Metadata Storage
- Option 1: Store in content file (current approach)
- Option 2: Separate `.meta.yaml` files
- Option 3: Database metadata with file content
- Decision: Option 1 for simplicity and portability

### Variable Substitution
- Use existing template system from composition engine
- Support default values: `{{var|default}}`
- Support nested variables: `{{user.name}}`
- Support conditional sections (future)

## Success Criteria

1. Zero breaking changes to existing components
2. Intuitive progression from simple to complex
3. Clear error messages for invalid compositions
4. Performance maintains with deep hierarchies
5. Documentation examples cover common patterns

---

*This system embodies KSI's philosophy: start simple, enhance progressively, maintain clarity.*