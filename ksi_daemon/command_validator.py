#!/usr/bin/env python3
"""
Command Validator - Refactored with Pydantic models
Provides fast, comprehensive validation using Pydantic's built-in validation
"""

import json
from typing import Dict, Any, Tuple, Optional, Union
from pydantic import ValidationError
from .protocols import (
    BaseCommand, CommandFactory, SocketResponse,
    COMMAND_PARAMETER_MAP, SuccessResponse, ErrorResponse
)
from .manager_framework import with_error_handling
import structlog

logger = structlog.get_logger('daemon.validator')


class CommandValidator:
    """Validates daemon commands and responses using Pydantic models"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.command_factory = CommandFactory()
        self.response_factory = SocketResponse()
    
    @with_error_handling("validate_command")
    def validate_command(self, command_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a command using Pydantic models
        
        Args:
            command_data: Either JSON string or parsed dict
            
        Returns:
            Tuple of (is_valid, error_message, parsed_command)
        """
        try:
            # Parse JSON if needed
            if isinstance(command_data, str):
                try:
                    parsed_data = json.loads(command_data)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON: {e}", None
            else:
                parsed_data = command_data
            
            # Use Pydantic for validation
            command = self.command_factory.parse_command(parsed_data)
            
            # Additional semantic validation if needed
            semantic_error = self._validate_command_semantics(command)
            if semantic_error:
                return False, semantic_error, command.model_dump()
            
            return True, None, command.model_dump()
            
        except ValidationError as e:
            # Format Pydantic validation errors nicely
            errors = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error['loc'])
                errors.append(f"{field_path}: {error['msg']}")
            
            error_msg = "Validation failed: " + "; ".join(errors)
            return False, error_msg, parsed_data if 'parsed_data' in locals() else None
        
        except Exception as e:
            return False, f"Validation error: {e}", None
    
    def _validate_command_semantics(self, command: BaseCommand) -> Optional[str]:
        """Perform additional semantic validation beyond schema"""
        # All validation is now handled by Pydantic validators
        # This method is kept for future cross-field validation if needed
        return None
    
    def validate_response(self, response_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Validate a response using Pydantic models
        
        Args:
            response_data: Either JSON string or parsed dict
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse JSON if needed
            if isinstance(response_data, str):
                try:
                    parsed_data = json.loads(response_data)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON: {e}"
            else:
                parsed_data = response_data
            
            # Determine response type and validate
            if parsed_data.get('status') == 'success':
                response = SuccessResponse(**parsed_data)
            elif parsed_data.get('status') == 'error':
                response = ErrorResponse(**parsed_data)
            else:
                return False, "Response must have status of 'success' or 'error'"
            
            return True, None
            
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error['loc'])
                errors.append(f"{field_path}: {error['msg']}")
            
            error_msg = "Response validation failed: " + "; ".join(errors)
            return False, error_msg
        
        except Exception as e:
            return False, f"Response validation error: {e}"
    
    def create_command(self, command: str, parameters: Dict[str, Any] = None, 
                      metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a valid command object"""
        cmd = self.command_factory.create_command(command, parameters or {}, metadata)
        return cmd.model_dump()
    
    def create_response(self, command: str, status: str = "success", 
                       result: Any = None, error: Dict[str, str] = None,
                       processing_time_ms: float = None) -> Dict[str, Any]:
        """Create a valid response object"""
        if status == "success":
            response = self.response_factory.success(command, result, processing_time_ms)
        else:
            response = self.response_factory.error(
                command, 
                error.get('code', 'UNKNOWN_ERROR'),
                error.get('message', 'Unknown error')
            )
        
        return response.model_dump()
    
    def get_command_help(self, command: str) -> Optional[Dict[str, Any]]:
        """Get help for a command based on its Pydantic model"""
        param_class = COMMAND_PARAMETER_MAP.get(command)
        if not param_class:
            return None
        
        help_info = {
            "command": command,
            "parameters": {},
            "examples": []
        }
        
        # Extract parameter info from Pydantic model
        schema = param_class.model_json_schema()
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        for param_name, param_schema in properties.items():
            help_info["parameters"][param_name] = {
                "type": param_schema.get('type', 'unknown'),
                "description": param_schema.get('description', ''),
                "required": param_name in required,
                "default": param_schema.get('default'),
                "enum": param_schema.get('enum')
            }
        
        return help_info


# Global validator instance
validator = CommandValidator()

# Convenience functions for backward compatibility
def validate_command(command_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate a command - convenience function"""
    return validator.validate_command(command_data)

def validate_response(response_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """Validate a response - convenience function"""
    return validator.validate_response(response_data)

def create_command(command: str, **parameters) -> Dict[str, Any]:
    """Create a command - convenience function"""
    return validator.create_command(command, parameters)

def create_response(command: str, status: str = "success", **kwargs) -> Dict[str, Any]:
    """Create a response - convenience function"""
    return validator.create_response(command, status, **kwargs)