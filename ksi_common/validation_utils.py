#!/usr/bin/env python3
"""
Validation Utilities - Common validation patterns for KSI system

Provides consistent patterns for:
- Data structure validation
- Type checking with helpful errors
- Schema validation
- Common validation rules
"""

from typing import Any, Dict, List, Optional, Union, Callable, Type
from pathlib import Path
import re

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("validation_utils")


class ValidationError(Exception):
    """Raised when validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


class Validator:
    """Chainable validator for complex validation rules."""
    
    def __init__(self, data: Any, field_name: str = "value"):
        self.data = data
        self.field_name = field_name
        self.errors: List[str] = []
    
    def required(self) -> "Validator":
        """Check that value is not None or empty."""
        if self.data is None:
            self.errors.append(f"{self.field_name} is required")
        elif isinstance(self.data, str) and not self.data.strip():
            self.errors.append(f"{self.field_name} cannot be empty")
        elif isinstance(self.data, (list, dict)) and not self.data:
            self.errors.append(f"{self.field_name} cannot be empty")
        return self
    
    def type(self, expected_type: Type) -> "Validator":
        """Check that value is of expected type."""
        if self.data is not None and not isinstance(self.data, expected_type):
            self.errors.append(
                f"{self.field_name} must be {expected_type.__name__}, "
                f"got {type(self.data).__name__}"
            )
        return self
    
    def min_length(self, length: int) -> "Validator":
        """Check minimum length for strings or collections."""
        if self.data is not None and hasattr(self.data, '__len__'):
            if len(self.data) < length:
                self.errors.append(f"{self.field_name} must have at least {length} items")
        return self
    
    def max_length(self, length: int) -> "Validator":
        """Check maximum length for strings or collections."""
        if self.data is not None and hasattr(self.data, '__len__'):
            if len(self.data) > length:
                self.errors.append(f"{self.field_name} must have at most {length} items")
        return self
    
    def pattern(self, regex: Union[str, re.Pattern], message: Optional[str] = None) -> "Validator":
        """Check that string matches regex pattern."""
        if self.data is not None and isinstance(self.data, str):
            pattern = re.compile(regex) if isinstance(regex, str) else regex
            if not pattern.match(self.data):
                msg = message or f"{self.field_name} format is invalid"
                self.errors.append(msg)
        return self
    
    def in_list(self, valid_values: List[Any]) -> "Validator":
        """Check that value is in list of valid values."""
        if self.data is not None and self.data not in valid_values:
            self.errors.append(
                f"{self.field_name} must be one of: {', '.join(str(v) for v in valid_values)}"
            )
        return self
    
    def custom(self, func: Callable[[Any], bool], message: str) -> "Validator":
        """Apply custom validation function."""
        if self.data is not None and not func(self.data):
            self.errors.append(message)
        return self
    
    def validate(self) -> None:
        """Raise ValidationError if any errors found."""
        if self.errors:
            raise ValidationError("; ".join(self.errors), field=self.field_name)
    
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """Get list of validation errors."""
        return self.errors.copy()


def validate_dict_structure(
    data: Dict[str, Any],
    required_fields: List[str],
    optional_fields: Optional[List[str]] = None,
    strict: bool = False
) -> Optional[str]:
    """
    Validate dictionary has required fields and optionally check for unknown fields.
    
    Args:
        data: Dictionary to validate
        required_fields: Fields that must be present
        optional_fields: Fields that may be present
        strict: If True, reject unknown fields
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(data, dict):
        return "Data must be a dictionary"
    
    # Check required fields
    missing = [field for field in required_fields if field not in data]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    
    # Check for unknown fields if strict
    if strict and optional_fields is not None:
        allowed = set(required_fields) | set(optional_fields)
        unknown = [field for field in data if field not in allowed]
        if unknown:
            return f"Unknown fields: {', '.join(unknown)}"
    
    return None


def validate_path(
    path: Union[str, Path],
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    writable: bool = False
) -> Optional[str]:
    """
    Validate a file system path.
    
    Args:
        path: Path to validate
        must_exist: Path must exist
        must_be_file: Path must be a file
        must_be_dir: Path must be a directory
        writable: Path or parent must be writable
        
    Returns:
        Error message if invalid, None if valid
    """
    try:
        path_obj = Path(path)
    except Exception as e:
        return f"Invalid path: {e}"
    
    if must_exist and not path_obj.exists():
        return f"Path does not exist: {path}"
    
    if path_obj.exists():
        if must_be_file and not path_obj.is_file():
            return f"Path is not a file: {path}"
        
        if must_be_dir and not path_obj.is_dir():
            return f"Path is not a directory: {path}"
    
    if writable:
        # Check if we can write to the path or its parent
        check_path = path_obj if path_obj.exists() else path_obj.parent
        if not check_path.exists():
            return f"Parent directory does not exist: {check_path}"
        
        # Simple write test
        try:
            test_file = check_path / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception:
            return f"Path is not writable: {check_path}"
    
    return None


