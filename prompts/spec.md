# Prompt Composition System Specification

Version 1.0 | Created: 2025-06-20

## Abstract

This specification defines a standardized format for composing AI prompts from modular components using YAML compositions and Markdown components. The system is designed for git-friendly collaboration and community sharing.

## 1. Components Specification

### 1.1 Component Format
- **File Extension**: `.md` (Markdown)
- **Encoding**: UTF-8
- **Location**: `components/` directory and subdirectories

### 1.2 Variable Syntax
- **Format**: `{{variable_name}}`
- **Case**: snake_case recommended
- **Escaping**: Use `\{{` to include literal braces
- **Nesting**: Variables can reference other variables

### 1.3 Component Structure
```markdown
# Component Title

Brief description of component purpose.

## Section Name
Content with {{variable_name}} substitution.

### Subsection
More content with {{another_variable}}.
```

### 1.4 Component Best Practices
- **Single Concern**: Each component should address one aspect
- **Clear Variables**: Use descriptive variable names
- **Documentation**: Include comments explaining usage
- **Reusability**: Design for multiple contexts

## 2. Compositions Specification

### 2.1 Composition Format
- **File Extension**: `.yaml`
- **Schema Version**: 1.0
- **Location**: `compositions/` directory

### 2.2 Composition Schema
```yaml
# Required fields
name: "composition_name"           # Unique identifier
version: "semver"                  # Semantic version
description: "text"                # Brief description
author: "author_name"              # Creator attribution

# Component assembly
components:
  - name: "component_identifier"   # Unique within composition
    source: "path/to/component.md" # Relative to prompts base
    vars:                          # Component variables (optional)
      key: "value"
    condition: "expression"        # Conditional inclusion (optional)

# Context validation
required_context:
  variable_name: "type - description"

# Metadata
metadata:
  tags: ["tag1", "tag2"]          # Categorization
  use_cases: ["case1", "case2"]   # Application examples
  tested_with: ["model1"]         # Compatibility info
  community_category: "category"  # Community organization

# Community sharing (optional)
sharing:
  license: "license_type"         # Default: MIT
  repository: "repo_url"          # Source repository
  documentation: "docs_url"       # Additional documentation
  examples: "examples_path"       # Usage examples
  version_history:               # Change tracking
    - version: "1.0"
      date: "YYYY-MM-DD"
      changes: "description"
```

### 2.3 Required Fields
- `name`: Must be unique, alphanumeric with underscores
- `version`: Must follow semantic versioning (semver)
- `description`: Brief, descriptive summary
- `author`: Creator identification
- `components`: Array of component specifications
- `required_context`: Context validation schema

### 2.4 Component Specification
```yaml
- name: "unique_name"              # Required
  source: "components/file.md"     # Required, relative path
  vars:                           # Optional, key-value pairs
    variable: "value"
  condition: "{{var}} == 'value'"  # Optional, boolean expression
```

### 2.5 Condition Expressions
- **Syntax**: Python-like boolean expressions
- **Variables**: Reference context using `{{variable}}`
- **Operators**: `==`, `!=`, `in`, `not in`, `and`, `or`
- **Examples**:
  - `"{{type}} == 'analysis'"`
  - `"{{complexity}} in ['high', 'expert']"`
  - `"{{advanced_mode}} == true"`

## 3. Context Specification

### 3.1 Context Format
- **Format**: JSON object
- **Encoding**: UTF-8
- **Validation**: Against `required_context` schema

### 3.2 Context Schema
```json
{
  "variable_name": "value",
  "nested_object": {
    "key": "value"
  },
  "array_value": ["item1", "item2"]
}
```

### 3.3 Data Types
- **string**: Text values
- **number**: Numeric values (integer or float)
- **boolean**: true/false values
- **array**: List of values
- **object**: Nested key-value pairs

## 4. Composition Engine Specification

### 4.1 Processing Pipeline
1. **Load Composition**: Parse YAML composition file
2. **Validate Context**: Check required context variables
3. **Process Components**: For each component:
   - Evaluate condition (if present)
   - Load component content
   - Substitute variables
