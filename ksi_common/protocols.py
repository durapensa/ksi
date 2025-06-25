"""Protocol definitions and event names for KSI.

Defines all event names, message formats, and protocol constants
used for communication between KSI components.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json


# Event name constants organized by namespace
class SystemEvents:
    """System-level events for daemon control."""
    HEALTH = "system:health"
    SHUTDOWN = "system:shutdown"
    DISCOVER = "system:discover"
    HELP = "system:help"
    CAPABILITIES = "system:capabilities"
    STATUS = "system:status"


class TransportEvents:
    """Transport layer events."""
    CONNECTION = "transport:connection"
    DISCONNECTION = "transport:disconnection"
    ERROR = "transport:error"


class CompletionEvents:
    """LLM completion events."""
    REQUEST = "completion:request"
    ASYNC = "completion:async"
    RESULT = "completion:result"
    CANCEL = "completion:cancel"


class AgentEvents:
    """Agent lifecycle and management events."""
    SPAWN = "agent:spawn"
    TERMINATE = "agent:terminate"
    LIST = "agent:list"
    INFO = "agent:info"
    SEND_MESSAGE = "agent:send_message"
    CONNECT = "agent:connect"
    DISCONNECT = "agent:disconnect"
    STATUS = "agent:status"


class StateEvents:
    """State management events."""
    GET = "state:get"
    SET = "state:set"
    DELETE = "state:delete"
    LIST = "state:list"
    CLEAR = "state:clear"


class MessageEvents:
    """Inter-agent messaging events."""
    PUBLISH = "message:publish"
    SUBSCRIBE = "message:subscribe"
    UNSUBSCRIBE = "message:unsubscribe"
    RECEIVED = "message:received"
    BROADCAST = "message:broadcast"
    DIRECT = "message:direct"
    CONVERSATIONS = "message:conversations"


class ConversationEvents:
    """Conversation history events."""
    LIST = "conversation:list"
    SEARCH = "conversation:search"
    GET = "conversation:get"
    EXPORT = "conversation:export"
    STATS = "conversation:stats"


class AdminEvents:
    """Administrative and monitoring events."""
    MONITOR_START = "admin:monitor:start"
    MONITOR_STOP = "admin:monitor:stop"
    METRICS_GET = "admin:metrics:get"
    CONTROL_RELOAD = "admin:control:reload"
    DEBUG_ENABLE = "admin:debug:enable"
    DEBUG_DISABLE = "admin:debug:disable"


@dataclass
class EventMessage:
    """Standard event message structure."""
    event: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    correlation_id: Optional[str] = None
    client_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "event": self.event,
            "data": self.data
        }
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.client_id:
            result["client_id"] = self.client_id
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventMessage':
        """Create from dictionary."""
        return cls(
            event=data["event"],
            data=data.get("data", {}),
            timestamp=data.get("timestamp"),
            correlation_id=data.get("correlation_id"),
            client_id=data.get("client_id")
        )


@dataclass
class EventResponse:
    """Standard event response structure."""
    status: str  # "success" or "error"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == "success"
    
    @property
    def is_error(self) -> bool:
        """Check if response indicates error."""
        return self.status == "error"
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"status": self.status}
        if self.result is not None:
            result["result"] = self.result
        if self.error is not None:
            result["error"] = self.error
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventResponse':
        """Create from dictionary."""
        return cls(
            status=data["status"],
            result=data.get("result"),
            error=data.get("error"),
            correlation_id=data.get("correlation_id")
        )
    
    @classmethod
    def success(cls, result: Dict[str, Any], correlation_id: Optional[str] = None) -> 'EventResponse':
        """Create success response."""
        return cls(
            status="success",
            result=result,
            correlation_id=correlation_id
        )
    
    @classmethod
    def error(cls, message: str, code: Optional[str] = None, 
             details: Optional[Dict[str, Any]] = None,
             correlation_id: Optional[str] = None) -> 'EventResponse':
        """Create error response."""
        error_data = {"message": message}
        if code:
            error_data["code"] = code
        if details:
            error_data["details"] = details
        return cls(
            status="error",
            error=error_data,
            correlation_id=correlation_id
        )


def build_event(event_name: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
    """Build a standard event message.
    
    Args:
        event_name: Name of the event
        data: Event data/payload
        **kwargs: Additional fields (timestamp, correlation_id, client_id)
        
    Returns:
        Dict ready to be JSON-serialized
    """
    msg = EventMessage(
        event=event_name,
        data=data or {},
        **kwargs
    )
    return msg.to_dict()


def parse_event(message: Dict[str, Any]) -> EventMessage:
    """Parse an event message.
    
    Args:
        message: Raw message dictionary
        
    Returns:
        EventMessage instance
    """
    return EventMessage.from_dict(message)


def is_event_message(message: Dict[str, Any]) -> bool:
    """Check if a message is a valid event message.
    
    Args:
        message: Message to check
        
    Returns:
        True if message has required event structure
    """
    return isinstance(message, dict) and "event" in message


def get_event_namespace(event_name: str) -> str:
    """Extract namespace from event name.
    
    Args:
        event_name: Full event name (e.g., "system:health")
        
    Returns:
        Namespace part (e.g., "system")
    """
    if ":" in event_name:
        return event_name.split(":", 1)[0]
    return ""