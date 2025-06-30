#!/usr/bin/env python3
"""
Injection type definitions for the prompt injection system.

Defines data structures for injection requests, results, and modes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional


class InjectionMode(Enum):
    """Injection execution modes."""
    DIRECT = "direct"    # Execute injection immediately in current context
    NEXT = "next"        # Queue injection for next completion request


class InjectionPosition(Enum):
    """Injection position relative to prompt."""
    BEFORE_PROMPT = "before_prompt"         # Inject before user prompt
    AFTER_PROMPT = "after_prompt"           # Inject after user prompt
    SYSTEM_REMINDER = "system_reminder"     # Inject as system reminder


class InjectionError(Enum):
    """Injection error types."""
    INVALID_MODE = "invalid_mode"
    INVALID_POSITION = "invalid_position"
    NO_SESSION = "no_session"
    QUEUE_FULL = "queue_full"
    STATE_ERROR = "state_error"


@dataclass
class InjectionRequest:
    """Request to inject content into a completion."""
    content: str                                    # Content to inject
    mode: InjectionMode                            # Execution mode
    position: InjectionPosition = InjectionPosition.BEFORE_PROMPT  # Where to inject
    session_id: Optional[str] = None               # Session to inject into
    priority: str = "normal"                       # Priority (high, normal, low)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def __post_init__(self):
        """Validate enum types after initialization."""
        if not isinstance(self.mode, InjectionMode):
            if isinstance(self.mode, str):
                try:
                    self.mode = InjectionMode(self.mode)
                except ValueError:
                    raise ValueError(f"Invalid injection mode: {self.mode}")
            else:
                raise ValueError(f"Mode must be InjectionMode enum, got {type(self.mode)}")
        
        if not isinstance(self.position, InjectionPosition):
            if isinstance(self.position, str):
                try:
                    self.position = InjectionPosition(self.position)
                except ValueError:
                    raise ValueError(f"Invalid injection position: {self.position}")
            else:
                raise ValueError(f"Position must be InjectionPosition enum, got {type(self.position)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "mode": self.mode.value,
            "position": self.position.value,
            "session_id": self.session_id,
            "priority": self.priority,
            "metadata": self.metadata
        }


@dataclass
class InjectionResult:
    """Result of an injection operation."""
    success: bool                                  # Whether injection succeeded
    mode: InjectionMode                           # Mode that was used
    position: Optional[InjectionPosition] = None  # Position that was used
    session_id: Optional[str] = None              # Session that was targeted
    request_id: Optional[str] = None              # Request ID if direct mode
    error: Optional[str] = None                   # Error message if failed
    error_type: Optional[InjectionError] = None   # Error type if failed
    queued: bool = False                          # Whether injection was queued
    queue_position: Optional[int] = None          # Position in queue if queued
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "success": self.success,
            "mode": self.mode.value,
            "queued": self.queued
        }
        
        if self.position:
            result["position"] = self.position.value
        if self.session_id:
            result["session_id"] = self.session_id
        if self.request_id:
            result["request_id"] = self.request_id
        if self.error:
            result["error"] = self.error
        if self.error_type:
            result["error_type"] = self.error_type.value
        if self.queue_position is not None:
            result["queue_position"] = self.queue_position
            
        return result