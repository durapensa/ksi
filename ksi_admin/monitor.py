"""
Monitor Client - Real-time observation of all daemon activity.

Provides comprehensive monitoring capabilities for administrators to observe
agent interactions, system events, and performance metrics.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Set
from datetime import datetime
from collections import defaultdict

from .base import AdminBaseClient
from .protocols import EventNamespace, MonitorEventTypes

logger = logging.getLogger(__name__)


class MonitorClient(AdminBaseClient):
    """
    Client for monitoring all daemon activity.
    
    Unlike regular clients that participate in the system, MonitorClient
    passively observes all events, messages, and state changes.
    """
    
    def __init__(self, socket_path: str = "var/run/daemon.sock"):
        """Initialize monitor client."""
        super().__init__(role="monitor", socket_path=socket_path)
        
        # Tracking data
        self.active_agents: Dict[str, Dict[str, Any]] = {}
        self.conversations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.tool_calls: List[Dict[str, Any]] = []
        self.system_events: List[Dict[str, Any]] = []
        
        # Specialized handlers
        self._message_handlers: List[Callable] = []
        self._agent_handlers: List[Callable] = []
        self._tool_handlers: List[Callable] = []
        self._system_handlers: List[Callable] = []
    
    def _get_capabilities(self) -> List[str]:
        """Monitor capabilities."""
        return ["monitor", "observe", "metrics", "replay"]
    
    # ========================================================================
    # MONITORING OPERATIONS
    # ========================================================================
    
    async def observe_all(self, event_types: Optional[List[str]] = None):
        """
        Start observing system events.
        
        Args:
            event_types: Specific event types to monitor (None = all)
        """
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        # Default to all event types
        if event_types is None:
            event_types = MonitorEventTypes.all_events()
        
        # First, connect as monitor agent
        await self.request_event("agent:connect", {
            "agent_id": self.client_id,
            "role": "monitor",
            "profile": "monitor"
        })
        
        # Subscribe to message bus events for comprehensive monitoring
        message_bus_events = [
            "DIRECT_MESSAGE", "BROADCAST", "CONVERSATION_MESSAGE",
            "TASK_ASSIGNMENT", "TOOL_CALL", "AGENT_STATUS", 
            "CONVERSATION_INVITE", "SYSTEM_EVENT"
        ]
        
        result = await self.request_event("message:subscribe", {
            "agent_id": self.client_id,
            "events": message_bus_events
        })
        
        logger.info(f"Monitor subscribed to events: {result}")
        
        # Also subscribe to all event patterns via our internal routing
        for event_type in event_types:
            self.on_event(event_type, self._route_event)
        
        # Register wildcard handler for any events not explicitly listed
        self.on_event("*", self._route_event)
        
        logger.info("Monitor observation started")
    
    async def stop_observing(self):
        """Stop observing events."""
        try:
            # Unsubscribe from message bus
            await self.request_event("message:unsubscribe", {
                "agent_id": self.client_id
            })
            
            # Disconnect agent
            await self.request_event("agent:disconnect", {
                "agent_id": self.client_id
            })
            
            logger.info("Monitor observation stopped")
            
        except Exception as e:
            logger.error(f"Error stopping observation: {e}")
    
    async def get_system_snapshot(self) -> Dict[str, Any]:
        """
        Get current system state snapshot.
        
        Returns:
            Dictionary containing current agents, conversations, metrics
        """
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_agents": len(self.active_agents),
            "agents": list(self.active_agents.values()),
            "active_conversations": len(self.conversations),
            "conversations": {
                conv_id: len(messages) 
                for conv_id, messages in self.conversations.items()
            },
            "recent_tool_calls": self.tool_calls[-10:],
            "recent_system_events": self.system_events[-10:]
        }
        
        # Try to get additional metrics from daemon
        try:
            metrics = await self.request_event(EventNamespace.METRICS_COLLECT, {})
            snapshot["system_metrics"] = metrics
        except Exception as e:
            logger.warning(f"Could not get system metrics: {e}")
        
        return snapshot
    
    # ========================================================================
    # EVENT ROUTING
    # ========================================================================
    
    async def _route_event(self, event_name: str, event_data: Dict[str, Any]):
        """Route events to appropriate handlers based on type."""
        # Extract message type for message bus events
        msg_type = event_data.get("type") if isinstance(event_data, dict) else None
        
        # Route based on event name or message type
        if event_name.startswith("agent:") or msg_type == "AGENT_STATUS":
            await self._handle_agent_event(event_name, event_data)
        
        elif event_name.startswith("message:") or msg_type in ["DIRECT_MESSAGE", "BROADCAST", "CONVERSATION_MESSAGE"]:
            await self._handle_message_event(event_name, event_data)
        
        elif event_name.startswith("tool:") or msg_type == "TOOL_CALL":
            await self._handle_tool_event(event_name, event_data)
        
        elif event_name.startswith("system:") or msg_type == "SYSTEM_EVENT":
            await self._handle_system_event(event_name, event_data)
        
        # Always try to extract and track agent/conversation data
        await self._update_tracking_data(event_name, event_data)
    
    async def _update_tracking_data(self, event_name: str, event_data: Dict[str, Any]):
        """Update internal tracking data from events."""
        # Track agent connections/disconnections
        if event_name == "agent:connect":
            agent_id = event_data.get("agent_id")
            if agent_id:
                self.active_agents[agent_id] = {
                    "id": agent_id,
                    "connected_at": datetime.utcnow().isoformat(),
                    "profile": event_data.get("profile"),
                    "status": "active"
                }
        
        elif event_name == "agent:disconnect":
            agent_id = event_data.get("agent_id")
            if agent_id and agent_id in self.active_agents:
                self.active_agents[agent_id]["status"] = "disconnected"
                self.active_agents[agent_id]["disconnected_at"] = datetime.utcnow().isoformat()
        
        # Track conversations
        if "conversation_id" in event_data:
            conv_id = event_data["conversation_id"]
            self.conversations[conv_id].append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": event_name,
                "data": event_data
            })
    
    # ========================================================================
    # SPECIALIZED HANDLERS
    # ========================================================================
    
    async def _handle_agent_event(self, event_name: str, event_data: Dict[str, Any]):
        """Handle agent-related events."""
        # Call registered agent handlers
        for handler in self._agent_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_name, event_data)
                else:
                    handler(event_name, event_data)
            except Exception as e:
                logger.error(f"Error in agent handler: {e}")
    
    async def _handle_message_event(self, event_name: str, event_data: Dict[str, Any]):
        """Handle message events."""
        # Call registered message handlers
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_name, event_data)
                else:
                    handler(event_name, event_data)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    async def _handle_tool_event(self, event_name: str, event_data: Dict[str, Any]):
        """Handle tool-related events."""
        # Track tool call
        self.tool_calls.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_name,
            "agent_id": event_data.get("agent_id"),
            "tool": event_data.get("tool"),
            "params": event_data.get("params"),
            "result": event_data.get("result")
        })
        
        # Keep only recent tool calls
        if len(self.tool_calls) > 1000:
            self.tool_calls = self.tool_calls[-500:]
        
        # Call registered tool handlers
        for handler in self._tool_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_name, event_data)
                else:
                    handler(event_name, event_data)
            except Exception as e:
                logger.error(f"Error in tool handler: {e}")
    
    async def _handle_system_event(self, event_name: str, event_data: Dict[str, Any]):
        """Handle system events."""
        # Track system event
        self.system_events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_name,
            "data": event_data
        })
        
        # Keep only recent events
        if len(self.system_events) > 1000:
            self.system_events = self.system_events[-500:]
        
        # Call registered system handlers
        for handler in self._system_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_name, event_data)
                else:
                    handler(event_name, event_data)
            except Exception as e:
                logger.error(f"Error in system handler: {e}")
    
    # ========================================================================
    # HANDLER REGISTRATION
    # ========================================================================
    
    def on_message_flow(self, callback: Callable):
        """Register handler for inter-agent messages."""
        self._message_handlers.append(callback)
    
    def on_agent_activity(self, callback: Callable):
        """Register handler for agent lifecycle events."""
        self._agent_handlers.append(callback)
    
    def on_tool_usage(self, callback: Callable):
        """Register handler for tool calls."""
        self._tool_handlers.append(callback)
    
    def on_system_event(self, callback: Callable):
        """Register handler for system events."""
        self._system_handlers.append(callback)
    
    def on_any_activity(self, callback: Callable):
        """Register handler for all activity."""
        # Register for all event types
        self.on_event("*", callback)
    
    # ========================================================================
    # QUERY OPERATIONS
    # ========================================================================
    
    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get list of currently active agents."""
        return [
            agent for agent in self.active_agents.values()
            if agent.get("status") == "active"
        ]
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get messages for a specific conversation."""
        return self.conversations.get(conversation_id, [])
    
    def get_recent_tool_calls(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent tool calls."""
        return self.tool_calls[-limit:]
    
    def get_recent_system_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent system events."""
        return self.system_events[-limit:]