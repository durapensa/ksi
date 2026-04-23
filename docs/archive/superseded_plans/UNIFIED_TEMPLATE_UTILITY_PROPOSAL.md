# Unified Template Utility Proposal

## Problem Statement

KSI currently has **duplicate template processing implementations**:
1. `ksi_common/template_utils.py` - Used by components and agents
2. `ksi_daemon/event_system.py._apply_mapping()` - Used by transformers

This duplication leads to:
- Inconsistent features across systems
- Maintenance burden
- Missed opportunities for shared enhancements

## Current Feature Comparison

### template_utils.py
- ✅ Basic substitution: `{{variable}}`
- ✅ Default values: `{{variable|default}}`
- ✅ Nested access: `{{variable.key}}`
- ✅ JSON serialization for complex types
- ❌ Array indexing
- ❌ Pass-through variable `{{$}}`
- ❌ Context access `{{_ksi_context.x}}`
- ❌ Function calls `{{timestamp_utc()}}`

### event_system._apply_mapping()
- ✅ Basic substitution: `{{variable}}`
- ✅ Nested access: `{{variable.key}}`
- ✅ Array indexing: `{{items.0}}`
- ✅ Recursive mapping for nested structures
- ❌ Default values
- ❌ Pass-through variable `{{$}}`
- ❌ Context access
- ❌ Function calls

## Proposed Unified Implementation

### Enhanced template_utils.py

```python
"""
Enhanced template variable substitution utilities.

Unified template processing for all KSI modules with support for:
- Basic substitution: {{variable}}
- Default values: {{variable|default}}
- Nested access: {{variable.key}}
- Array indexing: {{items.0}}
- Pass-through: {{$}}
- Context access: {{_ksi_context.agent_id}}
- Function calls: {{timestamp_utc()}}
- Math expressions: {{(count + 1) * 2}}
"""

import re
import time
from typing import Dict, Any, Union, List, Optional, Callable
from datetime import datetime
from ksi_common.json_utils import dumps as json_dumps
from ksi_common.utils import timestamp_utc

# Built-in template functions
TEMPLATE_FUNCTIONS = {
    'timestamp_utc': timestamp_utc,
    'time': time.time,
    'len': len,
    'str': str,
    'int': int,
    'float': float,
    'json': json_dumps,
    'upper': lambda s: str(s).upper(),
    'lower': lambda s: str(s).lower(),
}


def substitute_template(template: Any, data: Dict[str, Any], 
                       context: Optional[Dict[str, Any]] = None,
                       functions: Optional[Dict[str, Callable]] = None) -> Any:
    """
    Recursively substitute template variables in any structure.
    
    Args:
        template: Template value (string, dict, list, or any type)
        data: Data dictionary for variable substitution
        context: Optional context data (e.g., _ksi_context)
        functions: Optional additional functions for templates
        
    Returns:
        Processed template with all variables substituted
    """
    # Handle string templates
    if isinstance(template, str):
        return _substitute_string(template, data, context, functions)
    
    # Handle dictionaries recursively
    elif isinstance(template, dict):
        return {
            key: substitute_template(value, data, context, functions)
            for key, value in template.items()
        }
    
    # Handle lists recursively
    elif isinstance(template, list):
        return [
            substitute_template(item, data, context, functions)
            for item in template
        ]
    
    # Non-template values pass through
    else:
        return template


def _substitute_string(template: str, data: Dict[str, Any],
                      context: Optional[Dict[str, Any]] = None,
                      functions: Optional[Dict[str, Callable]] = None) -> str:
    """Substitute variables in a string template."""
    
    # Special case: {{$}} for entire data
    if template == "{{$}}":
        return data
    
    # Combine built-in and custom functions
    all_functions = TEMPLATE_FUNCTIONS.copy()
    if functions:
        all_functions.update(functions)
    
    def replace_var(match):
        var_expr = match.group(1).strip()
        
        # Handle {{$}} in string context
        if var_expr == "$":
            return json_dumps(data)
        
        # Handle function calls
        if '(' in var_expr and ')' in var_expr:
            return _evaluate_function(var_expr, data, context, all_functions)
        
        # Handle default values
        if '|' in var_expr:
            var_name, default_value = var_expr.split('|', 1)
            var_name = var_name.strip()
            default_value = default_value.strip()
        else:
            var_name = var_expr
            default_value = ""
        
        # Handle context access
        if var_name.startswith('_ksi_context.'):
            if context:
                context_path = var_name[13:]  # Remove prefix
                value = _get_nested_value(context, context_path)
            else:
                value = None
        else:
            # Regular variable access
            value = _get_nested_value(data, var_name)
        
        # Return value or default
        if value is None:
            return default_value
        elif isinstance(value, (dict, list)):
            return json_dumps(value)
        else:
            return str(value)
    
    return re.sub(r'\{\{([^}]+)\}\}', replace_var, template)


def _get_nested_value(data: Union[Dict, List], path: str) -> Any:
    """
    Get nested value supporting both dot notation and array indexes.
    
    Examples:
        data.key -> data['key']
        items.0 -> items[0]
        users.0.name -> users[0]['name']
    """
    parts = path.split('.')
    current = data
    
    for part in parts:
        if current is None:
            return None
            
        # Handle array index
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(current):
                current = current[index]
            else:
                return None
                
        # Handle dictionary key
        elif isinstance(current, dict) and part in current:
            current = current[part]
            
        else:
            return None
    
    return current


def _evaluate_function(expr: str, data: Dict[str, Any],
                      context: Optional[Dict[str, Any]],
                      functions: Dict[str, Callable]) -> str:
    """
    Evaluate function calls in templates.
    
    Examples:
        timestamp_utc() -> "2024-01-20T12:34:56Z"
        len(items) -> "5"
        upper(name) -> "JOHN"
    """
    # Parse function call (simplified - doesn't handle nested parens)
    match = re.match(r'(\w+)\((.*)\)', expr)
    if not match:
        return expr
    
    func_name = match.group(1)
    args_str = match.group(2).strip()
    
    if func_name not in functions:
        return expr
    
    func = functions[func_name]
    
    # No arguments
    if not args_str:
        try:
            result = func()
            return str(result)
        except:
            return expr
    
    # Single argument - resolve from data
    try:
        arg_value = _get_nested_value(data, args_str)
        if arg_value is None:
            # Try context
            if context and args_str.startswith('_ksi_context.'):
                arg_value = _get_nested_value(context, args_str[13:])
        
        if arg_value is not None:
            result = func(arg_value)
            return str(result)
    except:
        pass
    
    return expr


# Maintain backwards compatibility
substitute_variables = substitute_template


def extract_template_variables(content: str) -> set:
    """
    Extract all template variable names from a template string.
    
    Enhanced to handle:
    - Function calls: {{len(items)}} -> extracts 'items'
    - Context variables: {{_ksi_context.agent_id}} -> extracts '_ksi_context'
    - Pass-through: {{$}} -> extracts '$'
    """
    pattern = r'\{\{([^}]+)\}\}'
    matches = re.findall(pattern, content)
    
    variables = set()
    for match in matches:
        var_expr = match.strip()
        
        # Handle {{$}}
        if var_expr == '$':
            variables.add('$')
            continue
        
        # Handle function calls
        if '(' in var_expr and ')' in var_expr:
            # Extract argument
            func_match = re.match(r'\w+\((.*)\)', var_expr)
            if func_match and func_match.group(1):
                var_expr = func_match.group(1).strip()
        
        # Handle default values
        if '|' in var_expr:
            var_expr = var_expr.split('|')[0].strip()
        
        # Extract base variable name
        if '.' in var_expr:
            base_var = var_expr.split('.')[0]
        else:
            base_var = var_expr
            
        variables.add(base_var)
    
    return variables


# Export new functionality
__all__ = [
    'substitute_template',
    'substitute_variables',  # Backwards compat
    'extract_template_variables',
    'TEMPLATE_FUNCTIONS'
]
```

