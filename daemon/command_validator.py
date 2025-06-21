#!/usr/bin/env python3
"""
Command Validator - JSON Schema validation for daemon commands

Provides fast, comprehensive validation for the JSON protocol v2.0
with helpful error messages and performance optimizations.
"""

import json
import logging
from typing import Dict, Any, Tuple, Optional, Union
from datetime import datetime
from .command_schemas import (
    COMMAND_SCHEMA, 
    RESPONSE_SCHEMA,
    COMMAND_MAPPINGS,
    get_schema_for_command,
    get_command_type,
    CommandType
)

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
    SCHEMA_VALIDATION_AVAILABLE = True
except ImportError:
    SCHEMA_VALIDATION_AVAILABLE = False
    # Provide fallback for type annotations
    class ValidationError(Exception):
        pass
    Draft7Validator = None

logger = logging.getLogger('daemon.validator')

class CommandValidationError(Exception):
    """Raised when command validation fails"""
    def __init__(self, message: str, details: str = "", error_code: str = "VALIDATION_ERROR"):
        self.message = message
        self.details = details
        self.error_code = error_code
        super().__init__(message)

class CommandValidator:
    """Validates daemon commands and responses against JSON schemas"""
    
    def __init__(self):
        self.enabled = SCHEMA_VALIDATION_AVAILABLE
        self._compiled_validators = {}
        
        if not self.enabled:
            logger.warning("jsonschema not available - validation disabled")
            return
            
        # Pre-compile validators for performance
        try:
            self._main_validator = Draft7Validator(COMMAND_SCHEMA)
            self._response_validator = Draft7Validator(RESPONSE_SCHEMA)
            
            # Compile individual command type validators
            from .command_schemas import SCHEMA_MAPPINGS
            for command_type, schema in SCHEMA_MAPPINGS.items():
                self._compiled_validators[command_type] = Draft7Validator(schema)
                
            logger.info("Command validator initialized with pre-compiled schemas")
        except Exception as e:
            logger.error(f"Failed to initialize validator: {e}")
            self.enabled = False

    def validate_command(self, command_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a command against the JSON schema
        
        Args:
            command_data: Either JSON string or parsed dict
            
        Returns:
            Tuple of (is_valid, error_message, parsed_command)
        """
        if not self.enabled:
            # Basic validation when jsonschema not available
            try:
                if isinstance(command_data, str):
                    parsed = json.loads(command_data)
                else:
                    parsed = command_data
                    
                if not isinstance(parsed, dict):
                    return False, "Command must be a JSON object", None
                    
                if "command" not in parsed:
                    return False, "Missing required field: command", None
                    
                if "version" not in parsed:
                    return False, "Missing required field: version", None
                    
                return True, None, parsed
                
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}", None
        
        try:
            # Parse JSON if needed
            if isinstance(command_data, str):
                try:
                    parsed_command = json.loads(command_data)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON: {e}", None
            else:
                parsed_command = command_data
            
            # Validate against main schema
            self._main_validator.validate(parsed_command)
            
            # Additional semantic validation
            command_name = parsed_command.get("command")
            if command_name:
                semantic_error = self._validate_command_semantics(parsed_command)
                if semantic_error:
                    return False, semantic_error, parsed_command
            
            return True, None, parsed_command
            
        except ValidationError as e:
            error_msg = self._format_validation_error(e)
            return False, error_msg, parsed_command if 'parsed_command' in locals() else None
        except Exception as e:
            return False, f"Validation error: {e}", None

    def validate_response(self, response_data: Union[str, Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Validate a response against the response schema
        
        Args:
            response_data: Either JSON string or parsed dict
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.enabled:
            return True, None
            
        try:
            # Parse JSON if needed
            if isinstance(response_data, str):
                try:
                    parsed_response = json.loads(response_data)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON: {e}"
            else:
                parsed_response = response_data
            
            # Validate against response schema
            self._response_validator.validate(parsed_response)
            return True, None
            
        except ValidationError as e:
            error_msg = self._format_validation_error(e)
            return False, error_msg
        except Exception as e:
            return False, f"Response validation error: {e}"

    def _validate_command_semantics(self, command: Dict[str, Any]) -> Optional[str]:
        """Perform additional semantic validation beyond schema"""
        command_name = command.get("command")
        parameters = command.get("parameters", {})
        
        # Command-specific semantic validation
        if command_name == "SPAWN":
            # Validate SPAWN-specific logic
            if parameters.get("mode") == "async" and not parameters.get("agent_id"):
                logger.warning("Async SPAWN without agent_id may be hard to track")
                
        elif command_name == "AGENT_CONNECTION":
            # Validate agent connection logic
            action = parameters.get("action")
            if action not in ["connect", "disconnect"]:
                return f"Invalid agent connection action: {action}"
                
        elif command_name == "SUBSCRIBE":
            # Validate event types
            event_types = parameters.get("event_types", [])
            if not event_types:
                return "SUBSCRIBE requires at least one event type"
                
        elif command_name == "PUBLISH":
            # Validate publish payload
            payload = parameters.get("payload")
            if payload is not None and not isinstance(payload, dict):
                return "PUBLISH payload must be a JSON object"
        
        return None

    def _format_validation_error(self, error: ValidationError) -> str:
        """Format validation error into human-readable message"""
        path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        
        # Common error patterns with helpful messages
        if "is a required property" in error.message:
            missing_field = error.message.split("'")[1]
            return f"Missing required field '{missing_field}' in {path}"
            
        elif "is not of type" in error.message:
            return f"Invalid type for field '{path}': {error.message}"
            
        elif "is not one of" in error.message:
            return f"Invalid value for field '{path}': {error.message}"
            
        else:
            return f"Validation error in {path}: {error.message}"

    def create_command(self, command: str, parameters: Dict[str, Any] = None, 
                      metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a valid command object
        
        Args:
            command: Command name
            parameters: Command parameters
            metadata: Optional metadata
            
        Returns:
            Valid command dict
        """
        cmd_obj = {
            "command": command,
            "version": "2.0",
            "parameters": parameters or {}
        }
        
        if metadata:
            cmd_obj["metadata"] = metadata
            
        return cmd_obj

    def create_response(self, command: str, status: str = "success", 
                       result: Any = None, error: Dict[str, str] = None,
                       processing_time_ms: float = None) -> Dict[str, Any]:
        """
        Create a valid response object
        
        Args:
            command: Original command name
            status: "success" or "error"
            result: Result data (for success)
            error: Error information (for errors)
            processing_time_ms: Processing time in milliseconds
            
        Returns:
            Valid response dict
        """
        response = {
            "status": status,
            "command": command,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        if status == "success":
            response["result"] = result
        elif status == "error" and error:
            response["error"] = error
            
        if processing_time_ms is not None:
            response["metadata"]["processing_time_ms"] = processing_time_ms
            
        return response

    def get_command_help(self, command: str) -> Optional[Dict[str, Any]]:
        """Get schema-based help for a command"""
        if command not in COMMAND_MAPPINGS:
            return None
            
        try:
            schema = get_schema_for_command(command)
            command_type = get_command_type(command)
            
            # Extract parameter info from schema
            help_info = {
                "command": command,
                "type": command_type.value,
                "parameters": {},
                "examples": []
            }
            
            # Find the specific command schema within the group
            if "oneOf" in schema["allOf"][1]:
                for cmd_schema in schema["allOf"][1]["oneOf"]:
                    if cmd_schema["properties"]["command"]["const"] == command:
                        params = cmd_schema["properties"]["parameters"]["properties"]
                        required = cmd_schema["properties"]["parameters"].get("required", [])
                        
                        for param_name, param_schema in params.items():
                            help_info["parameters"][param_name] = {
                                "type": param_schema.get("type", "unknown"),
                                "description": param_schema.get("description", ""),
                                "required": param_name in required,
                                "default": param_schema.get("default")
                            }
                        break
            
            return help_info
            
        except Exception as e:
            logger.error(f"Error getting help for {command}: {e}")
            return None

# Global validator instance
validator = CommandValidator()

# Convenience functions
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