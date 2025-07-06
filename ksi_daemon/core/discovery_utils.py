#!/usr/bin/env python3
"""
Discovery System Utilities

Shared utilities for consistent event discovery formatting across all endpoints.
Supports multiple output formats for different consumers (CLI, MCP, API docs, etc.).
"""

import ast
import inspect
from typing import Any, Callable, Dict, Optional, Set

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("discovery.utils")


# Format style constants
FORMAT_VERBOSE = "verbose"  # Full detail with nested objects
FORMAT_COMPACT = "compact"  # Arrays instead of objects
FORMAT_ULTRA_COMPACT = "ultra_compact"  # Notation strings
FORMAT_MCP = "mcp"  # MCP tool-compatible format
FORMAT_JSON_SCHEMA = "json_schema"  # JSON Schema format


def format_parameter(param_name: str, param_info: Dict[str, Any], style: str = FORMAT_VERBOSE) -> Any:
    """
    Format a single parameter based on output style.

    Args:
        param_name: Parameter name
        param_info: Parameter info dict with type, required, default, description
        style: Output format style

    Returns:
        Formatted parameter (dict, list, or string based on style)
    """
    if style == FORMAT_VERBOSE:
        # Current default format
        return param_info

    elif style == FORMAT_COMPACT:
        # Array format: [name, type, required, default, description]
        return [
            param_name,
            param_info.get("type", "Any"),
            param_info.get("required", False),
            param_info.get("default"),
            param_info.get("description", f"{param_name} parameter"),
        ]

    elif style == FORMAT_ULTRA_COMPACT:
        # Ultra-compact: just required flag and default
        required = 1 if param_info.get("required", False) else 0
        default = param_info.get("default")
        if default is None:
            return required
        return [required, default]

    elif style == FORMAT_MCP:
        # MCP tool parameter format
        mcp_param = {
            "type": ksi_type_to_json_schema_type(param_info.get("type", "Any")),
            "description": param_info.get("description", f"{param_name} parameter"),
        }
        if "default" in param_info and param_info["default"] is not None:
            mcp_param["default"] = param_info["default"]
        if "allowed_values" in param_info:
            mcp_param["enum"] = param_info["allowed_values"]
        return mcp_param

    elif style == FORMAT_JSON_SCHEMA:
        # Standard JSON Schema format
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


def format_parameters(parameters: Dict[str, Dict[str, Any]], style: str = FORMAT_VERBOSE) -> Any:
    """
    Format all parameters based on output style.

    Args:
        parameters: Dict of parameter name to info
        style: Output format style

    Returns:
        Formatted parameters (dict or list based on style)
    """
    if style == FORMAT_VERBOSE:
        return parameters

    elif style == FORMAT_COMPACT:
        # Return as array of arrays
        return [format_parameter(name, info, style) for name, info in parameters.items()]

    elif style == FORMAT_ULTRA_COMPACT:
        # Return as array preserving order
        return [format_parameter(name, info, style) for name, info in parameters.items()]

    elif style in (FORMAT_MCP, FORMAT_JSON_SCHEMA):
        # Return as properties dict
        return {name: format_parameter(name, info, style) for name, info in parameters.items()}

    else:
        return parameters


