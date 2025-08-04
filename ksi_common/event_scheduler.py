#!/usr/bin/env python3
"""
Event Scheduler Utilities for KSI

Provides reusable TTL and event scheduling functionality that can be used
by any KSI service to schedule events for future execution.

Key Features:
- Schedule events to fire once after a delay
- Persistent scheduling that survives restarts
- Memory-efficient heap-based scheduling
- Event-driven architecture (no polling)
"""

import asyncio
import heapq
import time
import uuid
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("ksi.event_scheduler")


@dataclass
class ScheduledEvent:
    """Represents a scheduled event."""
    event_id: str
    event_name: str
    event_data: Dict[str, Any]
    fire_at: float  # Unix timestamp
    created_at: float = field(default_factory=time.time)
    
    def __lt__(self, other):
        """For heap comparison - earliest fire_at has priority."""
        return self.fire_at < other.fire_at


class EventScheduler:
    """
    Manages scheduled events using a min-heap for efficient scheduling.
    
    This scheduler is designed to be embedded in KSI services that need
    to schedule events for future execution. It's event-driven and only
    wakes up when there's an event to fire.
    """
    
    def __init__(self, emit_callback: Callable[[str, Dict[str, Any]], Any]):
        """
        Initialize the scheduler.
        
        Args:
            emit_callback: Async function to call when events fire.
                          Should accept (event_name, event_data).
        """
        self.emit_callback = emit_callback
        self.heap: List[ScheduledEvent] = []
        self.events_by_id: Dict[str, ScheduledEvent] = {}
        self.next_fire_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        
    async def start(self):
        """Start the scheduler."""
        self._running = True
        await self._schedule_next()
        logger.info("Event scheduler started")
        
    async def stop(self):
        """Stop the scheduler and cancel pending tasks."""
        self._running = False
        if self.next_fire_task and not self.next_fire_task.done():
            self.next_fire_task.cancel()
            try:
                await self.next_fire_task
            except asyncio.CancelledError:
                pass
        logger.info("Event scheduler stopped")
    
    async def schedule_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        delay_seconds: Optional[float] = None,
        fire_at: Optional[float] = None,
        event_id: Optional[str] = None
    ) -> str:
        """
        Schedule an event to fire in the future.
        
        Args:
            event_name: Name of the event to emit
            event_data: Data to pass with the event
            delay_seconds: Seconds from now to fire (mutually exclusive with fire_at)
            fire_at: Unix timestamp when to fire (mutually exclusive with delay_seconds)
            event_id: Optional ID for the event (generated if not provided)
            
        Returns:
            The event ID for tracking/cancellation
        """
        if delay_seconds is None and fire_at is None:
            raise ValueError("Either delay_seconds or fire_at must be specified")
        
        if delay_seconds is not None and fire_at is not None:
            raise ValueError("Cannot specify both delay_seconds and fire_at")
        
        if delay_seconds is not None:
            fire_at = time.time() + delay_seconds
            
        event_id = event_id or f"sched_{uuid.uuid4().hex[:8]}"
        
        async with self._lock:
            # Create the scheduled event
            scheduled = ScheduledEvent(
                event_id=event_id,
                event_name=event_name,
                event_data=event_data,
                fire_at=fire_at
            )
            
            # Add to heap and index
            heapq.heappush(self.heap, scheduled)
            self.events_by_id[event_id] = scheduled
            
            logger.debug(f"Scheduled event {event_id}: {event_name} to fire at {fire_at}")
            
            # Reschedule if this is the next event to fire
            await self._schedule_next()
            
        return event_id
    
    async def cancel_event(self, event_id: str) -> bool:
        """
        Cancel a scheduled event.
        
        Args:
            event_id: ID of the event to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        async with self._lock:
            if event_id not in self.events_by_id:
                return False
                
            # Remove from index
            del self.events_by_id[event_id]
            
            # Note: We don't remove from heap immediately for efficiency
            # Cancelled events are skipped when popped from heap
            
            logger.debug(f"Cancelled scheduled event {event_id}")
            return True
    
    async def get_scheduled_events(self) -> List[Dict[str, Any]]:
        """
        Get all currently scheduled events.
        
        Returns:
            List of scheduled event details
        """
        async with self._lock:
            return [
                {
                    "event_id": event.event_id,
                    "event_name": event.event_name,
                    "fire_at": event.fire_at,
                    "delay_remaining": max(0, event.fire_at - time.time()),
                    "created_at": event.created_at
                }
                for event in self.events_by_id.values()
            ]
    
    async def _schedule_next(self):
        """Schedule the next event to fire."""
        if not self._running:
            return
            
        # Cancel existing task if any
        if self.next_fire_task and not self.next_fire_task.done():
            self.next_fire_task.cancel()
            
        # Clean heap of cancelled events
        while self.heap and self.heap[0].event_id not in self.events_by_id:
            heapq.heappop(self.heap)
            
        if not self.heap:
            return
            
        # Schedule task for next event
        next_event = self.heap[0]
        delay = max(0, next_event.fire_at - time.time())
        
        self.next_fire_task = asyncio.create_task(self._fire_next(delay))
        
    async def _fire_next(self, delay: float):
        """Wait and fire the next scheduled event."""
        try:
            if delay > 0:
                await asyncio.sleep(delay)
                
            async with self._lock:
                # Clean cancelled events from top of heap
                while self.heap and self.heap[0].event_id not in self.events_by_id:
                    heapq.heappop(self.heap)
                    
                if not self.heap:
                    return
                    
                # Pop and fire the event
                event = heapq.heappop(self.heap)
                if event.event_id in self.events_by_id:
                    del self.events_by_id[event.event_id]
                    
                    logger.debug(f"Firing scheduled event {event.event_id}: {event.event_name}")
                    
                    # Fire the event (don't await to avoid blocking)
                    asyncio.create_task(
                        self.emit_callback(event.event_name, event.event_data)
                    )
                
                # Schedule next event
                await self._schedule_next()
                
        except asyncio.CancelledError:
            logger.debug("Scheduled event task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error firing scheduled event: {e}")
            # Continue scheduling
            await self._schedule_next()
    
    async def load_events(self, events: List[Dict[str, Any]]):
        """
        Load previously scheduled events (e.g., after restart).
        
        Args:
            events: List of event dicts with keys:
                    event_id, event_name, event_data, fire_at
        """
        async with self._lock:
            for event_dict in events:
                # Skip if already expired
                if event_dict["fire_at"] <= time.time():
                    continue
                    
                scheduled = ScheduledEvent(
                    event_id=event_dict["event_id"],
                    event_name=event_dict["event_name"],
                    event_data=event_dict.get("event_data", {}),
                    fire_at=event_dict["fire_at"],
                    created_at=event_dict.get("created_at", time.time())
                )
                
                heapq.heappush(self.heap, scheduled)
                self.events_by_id[scheduled.event_id] = scheduled
                
            logger.info(f"Loaded {len(events)} scheduled events")
            await self._schedule_next()


def create_ttl_event(
    target_event: str,
    target_data: Dict[str, Any],
    ttl_seconds: int,
    event_id_field: str = "id"
) -> Tuple[str, Dict[str, Any]]:
    """
    Helper to create a TTL expiration event.
    
    Args:
        target_event: Event to emit when TTL expires
        target_data: Data containing the ID to expire
        ttl_seconds: Seconds until expiration
        event_id_field: Field in target_data containing the ID
        
    Returns:
        Tuple of (schedule_event_name, schedule_event_data)
        
    Example:
        event_name, event_data = create_ttl_event(
            "routing:expire_rule",
            {"rule_id": "abc123"},
            300  # 5 minutes
        )
        await router.emit(event_name, event_data)
    """
    return (
        "scheduler:schedule_once",
        {
            "event_name": target_event,
            "event_data": target_data,
            "delay_seconds": ttl_seconds,
            "event_id": f"ttl_{target_data.get(event_id_field, 'unknown')}_{int(time.time())}"
        }
    )


# Export public API
__all__ = [
    'EventScheduler',
    'ScheduledEvent', 
    'create_ttl_event'
]