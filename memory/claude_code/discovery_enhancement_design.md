# Discovery System Enhancement Design

## Overview
Enhance the KSI discovery system to extract richer type information from TypedDict definitions and inline comments, providing better parameter documentation without requiring extra work from module authors.

## Current State
The discovery system uses AST analysis to extract:
- Parameter names from `data.get()` and `data["key"]` patterns
- Default values from `data.get()` calls
- Inline comments as descriptions
- Basic docstring parsing

Limitations:
- All parameters show as `type: "Any"`
- No extraction from TypedDict when used as type hints
- No parsing of validation rules from comments
- Generic example values

## Enhancement Goals

### 1. TypedDict Type Extraction
When a handler uses `data: SomeTypedDict`, extract:
- Field names and types from TypedDict definition
- Required vs NotRequired fields
- Merge with existing AST analysis results

### 2. Enhanced Comment Parsing
Parse structured patterns in inline comments:
- `"one of: X, Y, Z"` → `allowed_values: ["X", "Y", "Z"]`
- `"format: 'value1', 'value2'"` → `allowed_values: ["value1", "value2"]`
- `"must be valid X"` → `validation: "valid X"`
- `"List of composition names"` → hint for example generation

### 3. Type Resolution
Show actual types instead of "Any":
- From TypedDict: `str`, `List[str]`, `Dict[str, Any]`
- From defaults: `type(default_value)`
- Keep complex types as strings for now

### 4. Context-Aware Examples
Generate better examples based on:
- Actual types (List[str] → ["example1", "example2"])
- Parameter names (compositions → ["base_single_agent"])
- Allowed values from comments
- Context from description

## Implementation Plan

### Phase 1: TypedDict Extraction
1. Detect when handler parameter has TypedDict annotation
2. Find TypedDict class definition in module
3. Extract fields using AST analysis
4. Merge with existing parameter detection

### Phase 2: Enhanced AST Analysis
1. Extend HandlerAnalyzer to track type annotations
2. Parse inline comments for structured patterns
3. Extract validation rules and allowed values

### Phase 3: Type Resolution
1. Create type mapping for common types
2. Resolve TypedDict field types to strings
3. Fall back to inference from defaults

### Phase 4: Example Generation
1. Enhance generate_example_value() with type info
2. Use allowed_values when available
3. Generate type-appropriate examples

## Technical Approach

### AST Enhancements
```python
class EnhancedHandlerAnalyzer(ast.NodeVisitor):
    def __init__(self, source_lines=None, module_tree=None):
        # ... existing init ...
        self.typed_dicts = {}  # TypedDict definitions
        self.type_annotations = {}  # Parameter type hints
        
    def visit_ClassDef(self, node):
        # Extract TypedDict definitions
        if any(base.id == 'TypedDict' for base in node.bases 
               if isinstance(base, ast.Name)):
            self.typed_dicts[node.name] = self._extract_typed_dict_fields(node)
            
    def visit_FunctionDef(self, node):
        # Extract parameter type annotations
        for arg in node.args.args:
            if arg.annotation:
                self.type_annotations[arg.arg] = self._resolve_annotation(arg.annotation)
```

### Comment Pattern Parsing
```python
def parse_validation_patterns(comment: str) -> Dict[str, Any]:
    """Extract structured validation info from comments."""
    patterns = {
        r'one of:\s*(.+)': lambda m: {'allowed_values': parse_list(m.group(1))},
        r'format:\s*(.+)': lambda m: {'allowed_values': parse_list(m.group(1))},
        r'must be valid\s+(\w+)': lambda m: {'validation': f"valid {m.group(1)}"},
        r'choices?:\s*(.+)': lambda m: {'allowed_values': parse_list(m.group(1))},
    }
    
    result = {}
    for pattern, extractor in patterns.items():
        match = re.search(pattern, comment, re.IGNORECASE)
        if match:
            result.update(extractor(match))
    return result
```

### Type String Resolution
```python
def resolve_type_string(annotation: ast.AST) -> str:
    """Convert AST annotation to readable type string."""
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        # Handle List[str], Dict[str, Any], etc.
        base = resolve_type_string(annotation.value)
        if isinstance(annotation.slice, ast.Name):
            return f"{base}[{annotation.slice.id}]"
        # ... handle more complex cases
    return "Any"
```

## Example Output

Before enhancement:
```json
"compositions": {
  "type": "Any",
  "required": false,
  "default": null,
  "description": "List of composition names to compare"
}
```

After enhancement:
```json
"compositions": {
  "type": "List[str]",
  "required": true,
  "default": null,
  "description": "List of composition names to compare",
  "validation": "Must match existing composition names",
  "example": ["base_single_agent", "conversationalist"]
}
```

## Migration Path
1. No changes required to existing modules
2. Modules using TypedDict get automatic enhancement
3. Gradual adoption as modules add TypedDict definitions
4. Backward compatible with existing discovery clients

## Testing Strategy
1. Unit tests for AST analysis enhancements
2. Integration tests with real module TypedDicts
3. Regression tests for existing functionality
4. Example generation validation

## Future Enhancements
1. Extract types from function signatures beyond just data parameter
2. Support for Union types and Optional
3. Integration with JSON Schema generation
4. Runtime type validation based on discovery info