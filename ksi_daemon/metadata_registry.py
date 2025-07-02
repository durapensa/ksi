#!/usr/bin/env python3
"""
Metadata Registry for Event Handlers

Stores and exposes rich metadata about event handlers including:
- Parameter schemas from TypedDict definitions
- Performance characteristics  
- Documentation and best practices
- Usage examples
"""

import inspect
from typing import Dict, Any, Optional, List, Type, Callable, get_type_hints
from dataclasses import dataclass, field

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("metadata_registry", version="1.0.0")


@dataclass
class EventParameter:
    """Rich parameter definition for event handlers."""
    name: str
    type_name: str
    description: str
    required: bool = True
    default: Any = None
    allowed_values: Optional[List[Any]] = None
    example: Any = None
    constraints: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to discovery format."""
        result = {
            "type": self.type_name,
            "description": self.description,
            "required": self.required
        }
        if self.default is not None:
            result["default"] = self.default
        if self.allowed_values:
            result["allowed_values"] = self.allowed_values
        if self.example is not None:
            result["example"] = self.example
        if self.constraints:
            result["constraints"] = self.constraints
        return result


@dataclass
class EventExample:
    """Rich example definition for event handlers."""
    description: str
    data: Dict[str, Any]
    context: Optional[str] = None
    expected_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to discovery format."""
        result = {
            "description": self.description,
            "data": self.data
        }
        if self.context:
            result["context"] = self.context
        if self.expected_result:
            result["expected_result"] = self.expected_result
        return result


@dataclass
class EventMetadata:
    """Complete metadata for an event handler."""
    event_name: str
    function_name: str
    module_name: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[EventParameter] = field(default_factory=list)
    returns: Optional[str] = None
    examples: List[EventExample] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # Performance characteristics
    async_response: bool = False
    typical_duration_ms: Optional[int] = None
    has_side_effects: bool = True
    idempotent: bool = False
    
    # Resource requirements
    has_cost: bool = False
    requires_auth: bool = False
    rate_limited: bool = False
    
    # Documentation and best practices
    best_practices: List[str] = field(default_factory=list)
    common_errors: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
    
    # Technical metadata
    async_handler: bool = True


class MetadataRegistry:
    """Registry for event handler metadata."""
    
    def __init__(self):
        self._handlers: Dict[str, EventMetadata] = {}
        self._by_module: Dict[str, List[str]] = {}
    
    def register(self, event_name: str, metadata: EventMetadata):
        """Register event handler metadata."""
        self._handlers[event_name] = metadata
        
        # Track by module
        module_name = metadata.module_name
        if module_name not in self._by_module:
            self._by_module[module_name] = []
        if event_name not in self._by_module[module_name]:
            self._by_module[module_name].append(event_name)
            
        logger.debug(f"Registered metadata for {event_name}")
    
    def get(self, event_name: str) -> Optional[EventMetadata]:
        """Get metadata for an event."""
        return self._handlers.get(event_name)
    
    def get_by_module(self, module_name: str) -> List[EventMetadata]:
        """Get all event metadata for a module."""
        event_names = self._by_module.get(module_name, [])
        return [self._handlers[name] for name in event_names if name in self._handlers]
    
    def all_events(self) -> Dict[str, EventMetadata]:
        """Get all registered event metadata."""
        return self._handlers.copy()
    
    def get_api_schema(self) -> Dict[str, Any]:
        """Generate complete API schema from all registered handlers."""
        schema = {
            "events": {},
            "modules": {},
            "total_events": len(self._handlers)
        }
        
        for event_name, metadata in self._handlers.items():
            schema["events"][event_name] = {
                "summary": metadata.summary,
                "description": metadata.description,
                "parameters": [p.to_dict() for p in metadata.parameters],
                "returns": metadata.returns,
                "module": metadata.module_name,
                "tags": metadata.tags,
                "performance": {
                    "async_response": metadata.async_response,
                    "typical_duration_ms": metadata.typical_duration_ms,
                    "has_side_effects": metadata.has_side_effects,
                    "idempotent": metadata.idempotent
                },
                "requirements": {
                    "has_cost": metadata.has_cost,
                    "requires_auth": metadata.requires_auth,
                    "rate_limited": metadata.rate_limited
                },
                "documentation": {
                    "best_practices": metadata.best_practices,
                    "common_errors": metadata.common_errors,
                    "related_events": metadata.related_events
                },
                "examples": [ex.to_dict() for ex in metadata.examples]
            }
        
        # Group by module
        for module_name, event_names in self._by_module.items():
            schema["modules"][module_name] = {
                "events": event_names,
                "count": len(event_names)
            }
        
        return schema


