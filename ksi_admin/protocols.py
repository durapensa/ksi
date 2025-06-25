"""
Admin-specific protocol definitions and constants.

Defines the event namespaces and message formats for administrative operations.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json


# Event namespace constants
class EventNamespace:
    """Admin event namespaces for clean separation of concerns."""
    
    # Administrative operations
    ADMIN_AUTH = "admin:auth"
    ADMIN_CONTROL = "admin:control"
    ADMIN_AUDIT = "admin:audit"
    
    # Monitoring operations
    MONITOR_SUBSCRIBE = "monitor:subscribe"
    MONITOR_UNSUBSCRIBE = "monitor:unsubscribe"
    MONITOR_SNAPSHOT = "monitor:snapshot"
    MONITOR_REPLAY = "monitor:replay"
    
    # Metrics operations
    METRICS_COLLECT = "metrics:collect"
    METRICS_STREAM = "metrics:stream"
    METRICS_EXPORT = "metrics:export"
    METRICS_ALERT = "metrics:alert"
    
    # Debug operations
    DEBUG_TRACE = "debug:trace"
    DEBUG_PROFILE = "debug:profile"
    DEBUG_DUMP = "debug:dump"
    DEBUG_LOG_LEVEL = "debug:log_level"


@dataclass
class AdminMessage:
    """Standard admin message format."""
    event: str
    data: Dict[str, Any]
    client_id: str
    timestamp: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON for socket transmission."""
        msg = {
            "event": self.event,
            "data": self.data,
            "client_id": self.client_id
        }
        if self.timestamp:
            msg["timestamp"] = self.timestamp
        if self.correlation_id:
            msg["correlation_id"] = self.correlation_id
        return json.dumps(msg)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AdminMessage':
        """Parse from JSON."""
        data = json.loads(json_str)
        return cls(**data)


class MonitorEventTypes:
    """Event types that can be monitored."""
    # Agent events
    AGENT_CONNECT = "agent:connect"
    AGENT_DISCONNECT = "agent:disconnect"
    AGENT_STATUS = "agent:status"
    
    # Message events
    MESSAGE_SENT = "message:sent"
    MESSAGE_RECEIVED = "message:received"
    MESSAGE_BROADCAST = "message:broadcast"
    
    # Tool events
    TOOL_CALL = "tool:call"
    TOOL_RESULT = "tool:result"
    TOOL_ERROR = "tool:error"
    
    # System events
    SYSTEM_ERROR = "system:error"
    SYSTEM_WARNING = "system:warning"
    SYSTEM_INFO = "system:info"
    
    # Completion events
    COMPLETION_REQUEST = "completion:request"
    COMPLETION_RESULT = "completion:result"
    COMPLETION_ERROR = "completion:error"
    
    @classmethod
    def all_events(cls) -> List[str]:
        """Get all available event types."""
        return [
            value for name, value in cls.__dict__.items() 
            if not name.startswith('_') and isinstance(value, str)
        ]
    
    @classmethod
    def agent_events(cls) -> List[str]:
        """Get agent-related events."""
        return [cls.AGENT_CONNECT, cls.AGENT_DISCONNECT, cls.AGENT_STATUS]
    
    @classmethod
    def message_events(cls) -> List[str]:
        """Get message-related events."""
        return [cls.MESSAGE_SENT, cls.MESSAGE_RECEIVED, cls.MESSAGE_BROADCAST]
    
    @classmethod
    def tool_events(cls) -> List[str]:
        """Get tool-related events."""
        return [cls.TOOL_CALL, cls.TOOL_RESULT, cls.TOOL_ERROR]