#!/usr/bin/env python3
"""
Type-based Discovery System for KSI Event Handlers

Analyzes TypedDict annotations to automatically discover event parameters,
their types, requirements, and relationships.
"""

import inspect
from typing import (
    Any, Dict, List, Optional, Union, get_type_hints, get_origin, get_args,
    TypedDict, Literal, Type, Callable, _GenericAlias
)
from typing_extensions import Required, NotRequired, is_typeddict
import re

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("type_discovery", version="1.0.0")


class ParameterInfo(TypedDict):
    """Information about a single parameter."""
    type: str
    required: bool
    description: Optional[str]
    default: NotRequired[Any]
    allowed_values: NotRequired[List[Any]]


class HandlerVariant(TypedDict):
    """A specific usage variant of a handler."""
    name: str
    description: str
    parameters: Dict[str, ParameterInfo]
    discriminator: Optional[Dict[str, Any]]  # Field values that select this variant


class HandlerMetadata(TypedDict):
    """Complete metadata for an event handler."""
    parameters: Dict[str, ParameterInfo]
    variants: NotRequired[List[HandlerVariant]]
    return_type: Optional[str]
    description: Optional[str]


class TypeAnalyzer:
    """Analyze TypedDict definitions for parameter discovery."""
    
    def __init__(self):
        self._type_cache = {}
    
    def analyze_handler(self, handler_func: Callable) -> Optional[HandlerMetadata]:
        """Extract parameter metadata from type annotations."""
        try:
            # Get type hints with string annotations resolved
            # Pass the function's module globals to resolve ForwardRef from __future__ annotations
            func_globals = getattr(handler_func, '__globals__', None)
            hints = get_type_hints(handler_func, globalns=func_globals, include_extras=True)
            
            # Find data parameter type
            data_type = hints.get('data')
            if not data_type:
                logger.debug(f"No 'data' parameter found in {handler_func.__name__}")
                return None
            
            # Extract description from docstring
            description = None
            if handler_func.__doc__:
                # Take first line of docstring
                description = handler_func.__doc__.strip().split('\n')[0]
            
            # Handle Union types (multiple variants)
            if get_origin(data_type) is Union:
                return self._analyze_union_type(data_type, description)
            
            # Handle single TypedDict
            if is_typeddict(data_type):
                params = self._analyze_typed_dict(data_type)
                return HandlerMetadata(
                    parameters=params,
                    description=description,
                    return_type=self._format_type(hints.get('return'))
                )
            
            # Fallback for Dict[str, Any]
            logger.debug(f"Handler {handler_func.__name__} uses untyped Dict")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to analyze handler {handler_func.__name__}: {e}")
            return None
    
    def _analyze_union_type(self, union_type: Type, description: Optional[str]) -> HandlerMetadata:
        """Analyze Union type to extract variants."""
        variants = []
        all_params = {}
        
        # Get all union members
        union_args = get_args(union_type)
        
        for variant_type in union_args:
            if is_typeddict(variant_type):
                variant_params = self._analyze_typed_dict(variant_type)
                variant_name = variant_type.__name__
                
                # Create variant info
                variant = HandlerVariant(
                    name=variant_name,
                    description=variant_type.__doc__ or "",
                    parameters=variant_params,
                    discriminator=self._find_discriminator(variant_type, union_args)
                )
                variants.append(variant)
                
                # Merge parameters (mark as optional if not in all variants)
                for param_name, param_info in variant_params.items():
                    if param_name in all_params:
                        # Parameter exists in multiple variants
                        if param_info['required'] != all_params[param_name]['required']:
                            all_params[param_name]['required'] = False
                    else:
                        all_params[param_name] = param_info.copy()
        
        # Mark parameters as optional if they don't appear in all variants
        param_names_by_variant = [set(v['parameters'].keys()) for v in variants]
        if param_names_by_variant:
            common_params = set.intersection(*param_names_by_variant)
            for param_name in all_params:
                if param_name not in common_params:
                    all_params[param_name]['required'] = False
        
        return HandlerMetadata(
            parameters=all_params,
            variants=variants,
            description=description,
            return_type=None
        )
    
    def _analyze_typed_dict(self, td_class: Type[TypedDict]) -> Dict[str, ParameterInfo]:
        """Extract parameters from TypedDict."""
        params = {}
        
        # Get type hints with resolved ForwardRefs
        try:
            # Get module globals from the TypedDict class
            td_module = inspect.getmodule(td_class)
            td_globals = td_module.__dict__ if td_module else None
            annotations = get_type_hints(td_class, globalns=td_globals, include_extras=True)
        except Exception:
            # Fallback to raw annotations if get_type_hints fails
            annotations = {}
            for base in reversed(td_class.__mro__):
                if hasattr(base, '__annotations__'):
                    annotations.update(base.__annotations__)
        
        # Get required fields
        required_fields = getattr(td_class, '__required_keys__', set())
        
        for field_name, field_type in annotations.items():
            if field_name.startswith('_'):  # Skip metadata fields
                continue
            
            # Determine if field is required
            is_required = self._is_required_field(field_type, field_name, required_fields)
            
            param_info = ParameterInfo(
                type=self._format_type(field_type),
                required=is_required,
                description=self._extract_field_description(td_class, field_name)
            )
            
            # Extract literal values
            literal_values = self._extract_literal_values(field_type)
            if literal_values:
                param_info['allowed_values'] = literal_values
            
            # Extract default value if available
            default = self._extract_default_value(field_type)
            if default is not None:
                param_info['default'] = default
                param_info['required'] = False  # Has default means optional
            
            params[field_name] = param_info
        
        return params
    
    def _is_required_field(self, field_type: Type, field_name: str, required_keys: set) -> bool:
        """Determine if a field is required."""
        # Check for Required/NotRequired wrappers
        origin = get_origin(field_type)
        if origin is Required:
            return True
        elif origin is NotRequired:
            return False
        
        # Check __required_keys__ (TypedDict total=False support)
        return field_name in required_keys
    
    def _format_type(self, type_hint: Optional[Type]) -> str:
        """Format a type hint as a readable string."""
        if type_hint is None:
            return "Any"
        
        # Handle None type
        if type_hint is type(None):
            return "None"
        
        # Get origin for generic types
        origin = get_origin(type_hint)
        
        # Handle Required/NotRequired
        if origin in (Required, NotRequired):
            args = get_args(type_hint)
            if args:
                return self._format_type(args[0])
        
        # Handle Union types
        if origin is Union:
            args = get_args(type_hint)
            # Special case for Optional[X] (Union[X, None])
            if len(args) == 2 and type(None) in args:
                other_type = args[0] if args[1] is type(None) else args[1]
                return f"Optional[{self._format_type(other_type)}]"
            else:
                formatted_args = [self._format_type(arg) for arg in args]
                return f"Union[{', '.join(formatted_args)}]"
        
        # Handle Literal types
        if origin is Literal:
            args = get_args(type_hint)
            return f"Literal[{', '.join(repr(arg) for arg in args)}]"
        
        # Handle generic types (List, Dict, etc)
        if origin:
            args = get_args(type_hint)
            if args:
                formatted_args = [self._format_type(arg) for arg in args]
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
    
    def _extract_literal_values(self, type_hint: Type) -> Optional[List[Any]]:
        """Extract allowed values from Literal type."""
        origin = get_origin(type_hint)
        
        # Check Required/NotRequired wrapper
        if origin in (Required, NotRequired):
            args = get_args(type_hint)
            if args:
                return self._extract_literal_values(args[0])
        
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
        
        return None
    
    def _extract_default_value(self, type_hint: Type) -> Optional[Any]:
        """Extract default value from type annotation if available."""
        # This would need to be enhanced to extract actual defaults
        # For now, we can infer some defaults from type
        origin = get_origin(type_hint)
        
        # NotRequired fields implicitly have None default
        if origin is NotRequired:
            return None
        
        return None
    
    def _extract_field_description(self, td_class: Type[TypedDict], field_name: str) -> Optional[str]:
        """Extract field description from class docstring or comments."""
        # Try to parse from class docstring
        if td_class.__doc__:
            # Look for "field_name: description" pattern
            pattern = rf'^\s*{field_name}\s*:\s*(.+)$'
            for line in td_class.__doc__.split('\n'):
                match = re.match(pattern, line)
                if match:
                    return match.group(1).strip()
        
        # Could be enhanced to read source comments
        return None
    
    def _find_discriminator(self, variant_type: Type[TypedDict], 
                          all_variants: List[Type]) -> Optional[Dict[str, Any]]:
        """Find fields that uniquely identify this variant."""
        # Look for Required Literal fields that differ between variants
        variant_annotations = self._get_all_annotations(variant_type)
        discriminators = {}
        
        for field_name, field_type in variant_annotations.items():
            # Check if this is a required literal
            origin = get_origin(field_type)
            if origin is Required:
                inner_type = get_args(field_type)[0]
                if get_origin(inner_type) is Literal:
                    literal_values = get_args(inner_type)
                    if len(literal_values) == 1:
                        # This is a discriminator candidate
                        discriminators[field_name] = literal_values[0]
        
        return discriminators if discriminators else None
    
    def _get_all_annotations(self, td_class: Type[TypedDict]) -> Dict[str, Type]:
        """Get all annotations including from parent classes."""
        annotations = {}
        for base in reversed(td_class.__mro__):
            if hasattr(base, '__annotations__'):
                annotations.update(base.__annotations__)
        return annotations


# Global analyzer instance
_type_analyzer = TypeAnalyzer()


def analyze_handler(handler_func: Callable) -> Optional[HandlerMetadata]:
    """Analyze a handler function to extract parameter metadata."""
    return _type_analyzer.analyze_handler(handler_func)


def format_parameters_for_discovery(metadata: HandlerMetadata) -> Dict[str, Any]:
    """Format handler metadata for discovery output."""
    result = {
        'parameters': metadata['parameters'],
        'description': metadata.get('description', '')
    }
    
    if 'variants' in metadata and metadata['variants']:
        result['variants'] = [
            {
                'name': v['name'],
                'description': v['description'],
                'parameters': v['parameters']
            }
            for v in metadata['variants']
        ]
    
    return result