# KSI Discovery System Architecture

## Overview

KSI's discovery system uses a dual-analysis approach that combines TypedDict-based type discovery with AST-based code analysis to provide comprehensive event documentation.

## Historical Context

Analysis of git history before commit 8225bb1 (TypedDict migration start) revealed:
- **No existing parameter documentation in docstrings** - handlers had only brief one-line descriptions
- **No "Parameters:" sections** - the codebase never used formal parameter documentation
- **Minimal TypedDict comments** - early TypedDict definitions lacked inline documentation
- **Opportunity, not preservation** - the discovery system adds documentation that was missing, rather than preserving existing patterns

## Key Design Decision: Inline Comments Over Docstrings

Based on the historical analysis, we made a crucial design decision:

### Why Inline Comments?
1. **No Legacy to Preserve**: Since docstrings never contained parameter documentation, we're free to choose the best approach
2. **Co-location**: Inline comments keep documentation next to the parameter definition
3. **TypedDict Integration**: Comments naturally fit with TypedDict field definitions
4. **Structured Format**: Easy to parse structured data like `# allowed_values: ["a", "b"]`
5. **IDE Support**: Modern IDEs show inline comments in tooltips

### Example of Rich Inline Documentation:
```python
class EvaluationPromptData(TypedDict):
    composition_name: str  # Profile/prompt to evaluate
    test_suite: NotRequired[str]  # Test suite name (default: "basic_effectiveness")
    variables: NotRequired[Dict[str, Any]]  # Variables for composition
    output_format: NotRequired[str]  # allowed_values: ["json", "text", "markdown"]
    max_concurrent: NotRequired[int]  # range: 1-10, default: 3
```

This approach provides more value than trying to extract non-existent docstring patterns.

## Why Both Systems?

### TypedDict Analysis Provides:
1. **Accurate Type Information**: `List[Dict[str, Any]]`, `Optional[str]`, etc.
2. **Required/Optional Status**: Via `Required`/`NotRequired` annotations
3. **Literal Constraints**: Automatic extraction of allowed values
4. **Cross-Module Resolution**: Handles imported TypedDict definitions
5. **IDE Support**: Enables autocomplete and type checking

### AST Analysis Provides:
1. **Event Triggers**: Discovers which events a handler emits via `emit_event()` calls
2. **Dynamic Parameters**: Catches parameters accessed via computed keys
3. **Legacy Support**: Works with handlers not yet migrated to TypedDict
4. **Code Patterns**: Can detect workflow patterns and special handling
5. **Fallback Discovery**: When TypedDict isn't available or applicable

## How They Work Together

```python
# In discovery.py - both analyses always run:
type_metadata = type_analyze_handler(handler.func)  # TypedDict analysis
ast_analysis = analyze_handler(handler.func, event_name)  # AST analysis

# Smart merging:
if type_metadata and type_metadata.get('parameters'):
    # Start with TypedDict's accurate types
    handler_info['parameters'] = type_metadata['parameters'].copy()
    
    # Enhance with AST's descriptions and dynamic params
    # Merge descriptions, add missing parameters
    
    # Always get event triggers from AST
    handler_info['triggers'] = ast_analysis.get('triggers', [])
```

## Inline Comment Extraction

Both systems now extract inline comments:

### TypedDict Fields:
```python
class AgentSpawnData(TypedDict):
    profile: Required[str]  # Profile name
    agent_id: NotRequired[str]  # Agent ID (auto-generated if not provided)
```

### AST data.get() Calls:
```python
test_suite = data.get('test_suite', 'basic_effectiveness')  # Test suite to use
```

## Discovery Output Example

```bash
ksi help evaluation:prompt

Parameters:
  --composition_name: str (required)          # From TypedDict type + comment
      Composition/profile to test
  --test_suite: str (optional)               # TypedDict type + AST default
      Test suite to use (default: 'basic_effectiveness')
  --custom_param: Any (optional)              # Found only by AST
      Dynamic parameter

Triggers:                                     # Only from AST analysis
  - evaluation:started
  - completion:async
```

## Benefits of Dual Analysis

1. **No Information Loss**: Migration to TypedDict doesn't lose any documentation
2. **Progressive Enhancement**: Can migrate gradually while maintaining full discovery
3. **Redundancy**: If one system misses something, the other catches it
4. **Separation of Concerns**: Types vs behavior analysis
5. **Future Flexibility**: Each system can be enhanced independently

## Special Cases Handled

### Python Keywords
Some handlers can't use TypedDict due to Python keywords:
```python
# Can't use 'from' as TypedDict field
relationship_data = data.get('from')  # AST catches this
```

