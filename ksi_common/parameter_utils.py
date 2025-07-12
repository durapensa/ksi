#!/usr/bin/env python3
"""
Parameter Utilities for KSI

Shared utilities for parameter formatting, validation, and example generation.
Used across discovery, MCP integration, API documentation, and client libraries.
"""

import re
from typing import Any, Dict, List, Optional, Callable


def format_parameter(param_name: str, param_info: Dict[str, Any], style: str = "verbose") -> Any:
    """
    Format a single parameter based on output style.

    Args:
        param_name: Parameter name
        param_info: Parameter info dict with type, required, default, description
        style: Output format style (verbose, compact, ultra_compact, mcp, json_schema)

    Returns:
        Formatted parameter (dict, list, or string based on style)
    """
    if style == "verbose":
        # Current default format
        return param_info

    elif style == "compact":
        # Array format: [name, type, required, default, description]
        return [
            param_name,
            param_info.get("type", "Any"),
            param_info.get("required", False),
            param_info.get("default"),
            param_info.get("description", f"{param_name} parameter"),
        ]

    elif style == "ultra_compact":
        # Ultra-compact: just required flag and default
        required = 1 if param_info.get("required", False) else 0
        default = param_info.get("default")
        if default is None:
            return required
        return [required, default]

    elif style == "mcp":
        # MCP tool parameter format
        from .type_utils import ksi_type_to_json_schema_type
        
        mcp_param = {
            "type": ksi_type_to_json_schema_type(param_info.get("type", "Any")),
            "description": param_info.get("description", f"{param_name} parameter"),
        }
        if "default" in param_info and param_info["default"] is not None:
            mcp_param["default"] = param_info["default"]
        if "allowed_values" in param_info:
            mcp_param["enum"] = param_info["allowed_values"]
        return mcp_param

    elif style == "json_schema":
        # Standard JSON Schema format
        from .type_utils import ksi_type_to_json_schema_type
        
        schema = {
            "type": ksi_type_to_json_schema_type(param_info.get("type", "Any")),
            "description": param_info.get("description", f"{param_name} parameter"),
        }
        if "default" in param_info:
            schema["default"] = param_info["default"]
        if "allowed_values" in param_info:
            schema["enum"] = param_info["allowed_values"]
        return schema

    else:
        return param_info


def format_parameters(parameters: Dict[str, Dict[str, Any]], style: str = "verbose") -> Any:
    """
    Format all parameters based on output style.

    Args:
        parameters: Dict of parameter name to info
        style: Output format style

    Returns:
        Formatted parameters (dict or list based on style)
    """
    if style == "verbose":
        return parameters

    elif style == "compact":
        # Return as array of arrays
        return [format_parameter(name, info, style) for name, info in parameters.items()]

    elif style == "ultra_compact":
        # Return as array preserving order
        return [format_parameter(name, info, style) for name, info in parameters.items()]

    elif style in ("mcp", "json_schema"):
        # Return as properties dict
        return {name: format_parameter(name, info, style) for name, info in parameters.items()}

    else:
        return parameters


def generate_example_value(param_name: str, param_type: str, description: str = "") -> Any:
    """Generate appropriate example value based on type and context."""
    param_type_lower = param_type.lower()

    # Context-aware examples based on parameter name
    if "id" in param_name.lower():
        if "agent" in param_name.lower():
            return "agent_123"
        elif "session" in param_name.lower():
            return "session_abc"
        elif "request" in param_name.lower():
            return "req_xyz"
        return f"{param_name}_example"

    elif "name" in param_name.lower():
        if "module" in param_name.lower():
            return "ksi_daemon.core.example"
        elif "event" in param_name.lower():
            return "system:example"
        elif "composition" in param_name.lower():
            return "base_single_agent"
        return f"example_{param_name}"
    
    elif "compositions" in param_name.lower():
        # List of composition names
        return ["base_single_agent", "conversationalist"]

    elif "path" in param_name.lower():
        return f"/path/to/{param_name}"

    # Type-based examples with better List handling
    elif "list[str]" in param_type_lower:
        if "composition" in param_name.lower():
            return ["base_single_agent", "conversationalist"]
        return ["example1", "example2"]
    elif "list" in param_type_lower:
        return []
    elif "str" in param_type_lower:
        return f"example_{param_name}"
    elif "int" in param_type_lower:
        return 123
    elif "float" in param_type_lower:
        return 123.45
    elif "bool" in param_type_lower:
        return True
    elif "dict" in param_type_lower:
        return {}
    else:
        return f"<{param_type}>"


def generate_usage_example(event_name: str, parameters: Dict[str, Any], style: str = "cli") -> Dict[str, Any]:
    """
    Generate usage examples for different contexts.

    Args:
        event_name: Name of the event
        parameters: Parameter definitions
        style: Example style (cli, api, mcp)

    Returns:
        Usage example dict
    """
    example_data = {}

    for param_name, param_info in parameters.items():
        if param_info.get("required", False):
            # Add required parameters with example values
            example_data[param_name] = generate_example_value(
                param_name, param_info.get("type", "Any"), param_info.get("description", "")
            )
        elif "default" in param_info and param_info["default"] is not None:
            # Include parameters with non-None defaults
            example_data[param_name] = param_info["default"]

    if style == "cli":
        return {"command": f'echo \'{{"event": "{event_name}", "data": {example_data}}}\' | nc -U var/run/daemon.sock'}
    else:
        return {"event": event_name, "data": example_data}


