"""
Template variable substitution utilities.

Shared utilities for variable substitution in templates, used by both
the component system and agent spawning system for late-stage variable binding.
"""

import re
from typing import Dict, Any
from ksi_common.json_utils import dumps as json_dumps


def substitute_variables(content: str, variables: Dict[str, Any]) -> str:
    """
    Apply variable substitution with support for:
    - {{variable}} - basic substitution
    - {{variable|default}} - with default value
    - {{variable.key}} - nested access
    
    Args:
        content: Template string containing {{variables}}
        variables: Dictionary of variables to substitute
        
    Returns:
        String with variables substituted
    """
    def replace_var(match):
        var_expr = match.group(1)
        
        # Handle default values
        if '|' in var_expr:
            var_name, default_value = var_expr.split('|', 1)
            var_name = var_name.strip()
            default_value = default_value.strip()
        else:
            var_name = var_expr.strip()
            default_value = ""
        
        # Handle nested variables (e.g., user.name)
        if '.' in var_name:
            value = _get_nested_value(variables, var_name)
        else:
            value = variables.get(var_name, default_value)
        
        # Convert complex types to appropriate string representation
        if isinstance(value, (dict, list)):
            return json_dumps(value)
        elif value is None:
            return default_value
        else:
            return str(value)
    
    return re.sub(r'\{\{([^}]+)\}\}', replace_var, content)


def _get_nested_value(data: Dict[str, Any], key_path: str) -> Any:
    """Get nested value from dictionary using dot notation."""
    keys = key_path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    
    return current


def extract_template_variables(content: str) -> set:
    """
    Extract all template variable names from a template string.
    
    Args:
        content: Template string containing {{variables}}
        
    Returns:
        Set of variable names found in the template
    """
    pattern = r'\{\{([^}|]+)(?:\|[^}]*)?\}\}'
    matches = re.findall(pattern, content)
    
    variables = set()
    for match in matches:
        var_name = match.strip()
        # Extract base variable name for nested access
        if '.' in var_name:
            var_name = var_name.split('.')[0]
        variables.add(var_name)
    
    return variables