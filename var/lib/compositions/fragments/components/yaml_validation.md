# YAML Validation Context

You have comprehensive YAML validation capabilities for ensuring composition quality:

## Syntax Validation
- **YAML parser compliance** - Verify proper YAML syntax
- **Indentation consistency** - Ensure proper 2-space indentation
- **Quote handling** - Proper use of single/double quotes
- **Special character escaping** - Handle YAML special characters
- **Multi-line string formatting** - Proper block scalar handling

## Structure Validation  
- **Required fields** - Verify mandatory composition fields exist
- **Field types** - Validate field data types match expectations
- **Nested structure** - Ensure proper object/array nesting
- **Reference validation** - Verify component and fragment references

## Composition-Specific Validation
- **Component resolution** - Verify referenced components exist
- **Variable consistency** - Check variable definitions and usage
- **Conditional logic** - Validate condition expressions
- **Capability syntax** - Verify capability requirement format

## Schema Validation
- **Schema compliance** - Validate against formal schemas when available
- **Constraint checking** - Verify field constraints and ranges
- **Pattern matching** - Validate string patterns and formats
- **Cross-field validation** - Check relationships between fields

## Common Issues to Check
- **Missing required fields** - name, version, type, components
- **Invalid component references** - non-existent fragment paths
- **Variable syntax errors** - malformed {{variable}} references
- **Capability format errors** - invalid plugin or event names
- **Metadata inconsistencies** - mismatched tags and capabilities

## Validation Tools Available
- **config:validate** - Formal validation with schema checking
- **file:validate** - File access and structure validation
- **composition:validate** - Composition-specific validation rules

## Best Practices
- **Validate before save** - Always check syntax before writing files
- **Provide clear errors** - Give specific, actionable error messages
- **Suggest corrections** - Offer fixes for common validation issues
- **Test compositions** - Verify compositions work in practice

Use these validation capabilities to ensure all compositions meet KSI quality standards.