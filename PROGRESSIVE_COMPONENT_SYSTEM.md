# Progressive Component System

Technical architecture documentation for KSI's progressive component system with persona-first design, advanced JSON extraction, and model-aware development.

## System Architecture

The Progressive Component System provides:
- **Persona-First Design**: Domain experts with minimal system integration
- **Enhanced JSON Extraction**: Balanced brace parsing for arbitrary nesting
- **Model-Aware Development**: Git-based component optimization and compatibility
- **SQLite Index**: Database-driven discovery with full metadata storage
- **Event-Driven Integration**: Complete KSI system integration via legitimate events

## JSON Extraction Architecture

### Enhanced Balanced Brace Parsing

**Core Implementation**: `ksi_common/json_utils.py` with `JSONExtractor` class handles arbitrary JSON nesting levels.

**Technical Capability**:
- **Balanced Brace Algorithm**: Processes any nesting depth with linear time complexity
- **String-Aware Parsing**: Correctly handles escaped quotes and nested structures
- **Error Feedback**: Comprehensive error responses via `agent:json_extraction_error` events

**Legitimate KSI Events Structure**:
```json
{
  "event": "state:entity:update",
  "data": {
    "id": "agent_123_progress",
    "properties": {
      "percent": 50,
      "stage": "analysis"
    }
  }
}
```

**Performance Characteristics**:
- **Linear Time**: O(n) text processing
- **Memory Efficient**: Streaming approach without regex limitations
- **Error Recovery**: Detailed feedback for malformed JSON

## Persona-First Architecture

### Core Design Principle

**Foundation**: Agents are Claude adopting authentic domain personas, not artificial system behaviors.

**Three-Layer Architecture**:
1. **Pure Personas**: Authentic domain expertise (`components/personas/universal/`)
2. **KSI Capabilities**: Minimal system communication mixins (`components/capabilities/`)
3. **Combined Agents**: Complete personas with system awareness (`components/agents/`)

**Component Structure**:
```
components/
├── personas/universal/
│   ├── data_analyst.md        # Pure domain expertise
│   └── researcher.md          # No system awareness
├── capabilities/claude_code_1.0.x/
│   └── ksi_json_reporter.md   # Minimal KSI integration
└── agents/
    └── ksi_aware_analyst.md   # Persona + capability
```

**Benefits**:
- **Natural JSON Emission**: Reporting becomes professional communication
- **Authentic Expertise**: Domain knowledge maintained throughout interactions
- **Scalable Design**: Clean separation enables modular composition
- **Maintainable**: Clear boundaries between expertise and system integration

## Model-Aware Development

### Git-Based Component Optimization

**Branch Strategy**:
```bash
git checkout claude-opus-optimized    # Deep reasoning, long context
git checkout claude-sonnet-optimized  # Speed, efficiency
git checkout main                     # Model-agnostic base
```

**Compatibility Metadata** (`.gitattributes`):
```gitattributes
components/personas/deep_researcher.md model=claude-opus performance=reasoning
components/personas/quick_analyst.md model=claude-sonnet performance=speed
components/capabilities/ksi_json_v1054.md system=claude-code-1.0.54+
```

**Environment-Aware Discovery**:
```bash
# Find optimal components for current environment
ksi send composition:discover --compatible-with current

# Target specific performance characteristics
ksi send composition:discover --optimize-for speed --model sonnet-4
ksi send composition:discover --optimize-for reasoning --model opus-4
```

## Event-Driven Integration

### Component Lifecycle

**Creation and Management**:
```bash
# Create component via KSI events
ksi send composition:create_component --name "components/test/example" \
  --content "# Example Component\n\nContent here..."

# Spawn agent from component
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst" \
  --vars '{"domain": "financial"}' --prompt "Analyze business data"
```

**Progressive Frontmatter**:
```yaml
---
version: 2.1.0
author: ksi_system
mixins:
  - capabilities/claude_code_1.0.x/ksi_json_reporter
variables:
  agent_id: "{{agent_id}}"
  expertise_level: "advanced"
---
```

## Performance Architecture

### Component Rendering
- **60x+ speedup**: LRU cache with intelligent invalidation
- **Mixin Resolution**: Recursive composition with circular dependency detection
- **Variable Substitution**: Complex data types with default values

### SQLite Composition Index
- **Database-First**: Full metadata storage eliminates file I/O during queries
- **Git Integration**: Branch and compatibility metadata for model-aware discovery
- **Performance**: Sub-millisecond component discovery and filtering

### JSON Extraction
- **Balanced Brace Parsing**: Linear O(n) time complexity for arbitrary nesting
- **Error Recovery**: Comprehensive feedback for malformed JSON
- **Memory Efficiency**: Streaming approach without regex limitations

## Component Standards

### Frontmatter Requirements

**Modern Component Structure**:
```yaml
---
version: 2.1.0
author: ksi_system
description: "Component purpose and capabilities"
mixins:
  - capabilities/claude_code_1.0.x/ksi_json_reporter
variables:
  agent_id: "{{agent_id}}"
  expertise_level: "advanced"
---
```

