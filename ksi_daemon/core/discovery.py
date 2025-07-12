#!/usr/bin/env python3
"""
Event Discovery Module - Simplified Pure Event-Based Version

Provides essential discovery capabilities:
- List all events with parameters
- Show which events trigger other events
- Automatic extraction from implementation code
"""

import ast
import inspect
from typing import Any, Dict, TypedDict, Literal, Optional, Callable, List, get_type_hints, get_origin, get_args
from typing_extensions import NotRequired, Required, is_typeddict

from ksi_common.logging import get_bound_logger
from ksi_common.parameter_utils import (
    format_parameters, 
    generate_usage_example, 
    parse_validation_patterns,
    parse_docstring_params
)
from ksi_common.type_utils import format_type_annotation, extract_literal_values
from ksi_daemon.event_system import event_handler, get_router
from .discovery_utils import HandlerAnalyzer, extract_summary

logger = get_bound_logger("discovery", version="2.0.0")

# Cache for mined examples
_example_cache = {}

# Format style constants
FORMAT_VERBOSE = "verbose"
FORMAT_COMPACT = "compact" 
FORMAT_ULTRA_COMPACT = "ultra_compact"
FORMAT_MCP = "mcp"


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
            # Use real examples if available, otherwise generate
            if "examples" in handler_info and handler_info["examples"]:
                event_info["examples"] = handler_info["examples"]
            else:
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
    event_names: Optional[set] = None,
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


