#!/usr/bin/env python3
"""
Enhanced template processing utilities for KSI.

This module provides a unified interface for template substitution throughout
the KSI system, with advanced features for complex use cases.

Template Syntax:
    {{variable}} - Simple variable substitution
    {{variable|default}} - With default value
    {{object.field}} - Nested object access with dot notation
    {{array.0}} - Array indexing
    {{deep.nested.path.to.value}} - Arbitrary depth traversal
    {{$}} - Pass-through entire data structure
    {{_ksi_context.field}} - Access context variables
    {{func()}} - Function calls (timestamp_utc, len, upper, etc.)
    {{func(arg)}} - Function calls with arguments

Example:
    >>> data = {"user": {"name": "Alice", "id": 123}, "items": ["a", "b", "c"]}
    >>> template = "Hello {{user.name|Anonymous}} (ID: {{user.id}}), {{len(items)}} items"
    >>> substitute_template(template, data)
    'Hello Alice (ID: 123), 3 items'
"""

import re
import time
import json
from typing import Any, Dict, List, Union, Optional, Callable
from datetime import datetime, timezone


class TemplateResolutionError(Exception):
    """Raised when a template variable cannot be resolved in strict mode."""
    
    def __init__(self, message: str, template: str = None, missing_variable: str = None, 
                 available_variables: List[str] = None):
        super().__init__(message)
        self.template = template
        self.missing_variable = missing_variable
        self.available_variables = available_variables or []

# Try to import KSI utilities, fallback for standalone usage
try:
    from ksi_common.json_utils import dumps as json_dumps
except ImportError:
    json_dumps = json.dumps
    
try:
    from ksi_common.utils import timestamp_utc
except ImportError:
    def timestamp_utc():
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


# Template pattern for matching {{variable}} syntax
TEMPLATE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

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
    'is_event_handled': lambda event_name: _check_event_handled(event_name),
}


def _check_event_handled(event_name: str) -> bool:
    """
    Template function to check if an event is handled by real handlers or transformers.
    
    This is a wrapper around event_validation.is_event_handled() for use in templates.
    
    Args:
        event_name: The event name to check
        
    Returns:
        True if event has real handlers/transformers, False otherwise
    """
    try:
        from ksi_common.event_validation import is_event_handled
        return is_event_handled(event_name)
    except ImportError:
        # If event_validation is not available, assume event is valid
        return True


def substitute_template(template: Any, context: Dict[str, Any],
                       ksi_context: Optional[Dict[str, Any]] = None,
                       functions: Optional[Dict[str, Callable]] = None) -> Any:
    """
    Recursively substitute template variables in any data structure.
    
    This function processes strings, dictionaries, and lists, replacing
    {{variable}} patterns with values from the provided context.
    BREAKING CHANGE: Always raises exception on missing variables (fail-fast).
    
    Args:
        template: The template to process (string, dict, list, or any value)
        context: Dictionary containing values for substitution
        ksi_context: Optional KSI context data (e.g., _agent_id, _request_id)
        functions: Optional additional functions for templates
        
    Returns:
        The processed template with all variables substituted
        
    Raises:
        TemplateResolutionError: When a variable cannot be resolved
        
    Examples:
        >>> substitute_template("Hello {{name}}", {"name": "World"})
        'Hello World'
        
        >>> substitute_template("{{$}}", {"a": 1, "b": 2})
        {'a': 1, 'b': 2}
        
        >>> substitute_template("{{name|Guest}}", {})
        'Guest'
        
        >>> substitute_template("{{upper(name)}}", {"name": "alice"})
        'ALICE'
        
        >>> substitute_template("{{missing}}", {})
        TemplateResolutionError: Cannot resolve variable 'missing'
    """
    if isinstance(template, str):
        return _substitute_string(template, context, ksi_context, functions)
    elif isinstance(template, dict):
        return {k: substitute_template(v, context, ksi_context, functions) 
                for k, v in template.items()}
    elif isinstance(template, list):
        return [substitute_template(item, context, ksi_context, functions) 
                for item in template]
    else:
        # Static value - return as-is
        return template


