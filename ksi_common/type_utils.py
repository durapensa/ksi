#!/usr/bin/env python3
"""
Type Utilities for KSI

Shared utilities for type conversion, formatting, and analysis.
Used across discovery, MCP integration, API documentation, and type validation.
"""

from typing import Any, Type, get_origin, get_args


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


def format_type_annotation(type_hint: Any) -> str:
    """Format type annotation as readable string."""
    if type_hint is None:
        return "Any"
    
    # Handle None type
    if type_hint is type(None):
        return "None"
    
    # Get origin for generic types
    origin = get_origin(type_hint)
    
    # Handle Literal types
    from typing import Literal
    if origin is Literal:
        args = get_args(type_hint)
        return f"Literal[{', '.join(repr(arg) for arg in args)}]"
    
    # Handle generic types (List, Dict, etc)
    if origin:
        args = get_args(type_hint)
        if args:
            formatted_args = [format_type_annotation(arg) for arg in args]
            return f"{origin.__name__}[{', '.join(formatted_args)}]"
        return origin.__name__
    
    # Handle ForwardRef objects (from __future__ annotations)
    if hasattr(type_hint, '__forward_arg__'):
        # This is a ForwardRef that wasn't resolved
        return str(type_hint.__forward_arg__)
    
    # Handle regular types
    if hasattr(type_hint, '__name__'):
        return type_hint.__name__
    
    # Fallback - clean up the string representation
    type_str = str(type_hint)
    # Remove ForwardRef wrapper if present
    if type_str.startswith("ForwardRef("):
        import re
        match = re.match(r"ForwardRef\('([^']+)'", type_str)
        if match:
            return match.group(1)
    
    return type_str


def extract_literal_values(type_hint: Type) -> list:
    """Extract allowed values from Literal type annotation."""
    from typing import Literal, Union
    from typing_extensions import Required, NotRequired
    
    origin = get_origin(type_hint)
    
    # Check Required/NotRequired wrapper
    if origin in (Required, NotRequired):
        args = get_args(type_hint)
        if args:
            return extract_literal_values(args[0])
    
    # Check for Literal
    if origin is Literal:
        return list(get_args(type_hint))
    
    # Check Union for Literal members
    if origin is Union:
        all_literals = []
        for arg in get_args(type_hint):
            if get_origin(arg) is Literal:
                all_literals.extend(get_args(arg))
        if all_literals:
            return all_literals
    
    return []


def is_required_field(field_type: Type, field_name: str, required_keys: set) -> bool:
    """Determine if a TypedDict field is required."""
    from typing_extensions import Required, NotRequired
    
    # Check for Required/NotRequired wrappers
    origin = get_origin(field_type)
    if origin is Required:
        return True
    elif origin is NotRequired:
        return False
    
    # Check __required_keys__ (TypedDict total=False support)
    return field_name in required_keys


def unwrap_required_type(field_type: Type) -> Type:
    """Unwrap Required/NotRequired wrapper to get inner type."""
    from typing_extensions import Required, NotRequired
    
    origin = get_origin(field_type)
    if origin in (Required, NotRequired):
        args = get_args(field_type)
        return args[0] if args else field_type
    return field_type


def resolve_type_hints_safely(obj: Any, globalns: dict = None) -> dict:
    """
    Safely resolve type hints, falling back to raw annotations if needed.
    
    This handles common issues with ForwardRef resolution in TypedDict classes.
    """
    from typing import get_type_hints
    
    try:
        return get_type_hints(obj, globalns=globalns, include_extras=True)
    except Exception:
        # Fallback to raw annotations
        annotations = {}
        for base in reversed(obj.__mro__ if hasattr(obj, '__mro__') else [obj]):
            if hasattr(base, '__annotations__'):
                annotations.update(base.__annotations__)
        return annotations


def is_optional_type(type_hint: Type) -> bool:
    """Check if a type annotation represents an optional value (Union with None)."""
    from typing import Union
    
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        return type(None) in args
    return False


def get_non_none_type(type_hint: Type) -> Type:
    """Extract the non-None type from Optional[T] or Union[T, None]."""
    from typing import Union
    
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        non_none_types = [arg for arg in args if arg is not type(None)]
        if len(non_none_types) == 1:
            return non_none_types[0]
        elif len(non_none_types) > 1:
            # Still a union, just without None
            return Union[tuple(non_none_types)]
    
    return type_hint


def normalize_type_string(type_str: str) -> str:
    """Normalize type string for consistent display."""
    # Common normalizations
    normalizations = {
        "typing.List": "list",
        "typing.Dict": "dict", 
        "typing.Union": "Union",
        "typing.Optional": "Optional",
        "typing.Any": "Any",
        "builtins.str": "str",
        "builtins.int": "int",
        "builtins.float": "float",
        "builtins.bool": "bool",
    }
    
    for old, new in normalizations.items():
        type_str = type_str.replace(old, new)
    
    return type_str