class EmitEventVisitor(ast.NodeVisitor):
    """AST visitor to extract emit_event calls with specific event."""
    
    def __init__(self, event_name: str):
        self.event_name = event_name
        self.examples = []
        
    def visit_Call(self, node):
        """Visit function calls looking for emit_event."""
        # Check if this is emit_event
        if (isinstance(node.func, ast.Attribute) and 
            node.func.attr in ['emit_event', 'emit'] or
            isinstance(node.func, ast.Name) and 
            node.func.id in ['emit_event', 'emit']):
            
            # Check if first arg is our event name
            if (node.args and 
                isinstance(node.args[0], ast.Constant) and
                node.args[0].value == self.event_name):
                
                # Extract data from second argument
                if len(node.args) > 1:
                    data = self._extract_data(node.args[1])
                    if data is not None:
                        self.examples.append(data)
                        
        self.generic_visit(node)
        
    def _extract_data(self, node):
        """Extract data dict from AST node."""
        if isinstance(node, ast.Dict):
            # Build dict from AST
            result = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant):
                    key_str = key.value
                elif isinstance(key, ast.Str):  # Python 3.7 compatibility
                    key_str = key.s
                else:
                    continue  # Skip non-string keys
                    
                value_obj = self._extract_value(value)
                if value_obj is not None:
                    result[key_str] = value_obj
                    
            return result
        return None
        
    def _extract_value(self, node):
        """Extract value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):  # Python 3.7
            return node.s
        elif isinstance(node, ast.Num):  # Python 3.7
            return node.n
        elif isinstance(node, ast.List):
            return [self._extract_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            return self._extract_data(node)
        elif isinstance(node, ast.Name):
            # Simple names like True/False/None
            if node.id in ('True', 'False', 'None'):
                return eval(node.id)
        # For complex expressions, return a placeholder
        return None


class ExampleMiner:
    """Mines real usage examples from codebase for event discovery."""
    
    def __init__(self, event_name: str):
        self.event_name = event_name
        self.examples = []
        
    def mine_examples(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Mine real usage examples from codebase."""
        # Check cache first
        if self.event_name in _example_cache:
            return _example_cache[self.event_name][:limit]
        
        # Search for emit_event calls
        self._search_emit_calls()
        
        # Search for test cases
        self._search_test_cases()
        
        # Search for example scripts
        self._search_example_scripts()
        
        # Cache results
        _example_cache[self.event_name] = self.examples
        
        # Return up to limit examples
        return self.examples[:limit]
    
    def _search_emit_calls(self):
        """Search for emit_event() calls with this event."""
        import subprocess
        import json
        
        try:
            # Use ripgrep to find emit_event calls
            patterns = [
                f'emit_event\\("{self.event_name}"',
                f"emit_event\\('{self.event_name}'",
                f'emit_event\\(\\s*"{self.event_name}"',
            ]
            
            for pattern in patterns:
                result = subprocess.run(
                    ['rg', '--json', '-U', pattern, '.'],
                    capture_output=True,
                    text=True,
                    cwd='/Users/dp/projects/ksi'
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if not line:
                            continue
                        try:
                            match = json.loads(line)
                            if match.get('type') == 'match':
                                self._extract_example_from_match(match)
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.debug(f"Error mining emit_event examples: {e}")
    
    def _extract_example_from_match(self, match: Dict[str, Any]):
        """Extract example from ripgrep match using AST."""
        try:
            file_path = match['data']['path']['text']
            
            # Skip non-Python files
            if not file_path.endswith('.py'):
                return
                
            # Read and parse the file
            with open(file_path, 'r') as f:
                content = f.read()
                
            try:
                tree = ast.parse(content)
                visitor = EmitEventVisitor(self.event_name)
                visitor.visit(tree)
                
                # Add found examples
                for example_data in visitor.examples:
                    example = {
                        'source': f"{file_path}",
                        'type': 'emit_event',
                        'data': example_data,
                        'description': f"From {file_path.split('/')[-1]}"
                    }
                    
                    # Avoid duplicates
                    if not any(e['data'] == example_data for e in self.examples):
                        self.examples.append(example)
                        
            except SyntaxError:
                # Skip files with syntax errors
                pass
                
        except Exception as e:
            logger.debug(f"Error extracting example: {e}")
    
    def _search_test_cases(self):
        """Search for test cases using this event."""
        # Look for test files that might contain examples
        test_patterns = ['test_*.py', '*_test.py', 'tests/*.py']
        # Implementation would search these patterns
        pass
    
    def _search_example_scripts(self):
        """Search example directory for usage."""
        # Look in examples/ directory
        pass


class UnifiedHandlerAnalyzer:
    """Unified analyzer that combines TypedDict and AST analysis."""
    
    def __init__(self, func: Callable, typed_dict_class=None, event_name: str = None):
        self.func = func
        self.typed_dict_class = typed_dict_class
        self.event_name = event_name
        self.parameters = {}
        self.triggers = []
        self.examples = []
        
    def analyze(self) -> Dict[str, Any]:
        """Perform unified analysis combining TypedDict and AST."""
        # Get TypedDict class if not provided
        if not self.typed_dict_class:
            self.typed_dict_class = self._find_typed_dict_class()
        
        # Step 1: Extract TypedDict field information if available
        if self.typed_dict_class:
            self._analyze_typed_dict()
        
        # Step 2: Analyze handler implementation for runtime behavior
        self._analyze_implementation()
        
        # Step 3: Enhance with docstring info
        self._enhance_from_docstring()
        
        # Step 4: Mine real usage examples
        if self.event_name:
            miner = ExampleMiner(self.event_name)
            self.examples = miner.mine_examples(limit=2)
        
        result = {
            "parameters": self.parameters,
            "triggers": self.triggers
        }
        
        # Add examples if found
        if self.examples:
            result["examples"] = self.examples
            
        return result
    
    def _find_typed_dict_class(self):
        """Find TypedDict parameter type from type hints."""
        try:
            func_globals = getattr(self.func, '__globals__', None)
            hints = get_type_hints(self.func, globalns=func_globals, include_extras=True)
            data_type = hints.get('data')
            if data_type and is_typeddict(data_type):
                return data_type
        except Exception:
            pass
        return None
    
    def _analyze_typed_dict(self):
        """Extract parameter info from TypedDict definition."""
        try:
            # Get module globals for resolving ForwardRefs
            td_module = inspect.getmodule(self.typed_dict_class)
            td_globals = td_module.__dict__ if td_module else None
            annotations = get_type_hints(self.typed_dict_class, globalns=td_globals, include_extras=True)
        except Exception:
            # Fallback to raw annotations
            annotations = {}
            for base in reversed(self.typed_dict_class.__mro__):
                if hasattr(base, '__annotations__'):
                    annotations.update(base.__annotations__)
        
        # Get required fields
        required_fields = getattr(self.typed_dict_class, '__required_keys__', set())
        
        # Extract each field
        for field_name, field_type in annotations.items():
            if field_name.startswith('_'):
                continue
            
            # Determine if required
            origin = get_origin(field_type)
            if origin is Required:
                is_required = True
                inner_type = get_args(field_type)[0] if get_args(field_type) else field_type
            elif origin is NotRequired:
                is_required = False
                inner_type = get_args(field_type)[0] if get_args(field_type) else field_type
            else:
                is_required = field_name in required_fields
                inner_type = field_type
            
            # Extract field description from inline comment
            description = self._extract_field_comment(field_name)
            
            # Extract allowed values from Literal types
            allowed_values = extract_literal_values(inner_type)
            
            self.parameters[field_name] = {
                'type': format_type_annotation(inner_type),
                'required': is_required,
                'description': description or f"{field_name} parameter",
            }
            
            if allowed_values:
                self.parameters[field_name]['allowed_values'] = allowed_values
                
            # Parse validation patterns from description comment
            if description:
                validation_info = parse_validation_patterns(description)
                self.parameters[field_name].update(validation_info)
    
    def _analyze_implementation(self):
        """Analyze handler implementation for runtime behavior."""
        try:
            # Get source info
            source_file = inspect.getsourcefile(self.func)
            file_lines = None
            func_start_line = 0
            
            if source_file:
                try:
                    with open(source_file, 'r') as f:
                        file_lines = f.readlines()
                    func_start_line = inspect.getsourcelines(self.func)[1] - 1
                except Exception:
                    pass
            
            # Parse function source
            source = inspect.getsource(self.func)
            source_lines = source.splitlines()
            tree = ast.parse(source)
            
            # Use AST analyzer to find data access patterns
            analyzer = HandlerAnalyzer(
                file_lines if file_lines else source_lines,
                None,
                func_start_line
            )
            analyzer.visit(tree)
            
            # Extract triggers
            self.triggers = analyzer.triggers
            
            # Also run validation analyzer
            from .discovery_utils import ValidationAnalyzer
            validator = ValidationAnalyzer()
            validator.visit(tree)
            
            # Merge runtime information with TypedDict data
            for param_name, access_info in analyzer.data_gets.items():
                if param_name in self.parameters:
                    # Enhance existing parameter
                    if 'default' not in self.parameters[param_name] and access_info.get('default') is not None:
                        self.parameters[param_name]['default'] = access_info['default']
                    if access_info.get('comment') and not self.parameters[param_name].get('description'):
                        self.parameters[param_name]['description'] = access_info['comment']
                    # Parse validation patterns from comment
                    if access_info.get('comment'):
                        validation_info = parse_validation_patterns(access_info['comment'])
                        self.parameters[param_name].update(validation_info)
                else:
                    # New parameter found only in implementation
                    self.parameters[param_name] = {
                        'type': 'Any',
                        'required': access_info['required'],
                        'description': access_info.get('comment', f"{param_name} parameter"),
                    }
                    if access_info.get('default') is not None:
                        self.parameters[param_name]['default'] = access_info['default']
                    # Parse validation patterns from comment
                    if access_info.get('comment'):
                        validation_info = parse_validation_patterns(access_info['comment'])
                        self.parameters[param_name].update(validation_info)
            
            # Add required parameters from data["key"] access
            for param_name in analyzer.data_subscripts:
                if param_name not in self.parameters:
                    self.parameters[param_name] = {
                        'type': 'Any',
                        'required': True,
                        'description': f"{param_name} parameter"
                    }
            
            # Merge code-based validations
            for param_name, constraints in validator.validations.items():
                if param_name in self.parameters:
                    param_type = self.parameters[param_name].get('type', '').lower()
                    
                    # Merge each constraint
                    for constraint in constraints:
                        for key, value in constraint.items():
                            # Don't override existing constraints from comments
                            if key not in self.parameters[param_name]:
                                self.parameters[param_name][key] = value
                    
                    # Clean up redundant constraints for list/string types
                    # If we have both value and length constraints, prefer length
                    if ('list' in param_type or 'str' in param_type):
                        if ('min_length' in self.parameters[param_name] or 
                            'max_length' in self.parameters[param_name] or
                            'exact_length' in self.parameters[param_name]):
                            # Remove value constraints as they're redundant
                            self.parameters[param_name].pop('min_value', None)
                            self.parameters[param_name].pop('max_value', None)
                            self.parameters[param_name].pop('exact_value', None)
                    
        except Exception as e:
            logger.debug(f"Implementation analysis failed: {e}")
    
    def _extract_field_comment(self, field_name: str) -> Optional[str]:
        """Extract inline comment for TypedDict field."""
        if not self.typed_dict_class:
            return None
            
        try:
            source = inspect.getsource(self.typed_dict_class)
            source_lines = source.splitlines()
            tree = ast.parse(source)
            
            # Find the ClassDef node
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == self.typed_dict_class.__name__:
                    # Look for field annotation
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            if stmt.target.id == field_name:
                                # Extract comment from same line
                                if stmt.lineno <= len(source_lines):
                                    line = source_lines[stmt.lineno - 1]
                                    comment_idx = line.find('#')
                                    if comment_idx > 0:
                                        comment = line[comment_idx + 1:].strip()
                                        if comment and not comment.startswith(('TODO', 'FIXME', 'NOTE:', 'noqa')):
                                            return comment
        except Exception:
            pass
        
        return None
    
    def _enhance_from_docstring(self):
        """Enhance parameters with docstring information."""
        doc_params = parse_docstring_params(self.func)
        for name, doc_info in doc_params.items():
            if name in self.parameters:
                # Don't override existing info, just supplement
                for key, value in doc_info.items():
                    if key not in self.parameters[name] or not self.parameters[name][key]:
                        self.parameters[name][key] = value
            else:
                # Add documented parameter not found in code
                self.parameters[name] = doc_info


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for discovery service
    pass


class SystemDiscoverData(TypedDict):
    """Universal discovery endpoint - everything you need to understand KSI."""
    detail: NotRequired[bool]  # Include parameters and triggers (default: False)
    namespace: NotRequired[str]  # Filter by namespace (optional)
    event: NotRequired[str]  # Get details for specific event (optional)
    module: NotRequired[str]  # Filter by module name (optional)
    format_style: NotRequired[Literal['verbose', 'compact', 'ultra_compact', 'mcp']]  # Output format (default: verbose)


class SystemHelpData(TypedDict):
    """Get detailed help for a specific event."""
    event: str  # The event name to get help for (required)
    format_style: NotRequired[Literal['verbose', 'compact', 'mcp']]  # Output format (default: verbose)


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:startup")
async def handle_startup(config: SystemStartupData) -> Dict[str, Any]:
    """Initialize discovery service."""
    logger.info("Discovery service started")
    return {"status": "discovery_ready"}


@event_handler("system:discover")
async def handle_discover(data: SystemDiscoverData) -> Dict[str, Any]:
    """
    Universal discovery endpoint - everything you need to understand KSI.

    Parameters:
        detail (bool): Include parameters and triggers (default: False)
        namespace (str): Filter by namespace (optional)
        event (str): Get details for specific event (optional)
        module (str): Filter by module name (optional)
        format_style (str): Output format - verbose, compact, ultra_compact, mcp (default: verbose)

    Returns:
        Dictionary with events, their parameters, and what they trigger
    """
    include_detail = data.get("detail", False)
    namespace_filter = data.get("namespace")
    event_filter = data.get("event")
    module_filter = data.get("module")
    format_style = data.get("format_style", FORMAT_VERBOSE)

    from ksi_daemon.event_system import get_router

    router = get_router()

    all_events = {}

    # Gather all events first
    for event_name, handlers in router._handlers.items():
        handler = handlers[0]  # Use first handler

        handler_info = {
            "module": handler.module,
            "handler": handler.name,
            "async": handler.is_async,
            "summary": extract_summary(handler.func),
        }

        if include_detail:
            # Use unified analysis that combines TypedDict and AST
            analyzer = UnifiedHandlerAnalyzer(handler.func, event_name=event_name)
            analysis_result = analyzer.analyze()
            handler_info.update(analysis_result)

        all_events[event_name] = handler_info

    # Apply filters
    filtered_events = filter_events(all_events, namespace=namespace_filter, module=module_filter, pattern=event_filter)

    # Format events based on style
    formatted_events = {}
    for event_name, handler_info in filtered_events.items():
        formatted_events[event_name] = format_event_info(
            event_name, handler_info, style=format_style, include_params=include_detail, include_triggers=include_detail
        )

    # Build response
    response = build_discovery_response(formatted_events, style=format_style)
    
    # If filtering by module, add module description
    if module_filter:
        module_info = router.inspect_module(module_filter)
        if module_info and "docstring" in module_info:
            response["module_description"] = module_info["docstring"].split("\n")[0].strip()
    
    return response


@event_handler("system:help")
async def handle_help(data: SystemHelpData) -> Dict[str, Any]:
    """
    Get detailed help for a specific event.

    Parameters:
        event (str): The event name to get help for (required)
        format_style (str): Output format - verbose, compact, mcp (default: verbose)
    """
    event_name = data.get("event")
    if not event_name:
        return {"error": "event parameter required"}

    format_style = data.get("format_style", FORMAT_VERBOSE)

    from ksi_daemon.event_system import get_router

    router = get_router()

    # Find the event handler directly
    if event_name not in router._handlers:
        return {"error": f"Event not found: {event_name}"}

    handler = router._handlers[event_name][0]

    # Analyze the handler using unified approach
    handler_info = {
        "module": handler.module,
        "handler": handler.name,
        "async": handler.is_async,
        "summary": extract_summary(handler.func),
    }
    
    # Use unified analysis that combines TypedDict and AST
    analyzer = UnifiedHandlerAnalyzer(handler.func, event_name=event_name)
    analysis_result = analyzer.analyze()
    handler_info.update(analysis_result)

    # Format based on style
    if format_style == FORMAT_MCP:
        # Return MCP-compatible format
        return format_event_info(
            event_name, handler_info, style=FORMAT_MCP, include_params=True, include_triggers=False
        )
    else:
        # Standard help format
        formatted_info = format_event_info(
            event_name,
            handler_info,
            style=format_style,
            include_params=True,
            include_triggers=True,
            include_examples=True,
        )

        # Add usage example
        formatted_info["usage"] = generate_usage_example(event_name, handler_info.get("parameters", {}))

        return formatted_info




@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean shutdown."""
    logger.info("Discovery service stopped")