def extract_parameter_info(func: Callable, data_type: Optional[Type] = None) -> List[EventParameter]:
    """
    Extract parameter information using hybrid introspection system.
    
    4 layers of discovery:
    1. AST analysis (automatic discovery from function body)
    2. TypedDict support (type-safe event handlers)
    3. Docstring parsing (human descriptions)
    4. Function signature analysis
    """
    # Start with comprehensive metadata extraction
    combined_params = {}
    
    # Layer 1: AST-based discovery (automatic)
    ast_params = _extract_ast_parameters(func)
    combined_params.update(ast_params)
    
    # Layer 2: TypedDict extraction (if provided)
    if data_type and hasattr(data_type, '__annotations__'):
        typed_params = _extract_typeddict_parameters(data_type)
        # Merge TypedDict params (higher priority than AST)
        for key, info in typed_params.items():
            if key in combined_params:
                combined_params[key].update(info)
            else:
                combined_params[key] = info
    
    # Layer 3: Docstring parsing (for descriptions)
    docstring_params = _parse_docstring_parameters(func)
    for key, info in docstring_params.items():
        if key in combined_params:
            # Merge: keep discovery info but add docstring details
            combined_params[key].update(info)
        else:
            # Parameter only in docstring
            combined_params[key] = info
    
    # Layer 4: Function signature analysis (fallback)
    if not combined_params:
        try:
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)
            
            for param_name, param in sig.parameters.items():
                if param_name in ('data', 'context'):
                    continue
                    
                type_hint = type_hints.get(param_name, param.annotation)
                type_str = str(type_hint).replace('typing.', '').replace('typing_extensions.', '')
                required = param.default == inspect.Parameter.empty
                
                combined_params[param_name] = {
                    'type_name': type_str,
                    'description': f"{param_name} parameter", 
                    'required': required,
                    'default': param.default if not required else None,
                    'discovered_by': 'signature'
                }
        except Exception as e:
            logger.debug(f"Could not extract parameters from {func.__name__}: {e}")
    
    # Convert to EventParameter objects
    parameters = []
    for name, info in combined_params.items():
        parameters.append(EventParameter(
            name=name,
            type_name=info.get('type_name', 'Any'),
            description=info.get('description', f"{name} parameter"),
            required=info.get('required', True),
            default=info.get('default'),
            allowed_values=info.get('allowed_values'),
            example=info.get('example'),
            constraints=info.get('constraints')
        ))
    
    return parameters


def _extract_ast_parameters(func: Callable) -> Dict[str, Dict[str, Any]]:
    """Extract parameters using AST analysis of function body."""
    import ast
    
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)
        
        parameters = {}
        
        class DataAccessVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                # Look for data.get() calls
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == 'get' and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'data'):
                    
                    if node.args and isinstance(node.args[0], ast.Constant):
                        key = node.args[0].value
                        default = None
                        required = True
                        
                        if len(node.args) > 1:
                            required = False
                            if isinstance(node.args[1], ast.Constant):
                                default = node.args[1].value
                        
                        parameters[key] = {
                            'required': required,
                            'default': default,
                            'discovered_by': 'ast',
                            'type_name': 'Any',
                            'description': f"{key} parameter"
                        }
                
                self.generic_visit(node)
            
            def visit_Subscript(self, node):
                # Look for direct dict access: data["key"]
                if (isinstance(node.value, ast.Name) and
                    node.value.id == 'data' and
                    isinstance(node.slice, ast.Constant)):
                    
                    key = node.slice.value
                    if key not in parameters:
                        parameters[key] = {
                            'required': True,
                            'discovered_by': 'ast',
                            'type_name': 'Any',
                            'description': f"{key} parameter"
                        }
                
                self.generic_visit(node)
        
        visitor = DataAccessVisitor()
        visitor.visit(tree)
        
        return parameters
        
    except Exception as e:
        logger.debug(f"AST extraction failed for {func.__name__}: {e}")
        return {}