## Migration Plan

### Phase 1: Enhance template_utils.py
1. Add missing features from event_system
2. Add new features ({{$}}, functions, context)
3. Maintain backwards compatibility
4. Add comprehensive tests

### Phase 2: Update event_system.py
```python
# In event_system.py
from ksi_common.template_utils import substitute_template

def _apply_mapping(self, mapping: Any, data: Dict[str, Any], 
                   context: Optional[Dict[str, Any]] = None) -> Any:
    """Apply field mapping using unified template system."""
    return substitute_template(mapping, data, context)

# Remove duplicate implementation
```

### Phase 3: Update component system
- Ensure all component rendering uses enhanced features
- Add context support for component templates
- Document new template features

### Phase 4: System-wide adoption
- Update documentation
- Add template playground for testing
- Create migration guide for existing templates

## Benefits

### Immediate
- **Consistency**: Same template syntax everywhere
- **Maintenance**: Single implementation to enhance
- **Features**: All systems get all features

### Long-term
- **Extensibility**: Easy to add new functions/features
- **Testing**: Single test suite for all template logic
- **Performance**: Optimize once, benefit everywhere

## Example Usage

### Event Transformer
```yaml
transformers:
  - source: "agent:message"
    target: "audit:log"
    mapping: "{{$}}"  # Pass entire event
    
  - source: "task:completed"
    target: "metrics:record"
    mapping:
      task_id: "{{id}}"
      duration: "{{time() - started_at}}"
      user: "{{_ksi_context.user_id}}"
      timestamp: "{{timestamp_utc()}}"
```

### Component Template
```yaml
---
name: analyst_agent
---
You are {{role|Senior Analyst}} working on {{project}}.
Current time: {{timestamp_utc()}}
Assigned by: {{_ksi_context.user_id|system}}

Tasks: {{len(tasks)}} pending
First task: {{tasks.0.title|No tasks assigned}}
```

### Orchestration Pattern
```yaml
agent_configs:
  - agent_id: "agent_{{timestamp()}}"
    profile:
      name: "{{upper(agent_type)}}_agent"
      config: "{{$}}"  # Pass all orchestration config
```

## Testing Strategy

### Unit Tests
- Test each template feature in isolation
- Test edge cases (missing vars, null values)
- Test recursive structures
- Performance benchmarks

### Integration Tests
- Event transformers using templates
- Component rendering with templates
- Orchestration variable substitution

### Backwards Compatibility Tests
- Ensure existing templates still work
- Test migration path
- Verify no breaking changes

## Conclusion

Unifying template processing will:
1. Eliminate code duplication
2. Provide consistent features across KSI
3. Enable powerful new template capabilities
4. Simplify maintenance and testing

The migration can be done incrementally with full backwards compatibility, ensuring a smooth transition to the unified system.