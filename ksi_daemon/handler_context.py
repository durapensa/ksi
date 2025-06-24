#!/usr/bin/env python3
"""
Handler Context - Structured context for command handlers
Provides type-safe access to all daemon managers and services
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

# Avoid circular imports
if TYPE_CHECKING:
    from .core import KSIDaemonCore
    from .session_and_shared_state_manager import SessionAndSharedStateManager
    from .completion_manager import CompletionManager
    from .agent_profile_registry import AgentProfileRegistry
    from .message_bus import MessageBus
    from .agent_identity_registry import AgentIdentityRegistry
    from .hot_reload_manager import HotReloadManager
    from .timestamp_utils import TimestampManager


@dataclass
class HandlerContext:
    """
    Context object providing handlers with access to daemon services.
    
    All handlers receive this context to access managers and services
    in a type-safe way. This replaces the previous pattern of manually
    setting attributes on an empty class.
    """
    
    # Core daemon reference
    core_daemon: 'KSIDaemonCore'
    
    # Manager services
    state_manager: 'SessionAndSharedStateManager'
    completion_manager: 'CompletionManager'
    agent_manager: 'AgentProfileRegistry'
    message_bus: 'MessageBus'
    identity_manager: 'AgentIdentityRegistry'
    hot_reload_manager: 'HotReloadManager'
    
    # Optional services (not all handlers need these)
    timestamp_manager: Optional['TimestampManager'] = None
    
    def __post_init__(self):
        """Validate that all required services are provided"""
        required_attrs = [
            'core_daemon', 'state_manager', 'completion_manager',
            'agent_manager', 'message_bus', 'identity_manager', 
            'hot_reload_manager'
        ]
        
        for attr in required_attrs:
            if getattr(self, attr) is None:
                raise ValueError(f"Required service '{attr}' is None in HandlerContext")