def _substitute_string(template: str, context: Dict[str, Any],
                      ksi_context: Optional[Dict[str, Any]] = None,
                      functions: Optional[Dict[str, Callable]] = None) -> Any:
    """
    Substitute variables in a string template.
    
    Args:
        template: String containing {{variable}} patterns
        context: Dictionary with substitution values
        ksi_context: Optional KSI context data
        functions: Optional additional functions
        
    Returns:
        Processed template (string or original data for {{$}})
        
    Raises:
        TemplateResolutionError: When a variable cannot be resolved
    """
    # Special case: {{$}} for entire data
    if template == "{{$}}":
        return context
    
    # Combine built-in and custom functions
    all_functions = TEMPLATE_FUNCTIONS.copy()
    if functions:
        all_functions.update(functions)
    
    def replace_match(match):
        var_expr = match.group(1).strip()
        
        # Handle {{$}} in string context
        if var_expr == "$":
            return json_dumps(context)
        
        # Handle function calls
        if '(' in var_expr and ')' in var_expr:
            return _evaluate_function(var_expr, context, ksi_context, all_functions)
        
        # Handle default values
        if '|' in var_expr:
            var_name, default_value = var_expr.split('|', 1)
            var_name = var_name.strip()
            default_value = default_value.strip()
        else:
            var_name = var_expr
            default_value = None
        
        # Handle context access
        if var_name.startswith('_ksi_context.') and ksi_context:
            context_path = var_name[13:]  # Remove prefix
            value = resolve_path(context_path, ksi_context)
        else:
            # Regular variable access
            value = resolve_path(var_name, context)
        
        # Return value or default
        if value is None:
            if default_value is not None:
                return default_value
            else:
                # ALWAYS raise exception for missing variables (fail-fast)
                available_vars = list(context.keys())
                if ksi_context:
                    available_vars.extend([f"_ksi_context.{k}" for k in ksi_context.keys()])
                raise TemplateResolutionError(
                    f"Cannot resolve variable '{var_name}' in template",
                    template=template,
                    missing_variable=var_name,
                    available_variables=available_vars
                )
        elif isinstance(value, (dict, list)):
            return json_dumps(value)
        else:
            return str(value)
    
    return TEMPLATE_PATTERN.sub(replace_match, template)


def resolve_path(path: str, context: Dict[str, Any]) -> Any:
    """
    Resolve a dot-separated path in a nested data structure.
    
    Supports:
    - Object property access: "user.name"
    - Array indexing: "items.0"
    - Mixed access: "data.users.0.name"
    
    Args:
        path: Dot-separated path string
        context: The data structure to traverse
        
    Returns:
        The value at the path, or None if not found
        
    Examples:
        >>> data = {"user": {"name": "Alice"}, "items": ["a", "b"]}
        >>> resolve_path("user.name", data)
        'Alice'
        >>> resolve_path("items.0", data)
        'a'
    """
    if not path:
        return context
        
    parts = path.split('.')
    current = context
    
    for part in parts:
        if current is None:
            return None
            
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            # Array index access
            index = int(part)
            if 0 <= index < len(current):
                current = current[index]
            else:
                return None
        else:
            return None
    
    return current


