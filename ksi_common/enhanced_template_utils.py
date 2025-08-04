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
"""

import re
import time
import json
from typing import Dict, Any, Union, List, Optional, Callable
from datetime import datetime
from functools import lru_cache

# Import existing utilities - with fallbacks for testing
try:
    from ksi_common.json_utils import dumps as json_dumps
except ImportError:
    json_dumps = json.dumps
    
try:
    from ksi_common.utils import timestamp_utc
except ImportError:
    def timestamp_utc():
        return datetime.utcnow().isoformat() + "Z"


# Compiled regex patterns for template processing
TEMPLATE_VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
FUNCTION_CALL_PATTERN = re.compile(r'(\w+)\((.*)\)')

@lru_cache(maxsize=1000)
def _split_path(path: str) -> tuple:
    """
    Cache path splitting operation for repeated access patterns.
    Returns tuple for hashability in lru_cache.
    """
    return tuple(path.split('.'))


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
        
    Examples:
        >>> substitute_template("Hello {{name}}", {"name": "World"})
        'Hello World'
        
        >>> substitute_template("{{$}}", {"a": 1, "b": 2})
        {'a': 1, 'b': 2}
        
        >>> substitute_template({"msg": "{{upper(text)}}"}, {"text": "hello"})
        {'msg': 'HELLO'}
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
                      functions: Optional[Dict[str, Callable]] = None) -> Any:
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
        elif var_name == '_ksi_context':
            # _ksi_context might be a reference string or actual data
            value = _get_nested_value(data, var_name)
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
    
    return TEMPLATE_VARIABLE_PATTERN.sub(replace_var, template)


def _get_nested_value(data: Union[Dict, List, Any], path: str) -> Any:
    """
    Get nested value supporting both dot notation and array indexes.
    
    Examples:
        data.key -> data['key']
        items.0 -> items[0]
        users.0.name -> users[0]['name']
    """
    if not path:
        return data
        
    parts = _split_path(path)
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
    match = FUNCTION_CALL_PATTERN.match(expr)
    if not match:
        return f"{{{{{expr}}}}}"  # Return unchanged if not a valid function
    
    func_name = match.group(1)
    args_str = match.group(2).strip()
    
    if func_name not in functions:
        return f"{{{{{expr}}}}}"  # Return unchanged if function not found
    
    func = functions[func_name]
    
    # No arguments
    if not args_str:
        try:
            result = func()
            return str(result)
        except Exception:
            return f"{{{{{expr}}}}}"
    
    # Single argument - resolve from data
    try:
        # First try to resolve as a path
        arg_value = _get_nested_value(data, args_str)
        
        # Try context if not found in data
        if arg_value is None and context and args_str.startswith('_ksi_context.'):
            arg_value = _get_nested_value(context, args_str[13:])
        
        # If still not found, try as literal string
        if arg_value is None and args_str.startswith('"') and args_str.endswith('"'):
            arg_value = args_str[1:-1]
        
        if arg_value is not None:
            result = func(arg_value)
            return str(result)
        else:
            return f"{{{{{expr}}}}}"
    except Exception:
        return f"{{{{{expr}}}}}"


def extract_template_variables(content: Union[str, Dict, List]) -> set:
    """
    Extract all template variable names from a template.
    
    Enhanced to handle:
    - Function calls: {{len(items)}} -> extracts 'items'
    - Context variables: {{_ksi_context.agent_id}} -> extracts '_ksi_context'
    - Pass-through: {{$}} -> extracts '$'
    - Nested structures (dicts and lists)
    
    Args:
        content: Template content (string, dict, or list)
        
    Returns:
        Set of variable names found in the template
    """
    variables = set()
    
    # Handle different content types
    if isinstance(content, str):
        _extract_from_string(content, variables)
    elif isinstance(content, dict):
        for value in content.values():
            variables.update(extract_template_variables(value))
    elif isinstance(content, list):
        for item in content:
            variables.update(extract_template_variables(item))
    
    return variables


def _extract_from_string(content: str, variables: set):
    """Extract variables from a string template."""
    matches = TEMPLATE_VARIABLE_PATTERN.findall(content)
    
    for match in matches:
        var_expr = match.strip()
        
        # Handle {{$}}
        if var_expr == '$':
            variables.add('$')
            continue
        
        # Handle function calls
        if '(' in var_expr and ')' in var_expr:
            # Extract argument
            func_match = FUNCTION_CALL_PATTERN.match(var_expr)
            if func_match and func_match.group(1):
                var_expr = func_match.group(1).strip()
                # Skip literal strings
                if var_expr.startswith('"') and var_expr.endswith('"'):
                    continue
        
        # Handle default values
        if '|' in var_expr:
            var_expr = var_expr.split('|')[0].strip()
        
        # Skip empty expressions
        if not var_expr:
            continue
        
        # Extract base variable name
        if '.' in var_expr:
            base_var = _split_path(var_expr)[0]
        else:
            base_var = var_expr
            
        variables.add(base_var)


# Maintain backwards compatibility with simpler signature
def substitute_variables(content: str, variables: Dict[str, Any]) -> str:
    """
    Legacy function for backwards compatibility.
    
    Args:
        content: Template string containing {{variables}}
        variables: Dictionary of variables to substitute
        
    Returns:
        String with variables substituted
    """
    if not isinstance(content, str):
        raise TypeError("substitute_variables only accepts string content")
    
    result = substitute_template(content, variables)
    # Always return string for backwards compatibility
    if not isinstance(result, str):
        return json_dumps(result)
    return result




# Export new functionality
__all__ = [
    'substitute_template',
    'substitute_variables',  # Backwards compat
    'extract_template_variables',
    'TEMPLATE_FUNCTIONS'
]


# Simple test to verify functionality
if __name__ == "__main__":
    # Test data
    data = {
        "name": "Alice",
        "items": ["apple", "banana", "cherry"],
        "user": {"id": 123, "role": "admin"},
        "count": 5
    }
    
    context = {
        "_agent_id": "agent_123",
        "user_id": "user_456"
    }
    
    # Test cases
    tests = [
        ("Hello {{name}}", "Hello Alice"),
        ("{{name|Bob}}", "Alice"),
        ("{{missing|default}}", "default"),
        ("Items: {{items}}", 'Items: ["apple", "banana", "cherry"]'),
        ("First: {{items.0}}", "First: apple"),
        ("User ID: {{user.id}}", "User ID: 123"),
        ("{{$}}", data),  # Pass-through
        ("Data: {{$}}", f"Data: {json_dumps(data)}"),
        ("{{upper(name)}}", "ALICE"),
        ("{{len(items)}}", "3"),
        ("{{timestamp_utc()}}", None),  # Dynamic
        ("Agent: {{_ksi_context._agent_id}}", "Agent: agent_123"),
    ]
    
    print("Enhanced Template Utils Tests:\n")
    for template, expected in tests:
        result = substitute_template(template, data, context)
        if expected is None:
            print(f"✓ {template} -> {result}")
        elif result == expected:
            print(f"✓ {template} -> {result}")
        else:
            print(f"✗ {template} -> {result} (expected: {expected})")
    
    # Test variable extraction
    print("\nVariable Extraction Tests:")
    test_templates = [
        "Hello {{name}} from {{user.role}}",
        "Count: {{len(items)}} items",
        "{{_ksi_context.agent_id}} says {{upper(message)}}",
        "All data: {{$}}"
    ]
    
    for template in test_templates:
        vars = extract_template_variables(template)
        print(f"{template} -> {vars}")