**Event Emission Patterns**:
- **Legitimate Events**: Use only real KSI events (`agent:*`, `state:*`, `message:*`)
- **MANDATORY Language**: Imperative instructions for consistent behavior
- **Complete JSON**: Provide exact structures agents should emit

## Development Workflow

### Component Creation

**Base Component**:
```bash
# 1. Create persona
ksi send composition:create_component --name "personas/data_analyst" \
  --content "# Senior Data Analyst\n\nExpert in statistical analysis..."

# 2. Create model variants
git checkout claude-opus-optimized
ksi send composition:create_component --name "personas/deep_data_analyst" \
  --content "# Senior Data Scientist\n\nDeep analytical capabilities..."

# 3. Update compatibility
echo "personas/deep_data_analyst.md model=claude-opus performance=reasoning" >> .gitattributes
git add . && git commit -m "Add deep reasoning data analyst for Opus"
```

### Validation

**Component Testing**:
```bash
# Test JSON emission
ksi send agent:spawn_from_component --component "personas/deep_data_analyst" \
  --prompt "Analyze complex dataset and emit progress events"

# Verify event extraction
ksi send monitor:get_events --event-patterns "agent:*" --limit 5
```

## Best Practices

### Component Design Principles

1. **Persona-First**: Authentic domain expertise before system integration
2. **Minimal KSI Integration**: Add capabilities as mixins, not core identity
3. **MANDATORY Language**: Use imperative instructions for reliable JSON emission
4. **Legitimate Events**: Only real KSI events (`agent:*`, `state:*`, `message:*`)

### Proven JSON Emission Pattern

**Reliable Template**:
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

[Domain expertise content]

During work, emit progress:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50}}}
```

**Success Factors**:
- **Imperative Language**: "MANDATORY:" not conditional "when"
- **Direct Instructions**: "Start your response with" not "emit when starting"
- **Complete JSON**: Exact structures, not abstract descriptions
- **Processing Time**: Allow 30-60 seconds for complex tasks

### Error Handling

**JSON Extraction Errors**:
- **Comprehensive Feedback**: Detailed error messages via `agent:json_extraction_error`
- **Recovery Guidance**: Specific suggestions for JSON correction
- **System Logging**: All extraction failures tracked for pattern analysis

## System Status

### Production Ready Components

**Component Library** (2025 Standards):
- `components/personas/universal/` - Pure domain expertise
- `components/capabilities/claude_code_1.0.x/` - KSI integration mixins
- `components/agents/` - Complete persona + capability combinations
- `orchestrations/` - Game theory experiments, MIPRO optimization

**Validated Features**:
- ✅ **JSON Extraction**: Balanced brace parsing for arbitrary nesting
- ✅ **Persona-First Architecture**: Proven natural JSON emission
- ✅ **Model-Aware Development**: Git-based optimization and compatibility
- ✅ **SQLite Index**: Database-driven discovery with full metadata
- ✅ **Event-Driven Integration**: Complete KSI system integration

### Technical Foundation

**Core Systems**:
- `ksi_common/json_utils.py`: Enhanced JSON extraction with error feedback
- `ksi_common/component_renderer.py`: 60x+ cached rendering performance
- `ksi_daemon/composition/composition_service.py`: Event-driven component lifecycle

**Performance Characteristics**:
- **Component Rendering**: Sub-millisecond cached access
- **JSON Extraction**: Linear O(n) balanced brace parsing
- **Discovery**: Database-first queries eliminate file I/O overhead

The Progressive Component System provides a robust foundation for consistent, scalable AI agent development with reliable JSON event emission and comprehensive error handling.

## Document Maintenance Patterns

### Update Principles

**CONSOLIDATE, DON'T APPEND**: When updating this document:
- **Replace outdated information** instead of adding new sections
- **Update existing patterns** rather than documenting new approaches
- **Evolve technical standards** in place, don't create parallel standards
- **Remove obsolete content** when patterns are superseded

### What Belongs Here
- **Core Architecture**: System design principles and technical foundations
- **Performance Characteristics**: Benchmarks, complexity analysis, optimization patterns
- **Component Standards**: Current patterns, frontmatter requirements, best practices
- **API Patterns**: Event-driven integration, development workflows

### What Doesn't Belong Here
- **Development History**: Belongs in git commits and project_knowledge.md
- **Implementation Details**: Specific code examples belong in project_knowledge.md
- **Workflow Instructions**: Belongs in CLAUDE.md
- **Progress Reports**: Temporary information that becomes outdated
- **Experimental Results**: Unless they establish new production standards

### Update Patterns
- **Technical Changes**: Update relevant architecture sections, don't add "New Feature" sections
- **Performance Updates**: Replace old metrics with current benchmarks
- **Standard Evolution**: Modify existing best practices, remove deprecated patterns
- **System Status**: Update production readiness indicators, remove completed milestones

**Target**: Maintain ~270 lines focused on essential technical architecture

---

*Technical Architecture Reference*
*Status: Production Ready - 2025 Standards*