def format_event_info(
    event_name: str,
    handler_info: Dict[str, Any],
    style: str = FORMAT_VERBOSE,
    include_params: bool = True,
    include_triggers: bool = True,
    include_examples: bool = False,
) -> Dict[str, Any]:
    """
    Format event information consistently across all discovery endpoints.

    Args:
        event_name: Name of the event
        handler_info: Handler analysis results
        style: Output format style
        include_params: Include parameter details
        include_triggers: Include trigger information
        include_examples: Generate usage examples

    Returns:
        Formatted event information
    """
    if style == FORMAT_VERBOSE:
        # Full verbose format (current default)
        event_info = {
            "module": handler_info.get("module", ""),
            "handler": handler_info.get("handler", ""),
            "async": handler_info.get("async", True),
            "summary": handler_info.get("summary", ""),
        }

        if include_params and "parameters" in handler_info:
            event_info["parameters"] = handler_info["parameters"]

        if include_triggers and "triggers" in handler_info:
            event_info["triggers"] = handler_info["triggers"]

        if include_examples:
            event_info["examples"] = [generate_usage_example(event_name, handler_info.get("parameters", {}))]

        return event_info

    elif style == FORMAT_COMPACT:
        # Compact format with abbreviated keys
        event_info = {
            "m": handler_info.get("module", "").replace("ksi_daemon.", ""),
            "h": handler_info.get("handler", ""),
            "s": handler_info.get("summary", ""),
        }

        if handler_info.get("sync", False):
            event_info["y"] = True

        if include_params and "parameters" in handler_info:
            event_info["p"] = format_parameters(handler_info["parameters"], style)

        if include_triggers and handler_info.get("triggers"):
            event_info["t"] = handler_info["triggers"]

        return event_info

    elif style == FORMAT_ULTRA_COMPACT:
        # Ultra-compact for smallest possible size
        event_info = {
            "m": handler_info.get("module", "").replace("ksi_daemon.", ""),
            "h": handler_info.get("handler", "").replace("handle_", ""),
            "s": handler_info.get("summary", "")[:100],  # Truncate summary
        }

        if include_params and "parameters" in handler_info:
            # Only include if has parameters
            params = format_parameters(handler_info["parameters"], style)
            if params:
                event_info["p"] = params

        if include_triggers and handler_info.get("triggers"):
            event_info["t"] = handler_info["triggers"]

        return event_info

    elif style == FORMAT_MCP:
        # MCP-specific format for tool generation
        return {
            "name": event_name,
            "description": handler_info.get("summary", f"Execute {event_name} event"),
            "inputSchema": {
                "type": "object",
                "properties": format_parameters(handler_info.get("parameters", {}), style),
                "required": [
                    name for name, info in handler_info.get("parameters", {}).items() if info.get("required", False)
                ],
            },
        }

    else:
        return format_event_info(
            event_name, handler_info, FORMAT_VERBOSE, include_params, include_triggers, include_examples
        )


