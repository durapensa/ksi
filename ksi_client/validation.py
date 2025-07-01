#!/usr/bin/env python3
"""
KSI Client Parameter Validation

Validates event parameters against discovered schemas.
"""

import re
from typing import Dict, Any, List, Union
import structlog

from .exceptions import KSIValidationError

logger = structlog.get_logger("ksi.client.validation")


class ParameterValidator:
    """Validates parameters against discovered event schemas."""
    
    @staticmethod
    def validate_params(event_name: str, params: Dict[str, Any], 
                       schema: Dict[str, Dict[str, Any]]) -> None:
        """
        Validate parameters against schema.
        
        Args:
            event_name: Name of the event
            params: Parameters to validate
            schema: Parameter schema from discovery
            
        Raises:
            KSIValidationError: If validation fails
        """
        errors = []
        
        # Check required parameters
        for param_name, param_info in schema.items():
            if param_info.get("required", False) and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
        
        # Validate each provided parameter
        for param_name, value in params.items():
            if param_name not in schema:
                # Unknown parameter - log warning but don't fail
                logger.warning(f"Unknown parameter '{param_name}' for event {event_name}")
                continue
            
            param_info = schema[param_name]
            
            # Type validation
            expected_type = param_info.get("type", "Any")
            if expected_type != "Any" and not ParameterValidator._check_type(value, expected_type):
                errors.append(
                    f"Parameter '{param_name}' expected {expected_type}, "
                    f"got {type(value).__name__}"
                )
            
            # Additional validations
            ParameterValidator._validate_constraints(param_name, value, param_info, errors)
        
        # Raise error if any validation failed
        if errors:
            raise KSIValidationError(f"Validation failed for {event_name}: {'; '.join(errors)}")
    
    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "str": str,
            "int": int,
            "float": (int, float),  # int is acceptable for float
            "bool": bool,
            "list": list,
            "dict": dict,
            "Any": object,  # Always matches
        }
        
        # Handle Union types (simplified)
        if "Union" in expected_type or "|" in expected_type:
            return True  # Skip complex type checking for now
        
        expected_python_type = type_map.get(expected_type.lower(), object)
        return isinstance(value, expected_python_type)
    
    @staticmethod
    def _validate_constraints(param_name: str, value: Any, 
                            param_info: Dict[str, Any], errors: List[str]) -> None:
        """Validate additional constraints on parameter."""
        
        # String constraints
        if isinstance(value, str):
            # Min length
            min_length = param_info.get("min_length")
            if min_length is not None and len(value) < min_length:
                errors.append(f"Parameter '{param_name}' too short (min: {min_length})")
            
            # Max length
            max_length = param_info.get("max_length")
            if max_length is not None and len(value) > max_length:
                errors.append(f"Parameter '{param_name}' too long (max: {max_length})")
            
            # Pattern matching
            pattern = param_info.get("pattern")
            if pattern and not re.match(pattern, value):
                errors.append(f"Parameter '{param_name}' doesn't match pattern: {pattern}")
            
            # Allowed values
            allowed_values = param_info.get("allowed_values")
            if allowed_values and value not in allowed_values:
                errors.append(
                    f"Parameter '{param_name}' must be one of: {', '.join(allowed_values)}"
                )
        
        # Numeric constraints
        elif isinstance(value, (int, float)):
            # Min value
            min_val = param_info.get("min")
            if min_val is not None and value < min_val:
                errors.append(f"Parameter '{param_name}' too small (min: {min_val})")
            
            # Max value
            max_val = param_info.get("max")
            if max_val is not None and value > max_val:
                errors.append(f"Parameter '{param_name}' too large (max: {max_val})")
        
        # List constraints
        elif isinstance(value, list):
            # Min items
            min_items = param_info.get("min_items")
            if min_items is not None and len(value) < min_items:
                errors.append(f"Parameter '{param_name}' needs at least {min_items} items")
            
            # Max items
            max_items = param_info.get("max_items")
            if max_items is not None and len(value) > max_items:
                errors.append(f"Parameter '{param_name}' has too many items (max: {max_items})")


def validate_event_params(event_name: str, params: Dict[str, Any], 
                         event_info: Dict[str, Any]) -> None:
    """
    Validate parameters for an event.
    
    Args:
        event_name: Name of the event
        params: Parameters to validate
        event_info: Event information from discovery
        
    Raises:
        KSIValidationError: If validation fails
    """
    schema = event_info.get("parameters", {})
    ParameterValidator.validate_params(event_name, params, schema)