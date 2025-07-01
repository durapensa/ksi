"""
KSI TUI Services - Business logic layer for KSI TUI applications.

This package provides clean service abstractions that handle all
interactions with the KSI daemon, separating business logic from UI concerns.
"""

from .chat_service import (
    ChatService,
    ChatMessage,
    ChatSession,
    ChatError,
    ConnectionError,
    SessionError,
)

from .monitor_service import (
    MonitorService,
    SystemHealth,
    AgentInfo,
    EventInfo,
    PerformanceMetrics,
    MonitorError,
)

__all__ = [
    # Chat service
    "ChatService",
    "ChatMessage",
    "ChatSession",
    "ChatError",
    "ConnectionError",
    "SessionError",
    
    # Monitor service
    "MonitorService",
    "SystemHealth",
    "AgentInfo",
    "EventInfo",
    "PerformanceMetrics",
    "MonitorError",
]