def filter_events(
    all_events: Dict[str, Any],
    namespace: Optional[str] = None,
    module: Optional[str] = None,
    pattern: Optional[str] = None,
    event_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Filter events based on various criteria.

    Args:
        all_events: Dict of all events
        namespace: Filter by event namespace (e.g., "system", "completion")
        module: Filter by module name
        pattern: Filter by event name pattern (supports wildcards)
        event_names: Specific set of event names to include

    Returns:
        Filtered events dict
    """
    filtered = {}

    for event_name, event_info in all_events.items():
        # Check specific event names filter
        if event_names and event_name not in event_names:
            continue

        # Check namespace filter
        if namespace:
            event_ns = event_name.split(":")[0] if ":" in event_name else "default"
            if event_ns != namespace:
                continue

        # Check module filter
        if module:
            event_module = event_info.get("module", "")
            if not (event_module == module or event_module.endswith(f".{module}")):
                continue

        # Check pattern filter
        if pattern:
            import fnmatch

            if not fnmatch.fnmatch(event_name, pattern):
                continue

        filtered[event_name] = event_info

    return filtered


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


def generate_example_value(param_name: str, param_type: str, description: str) -> Any:
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
        return f"example_{param_name}"

    elif "path" in param_name.lower():
        return f"/path/to/{param_name}"

    # Type-based examples
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
    elif "list" in param_type_lower:
        return []
    else:
        return f"<{param_type}>"


def ksi_type_to_json_schema_type(ksi_type: str) -> str:
    """Convert KSI type string to JSON Schema type."""
    type_map = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "dict": "object",
        "list": "array",
        "any": "object",
        "Any": "object",
    }
    return type_map.get(ksi_type, "string")


def extract_summary(func: Callable) -> str:
    """Extract summary from function docstring."""
    doc = inspect.getdoc(func)
    if doc:
        # First line is summary
        return doc.split("\n")[0].strip()
    return f"Handle {func.__name__}"


def analyze_handler(func: Callable, event_name: str) -> Dict[str, Any]:
    """
    Analyze handler implementation to extract parameters and triggers.

    Returns dict with:
    - parameters: Dict of param info extracted from data access
    - triggers: List of events this handler emits
    """
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)

        analyzer = HandlerAnalyzer()
        analyzer.visit(tree)

        # Merge parameters from different sources
        parameters = {}

        # From data.get() calls
        for name, info in analyzer.data_gets.items():
            parameters[name] = {
                "type": "Any",
                "required": info["required"],
                "default": info["default"],
                "description": f"{name} parameter",
            }

        # From data["key"] access
        for name in analyzer.data_subscripts:
            if name not in parameters:
                parameters[name] = {"type": "Any", "required": True, "description": f"{name} parameter"}

        # Try to enhance with docstring info
        doc_params = parse_docstring_params(func)
        for name, doc_info in doc_params.items():
            if name in parameters:
                parameters[name].update(doc_info)
            else:
                # Add parameters documented but not found in code
                parameters[name] = doc_info

        return {"parameters": parameters, "triggers": analyzer.triggers}

    except Exception as e:
        logger.debug(f"Analysis failed for {func.__name__}: {e}")
        return {"parameters": {}, "triggers": []}


class HandlerAnalyzer(ast.NodeVisitor):
    """AST visitor to extract parameters and event triggers."""

    def __init__(self):
        self.data_gets = {}  # data.get() calls
        self.data_subscripts = set()  # data["key"] access
        self.triggers = []  # Events emitted

    def visit_Call(self, node):
        # Check for data.get() calls
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "data"
        ):
            if node.args and isinstance(node.args[0], ast.Constant):
                key = node.args[0].value
                default = None
                required = True

                if len(node.args) > 1:
                    required = False
                    if isinstance(node.args[1], ast.Constant):
                        default = node.args[1].value

                self.data_gets[key] = {"required": required, "default": default}

        # Check for event emissions
        elif self._is_emit_call(node):
            event_name = self._extract_event_name(node)
            if event_name:
                self.triggers.append(event_name)

        self.generic_visit(node)

    def visit_Subscript(self, node):
        # Check for data["key"] access
        if isinstance(node.value, ast.Name) and node.value.id == "data" and isinstance(node.slice, ast.Constant):
            key = node.slice.value
            self.data_subscripts.add(key)

        self.generic_visit(node)

    def _is_emit_call(self, node):
        """Check if this is an event emission."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in ["emit", "emit_event", "emit_first"]
        elif isinstance(node.func, ast.Name):
            return node.func.id in ["emit_event", "emit"]
        return False

    def _extract_event_name(self, node):
        """Extract event name from emit call."""
        if node.args and isinstance(node.args[0], ast.Constant):
            return node.args[0].value
        return None


def parse_docstring_params(func: Callable) -> Dict[str, Dict[str, Any]]:
    """
    Extract parameter descriptions from docstring.

    Supports multiple docstring formats:
    - Google style
    - NumPy style
    - Simple "name: description" format
    """
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


def build_discovery_response(
    events: Dict[str, Any],
    style: str = FORMAT_VERBOSE,
    include_stats: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a complete discovery response with consistent structure.

    Args:
        events: Filtered and formatted events
        style: Output format style
        include_stats: Include statistics
        metadata: Additional metadata to include

    Returns:
        Complete discovery response
    """
    response = {"events": events}

    if include_stats:
        response["total"] = len(events)

        # Extract namespaces
        namespaces = set()
        for event_name in events.keys():
            if ":" in event_name:
                namespaces.add(event_name.split(":")[0])
            else:
                namespaces.add("default")
        response["namespaces"] = sorted(namespaces)

    if metadata:
        response.update(metadata)

    # Add format metadata for ultra-compact
    if style == FORMAT_ULTRA_COMPACT:
        response["_legend"] = {
            "m": "module (without ksi_daemon prefix)",
            "h": "handler function",
            "s": "summary",
            "y": "sync flag (omitted=async)",
            "p": "parameters [[name, type?, required?, default?, desc?], ...]",
            "t": "triggers array",
        }

    return response