4. **Assemble Prompt**: Join processed components
5. **Return Result**: Final composed prompt

### 4.2 Variable Substitution
- **Order**: Component vars override context vars
- **Recursion**: Single-pass substitution (no recursive resolution)
- **Missing Variables**: Raise error for undefined variables
- **Type Conversion**: Convert all values to strings

### 4.3 Error Handling
- **File Not Found**: Clear error message with path
- **Invalid YAML**: Syntax error with line number
- **Missing Context**: List all missing required variables
- **Condition Error**: Graceful fallback with warning

## 5. File Organization

### 5.1 Directory Structure
```
prompts/
├── components/                    # Component library
│   ├── general/                  # General-purpose components
│   ├── domain/                   # Domain-specific components
│   └── experimental/             # Experimental components
├── compositions/                 # Composition recipes
├── examples/                     # Usage examples
├── community/                    # Community contributions
├── composer.py                   # Composition engine
├── README.md                     # Documentation
└── spec.md                       # This specification
```

### 5.2 Naming Conventions
- **Components**: Descriptive nouns (`system_identity.md`)
- **Compositions**: Use case names (`autonomous_researcher.yaml`)
- **Variables**: snake_case (`experiment_name`)
- **Directories**: Lowercase with underscores

## 6. Versioning and Compatibility

### 6.1 Semantic Versioning
- **Major**: Breaking changes to composition format
- **Minor**: New features, backward compatible
- **Patch**: Bug fixes, clarifications

### 6.2 Backward Compatibility
- **Components**: Stable variable interfaces
- **Compositions**: Maintain required_context schema
- **Engine**: Support previous composition versions

### 6.3 Migration
- **Deprecation**: 2 version warning period
- **Migration Tools**: Automated conversion utilities
- **Documentation**: Clear upgrade paths

## 7. Security Considerations

### 7.1 Code Injection
- **Variable Substitution**: Simple string replacement only
- **Condition Evaluation**: Restricted expression syntax
- **File Access**: Sandboxed to prompts directory

### 7.2 Content Validation
- **Component Sources**: Validate file paths
- **YAML Parsing**: Safe loading only
- **Context Validation**: Type and format checking

## 8. Community Standards

### 8.1 Contribution Guidelines
- **License**: MIT preferred for maximum sharing
- **Attribution**: Clear author identification
- **Documentation**: Comprehensive usage examples
- **Testing**: Validation before submission

### 8.2 Quality Standards
- **Clarity**: Clear, understandable prompts
- **Modularity**: Reusable, focused components
- **Reliability**: Tested and validated compositions
- **Maintenance**: Responsive to issues and updates

### 8.3 Organization
- **Categories**: Standardized categorization system
- **Tagging**: Consistent tag vocabulary
- **Search**: Discoverable through metadata
- **Curation**: Community review and quality control

## 9. Implementation Examples

### 9.1 Basic Usage
```python
from composer import PromptComposer

composer = PromptComposer("prompts/")
prompt = composer.compose("autonomous_researcher", {
    "experiment_name": "test_analysis",
    "output_filename": "results.md"
})
```

### 9.2 Validation
```python
issues = composer.validate_composition("my_composition")
if not issues:
    print("Composition is valid")
```

### 9.3 Programmatic Creation
```python
composition = {
    "name": "dynamic_composition",
    "version": "1.0",
    "description": "Dynamically created composition",
    "author": "automated_system",
    "components": [
        {
            "name": "identity",
            "source": "components/system_identity.md",
            "vars": {"role": "assistant"}
        }
    ],
    "required_context": {}
}
```

## 10. Future Extensions

### 10.1 Planned Features
- **Template Inheritance**: Composition extends others
- **Component Validation**: Schema validation for components
- **Plugin System**: Custom variable processors
- **IDE Integration**: Editor support for composition files

### 10.2 Research Areas
- **Automatic Optimization**: ML-based prompt improvement
- **Performance Metrics**: Quality measurement systems
- **A/B Testing**: Framework for prompt comparison
- **Community Analytics**: Usage and effectiveness tracking

---

**Specification Version**: 1.0  
**Last Updated**: 2025-06-20  
**Status**: Initial Release