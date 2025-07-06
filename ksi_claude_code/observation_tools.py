"""
Observation tools for monitoring agent behavior through KSI's observation system.

These tools provide real-time monitoring of agent events without requiring
daemon modifications.
"""

from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime

from .ksi_base_tool import KSIBaseTool

import logging
logger = logging.getLogger(__name__)


@dataclass
class ObservationSubscription:
    """Active observation subscription"""
    subscription_id: str
    target_agent: str
    event_patterns: List[str]
    created_at: datetime


class ObservationTool(KSIBaseTool):
    """Monitor agent behavior through KSI's observation system"""
    
    name = "ksi_observation"
    description = "Subscribe to and monitor agent events"
    
    def __init__(self):
        super().__init__()
        self.active_subscriptions: Dict[str, ObservationSubscription] = {}
    
    async def subscribe(
        self,
        target_agent: str,
        event_patterns: Optional[List[str]] = None,
        rate_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Subscribe to observe an agent's events
        
        Args:
            target_agent: Agent ID or session ID to observe
            event_patterns: Event patterns to filter (e.g., ["agent:progress:*"])
            rate_limit: Optional rate limit per minute
            
        Returns:
            Dictionary with subscription_id for streaming
        """
        # Default to all agent events if no patterns specified
        if not event_patterns:
            event_patterns = ["agent:*"]
        
        # Build subscription request
        subscription_data = {
            "target": target_agent,
            "observer": "claude_code",  # Identify ourselves
            "event_patterns": event_patterns
        }
        
        if rate_limit:
            subscription_data["rate_limit"] = rate_limit
        
        logger.info(f"Subscribing to observe agent {target_agent}")
        
        # Send subscription request
        response = await self.send_event(
            "observation:subscribe",
            subscription_data
        )
        
        if not response.get("success", False):
            error = response.get("error", "Unknown error")
            raise RuntimeError(f"Failed to subscribe: {error}")
        
        # Store subscription info
        sub_id = response.get("subscription_id")
        subscription = ObservationSubscription(
            subscription_id=sub_id,
            target_agent=target_agent,
            event_patterns=event_patterns,
            created_at=datetime.utcnow()
        )
        self.active_subscriptions[sub_id] = subscription
        
        logger.info(f"Created subscription {sub_id} for agent {target_agent}")
        
        return {
            "subscription_id": sub_id,
            "target": target_agent,
            "patterns": event_patterns
        }
    
    async def unsubscribe(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel an observation subscription
        
        Args:
            subscription_id: Subscription to cancel
            
        Returns:
            Cancellation result
        """
        if subscription_id not in self.active_subscriptions:
            logger.warning(f"Subscription {subscription_id} not found in active list")
        
        # Send unsubscribe request
        response = await self.send_event(
            "observation:unsubscribe",
            {"subscription_id": subscription_id}
        )
        
        # Remove from active list
        if subscription_id in self.active_subscriptions:
            del self.active_subscriptions[subscription_id]
        
        logger.info(f"Unsubscribed from {subscription_id}")
        
        return response
    
    async def stream_observations(
        self,
        subscription_id: str,
        timeout: Optional[float] = 1.0
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream observations from a subscription
        
        Args:
            subscription_id: Subscription to stream from
            timeout: Polling timeout in seconds
            
        Yields:
            Observation events as they occur
        """
        logger.info(f"Starting observation stream for {subscription_id}")
        
        try:
            async for event in self.stream_events(subscription_id, timeout):
                # Add subscription context
                event["subscription_id"] = subscription_id
                
                # Log significant events
                if event.get("event", "").endswith(":error"):
                    logger.warning(f"Error event: {event}")
                elif "milestone" in event.get("event", ""):
                    logger.info(f"Milestone: {event}")
                
                yield event
                
        except asyncio.CancelledError:
            logger.info(f"Observation stream cancelled for {subscription_id}")
            raise
        except Exception as e:
            logger.error(f"Error in observation stream: {e}")
            raise
    
    async def observe_until_complete(
        self,
        target_agent: str,
        completion_events: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Observe an agent until it completes
        
        Args:
            target_agent: Agent to observe
            completion_events: Events that signal completion
            
        Returns:
            List of all observations
        """
        if not completion_events:
            completion_events = [
                "agent:complete",
                "agent:task:complete",
                "agent:terminated"
            ]
        
        # Subscribe to agent
        sub = await self.subscribe(
            target_agent=target_agent,
            event_patterns=["agent:*"]
        )
        
        observations = []
        
        try:
            async for event in self.stream_observations(sub["subscription_id"]):
                observations.append(event)
                
                # Check for completion
                if any(event.get("event", "").startswith(pattern.rstrip("*")) 
                       for pattern in completion_events):
                    logger.info(f"Agent {target_agent} completed with event: {event['event']}")
                    break
                    
        finally:
            # Always unsubscribe
            await self.unsubscribe(sub["subscription_id"])
        
        return observations
    
    async def monitor_progress(
        self,
        target_agent: str,
        callback: Optional[Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Monitor agent progress with optional callback
        
        Args:
            target_agent: Agent to monitor
            callback: Optional async callback for events
            
        Yields:
            Progress updates
        """
        # Subscribe to progress events
        sub = await self.subscribe(
            target_agent=target_agent,
            event_patterns=[
                "agent:progress:*",
                "agent:milestone:*",
                "agent:status:*"
            ]
        )
        
        try:
            async for event in self.stream_observations(sub["subscription_id"]):
                # Call callback if provided
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                
                # Yield progress info
                yield {
                    "event_type": event.get("event", ""),
                    "data": event.get("data", {}),
                    "timestamp": event.get("timestamp", datetime.utcnow().isoformat())
                }
                
        finally:
            await self.unsubscribe(sub["subscription_id"])
    
    async def get_active_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Get list of active subscriptions
        
        Returns:
            List of subscription details
        """
        return [
            {
                "subscription_id": sub_id,
                "target": sub.target_agent,
                "patterns": sub.event_patterns,
                "created_at": sub.created_at.isoformat()
            }
            for sub_id, sub in self.active_subscriptions.items()
        ]
    
    async def observe_spawn_events(
        self,
        coordinator_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Observe when an agent spawns children
        
        Args:
            coordinator_id: Agent that might spawn children
            
        Yields:
            Spawn event details
        """
        sub = await self.subscribe(
            target_agent=coordinator_id,
            event_patterns=[
                "agent:spawn:*",
                "agent:child:*"
            ]
        )
        
        try:
            async for event in self.stream_observations(sub["subscription_id"]):
                if "spawn:success" in event.get("event", ""):
                    yield {
                        "parent": coordinator_id,
                        "child": event.get("data", {}).get("agent_id"),
                        "profile": event.get("data", {}).get("profile"),
                        "timestamp": event.get("timestamp")
                    }
        finally:
            await self.unsubscribe(sub["subscription_id"])
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "target_agent": {
                        "type": "string",
                        "description": "Agent ID or session ID to observe"
                    },
                    "event_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Event patterns to filter (e.g., ['agent:progress:*'])"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["subscribe", "unsubscribe", "stream"],
                        "description": "Action to perform"
                    }
                },
                "required": ["target_agent", "action"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute observation operation"""
        action = kwargs.get("action", "subscribe")
        
        if action == "subscribe":
            return await self.subscribe(
                target_agent=kwargs["target_agent"],
                event_patterns=kwargs.get("event_patterns")
            )
        elif action == "unsubscribe":
            return await self.unsubscribe(
                subscription_id=kwargs["subscription_id"]
            )
        else:
            raise ValueError(f"Unknown action: {action}")