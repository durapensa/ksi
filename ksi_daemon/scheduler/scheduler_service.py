#!/usr/bin/env python3
"""
Scheduler Service for KSI

Provides system-wide event scheduling capabilities using the event-driven
EventScheduler from ksi_common. This service handles scheduled events and
integrates with the KSI event system.

Events:
- scheduler:schedule_once - Schedule an event to fire once after a delay
- scheduler:cancel - Cancel a scheduled event
- scheduler:list - List all scheduled events
- scheduler:status - Get scheduler status and metrics
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional

from ksi_common.event_response_builder import success_response, error_response
from ksi_common.event_scheduler import EventScheduler
from ksi_daemon.event_system import event_handler, get_router

logger = logging.getLogger("ksi.scheduler_service")


# Global scheduler instance
scheduler_instance = None
metrics = {
    "events_scheduled": 0,
    "events_fired": 0,
    "events_cancelled": 0,
    "events_failed": 0,
    "service_started": time.time()
}
        
async def initialize_scheduler():
    """Initialize the scheduler on first use."""
    global scheduler_instance
    if scheduler_instance is None:
        router = get_router()
        scheduler_instance = EventScheduler(emit_scheduled_event)
        await scheduler_instance.start()
        logger.info("Scheduler service initialized")
    return scheduler_instance
        
async def emit_scheduled_event(event_name: str, event_data: Dict[str, Any]):
    """Callback for scheduler to emit events."""
    try:
        # Add scheduler context
        event_data["_scheduled_emission"] = True
        event_data["_emission_time"] = time.time()
        
        # Emit the scheduled event
        router = get_router()
        await router.emit(event_name, event_data)
        
        metrics["events_fired"] += 1
        logger.debug(f"Fired scheduled event: {event_name}")
        
    except Exception as e:
        metrics["events_failed"] += 1
        logger.error(f"Failed to fire scheduled event {event_name}: {e}")
        
@event_handler("scheduler:schedule_once")
async def handle_schedule_once(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle scheduling a one-time event."""
        try:
            # Validate parameters
            event_name = data.get("event_name")
            event_data = data.get("event_data", {})
            delay_seconds = data.get("delay_seconds")
            fire_at = data.get("fire_at")
            event_id = data.get("event_id")
            
            if not event_name:
                return error_response("event_name is required")
                
            # Ensure scheduler is initialized
            scheduler = await initialize_scheduler()
            
            # Schedule the event
            scheduled_id = await scheduler.schedule_event(
                event_name=event_name,
                event_data=event_data,
                delay_seconds=delay_seconds,
                fire_at=fire_at,
                event_id=event_id
            )
            
            metrics["events_scheduled"] += 1
            
            logger.info(f"Scheduled event {scheduled_id}: {event_name} "
                       f"to fire in {delay_seconds or (fire_at - time.time())} seconds")
            
            return success_response({
                "event_id": scheduled_id,
                "event_name": event_name,
                "fire_at": fire_at or (time.time() + delay_seconds),
                "status": "scheduled"
            })
            
        except ValueError as e:
            return error_response(str(e))
        except Exception as e:
            logger.error(f"Error scheduling event: {e}")
            return error_response(f"Failed to schedule event: {str(e)}")
            
@event_handler("scheduler:cancel")
async def handle_cancel(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle cancelling a scheduled event."""
        event_id = data.get("event_id")
        if not event_id:
            return error_response("event_id is required")
            
        # Ensure scheduler is initialized
        scheduler = await initialize_scheduler()
        
        cancelled = await scheduler.cancel_event(event_id)
        
        if cancelled:
            metrics["events_cancelled"] += 1
            logger.info(f"Cancelled scheduled event {event_id}")
            return success_response({"event_id": event_id, "status": "cancelled"})
        else:
            return error_response(f"Event {event_id} not found")
            
@event_handler("scheduler:list")
async def handle_list(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle listing scheduled events."""
        # Ensure scheduler is initialized
        scheduler = await initialize_scheduler()
        
        events = await scheduler.get_scheduled_events()
        
        return success_response({
            "count": len(events),
            "events": events
        })
        
@event_handler("scheduler:status")
async def handle_status(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle getting scheduler status."""
        # Ensure scheduler is initialized
        scheduler = await initialize_scheduler()
        
        scheduled_events = await scheduler.get_scheduled_events()
        
        return success_response({
            "status": "running" if scheduler_instance is not None else "stopped",
            "metrics": metrics,
            "scheduled_count": len(scheduled_events),
            "uptime": time.time() - metrics["service_started"]
        })
        
# Checkpoint support would be added here if needed