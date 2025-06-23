#!/usr/bin/env python3
"""
Completion Protocol - Parameters for completion socket operations

Handles LLM completion requests with async processing.
All completions are queued and results delivered via messaging.sock.
Commands: COMPLETION
"""

from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator
import uuid


# ============================================================================
# COMPLETION REQUEST
# ============================================================================

class CompletionParameters(BaseModel):
    """Parameters for COMPLETION command - all completions are async"""
    prompt: str = Field(..., description="The prompt to send to the LLM")
    model: str = Field(default="sonnet", description="Claude model to use")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    agent_id: Optional[str] = Field(None, description="Agent ID if routing through an agent")
    client_id: str = Field(..., description="Client ID for callback routing (required)")
    timeout: int = Field(default=300, description="Timeout in seconds (max 5 minutes)")
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


# ============================================================================
# COMPLETION RESPONSE (Immediate acknowledgment)
# ============================================================================

class CompletionAcknowledgment(BaseModel):
    """Immediate response when completion is queued"""
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    status: Literal["queued", "processing"] = "queued"
    estimated_time: Optional[int] = Field(None, description="Estimated completion time in seconds")
    queue_position: Optional[int] = Field(None, description="Position in processing queue")


# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

class ModelConfig(BaseModel):
    """Configuration for LLM models"""
    model: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    system_prompt: Optional[str] = None
    tools_enabled: bool = True
    
    @field_validator('temperature')
    def validate_temperature(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Temperature must be between 0 and 1")
        return v


# ============================================================================
# COMPLETION QUEUE MANAGEMENT
# ============================================================================

class CompletionQueueStatus(BaseModel):
    """Status of the completion processing queue"""
    queue_length: int
    active_workers: int
    estimated_wait_time: int  # seconds
    requests_per_minute: float


# ============================================================================
# NOTES ON ASYNC FLOW
# ============================================================================
"""
1. Client subscribes to COMPLETION_RESULT events on messaging.sock
2. Client sends COMPLETION request with client_id
3. Completion.sock returns immediate acknowledgment with request_id
4. When complete, result is published to messaging.sock as COMPLETION_RESULT event
5. Client receives result via messaging subscription

No blocking, no polling, clean async flow.
"""