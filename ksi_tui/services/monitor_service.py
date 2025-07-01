"""
MonitorService - Clean abstraction for monitoring operations with KSI daemon.

Provides a high-level interface for system monitoring, handling:
- Real-time event subscriptions
- System health monitoring
- Agent status tracking
- Performance metrics collection
"""

from typing import Optional, List, Dict, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging
from collections import defaultdict

# Import KSI client components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ksi_client import EventBasedClient, MultiAgentClient
from ksi_common import config

logger = logging.getLogger(__name__)


class MonitorError(Exception):
    """Base exception for monitor service errors."""
    pass


@dataclass
class SystemHealth:
    """System health information."""
    status: str  # "healthy", "degraded", "error"
    daemon_alive: bool
    active_agents: int
    active_conversations: int
    memory_usage: Optional[str] = None
    cpu_usage: Optional[float] = None
    uptime: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return self.status == "healthy"


@dataclass
class AgentInfo:
    """Information about an agent."""
    agent_id: str
    status: str  # "active", "idle", "terminated"
    profile: str
    spawned_at: datetime
    last_activity: Optional[datetime] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    permissions: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventInfo:
    """Information about a system event."""
    event_name: str
    timestamp: datetime
    client_id: Optional[str]
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    severity: str = "info"


@dataclass
class PerformanceMetrics:
    """System performance metrics."""
    timestamp: datetime
    total_events: int
    events_per_second: float
    active_connections: int
    completion_queue_size: int
    average_latency_ms: Optional[float] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None