def validate_identifier(
    identifier: str,
    allow_dash: bool = True,
    allow_underscore: bool = True,
    allow_dot: bool = False,
    min_length: int = 1,
    max_length: int = 255
) -> Optional[str]:
    """
    Validate an identifier (name, ID, etc).
    
    Args:
        identifier: String to validate
        allow_dash: Allow hyphens
        allow_underscore: Allow underscores
        allow_dot: Allow dots
        min_length: Minimum length
        max_length: Maximum length
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(identifier, str):
        return "Identifier must be a string"
    
    if len(identifier) < min_length:
        return f"Identifier too short (minimum {min_length} characters)"
    
    if len(identifier) > max_length:
        return f"Identifier too long (maximum {max_length} characters)"
    
    # Build allowed character pattern
    allowed = "a-zA-Z0-9"
    if allow_dash:
        allowed += "-"
    if allow_underscore:
        allowed += "_"
    if allow_dot:
        allowed += "."
    
    pattern = f"^[{allowed}]+$"
    
    if not re.match(pattern, identifier):
        return f"Identifier contains invalid characters (allowed: {allowed})"
    
    # Additional checks
    if identifier.startswith('-') or identifier.endswith('-'):
        return "Identifier cannot start or end with dash"
    
    if identifier.startswith('.') or identifier.endswith('.'):
        return "Identifier cannot start or end with dot"
    
    return None


def validate_config_value(
    key: str,
    value: Any,
    expected_type: Optional[Type] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    valid_values: Optional[List[Any]] = None
) -> Optional[str]:
    """
    Validate a configuration value.
    
    Args:
        key: Config key name (for error messages)
        value: Value to validate
        expected_type: Expected type
        validator: Custom validation function
        valid_values: List of valid values
        
    Returns:
        Error message if invalid, None if valid
    """
    # Type check
    if expected_type and not isinstance(value, expected_type):
        return f"{key} must be {expected_type.__name__}, got {type(value).__name__}"
    
    # Valid values check
    if valid_values is not None and value not in valid_values:
        return f"{key} must be one of: {', '.join(str(v) for v in valid_values)}"
    
    # Custom validation
    if validator and not validator(value):
        return f"{key} validation failed"
    
    return None


class SchemaValidator:
    """
    Validate data against a schema definition.
    
    Simple schema format:
    {
        "name": {"type": str, "required": True},
        "age": {"type": int, "min": 0, "max": 150},
        "email": {"type": str, "pattern": r"^[\w\.-]+@[\w\.-]+$"}
    }
    """
    
    def __init__(self, schema: Dict[str, Dict[str, Any]]):
        self.schema = schema
    
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate data against schema.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check required fields
        for field, rules in self.schema.items():
            if rules.get("required", False) and field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Validate present fields
        for field, value in data.items():
            if field not in self.schema:
                continue  # Skip unknown fields
            
            rules = self.schema[field]
            field_errors = self._validate_field(field, value, rules)
            errors.extend(field_errors)
        
        return errors
    
    def _validate_field(self, field: str, value: Any, rules: Dict[str, Any]) -> List[str]:
        """Validate a single field against its rules."""
        errors = []
        
        # Type check
        if "type" in rules and not isinstance(value, rules["type"]):
            errors.append(
                f"{field} must be {rules['type'].__name__}, "
                f"got {type(value).__name__}"
            )
            return errors  # Skip other checks if type is wrong
        
        # Numeric constraints
        if isinstance(value, (int, float)):
            if "min" in rules and value < rules["min"]:
                errors.append(f"{field} must be at least {rules['min']}")
            if "max" in rules and value > rules["max"]:
                errors.append(f"{field} must be at most {rules['max']}")
        
        # String constraints
        if isinstance(value, str):
            if "min_length" in rules and len(value) < rules["min_length"]:
                errors.append(f"{field} must be at least {rules['min_length']} characters")
            if "max_length" in rules and len(value) > rules["max_length"]:
                errors.append(f"{field} must be at most {rules['max_length']} characters")
            if "pattern" in rules and not re.match(rules["pattern"], value):
                errors.append(f"{field} format is invalid")
        
        # List constraints
        if isinstance(value, list):
            if "min_items" in rules and len(value) < rules["min_items"]:
                errors.append(f"{field} must have at least {rules['min_items']} items")
            if "max_items" in rules and len(value) > rules["max_items"]:
                errors.append(f"{field} must have at most {rules['max_items']} items")
        
        # Enum constraint
        if "enum" in rules and value not in rules["enum"]:
            errors.append(f"{field} must be one of: {', '.join(str(v) for v in rules['enum'])}")
        
        # Custom validator
        if "validator" in rules and not rules["validator"](value):
            errors.append(f"{field} validation failed")
        
        return errors