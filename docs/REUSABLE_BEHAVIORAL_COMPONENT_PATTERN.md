# Reusable Behavioral Component Pattern

## Overview

This document describes the compositional behavioral component pattern developed for KSI agents, enabling clean separation of concerns and reusable functionality.

## Core Pattern

### 1. Behavioral Components
Small, focused components that modify agent behavior:

```yaml
# components/behaviors/core/claude_code_override.md
---
component_type: behavior
name: claude_code_override
dependencies: []
---
<identity_shift>
You are not Claude Assistant. You execute tasks directly and efficiently.
</identity_shift>
```

### 2. Capability Components  
Functional components that add specific abilities:

```yaml
# components/behaviors/core/json_emission.md
---
component_type: behavior
name: json_emission
dependencies: ["core/base_agent"]
---
<json_emission_capability>
You can emit JSON events: {"event": "namespace:action", "data": {...}}
</json_emission_capability>
```

### 3. Composed Agent Components
Combine behaviors for specific use cases:

```yaml
# components/agents/test_agent.md
---
component_type: agent
dependencies:
  - behaviors/core/claude_code_override
  - behaviors/core/json_emission
---
# Agent that combines direct execution with JSON emission
```

## Architectural Benefits

### **Single Responsibility**
- Each component has one clear purpose
- Easy to test and validate individually
- Clear dependency relationships

### **Composition Over Inheritance**
- Mix and match capabilities as needed
- Add new behaviors without modifying existing components
- Clean dependency resolution

### **Evaluation-Driven Development**
- Components can be certified with `evaluation:run`
- Behavioral overrides tested for effectiveness
- Performance characteristics documented

## Usage Patterns

### **Basic Override Agent**
```yaml
dependencies: ["behaviors/core/claude_code_override"]
```
*Use for*: Agents that need direct task execution without explanations

### **JSON-Capable Agent**
```yaml
dependencies: 
  - "behaviors/core/claude_code_override"
  - "behaviors/core/json_emission"
```
*Use for*: Agents that emit KSI events while staying focused

### **Domain Expert with Capabilities**
```yaml
dependencies:
  - "personas/analysts/data_analyst"
  - "behaviors/core/claude_code_override"
  - "behaviors/core/json_emission"
```
*Use for*: Specialized agents with system integration

## Implementation Guidelines

### **Component Structure**
1. **Frontmatter**: Declare type, dependencies, metadata
2. **Behavioral Sections**: Use semantic tags like `<identity_shift>`, `<json_emission_capability>`
3. **Documentation**: Clear usage notes and composition guidance

### **Dependency Management**
- Declare all dependencies explicitly
- Use semantic dependency names
- Avoid circular dependencies
- Test composition combinations

### **Testing Strategy**
1. **Individual Component Testing**: Each component passes `evaluation:run`
2. **Composition Testing**: Combined components work together
3. **Integration Testing**: Agents perform expected behaviors in KSI

## Unified Evaluation System

### **Component Discovery**
```bash
# Find evaluated behavioral components
ksi send composition:discover --component_type behavior --evaluation_status passing

# Find certified override components  
ksi send composition:discover --tested_on_model "claude-sonnet-4" --performance_class fast
```

### **Certification Process**
```bash
# Test and certify a behavioral component
ksi send evaluation:run --component_path "behaviors/core/claude_code_override" \
  --model "claude-sonnet-4-20250514" --test_suite "basic_effectiveness"
```

## Design Principles

### **Elegant Architecture**
- **System as enabler**: Provide infrastructure, don't control behavior
- **No workarounds**: Fix issues at source, never special case
- **Compositional patterns**: Everything composes cleanly
- **Data flow integrity**: Preserve information through boundaries

### **Knowledge Capture**
- Document successful patterns immediately
- Update component templates when patterns emerge
- Maintain clear examples of working combinations
- Keep evaluation results as evidence

## Development Roadmap

### **Current Phase: Foundation Building** (2025-01-27)
We've established the compositional pattern and unified evaluation system. Next steps:

1. **Build evaluation test suites** for behavioral effectiveness
2. **Create simple component improver agent** that can:
   - Read a component
   - Analyze its structure and purpose
   - Suggest specific improvements
   - Create improved version
   - Test improvement with evaluation:run
3. **Prove single agent can improve single component** before scaling

### **Future Phases**

**Phase 2: Tool Integration**
- Connect MIPRO/DSPy for systematic optimization
- Still single agent, single component focus
- Quantitative improvement metrics

**Phase 3: Orchestration Patterns**
- Implement three-layer pattern from investigation
- Multiple agents working together
- Natural language analysis → JSON translation → execution

**Phase 4: Ecosystem Effects**
- Tournament-based selection
- Components optimizing other components
- Self-improving behavioral libraries

## Conclusion

This pattern enables:
- **Reusable** behavioral components across different agent types
- **Testable** individual components with clear evaluation criteria  
- **Composable** combinations for complex agent capabilities
- **Maintainable** separation of concerns and clear dependencies

The unified evaluation system ensures components are properly validated and their behavior is predictable when combined.