### Dynamic Access
```python
param_name = f"{prefix}_{suffix}"
value = data.get(param_name)  # AST can catch computed keys
```

### Multi-Source Parameters
```python
# TypedDict defines the structure
class ConfigData(TypedDict):
    key: str
    value: Any

# AST finds additional runtime behavior
if data.get('force'):  # Parameter not in TypedDict
    force_update()
```

## Implementation Plan for Enhanced Discovery

### Phase 1: Enhanced Comment Extraction (Current Focus)

**Goal**: Extract richer documentation from inline comments without relying on docstrings.

**Tasks**:
1. **Structured Comment Syntax** ✅
   - Extract inline comments from TypedDict field definitions
   - Parse structured formats: `# allowed_values: ["json", "text", "compact"]`
   - Support multi-line comments with continuation

2. **Default Value Detection** (In Progress)
   - Scan AST for `data.get('param', default)` patterns
   - Match parameters to TypedDict fields
   - Include defaults in discovery output

3. **Validation Rule Extraction**
   - Parse comments for validation hints: `# min_length: 5`
   - Extract range constraints: `# range: 0-100`
   - Document mutually exclusive parameters

### Phase 2: Behavioral Analysis Enhancement

**Goal**: Provide deeper insights into event handler behavior.

**Tasks**:
1. **Event Chain Discovery**
   - Track which events trigger other events
   - Build event dependency graph
   - Show common event sequences

2. **Error Pattern Detection**
   - Identify error events that handlers might emit
   - Document error conditions from code
   - Link errors to recovery patterns

3. **State Mutation Analysis**
   - Track which handlers modify global state
   - Identify state dependencies
   - Document side effects

### Phase 3: Runtime Discovery Integration

**Goal**: Combine static analysis with runtime information.

**Tasks**:
1. **Example Value Collection**
   - Collect actual parameter values from event logs
   - Build realistic example sets
   - Update discovery with real-world usage

2. **Performance Profiling**
   - Track handler execution times
   - Identify slow handlers
   - Add performance hints to discovery

3. **Usage Statistics**
   - Count event frequency
   - Track parameter combinations
   - Highlight common patterns

### Phase 4: Advanced Features

**Goal**: Make discovery a comprehensive development tool.

**Tasks**:
1. **Interactive Mode**
   - REPL-style discovery exploration
   - Tab completion for event names
   - Live parameter validation

2. **Export Formats**
   - OpenAPI schema generation
   - GraphQL schema export
   - Markdown documentation

3. **Discovery Plugins**
   - Allow modules to provide custom discovery
   - Support third-party analyzers
   - Enable domain-specific discovery

## Implementation Strategy

### Current State (32% TypedDict Migration)
- TypedDict analyzer extracts types and inline comments
- AST analyzer provides fallback and trigger discovery
- Both systems run in parallel and merge results

### Next Steps (Priority Order)

1. **Complete Default Value Extraction** (1-2 days)
   - Enhance AST analyzer to reliably find `data.get()` defaults
   - Map defaults back to TypedDict parameters
   - Include in discovery output

2. **Improve Comment Parsing** (2-3 days)
   - Support more structured comment formats
   - Handle multi-line descriptions
   - Extract validation rules and constraints

3. **Add Relationship Documentation** (3-4 days)
   - Document parameter dependencies
   - Identify mutually exclusive options
   - Show conditional requirements

4. **Create Discovery Test Suite** (2-3 days)
   - Unit tests for both analyzers
   - Integration tests for merging logic
   - Regression tests for all formats

### Success Metrics

- **Coverage**: 100% of events discoverable with rich documentation
- **Accuracy**: TypedDict types match runtime expectations
- **Usability**: Users can understand events without reading source
- **Performance**: Discovery completes in <100ms for full scan

## Future Enhancements (Post-Implementation)

1. **Trigger Declarations**: Allow TypedDict to declare emitted events
2. **Workflow Patterns**: Extract complex patterns from comment syntax
3. **Validation Rules**: Use TypedDict for runtime parameter validation
4. **Performance**: Cache analysis results for faster discovery
5. **Documentation Generation**: Export discovery data for API docs
6. **AI Integration**: Use LLM to generate parameter descriptions from code context

## Conclusion

The dual-analysis approach gives KSI the most comprehensive discovery system possible:
- **Type safety** from TypedDict
- **Behavioral insights** from AST
- **Human-friendly documentation** from inline comments
- **Complete coverage** through intelligent merging

This architecture ensures that as we continue to enhance type safety, we don't lose the dynamic discovery capabilities that make KSI's CLI so powerful and user-friendly.