def parse_validation_patterns(comment: str) -> Dict[str, Any]:
    """Extract structured validation info from comments."""
    patterns = {
        # Allowed values patterns
        r'one of:\s*(.+)': lambda m: {'allowed_values': parse_list_values(m.group(1))},
        r'format:\s*(.+)': lambda m: {'allowed_values': parse_list_values(m.group(1))},
        r'choices?:\s*(.+)': lambda m: {'allowed_values': parse_list_values(m.group(1))},
        r'options?:\s*(.+)': lambda m: {'allowed_values': parse_list_values(m.group(1))},
        
        # Range patterns
        r'range:\s*(\d+)\s*-\s*(\d+)': lambda m: {'min_value': int(m.group(1)), 'max_value': int(m.group(2))},
        r'min:\s*(\d+)': lambda m: {'min_value': int(m.group(1))},
        r'max:\s*(\d+)': lambda m: {'max_value': int(m.group(1))},
        r'>\s*(\d+)': lambda m: {'min_value': int(m.group(1)) + 1},
        r'>=\s*(\d+)': lambda m: {'min_value': int(m.group(1))},
        r'<\s*(\d+)': lambda m: {'max_value': int(m.group(1)) - 1},
        r'<=\s*(\d+)': lambda m: {'max_value': int(m.group(1))},
        
        # Length patterns
        r'length:\s*(\d+)': lambda m: {'exact_length': int(m.group(1))},
        r'min[_\s]?length:\s*(\d+)': lambda m: {'min_length': int(m.group(1))},
        r'max[_\s]?length:\s*(\d+)': lambda m: {'max_length': int(m.group(1))},
        
        # Pattern validation
        r'pattern:\s*([^\s]+)': lambda m: {'pattern': m.group(1)},
        r'regex:\s*([^\s]+)': lambda m: {'pattern': m.group(1)},
        r'match:\s*([^\s]+)': lambda m: {'pattern': m.group(1)},
        
        # Type validation
        r'must be valid\s+(\w+)': lambda m: {'validation_type': m.group(1)},
        r'valid\s+(\w+)': lambda m: {'validation_type': m.group(1)},
        
        # Parenthetical patterns
        r'\(([^)]+)\)\s*$': lambda m: process_parenthetical_options(m.group(1)),
    }
    
    result = {}
    for pattern, extractor in patterns.items():
        match = re.search(pattern, comment, re.IGNORECASE)
        if match:
            extracted = extractor(match)
            if extracted:
                result.update(extracted)
    return result


def parse_list_values(text: str) -> Optional[List[str]]:
    """Parse comma-separated values from text, handling quoted strings."""
    # Handle quoted values like 'value1', 'value2' or "value1", "value2"
    values = []
    
    # First try to extract quoted values
    quoted_pattern = r'["\'](["\']*)["\']'
    quoted_matches = re.findall(quoted_pattern, text)
    if quoted_matches:
        return quoted_matches
    
    # Fall back to comma-separated values
    parts = text.split(',')
    for part in parts:
        cleaned = part.strip().strip('"').strip("'")
        if cleaned:
            values.append(cleaned)
    
    return values if values else None


def process_parenthetical_options(text: str) -> Dict[str, Any]:
    """Process options in parentheses like (default: value) or (one of: a, b, c)."""
    if ':' in text:
        key, value = text.split(':', 1)
        key = key.strip().lower()
        value = value.strip()
        
        if key in ['one of', 'choices', 'options']:
            return {'allowed_values': parse_list_values(value)}
        elif key == 'default':
            # Try to parse as literal
            try:
                import ast
                return {'default': ast.literal_eval(value)}
            except:
                return {'default': value}
    
    return {}


def parse_docstring_params(func: Callable) -> Dict[str, Dict[str, Any]]:
    """
    Extract parameter descriptions from docstring.

    Supports multiple docstring formats:
    - Google style
    - NumPy style
    - Simple "name: description" format
    """
    import inspect
    
    doc = inspect.getdoc(func)
    if not doc:
        return {}

    params = {}
    lines = doc.split("\n")
    in_params = False
    current_param = None

    for line in lines:
        line = line.strip()

        # Look for parameter section
        if line.lower() in ["parameters:", "args:", "arguments:", "params:"]:
            in_params = True
            continue
        elif line and line.endswith(":") and not in_params:
            # Other section started
            in_params = False
            continue

        if in_params and line:
            # Check if this is a parameter definition
            if line.startswith(("-", "*")) or (line and line[0].isalpha()):
                # Parse parameter line
                param_def = line.lstrip("-*").strip()

                # Try different formats
                if ":" in param_def:
                    # Format: "name (type): description" or "name: description"
                    parts = param_def.split(":", 1)
                    name_part = parts[0].strip()
                    desc_part = parts[1].strip() if len(parts) > 1 else ""

                    # Extract type if present
                    if "(" in name_part and ")" in name_part:
                        name = name_part[: name_part.index("(")].strip()
                        type_str = name_part[name_part.index("(") + 1 : name_part.rindex(")")].strip()
                    else:
                        name = name_part
                        type_str = "Any"

                    # Check for optional/required hints
                    required = True
                    if "optional" in desc_part.lower() or "default" in desc_part.lower():
                        required = False

                    # Extract default value if mentioned
                    default = None
                    if "default:" in desc_part.lower():
                        default_start = desc_part.lower().index("default:") + 8
                        default_text = desc_part[default_start:].split(".")[0].strip()
                        # Try to parse the default value
                        try:
                            import ast
                            default = ast.literal_eval(default_text)
                        except (ValueError, SyntaxError):
                            default = default_text

                    params[name] = {"type": type_str, "description": desc_part, "required": required}
                    if default is not None:
                        params[name]["default"] = default

                    current_param = name

                elif current_param and line.startswith(" "):
                    # Continuation of previous parameter description
                    params[current_param]["description"] += " " + line

    return params