#!/usr/bin/env python3
"""
Foundation Protocol - Base infrastructure for all socket protocols

Provides core models and factories used across all daemon sockets.
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from ..timestamp_utils import TimestampManager


# ============================================================================
# BASE COMMAND INFRASTRUCTURE
# ============================================================================

class BaseCommand(BaseModel):
    """Base model for all commands across all sockets"""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    
    command: str
    version: Literal["2.0"] = Field(default="2.0")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('metadata')
    def validate_metadata(cls, v):
        if v is not None:
            allowed_keys = {'timestamp', 'client_id', 'request_id'}
            extra_keys = set(v.keys()) - allowed_keys
            if extra_keys:
                raise ValueError(f"Unknown metadata keys: {extra_keys}")
        return v


# ============================================================================
# BASE RESPONSE INFRASTRUCTURE
# ============================================================================

class BaseResponse(BaseModel):
    """Base model for all daemon responses"""
    model_config = ConfigDict(
        extra='forbid',
        # Allow model_dump() to convert Python types to JSON-compatible
        json_encoders={
            datetime: lambda v: v.isoformat() + 'Z'
        }
    )
    
    status: Literal["success", "error"] = Field(..., description="'success' or 'error'")
    command: str = Field(..., description="The command that was executed")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"timestamp": TimestampManager.timestamp_utc()}
    )
    
    @field_validator('metadata')
    def add_timestamp(cls, v):
        if v is None:
            v = {}
        if 'timestamp' not in v:
            v['timestamp'] = TimestampManager.timestamp_utc()
        return v


class SuccessResponse(BaseResponse):
    """Standard success response"""
    status: Literal["success"] = "success"
    result: Any = Field(..., description="Command-specific result data")


class ErrorInfo(BaseModel):
    """Error details"""
    code: str
    message: str
    timestamp: str = Field(default_factory=TimestampManager.timestamp_utc)
    details: Optional[Dict[str, Any]] = None
    
    @field_validator('timestamp', mode='before')
    def set_timestamp(cls, v):
        if v is None:
            return TimestampManager.timestamp_utc()
        return v


class ErrorResponse(BaseResponse):
    """Standard error response"""
    status: Literal["error"] = "error"
    error: ErrorInfo
    result: None = None  # Errors don't have results


# ============================================================================
# UNIFIED RESPONSE FACTORY
# ============================================================================

class SocketResponse:
    """Unified factory for creating type-safe responses across all sockets"""
    
    @staticmethod
    def success(command: str, result: Any = None, processing_time_ms: Optional[float] = None) -> Dict[str, Any]:
        """Create a success response"""
        metadata = {"timestamp": TimestampManager.timestamp_utc()}
        if processing_time_ms is not None:
            metadata['processing_time_ms'] = processing_time_ms
            
        response = SuccessResponse(
            command=command,
            result=result if result is not None else {},
            metadata=metadata
        )
        return response.model_dump()
    
    @staticmethod
    def error(command: str, error_code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an error response"""
        response = ErrorResponse(
            command=command,
            error=ErrorInfo(
                code=error_code,
                message=message,
                details=details
            )
        )
        return response.model_dump()
    
    @staticmethod
    def health_check(uptime: int = 0, managers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a HEALTH_CHECK response"""
        result = {
            "status": "healthy",
            "uptime": uptime,
            "managers": managers or {}
        }
        return SocketResponse.success("HEALTH_CHECK", result)
    
    @staticmethod
    def get_processes(processes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a GET_PROCESSES response"""
        result = {
            "processes": processes,
            "total": len(processes)
        }
        return SocketResponse.success("GET_PROCESSES", result)
    
    @staticmethod
    def get_agents(agents: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create a GET_AGENTS response"""
        return SocketResponse.success("GET_AGENTS", {"agents": agents})
    
    @staticmethod
    def get_agent_kv(key: str, value: Any, found: bool) -> Dict[str, Any]:
        """Create a GET_AGENT_KV response"""
        return SocketResponse.success("GET_AGENT_KV", {
            "key": key,
            "value": value,
            "found": found
        })
    
    @staticmethod
    def set_agent_kv(key: str) -> Dict[str, Any]:
        """Create a SET_AGENT_KV response"""
        return SocketResponse.success("SET_AGENT_KV", {
            "key": key,
            "status": "set"
        })
    
    @staticmethod
    def cleanup(cleanup_type: str, details: str) -> Dict[str, Any]:
        """Create a CLEANUP response"""
        return SocketResponse.success("CLEANUP", {
            "status": "cleaned",
            "cleanup_type": cleanup_type,
            "details": details
        })
    
    @staticmethod
    def list_items(command: str, items: List[Dict[str, Any]], total: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a list response for commands that return collections"""
        result = {
            "items": items,
            "total": total if total is not None else len(items)
        }
        if metadata:
            result["metadata"] = metadata
        return SocketResponse.success(command, result)


# ============================================================================
# COMMAND INFRASTRUCTURE
# ============================================================================

class CommandFactory:
    """Factory for creating and validating commands"""
    
    @staticmethod
    def create_command(command_name: str, parameters: Dict[str, Any], 
                      metadata: Optional[Dict[str, Any]] = None) -> BaseCommand:
        """Create a validated command instance"""
        # Import here to avoid circular dependencies
        from . import COMMAND_PARAMETER_MAP
        
        param_class = COMMAND_PARAMETER_MAP.get(command_name)
        if not param_class:
            # For commands without specific parameter models
            return BaseCommand(
                command=command_name,
                parameters=parameters,
                metadata=metadata
            )
        
        # Validate parameters
        validated_params = param_class(**parameters)
        
        return BaseCommand(
            command=command_name,
            parameters=validated_params.model_dump(),
            metadata=metadata
        )
    
    @staticmethod
    def parse_command(command_data: Union[str, Dict[str, Any]]) -> BaseCommand:
        """Parse and validate a command from JSON or dict"""
        if isinstance(command_data, str):
            import json
            command_data = json.loads(command_data)
        
        command_name = command_data.get('command')
        parameters = command_data.get('parameters', {})
        
        return CommandFactory.create_command(
            command_name,
            parameters,
            command_data.get('metadata')
        )