#!/usr/bin/env python3
"""
Example service demonstrating checkpoint participation utility.

This is a simple counter service that maintains state and uses the
checkpoint_participant decorator to persist its state across restarts.
"""

from typing import Dict, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder
from ksi_common.checkpoint_participation import checkpoint_participant
from ksi_common.service_lifecycle import service_startup, service_shutdown

logger = get_bound_logger("example_checkpoint_service", version="1.0.0")


@checkpoint_participant("example_counter")
class CounterService:
    """Example service that maintains a counter with checkpoint support."""
    
    def __init__(self):
        """Initialize the counter service."""
        self.counters: Dict[str, int] = {}
        self.total_operations = 0
        self.config = {
            "max_counters": 100,
            "auto_reset_threshold": 1000
        }
        logger.info("Counter service initialized")
    
    def increment(self, counter_name: str, amount: int = 1) -> int:
        """Increment a counter."""
        if counter_name not in self.counters:
            if len(self.counters) >= self.config["max_counters"]:
                raise ValueError(f"Maximum number of counters ({self.config['max_counters']}) reached")
            self.counters[counter_name] = 0
        
        self.counters[counter_name] += amount
        self.total_operations += 1
        
        # Auto-reset if threshold reached
        if self.counters[counter_name] > self.config["auto_reset_threshold"]:
            self.counters[counter_name] = 0
            logger.info(f"Counter {counter_name} auto-reset at threshold")
        
        return self.counters[counter_name]
    
    def get_counter(self, counter_name: str) -> int:
        """Get current value of a counter."""
        return self.counters.get(counter_name, 0)
    
    def get_all_counters(self) -> Dict[str, int]:
        """Get all counters."""
        return self.counters.copy()
    
    def reset_counter(self, counter_name: str) -> bool:
        """Reset a specific counter."""
        if counter_name in self.counters:
            self.counters[counter_name] = 0
            self.total_operations += 1
            return True
        return False
    
    def collect_checkpoint_data(self) -> Dict[str, Any]:
        """Collect data for checkpoint.
        
        This method is called by the checkpoint system to save state.
        """
        logger.info(f"Collecting checkpoint data: {len(self.counters)} counters, "
                   f"{self.total_operations} total operations")
        
        return {
            "counters": self.counters.copy(),
            "total_operations": self.total_operations,
            "config": self.config.copy()
        }
    
    def restore_from_checkpoint(self, data: Dict[str, Any]) -> None:
        """Restore service state from checkpoint.
        
        This method is called by the checkpoint system during restore.
        """
        self.counters = data.get("counters", {})
        self.total_operations = data.get("total_operations", 0)
        
        # Merge config, keeping new defaults for missing keys
        saved_config = data.get("config", {})
        self.config.update(saved_config)
        
        logger.info(f"Restored from checkpoint: {len(self.counters)} counters, "
                   f"{self.total_operations} total operations")


# Create singleton service instance
counter_service = CounterService()


# Event handlers

@service_startup("example_counter", load_transformers=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize service on startup."""
    logger.info("Example counter service started")
    return {"status": "ready", "counters": len(counter_service.counters)}


@service_shutdown("example_counter")
async def handle_shutdown(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    logger.info(f"Counter service shutting down with {counter_service.total_operations} total operations")


@event_handler("counter:increment")
async def handle_increment(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Increment a counter."""
    counter_name = data.get("name", "default")
    amount = data.get("amount", 1)
    
    try:
        new_value = counter_service.increment(counter_name, amount)
        return event_response_builder({
            "counter": counter_name,
            "value": new_value,
            "total_operations": counter_service.total_operations
        }, context)
    except ValueError as e:
        return event_response_builder({
            "error": str(e),
            "max_counters": counter_service.config["max_counters"]
        }, context)


@event_handler("counter:get")
async def handle_get(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get counter value."""
    counter_name = data.get("name", "default")
    value = counter_service.get_counter(counter_name)
    
    return event_response_builder({
        "counter": counter_name,
        "value": value
    }, context)


@event_handler("counter:list")
async def handle_list(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all counters."""
    counters = counter_service.get_all_counters()
    
    return event_response_builder({
        "counters": counters,
        "total": len(counters),
        "total_operations": counter_service.total_operations
    }, context)


@event_handler("counter:reset")
async def handle_reset(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reset a counter."""
    counter_name = data.get("name")
    
    if not counter_name:
        return event_response_builder({
            "error": "Counter name required"
        }, context)
    
    if counter_service.reset_counter(counter_name):
        return event_response_builder({
            "counter": counter_name,
            "status": "reset"
        }, context)
    else:
        return event_response_builder({
            "error": f"Counter '{counter_name}' not found"
        }, context)