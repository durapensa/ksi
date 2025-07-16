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

### Phase 3: Rendering Support
- Implement recursive mixin resolution
- Apply variable substitution at render time
- Handle circular dependency detection
- Support conditional mixins

### Phase 4: Full YAML Components
- Allow `.yaml` component files
- Support all composition features
- Enable component versioning
- Add component discovery enhancements

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

### Phase 3 Tests
1. Test recursive mixin resolution
2. Test variable substitution in mixed components
3. Test conditional mixin application
4. Performance test deep inheritance chains

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