def _extract_typeddict_parameters(data_type: Type) -> Dict[str, Dict[str, Any]]:
    """Extract parameters from TypedDict annotations."""
    try:
        # Get type hints including special forms
        hints = get_type_hints(data_type, include_extras=True)
        
        # Get required/optional keys
        required_keys = getattr(data_type, '__required_keys__', set())
        
        parameters = {}
        for key, type_hint in hints.items():
            # Extract type information
            type_str = _get_type_string(type_hint)
            is_required = key in required_keys
            
            parameters[key] = {
                'type_name': type_str,
                'required': is_required,
                'discovered_by': 'typeddict',
                'description': f"{key} parameter"
            }
        
        return parameters
        
    except Exception as e:
        logger.debug(f"TypedDict extraction failed: {e}")
        return {}


def _parse_docstring_parameters(func: Callable) -> Dict[str, Dict[str, Any]]:
    """Parse parameter documentation from docstring."""
    import re
    
    docstring = inspect.getdoc(func) or ""
    if not docstring:
        return {}
    
    params = {}
    lines = docstring.split('\n')
    
    # Regex patterns for parameter documentation
    param_section_pattern = re.compile(r'^\s*(Args|Arguments|Parameters|Params):\s*$', re.IGNORECASE)
    param_pattern = re.compile(r'^\s*(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)$')
    section_end_pattern = re.compile(r'^\s*(Returns?|Raises?|Example|Examples|Note|Notes):\s*$', re.IGNORECASE)
    
    in_params_section = False
    current_param = None
    
    for line in lines:
        # Check for parameter section start
        if param_section_pattern.match(line):
            in_params_section = True
            continue
        
        # Check for section end
        if section_end_pattern.match(line):
            in_params_section = False
            current_param = None
            continue
        
        if in_params_section:
            # Try to match parameter line
            param_match = param_pattern.match(line)
            if param_match:
                param_name = param_match.group(1)
                param_type = param_match.group(2)
                param_desc = param_match.group(3).strip()
                
                param_info = {
                    "description": param_desc,
                    "required": "optional" not in param_desc.lower(),
                    "discovered_by": "docstring",
                    "type_name": param_type or "Any"
                }
                
                # Check for default value in description
                default_match = re.search(r'default[s]?\s*[:=]\s*([^\s,)]+)', param_desc, re.IGNORECASE)
                if default_match:
                    param_info["default"] = default_match.group(1).strip("\"'")
                    param_info["required"] = False
                
                # Check for allowed values
                allowed_match = re.search(r'(?:one of|allowed|valid values?)[:=]\s*\[([^\]]+)\]', param_desc, re.IGNORECASE)
                if allowed_match:
                    values = [v.strip().strip("\"'") for v in allowed_match.group(1).split(',')]
                    param_info["allowed_values"] = values
                
                params[param_name] = param_info
                current_param = param_name
            
            # Handle continuation lines for current parameter
            elif current_param and line.strip():
                # This is a continuation of the previous parameter's description
                params[current_param]["description"] += " " + line.strip()
    
    return params


def _get_type_string(type_hint: Any) -> str:
    """Convert type hint to readable string."""
    from typing import Union, get_origin, get_args
    
    if hasattr(type_hint, '__name__'):
        return type_hint.__name__
    
    # Handle Union types
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        # Check if it's Optional (Union with None)
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return f"Optional[{_get_type_string(non_none_args[0])}]"
        return f"Union[{', '.join(_get_type_string(arg) for arg in args)}]"
    
    # Handle generic types
    if origin:
        args = get_args(type_hint)
        if args:
            return f"{origin.__name__}[{', '.join(_get_type_string(arg) for arg in args)}]"
        return origin.__name__
    
    # Default to string representation
    return str(type_hint)


# Global registry
_global_registry: Optional[MetadataRegistry] = None


def get_registry() -> MetadataRegistry:
    """Get the global metadata registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = MetadataRegistry()
    return _global_registry