def _evaluate_function(expr: str, context: Dict[str, Any],
                      ksi_context: Optional[Dict[str, Any]],
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
        return f"{{{{{expr}}}}}"  # Return unchanged if not valid
    
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
    
    # Single argument - resolve from context
    try:
        # First try to resolve as a path
        arg_value = resolve_path(args_str, context)
        
        # Try ksi_context if not found and path suggests it
        if arg_value is None and ksi_context and args_str.startswith('_ksi_context.'):
            arg_value = resolve_path(args_str[13:], ksi_context)
        
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


def apply_mapping(mapping: Any, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> Any:
    """
    Apply a field mapping with template substitution.
    
    Enhanced to support:
    - Direct pass-through with "{{$}}"
    - KSI context variables
    - Function calls in templates
    
    Args:
        mapping: Mapping specification (dict, string, or any template)
        data: Source data for template substitution
        context: Optional KSI context (for _ksi_context access)
        
    Returns:
        Transformed data according to mapping
        
    Examples:
        >>> mapping = "{{$}}"  # Pass everything through
        >>> data = {"a": 1, "b": 2}
        >>> apply_mapping(mapping, data)
        {'a': 1, 'b': 2}
        
        >>> mapping = {
        ...     "user_id": "{{id}}",
        ...     "name": "{{first|Anonymous}} {{last}}",
        ...     "created": "{{timestamp_utc()}}"
        ... }
        >>> apply_mapping(mapping, {"id": 123, "first": "John"})
        {'user_id': '123', 'name': 'John ', 'created': '2024-01-20T...'}
    """
    # Handle non-dict mappings (e.g., "{{$}}" or direct templates)
    if not isinstance(mapping, dict):
        return substitute_template(mapping, data, context)
    
    # Original dict mapping logic
    result = {}
    
    for target_field, source_value in mapping.items():
        # Apply template substitution to the source value
        processed_value = substitute_template(source_value, data, context)
        
        # Handle nested target fields
        if '.' in target_field:
            # Create nested structure
            current = result
            parts = target_field.split('.')
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = processed_value
        else:
            result[target_field] = processed_value
    
    return result


def extract_variables(template: Any) -> List[str]:
    """
    Extract all variable names from a template.
    
    Enhanced to handle:
    - Function calls: {{len(items)}} -> extracts 'items'
    - Context variables: {{_ksi_context.agent_id}} -> extracts '_ksi_context'
    - Pass-through: {{$}} -> extracts '$'
    - Default values: {{name|default}} -> extracts 'name'
    
    Args:
        template: The template to analyze
        
    Returns:
        List of unique variable names found in the template
        
    Examples:
        >>> extract_variables("Hello {{name|Guest}}, {{len(items)}} items")
        ['items', 'name']
        
        >>> extract_variables("{{_ksi_context.agent_id}} says {{upper(message)}}")
        ['_ksi_context', 'message']
    """
    variables = set()
    
    def extract_from_string(s: str):
        for match in TEMPLATE_PATTERN.finditer(s):
            var_expr = match.group(1).strip()
            
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
                    # Skip literal strings
                    if var_expr.startswith('"') and var_expr.endswith('"'):
                        continue
                else:
                    continue
            
            # Handle default values
            if '|' in var_expr:
                var_expr = var_expr.split('|')[0].strip()
            
            # Skip empty expressions
            if not var_expr:
                continue
            
            # Extract base variable name
            if '.' in var_expr:
                base_var = var_expr.split('.')[0]
            else:
                base_var = var_expr
                
            variables.add(base_var)
    
    if isinstance(template, str):
        extract_from_string(template)
    elif isinstance(template, dict):
        for value in template.values():
            variables.update(extract_variables(value))
    elif isinstance(template, list):
        for item in template:
            variables.update(extract_variables(item))
    
    return sorted(list(variables))


def validate_template(template: Any, required_vars: List[str] = None,
                     available_vars: Dict[str, Any] = None) -> bool:
    """
    Validate that a template is well-formed and contains expected variables.
    
    Enhanced to:
    - Check if all template variables can be resolved
    - Validate function calls are valid
    - Properly detect unresolvable variables
    
    Args:
        template: The template to validate
        required_vars: List of variable names that must be present
        available_vars: Dict of available variables to check against
        
    Returns:
        True if template is valid, False if it contains unresolvable variables
        
    Examples:
        >>> validate_template("Hello {{name}}", required_vars=["name"])
        True
        >>> validate_template("Hello {{name}}", required_vars=["name", "id"])
        False
        >>> validate_template("{{missing}}", available_vars={"present": "value"})
        False
        >>> validate_template("{{present}}", available_vars={"present": "value"})
        True
    """
    if required_vars is not None:
        found_vars = extract_variables(template)
        if not all(var in found_vars for var in required_vars):
            return False
    
    if available_vars is not None:
        # Check if all template variables can be resolved
        # Since strict mode is now the default, this will raise if unresolvable
        try:
            substitute_template(template, available_vars)
            return True
        except TemplateResolutionError:
            return False
        except Exception:
            # Other exceptions might indicate malformed templates
            return False
    
    return True


# Backward compatibility aliases
def substitute_variables(content: str, variables: Dict[str, Any]) -> str:
    """
    Legacy function for backward compatibility.
    
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


# Convenience function for backward compatibility with event_system
def apply_event_mapping(mapping: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply mapping for event transformation (alias for apply_mapping).
    
    This function maintains compatibility with the event system's
    transformer functionality.
    """
    return apply_mapping(mapping, data)


# Export all public functions
__all__ = [
    'substitute_template',
    'substitute_variables',  # Backward compat
    'resolve_path',
    'apply_mapping',
    'apply_event_mapping',  # Backward compat
    'extract_variables',
    'validate_template',
    'TEMPLATE_FUNCTIONS',
]


# Self-test when run directly
if __name__ == "__main__":
    # Test data
    test_data = {
        "name": "Alice",
        "items": ["apple", "banana", "cherry"],
        "user": {"id": 123, "role": "admin"},
        "count": 5
    }
    
    test_context = {
        "_agent_id": "agent_123",
        "user_id": "user_456"
    }
    
    print("=== Enhanced Template Utils Tests ===\n")
    
    # Test cases
    tests = [
        # Basic substitution
        ("Hello {{name}}", test_data, None, "Hello Alice"),
        
        # Default values
        ("{{name|Bob}}", test_data, None, "Alice"),
        ("{{missing|default}}", test_data, None, "default"),  # Default prevents error
        
        # Nested access
        ("User: {{user.role}}", test_data, None, "User: admin"),
        ("First item: {{items.0}}", test_data, None, "First item: apple"),
        
        # Pass-through
        ("{{$}}", {"a": 1}, None, {"a": 1}),
        
        # Function calls
        ("{{upper(name)}}", test_data, None, "ALICE"),
        ("{{len(items)}} items", test_data, None, "3 items"),
        
        # Context access
        ("Agent: {{_ksi_context._agent_id}}", test_data, test_context, "Agent: agent_123"),
        
        # Complex example
        ("{{upper(name)|UNKNOWN}} has {{len(items)}} items", test_data, None, "ALICE has 3 items"),
    ]
    
    for template, data, context, expected in tests:
        try:
            result = substitute_template(template, data, context)
            status = "✓" if result == expected else "✗"
            print(f"{status} {template}")
            print(f"  Result: {result}")
            if result != expected:
                print(f"  Expected: {expected}")
        except TemplateResolutionError as e:
            print(f"✗ {template}")
            print(f"  Error: {e}")
        print()
    
    # Test apply_mapping
    print("\n=== Mapping Tests ===\n")
    
    # Pass-through mapping
    mapping1 = "{{$}}"
    result1 = apply_mapping(mapping1, test_data)
    print(f"Pass-through: {result1 == test_data}")
    
    # Complex mapping
    mapping2 = {
        "user_name": "{{name|Anonymous}}",
        "item_count": "{{len(items)}}",
        "first_item": "{{items.0}}",
        "admin": "{{user.role == 'admin'}}",
        "timestamp": "{{timestamp_utc()}}"
    }
    result2 = apply_mapping(mapping2, test_data)
    print(f"Complex mapping: {result2}")
    
    # Test variable extraction
    print("\n=== Variable Extraction ===\n")
    template = "{{name|Guest}} has {{len(items)}} items, agent: {{_ksi_context.agent_id}}"
    vars = extract_variables(template)
    print(f"Template: {template}")
    print(f"Variables: {vars}")
    
    # Test strict mode validation
    print("\n=== Strict Mode Validation ===\n")
    print("Testing with missing variable:")
    try:
        substitute_template("{{missing_var}}", {"existing_var": "value"})
        print("ERROR: Should have raised TemplateResolutionError")
    except TemplateResolutionError as e:
        print(f"✓ Correctly raised: {e}")
    
    print("\nTesting validate_template():")
    result = validate_template("{{missing_var}}", available_vars={"existing_var": "value"})
    print(f"validate_template('{{{{missing_var}}}}') = {result} (expected: False)")
    
    result = validate_template("{{existing_var}}", available_vars={"existing_var": "value"})
    print(f"validate_template('{{{{existing_var}}}}') = {result} (expected: True)")