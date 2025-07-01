# Composition Patterns

Master these proven composition patterns for effective KSI agent design:

## Core Agent Pattern
```yaml
components:
  - name: agent_identity
    source: components/system_identity.md
    vars:
      role: "specific role description"
      mission: "clear mission statement"
  
  - name: daemon_commands
    source: components/daemon_commands.md
    vars:
      daemon_commands: '{{daemon_commands}}'
      
  - name: response_control
    source: components/conversation_control/response_rules.md
```

## Capability Declaration Pattern
```yaml
required_context:
  agent_id: "string - unique identifier"
  capabilities:
    plugins: [specific_plugin_list]
    # OR
    plugins: [all]
    exclude: [dangerous_plugin]
```

## Conditional Component Pattern
```yaml
components:
  - name: optional_feature
    source: components/feature.md
    condition: '{{enable_feature}}'
    vars:
      feature_config: '{{feature_config}}'
```

## Safety-First Admin Pattern
```yaml
capabilities:
  plugins: [file_plugin, config_plugin]
  exclude_events: [file:delete, config:reload]  # Prevent destructive ops
```

## Variable Inheritance Pattern
```yaml
# Base composition
base_vars: &base_vars
  timeout: 30
  retry_count: 3

# Use in components
components:
  - name: service_config
    vars:
      <<: *base_vars
      specific_setting: value
```

## Mixin Pattern for Shared Capabilities
```yaml
# Common capability mixin
standard_capabilities: &standard_caps
  plugins: [completion_plugin, conversation_plugin]

# Use in multiple compositions
required_context:
  capabilities:
    <<: *standard_caps
    additional_plugin: [state_plugin]
```

## Progressive Enhancement Pattern
```yaml
# Base capabilities
minimal:
  plugins: [completion_plugin]

# Enhanced with more features  
standard:
  plugins: [completion_plugin, conversation_plugin]

# Full featured
advanced:
  plugins: [all]
  exclude: [system_plugin]
```

## Validation and Metadata Pattern
```yaml
metadata:
  tags: [descriptive, functional, tags]
  use_cases:
    - specific_use_case_1
    - specific_use_case_2
  capabilities_required: [plugin_name]
  safety_features:
    - backup_creation
    - validation_checks
  tested_with: [claude-sonnet-4]
```

## Fragment Organization Pattern
```
fragments/
├── components/           # Reusable building blocks
│   ├── identity/        # Role and mission definitions
│   ├── capabilities/    # Capability-specific contexts
│   └── controls/        # Behavior and output controls
├── mixins/              # Shared capability sets
└── templates/           # Base composition templates
```

## Error Handling Pattern
```yaml
components:
  - name: error_handling
    source: components/error_handling.md
    vars:
      fallback_behavior: "safe_mode"
      error_reporting: "detailed"
```

Use these patterns to create consistent, maintainable, and safe compositions.