class MonitorService:
    """Service for monitoring KSI daemon and system activity."""
    
    def __init__(
        self,
        client_id: str = "monitor_service",
        socket_path: Optional[str] = None,
        event_buffer_size: int = 10000,
    ):
        """
        Initialize the monitor service.
        
        Args:
            client_id: Client identifier
            socket_path: Path to daemon socket
            event_buffer_size: Maximum events to buffer
        """
        self.client_id = client_id
        self.socket_path = socket_path or str(config.socket_path)
        self.event_buffer_size = event_buffer_size
        
        # Client instances
        self._event_client: Optional[EventBasedClient] = None
        self._agent_client: Optional[MultiAgentClient] = None
        
        # State
        self._connected = False
        self._subscriptions: Set[str] = set()
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Monitoring data
        self._agents: Dict[str, AgentInfo] = {}
        self._events_buffer: List[EventInfo] = []
        self._metrics_history: List[PerformanceMetrics] = []
        
        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
    
    @property
    def connected(self) -> bool:
        """Check if service is connected."""
        return self._connected
    
    async def connect(self) -> bool:
        """
        Connect to the KSI daemon.
        
        Returns:
            True if connected successfully
        """
        try:
            # Create client instances
            self._event_client = EventBasedClient(
                client_id=f"{self.client_id}_event",
                socket_path=self.socket_path
            )
            
            self._agent_client = MultiAgentClient(
                client_id=f"{self.client_id}_agent",
                socket_path=self.socket_path
            )
            
            # Connect both clients
            if not await self._event_client.connect():
                raise MonitorError("Failed to connect event client")
            
            if not await self._agent_client.connect():
                raise MonitorError("Failed to connect agent client")
            
            self._connected = True
            
            # Start background monitoring
            self._start_monitoring()
            
            logger.info(f"MonitorService connected to {self.socket_path}")
            return True
            
        except Exception as e:
            self._connected = False
            logger.error(f"Connection failed: {e}")
            raise MonitorError(f"Failed to connect: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from the daemon."""
        # Stop monitoring
        self._stop_monitoring()
        
        # Disconnect clients
        if self._event_client:
            try:
                await self._event_client.disconnect()
            except Exception:
                pass
        
        if self._agent_client:
            try:
                await self._agent_client.disconnect()
            except Exception:
                pass
        
        self._connected = False
        logger.info("MonitorService disconnected")
    
    def _start_monitoring(self) -> None:
        """Start background monitoring tasks."""
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        if not self._health_check_task or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    def _stop_monitoring(self) -> None:
        """Stop background monitoring tasks."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
    
    async def _monitor_loop(self) -> None:
        """Background loop for monitoring events."""
        try:
            # Subscribe to all events for monitoring
            await self.subscribe_events(["*"])
            
            while self._connected:
                await asyncio.sleep(0.1)  # Small delay to prevent busy loop
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
    
    async def _health_check_loop(self) -> None:
        """Background loop for health checks."""
        try:
            while self._connected:
                try:
                    # Perform health check
                    await self.get_health()
                    
                    # Update agent list
                    await self._update_agent_list()
                    
                    # Collect metrics
                    await self._collect_metrics()
                    
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                
                # Check every 5 seconds
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            pass
    
    async def subscribe_events(
        self,
        patterns: List[str],
        handler: Optional[Callable[[EventInfo], None]] = None,
    ) -> None:
        """
        Subscribe to event patterns.
        
        Args:
            patterns: Event patterns to subscribe to (e.g., ["agent:*", "completion:*"])
            handler: Optional handler for these specific patterns
        """
        if not self._connected:
            return
        
        for pattern in patterns:
            if pattern not in self._subscriptions:
                # Subscribe via event client
                def event_callback(event_name: str, event_data: dict):
                    event_info = EventInfo(
                        event_name=event_name,
                        timestamp=datetime.now(),
                        client_id=event_data.get("client_id"),
                        data=event_data,
                        correlation_id=event_data.get("correlation_id"),
                    )
                    
                    # Add to buffer
                    self._add_to_event_buffer(event_info)
                    
                    # Call handlers
                    self._notify_event_handlers(pattern, event_info)
                    
                    # Call specific handler if provided
                    if handler:
                        try:
                            handler(event_info)
                        except Exception as e:
                            logger.error(f"Event handler error: {e}")
                
                self._event_client.subscribe(pattern, event_callback)
                self._subscriptions.add(pattern)
                
                if handler:
                    self._event_handlers[pattern].append(handler)
    
    async def unsubscribe_events(self, patterns: List[str]) -> None:
        """Unsubscribe from event patterns."""
        for pattern in patterns:
            if pattern in self._subscriptions:
                self._event_client.unsubscribe(pattern)
                self._subscriptions.remove(pattern)
                self._event_handlers.pop(pattern, None)
    
    def add_event_handler(
        self,
        pattern: str,
        handler: Callable[[EventInfo], None],
    ) -> None:
        """Add an event handler for a pattern."""
        self._event_handlers[pattern].append(handler)
    
    def remove_event_handler(
        self,
        pattern: str,
        handler: Callable[[EventInfo], None],
    ) -> None:
        """Remove an event handler."""
        if pattern in self._event_handlers and handler in self._event_handlers[pattern]:
            self._event_handlers[pattern].remove(handler)
    
    def _add_to_event_buffer(self, event: EventInfo) -> None:
        """Add event to buffer with size limit."""
        self._events_buffer.append(event)
        if len(self._events_buffer) > self.event_buffer_size:
            self._events_buffer.pop(0)
    
    def _notify_event_handlers(self, pattern: str, event: EventInfo) -> None:
        """Notify handlers for an event pattern."""
        for handler in self._event_handlers.get(pattern, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    async def get_health(self) -> SystemHealth:
        """Get current system health."""
        if not self._connected:
            return SystemHealth(
                status="error",
                daemon_alive=False,
                active_agents=0,
                active_conversations=0,
                errors=["Not connected to daemon"],
            )
        
        try:
            # Query daemon health
            health_result = await self._event_client.request_event("system:health", {})
            
            # Count active agents
            active_agents = len([a for a in self._agents.values() if a.status == "active"])
            
            # Get conversation count
            conv_result = await self._event_client.request_event("conversation:active", {})
            active_conversations = len(conv_result.get("active_sessions", []))
            
            return SystemHealth(
                status="healthy",
                daemon_alive=True,
                active_agents=active_agents,
                active_conversations=active_conversations,
                memory_usage=health_result.get("memory_usage"),
                cpu_usage=health_result.get("cpu_usage"),
                uptime=health_result.get("uptime"),
            )
            
        except Exception as e:
            return SystemHealth(
                status="error",
                daemon_alive=False,
                active_agents=0,
                active_conversations=0,
                errors=[str(e)],
            )
    
    async def get_agents(self) -> List[AgentInfo]:
        """Get list of all agents."""
        return list(self._agents.values())
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get specific agent info."""
        return self._agents.get(agent_id)
    
    async def _update_agent_list(self) -> None:
        """Update the agent list from daemon."""
        if not self._connected:
            return
        
        try:
            # Get agent list
            agents = await self._agent_client.list_agents()
            
            # Update agent info
            current_ids = set()
            for agent_data in agents:
                if isinstance(agent_data, str):
                    agent_id = agent_data
                    agent_info = AgentInfo(
                        agent_id=agent_id,
                        status="active",
                        profile="unknown",
                        spawned_at=datetime.now(),
                    )
                else:
                    agent_id = agent_data.get("agent_id", "")
                    agent_info = AgentInfo(
                        agent_id=agent_id,
                        status=agent_data.get("status", "active"),
                        profile=agent_data.get("profile", "unknown"),
                        spawned_at=datetime.now(),
                        parent_id=agent_data.get("parent_id"),
                    )
                
                self._agents[agent_id] = agent_info
                current_ids.add(agent_id)
            
            # Remove terminated agents
            for agent_id in list(self._agents.keys()):
                if agent_id not in current_ids:
                    self._agents[agent_id].status = "terminated"
                    
        except Exception as e:
            logger.error(f"Failed to update agent list: {e}")
    
    async def _collect_metrics(self) -> None:
        """Collect performance metrics."""
        try:
            # Calculate events per second
            now = datetime.now()
            recent_events = [
                e for e in self._events_buffer
                if (now - e.timestamp).total_seconds() < 60
            ]
            events_per_second = len(recent_events) / 60.0 if recent_events else 0
            
            # Get queue status
            queue_result = await self._event_client.request_event("completion:queue_status", {})
            queue_size = queue_result.get("queue_size", 0)
            
            # Create metrics
            metrics = PerformanceMetrics(
                timestamp=now,
                total_events=len(self._events_buffer),
                events_per_second=events_per_second,
                active_connections=len(self._subscriptions),
                completion_queue_size=queue_size,
            )
            
            # Add to history
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > 100:
                self._metrics_history.pop(0)
                
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
    
    def get_recent_events(
        self,
        limit: int = 100,
        pattern: Optional[str] = None,
    ) -> List[EventInfo]:
        """Get recent events from buffer."""
        events = self._events_buffer[-limit:]
        
        if pattern:
            # Simple pattern matching
            import re
            regex = pattern.replace("*", ".*")
            events = [e for e in events if re.match(regex, e.event_name)]
        
        return events
    
    def get_metrics(self) -> List[PerformanceMetrics]:
        """Get performance metrics history."""
        return self._metrics_history.copy()
    
    def get_latest_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the most recent metrics."""
        return self._metrics_history[-1] if self._metrics_history else None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()