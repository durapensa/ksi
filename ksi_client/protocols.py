#!/usr/bin/env python3
"""
KSI Client Protocol Models

Minimal protocol models needed by the client library.
These are extracted from the main daemon protocols to keep the client
lightweight and independent.
"""

from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# CLIENT-SIDE PROTOCOL MODELS
# ============================================================================

class CompletionParameters(BaseModel):
    """Parameters for COMPLETION command - client-side validation"""
    prompt: str = Field(..., description="The prompt to send to the LLM")
    model: str = Field(default="sonnet", description="Claude model to use")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    agent_id: Optional[str] = Field(None, description="Agent ID if routing through an agent")
    client_id: str = Field(..., description="Client ID for callback routing (required)")
    timeout: int = Field(default=300, description="Timeout in seconds (max 10 minutes)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @field_validator('client_id')
    def validate_client_id(cls, v):
        if not v:
            raise ValueError("client_id is required for async completion callbacks")
        return v
    
    @field_validator('timeout')
    def validate_timeout(cls, v):
        if v < 1 or v > 600:  # 10 minutes max
            raise ValueError("Timeout must be between 1 and 600 seconds")
        return v


class CompletionAcknowledgment(BaseModel):
    """Response to COMPLETION command submission"""
    request_id: str = Field(..., description="Unique request identifier")
    status: Literal["queued"] = Field(default="queued", description="Request status")
    estimated_time: Optional[int] = Field(None, description="Estimated completion time in seconds")


# ============================================================================
# RESPONSE UTILITIES (client-side)
# ============================================================================

class ClientResponse:
    """Client-side response handling utilities"""
    
    @staticmethod
    def is_success(response: Dict[str, Any]) -> bool:
        """Check if response indicates success"""
        return response.get("status") == "success"
    
    @staticmethod
    def is_error(response: Dict[str, Any]) -> bool:
        """Check if response indicates error"""
        return response.get("status") == "error"
    
    @staticmethod
    def get_result(response: Dict[str, Any]) -> Any:
        """Extract result data from successful response"""
        if ClientResponse.is_success(response):
            return response.get("result", {})
        return None
    
    @staticmethod
    def get_error_message(response: Dict[str, Any]) -> str:
        """Extract error message from error response"""
        if ClientResponse.is_error(response):
            error_info = response.get("error", {})
            return error_info.get("message", "Unknown error")
        return ""
    
    @staticmethod
    def get_error_code(response: Dict[str, Any]) -> str:
        """Extract error code from error response"""
        if ClientResponse.is_error(response):
            error_info = response.get("error", {})
            return error_info.get("code", "UNKNOWN_ERROR")
        return ""