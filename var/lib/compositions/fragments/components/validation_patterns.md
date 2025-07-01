# Validation Patterns

Master these validation patterns for ensuring data quality and system integrity:

## Multi-Layer Validation
1. **Syntax validation** - Parse YAML/JSON without errors
2. **Schema validation** - Conform to formal data schemas  
3. **Semantic validation** - Logical consistency and business rules
4. **Integration validation** - Components work together correctly

## Validation Workflow
```
Input Data → Syntax Check → Schema Check → Semantic Check → Integration Check → Valid/Invalid
```

## Common Validation Patterns

### Required Field Pattern
```yaml
# Schema definition
required: [name, version, type]
properties:
  name:
    type: string
    minLength: 1
```

### Conditional Validation Pattern
```yaml
# Validate based on other field values
if:
  properties:
    type:
      const: "profile"
then:
  required: [components, required_context]
```

### Reference Validation Pattern
```yaml
# Validate component references exist
properties:
  source:
    type: string
    pattern: "^components/.+\\.md$"
    # Additional check: file must exist
```

### Capability Validation Pattern
```yaml
# Validate capability declarations
properties:
  capabilities:
    type: object
    properties:
      plugins:
        type: array
        items:
          enum: [completion_plugin, agent_plugin, state_plugin, file_plugin, config_plugin]
```

## Error Handling Patterns

### Detailed Error Reporting
```yaml
# Provide specific, actionable error messages
errors:
  - field: "components[0].source"
    message: "Referenced component 'missing.md' does not exist"
    suggestion: "Check the path or create the missing component"
```

### Validation Context
```yaml
# Include validation context for debugging
validation_context:
  file_path: "/path/to/composition.yaml"
  line_number: 15
  validation_type: "schema"
  validator_version: "1.0"
```

## Progressive Validation

### Fast Fail Pattern
- **Stop on first error** for syntax issues
- **Continue validation** for schema issues to collect all errors
- **Provide summary** of all validation issues found

### Validation Levels
- **Level 1: Syntax** - YAML parsing succeeds
- **Level 2: Structure** - Required fields present, correct types
- **Level 3: References** - All referenced components exist
- **Level 4: Semantics** - Logical consistency and business rules
- **Level 5: Integration** - Components work together

## Domain-Specific Patterns

### Composition Validation
1. **Metadata validation** - name, version, type, author
2. **Component validation** - source paths, variable usage
3. **Capability validation** - plugin requirements, exclusions
4. **Reference validation** - fragment and template existence

### Configuration Validation  
1. **Type checking** - string, number, boolean validation
2. **Range validation** - numeric bounds, string lengths
3. **Format validation** - URLs, file paths, regex patterns
4. **Dependency validation** - related configuration consistency

### Schema Validation
1. **Schema syntax** - Valid JSON Schema structure
2. **Constraint logic** - Logical consistency of rules
3. **Pattern validity** - Regex patterns compile correctly
4. **Example validation** - Provided examples pass schema

## Validation Tools Integration

### Using config:validate
```bash
# Validate composition structure
{"event": "config:validate", "data": {
  "config_type": "composition",
  "file_path": "profiles/new_agent.yaml",
  "schema_path": "schemas/composition_schema.yaml"
}}
```

### Using file:validate
```bash  
# Validate file accessibility
{"event": "file:validate", "data": {
  "path": "components/new_component.md",
  "check_writable": true
}}
```

## Best Practices
- **Validate early** - Check data as soon as it's received
- **Provide context** - Include file paths and line numbers in errors
- **Suggest fixes** - Offer specific remediation steps
- **Cache validation** - Don't re-validate unchanged data
- **Log validation** - Track validation attempts and results

Use these patterns to create robust validation systems that ensure data quality.