#!/usr/bin/env python3
"""
Scheduled Event Service for KSI
================================

Provides scheduling capabilities for periodic events during episodes.
Essential for game mechanics like resource regeneration, periodic scoring,
and time-based victory conditions.

Features:
- Cron-like scheduling for recurring events
- Interval-based scheduling (every N steps/seconds)
- Conditional scheduling based on game state
- Priority queues for event ordering
- Episode-aware scheduling (auto cleanup)
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import heapq
from collections import defaultdict
import json

from ksi_common.event_types import Event
from ksi_daemon.base import ServiceBase, EventHandler


class ScheduleType(Enum):
    """Types of scheduling patterns."""
    INTERVAL = "interval"  # Every N units
    CRON = "cron"  # Cron-like pattern
    CONDITIONAL = "conditional"  # Based on conditions
    ONE_TIME = "one_time"  # Single execution
    EXPONENTIAL = "exponential"  # Exponential backoff/growth


@dataclass
class ScheduledEvent:
    """A scheduled event."""
    event_id: str
    episode_id: str
    event_type: str
    event_data: Dict
    schedule_type: ScheduleType
    schedule_config: Dict
    priority: int = 0
    enabled: bool = True
    last_execution: Optional[float] = None
    execution_count: int = 0
    max_executions: Optional[int] = None
    condition: Optional[Callable] = None
    metadata: Dict = field(default_factory=dict)
    
    def __lt__(self, other):
        """For priority queue ordering."""
        return self.priority > other.priority  # Higher priority first


@dataclass
class SchedulePattern:
    """Pattern for scheduled execution."""
    pattern_type: ScheduleType
    interval: Optional[float] = None  # For interval type
    cron_expression: Optional[str] = None  # For cron type
    condition_check: Optional[str] = None  # Event to check condition
    base_interval: Optional[float] = None  # For exponential
    growth_factor: Optional[float] = None  # For exponential


class ScheduledEventService(ServiceBase):
    """Service for managing scheduled events."""
    
    def __init__(self):
        super().__init__("scheduler")
        self.scheduled_events: Dict[str, ScheduledEvent] = {}
        self.episode_schedules: Dict[str, List[str]] = defaultdict(list)
        self.event_queue: List[Tuple[float, str]] = []  # (next_time, event_id)
        self.running = False
        self.scheduler_task = None
        
        # Predefined schedule patterns
        self.patterns = {
            "resource_regeneration": SchedulePattern(
                pattern_type=ScheduleType.INTERVAL,
                interval=5.0  # Every 5 seconds
            ),
            "pollution_growth": SchedulePattern(
                pattern_type=ScheduleType.EXPONENTIAL,
                base_interval=10.0,
                growth_factor=1.1
            ),
            "metric_calculation": SchedulePattern(
                pattern_type=ScheduleType.INTERVAL,
                interval=10.0
            ),
            "victory_check": SchedulePattern(
                pattern_type=ScheduleType.INTERVAL,
                interval=1.0
            ),
            "spawn_resources": SchedulePattern(
                pattern_type=ScheduleType.CONDITIONAL,
                condition_check="resource:below_threshold"
            )
        }
    
    async def on_start(self):
        """Start the scheduler."""
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("Scheduled event service started")
    
    async def on_stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Scheduled event service stopped")
    
    @EventHandler("scheduler:create")
    async def handle_create_schedule(self, event: Event) -> Dict:
        """Create a new scheduled event."""
        data = event.data
        
        # Parse schedule configuration
        schedule_type = ScheduleType(data.get("schedule_type", "interval"))
        
        scheduled_event = ScheduledEvent(
            event_id=data.get("event_id", f"scheduled_{int(time.time()*1000)}"),
            episode_id=data["episode_id"],
            event_type=data["event_type"],
            event_data=data.get("event_data", {}),
            schedule_type=schedule_type,
            schedule_config=data.get("schedule_config", {}),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
            max_executions=data.get("max_executions"),
            metadata=data.get("metadata", {})
        )
        
        # Store the scheduled event
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[scheduled_event.episode_id].append(scheduled_event.event_id)
        
        # Add to queue
        next_time = self._calculate_next_execution(scheduled_event)
        if next_time:
            heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        self.logger.debug(f"Created scheduled event: {scheduled_event.event_id}")
        
        return {
            "result": {
                "event_id": scheduled_event.event_id,
                "next_execution": next_time
            }
        }
    
    @EventHandler("scheduler:update")
    async def handle_update_schedule(self, event: Event) -> Dict:
        """Update an existing scheduled event."""
        data = event.data
        event_id = data["event_id"]
        
        if event_id not in self.scheduled_events:
            return {"error": f"Scheduled event {event_id} not found"}
        
        scheduled_event = self.scheduled_events[event_id]
        
        # Update fields
        if "enabled" in data:
            scheduled_event.enabled = data["enabled"]
        if "priority" in data:
            scheduled_event.priority = data["priority"]
        if "schedule_config" in data:
            scheduled_event.schedule_config.update(data["schedule_config"])
        if "event_data" in data:
            scheduled_event.event_data.update(data["event_data"])
        
        # Recalculate next execution if needed
        if scheduled_event.enabled:
            next_time = self._calculate_next_execution(scheduled_event)
            if next_time:
                # Remove old entry and add new one
                self.event_queue = [(t, eid) for t, eid in self.event_queue if eid != event_id]
                heapq.heapify(self.event_queue)
                heapq.heappush(self.event_queue, (next_time, event_id))
        
        return {"result": {"status": "updated"}}
    
    @EventHandler("scheduler:cancel")
    async def handle_cancel_schedule(self, event: Event) -> Dict:
        """Cancel a scheduled event."""
        data = event.data
        event_id = data["event_id"]
        
        if event_id not in self.scheduled_events:
            return {"error": f"Scheduled event {event_id} not found"}
        
        # Remove from structures
        scheduled_event = self.scheduled_events[event_id]
        del self.scheduled_events[event_id]
        self.episode_schedules[scheduled_event.episode_id].remove(event_id)
        
        # Remove from queue
        self.event_queue = [(t, eid) for t, eid in self.event_queue if eid != event_id]
        heapq.heapify(self.event_queue)
        
        return {"result": {"status": "cancelled"}}
    
    @EventHandler("scheduler:list")
    async def handle_list_schedules(self, event: Event) -> Dict:
        """List scheduled events for an episode."""
        data = event.data
        episode_id = data.get("episode_id")
        
        if episode_id:
            event_ids = self.episode_schedules.get(episode_id, [])
            schedules = [self.scheduled_events[eid] for eid in event_ids if eid in self.scheduled_events]
        else:
            schedules = list(self.scheduled_events.values())
        
        result = []
        for scheduled_event in schedules:
            next_time = self._calculate_next_execution(scheduled_event)
            result.append({
                "event_id": scheduled_event.event_id,
                "episode_id": scheduled_event.episode_id,
                "event_type": scheduled_event.event_type,
                "schedule_type": scheduled_event.schedule_type.value,
                "enabled": scheduled_event.enabled,
                "execution_count": scheduled_event.execution_count,
                "next_execution": next_time,
                "priority": scheduled_event.priority
            })
        
        return {"result": result}
    
    @EventHandler("scheduler:episode_ended")
    async def handle_episode_ended(self, event: Event) -> Dict:
        """Clean up schedules when episode ends."""
        data = event.data
        episode_id = data["episode_id"]
        
        # Cancel all schedules for this episode
        event_ids = self.episode_schedules.get(episode_id, []).copy()
        
        for event_id in event_ids:
            if event_id in self.scheduled_events:
                del self.scheduled_events[event_id]
        
        # Clean up episode entry
        if episode_id in self.episode_schedules:
            del self.episode_schedules[episode_id]
        
        # Remove from queue
        self.event_queue = [(t, eid) for t, eid in self.event_queue 
                           if eid not in event_ids]
        heapq.heapify(self.event_queue)
        
        self.logger.info(f"Cleaned up {len(event_ids)} scheduled events for episode {episode_id}")
        
        return {"result": {"cleaned_up": len(event_ids)}}
    
    # ==================== PRESET SCHEDULES ====================
    
    @EventHandler("scheduler:create_preset")
    async def handle_create_preset(self, event: Event) -> Dict:
        """Create a preset scheduled event pattern."""
        data = event.data
        preset_name = data["preset"]
        episode_id = data["episode_id"]
        
        if preset_name not in self.patterns:
            return {"error": f"Unknown preset: {preset_name}"}
        
        pattern = self.patterns[preset_name]
        
        # Create scheduled event based on pattern
        if preset_name == "resource_regeneration":
            return await self._create_resource_regeneration(episode_id, data)
        elif preset_name == "pollution_growth":
            return await self._create_pollution_growth(episode_id, data)
        elif preset_name == "metric_calculation":
            return await self._create_metric_calculation(episode_id, data)
        elif preset_name == "victory_check":
            return await self._create_victory_check(episode_id, data)
        elif preset_name == "spawn_resources":
            return await self._create_resource_spawning(episode_id, data)
        
        return {"error": "Preset not implemented"}
    
    async def _create_resource_regeneration(self, episode_id: str, config: Dict) -> Dict:
        """Create resource regeneration schedule."""
        event_data = {
            "resource_type": config.get("resource_type", "commons_resource"),
            "regeneration_rate": config.get("regeneration_rate", 0.1),
            "max_amount": config.get("max_amount", 100),
            "location": config.get("location", {"x": 12, "y": 12})
        }
        
        scheduled_event = ScheduledEvent(
            event_id=f"regen_{episode_id}_{int(time.time())}",
            episode_id=episode_id,
            event_type="resource:regenerate",
            event_data=event_data,
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval": config.get("interval", 5.0)},
            priority=5,
            metadata={"preset": "resource_regeneration"}
        )
        
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[episode_id].append(scheduled_event.event_id)
        
        next_time = self._calculate_next_execution(scheduled_event)
        heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        return {"result": {"event_id": scheduled_event.event_id}}
    
    async def _create_pollution_growth(self, episode_id: str, config: Dict) -> Dict:
        """Create pollution growth schedule."""
        event_data = {
            "pollution_type": config.get("pollution_type", "industrial"),
            "growth_rate": config.get("growth_rate", 0.05),
            "affected_area": config.get("affected_area", {"radius": 10})
        }
        
        scheduled_event = ScheduledEvent(
            event_id=f"pollution_{episode_id}_{int(time.time())}",
            episode_id=episode_id,
            event_type="resource:pollution_growth",
            event_data=event_data,
            schedule_type=ScheduleType.EXPONENTIAL,
            schedule_config={
                "base_interval": config.get("base_interval", 10.0),
                "growth_factor": config.get("growth_factor", 1.1),
                "max_interval": config.get("max_interval", 60.0)
            },
            priority=3,
            metadata={"preset": "pollution_growth"}
        )
        
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[episode_id].append(scheduled_event.event_id)
        
        next_time = self._calculate_next_execution(scheduled_event)
        heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        return {"result": {"event_id": scheduled_event.event_id}}
    
    async def _create_metric_calculation(self, episode_id: str, config: Dict) -> Dict:
        """Create periodic metric calculation."""
        event_data = {
            "metric_types": config.get("metric_types", ["gini", "collective_return", "cooperation_rate"]),
            "data_source": {"episode_id": episode_id},
            "save_history": config.get("save_history", True)
        }
        
        scheduled_event = ScheduledEvent(
            event_id=f"metrics_{episode_id}_{int(time.time())}",
            episode_id=episode_id,
            event_type="metrics:calculate",
            event_data=event_data,
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval": config.get("interval", 10.0)},
            priority=2,
            metadata={"preset": "metric_calculation"}
        )
        
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[episode_id].append(scheduled_event.event_id)
        
        next_time = self._calculate_next_execution(scheduled_event)
        heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        return {"result": {"event_id": scheduled_event.event_id}}
    
    async def _create_victory_check(self, episode_id: str, config: Dict) -> Dict:
        """Create victory condition checking."""
        event_data = {
            "episode_id": episode_id,
            "victory_conditions": config.get("victory_conditions", [])
        }
        
        scheduled_event = ScheduledEvent(
            event_id=f"victory_{episode_id}_{int(time.time())}",
            episode_id=episode_id,
            event_type="episode:check_victory",
            event_data=event_data,
            schedule_type=ScheduleType.INTERVAL,
            schedule_config={"interval": config.get("interval", 1.0)},
            priority=10,  # High priority
            metadata={"preset": "victory_check"}
        )
        
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[episode_id].append(scheduled_event.event_id)
        
        next_time = self._calculate_next_execution(scheduled_event)
        heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        return {"result": {"event_id": scheduled_event.event_id}}
    
    async def _create_resource_spawning(self, episode_id: str, config: Dict) -> Dict:
        """Create conditional resource spawning."""
        event_data = {
            "resource_types": config.get("resource_types", ["food", "water"]),
            "spawn_locations": config.get("spawn_locations", []),
            "threshold": config.get("threshold", 10)
        }
        
        # Define condition function
        async def check_resource_threshold():
            # Query current resource levels
            result = await self.emit_event("resource:query", {
                "query_type": "aggregate",
                "parameters": {"resource_types": event_data["resource_types"]}
            })
            total = result.get("result", {}).get("total", 0)
            return total < event_data["threshold"]
        
        scheduled_event = ScheduledEvent(
            event_id=f"spawn_{episode_id}_{int(time.time())}",
            episode_id=episode_id,
            event_type="resource:spawn_batch",
            event_data=event_data,
            schedule_type=ScheduleType.CONDITIONAL,
            schedule_config={
                "check_interval": config.get("check_interval", 5.0),
                "condition_event": "resource:below_threshold"
            },
            priority=4,
            condition=check_resource_threshold,
            metadata={"preset": "spawn_resources"}
        )
        
        self.scheduled_events[scheduled_event.event_id] = scheduled_event
        self.episode_schedules[episode_id].append(scheduled_event.event_id)
        
        next_time = self._calculate_next_execution(scheduled_event)
        heapq.heappush(self.event_queue, (next_time, scheduled_event.event_id))
        
        return {"result": {"event_id": scheduled_event.event_id}}
    
    # ==================== SCHEDULER LOOP ====================
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                current_time = time.time()
                
                # Process due events
                while self.event_queue and self.event_queue[0][0] <= current_time:
                    _, event_id = heapq.heappop(self.event_queue)
                    
                    if event_id in self.scheduled_events:
                        scheduled_event = self.scheduled_events[event_id]
                        
                        if scheduled_event.enabled:
                            await self._execute_scheduled_event(scheduled_event)
                            
                            # Schedule next execution if needed
                            if self._should_reschedule(scheduled_event):
                                next_time = self._calculate_next_execution(scheduled_event)
                                if next_time:
                                    heapq.heappush(self.event_queue, (next_time, event_id))
                
                # Sleep until next event or 1 second
                if self.event_queue:
                    sleep_time = min(1.0, max(0.01, self.event_queue[0][0] - time.time()))
                else:
                    sleep_time = 1.0
                
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _execute_scheduled_event(self, scheduled_event: ScheduledEvent):
        """Execute a scheduled event."""
        try:
            # Check condition if present
            if scheduled_event.condition:
                if not await scheduled_event.condition():
                    self.logger.debug(f"Condition not met for {scheduled_event.event_id}")
                    return
            
            # Emit the scheduled event
            await self.emit_event(scheduled_event.event_type, scheduled_event.event_data)
            
            # Update execution info
            scheduled_event.last_execution = time.time()
            scheduled_event.execution_count += 1
            
            self.logger.debug(f"Executed scheduled event: {scheduled_event.event_id} "
                            f"(count: {scheduled_event.execution_count})")
            
        except Exception as e:
            self.logger.error(f"Error executing scheduled event {scheduled_event.event_id}: {e}")
    
    def _calculate_next_execution(self, scheduled_event: ScheduledEvent) -> Optional[float]:
        """Calculate next execution time for a scheduled event."""
        current_time = time.time()
        
        if scheduled_event.schedule_type == ScheduleType.INTERVAL:
            interval = scheduled_event.schedule_config.get("interval", 1.0)
            if scheduled_event.last_execution:
                return scheduled_event.last_execution + interval
            else:
                return current_time + interval
        
        elif scheduled_event.schedule_type == ScheduleType.EXPONENTIAL:
            base = scheduled_event.schedule_config.get("base_interval", 1.0)
            factor = scheduled_event.schedule_config.get("growth_factor", 2.0)
            max_interval = scheduled_event.schedule_config.get("max_interval", 3600.0)
            
            # Calculate exponential interval
            interval = base * (factor ** scheduled_event.execution_count)
            interval = min(interval, max_interval)
            
            if scheduled_event.last_execution:
                return scheduled_event.last_execution + interval
            else:
                return current_time + interval
        
        elif scheduled_event.schedule_type == ScheduleType.CONDITIONAL:
            # Check at regular intervals
            check_interval = scheduled_event.schedule_config.get("check_interval", 5.0)
            return current_time + check_interval
        
        elif scheduled_event.schedule_type == ScheduleType.ONE_TIME:
            # Execute once at specified time
            if scheduled_event.execution_count == 0:
                delay = scheduled_event.schedule_config.get("delay", 0)
                return current_time + delay
            else:
                return None  # Already executed
        
        elif scheduled_event.schedule_type == ScheduleType.CRON:
            # Parse cron expression (simplified)
            # For now, just use interval as fallback
            interval = scheduled_event.schedule_config.get("interval", 60.0)
            return current_time + interval
        
        return None
    
    def _should_reschedule(self, scheduled_event: ScheduledEvent) -> bool:
        """Check if event should be rescheduled."""
        # Check max executions
        if scheduled_event.max_executions:
            if scheduled_event.execution_count >= scheduled_event.max_executions:
                return False
        
        # One-time events don't reschedule
        if scheduled_event.schedule_type == ScheduleType.ONE_TIME:
            return False
        
        return scheduled_event.enabled
    
    @EventHandler("scheduler:get_stats")
    async def handle_get_stats(self, event: Event) -> Dict:
        """Get scheduler statistics."""
        stats = {
            "total_scheduled": len(self.scheduled_events),
            "enabled": sum(1 for e in self.scheduled_events.values() if e.enabled),
            "disabled": sum(1 for e in self.scheduled_events.values() if not e.enabled),
            "episodes_active": len(self.episode_schedules),
            "queue_size": len(self.event_queue),
            "by_type": defaultdict(int),
            "by_episode": {}
        }
        
        # Count by type
        for scheduled_event in self.scheduled_events.values():
            stats["by_type"][scheduled_event.schedule_type.value] += 1
        
        # Count by episode
        for episode_id, event_ids in self.episode_schedules.items():
            stats["by_episode"][episode_id] = len(event_ids)
        
        # Next scheduled events
        if self.event_queue:
            next_events = sorted(self.event_queue)[:5]
            stats["next_events"] = [
                {
                    "time": next_time,
                    "event_id": event_id,
                    "seconds_until": next_time - time.time()
                }
                for next_time, event_id in next_events
            ]
        
        return {"result": stats}


# ==================== SERVICE INITIALIZATION ====================

def create_scheduler_service():
    """Create and initialize the scheduler service."""
    return ScheduledEventService()


if __name__ == "__main__":
    # Example usage
    print("Scheduled Event Service")
    print("="*40)
    print("Provides scheduling capabilities for:")
    print("- Resource regeneration")
    print("- Pollution growth")
    print("- Periodic metrics")
    print("- Victory conditions")
    print("- Conditional spawning")
    print("\nSchedule types:")
    print("- Interval (every N seconds)")
    print("- Exponential (growing intervals)")
    print("- Conditional (based on state)")
    print("- One-time (single execution)")
    print("- Cron-like patterns")