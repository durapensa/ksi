#!/usr/bin/env python3
"""
Checkpoint Participation Utility

Provides a simple decorator and base class for services to participate in the 
checkpoint/restore system without boilerplate code.

Usage:
    # Simple usage with decorator
    @checkpoint_participant("my_service")
    class MyService:
        def collect_checkpoint_data(self) -> Dict[str, Any]:
            return {"my_state": self.state}
            
        def restore_from_checkpoint(self, data: Dict[str, Any]) -> None:
            self.state = data.get("my_state", {})

    # Or use the base class
    class MyService(CheckpointParticipant):
        def __init__(self):
            super().__init__("my_service")
            
        def collect_checkpoint_data(self) -> Dict[str, Any]:
            return {"my_state": self.state}
            
        def restore_from_checkpoint(self, data: Dict[str, Any]) -> None:
            self.state = data.get("my_state", {})
"""

from typing import Dict, Any, Optional, Callable, TypeVar, Protocol
from functools import wraps
import asyncio
import inspect

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder

logger = get_bound_logger("checkpoint_participation", version="1.0.0")

T = TypeVar('T')


class CheckpointInterface(Protocol):
    """Protocol defining the checkpoint interface services must implement."""
    
    def collect_checkpoint_data(self) -> Dict[str, Any]:
        """Collect data to include in checkpoint."""
        ...
    
    def restore_from_checkpoint(self, data: Dict[str, Any]) -> None:
        """Restore service state from checkpoint data."""
        ...


class CheckpointParticipant:
    """Base class for services that participate in checkpointing."""
    
    def __init__(self, service_name: str):
        """Initialize checkpoint participant.
        
        Args:
            service_name: Unique name for this service in checkpoints
        """
        self.service_name = service_name
        self._register_handlers()
    
    def _register_handlers(self):
        """Register checkpoint event handlers."""
        # Store references to handlers for potential cleanup
        self._collect_handler = self._create_collect_handler()
        self._restore_handler = self._create_restore_handler()
    
    def _create_collect_handler(self):
        """Create the checkpoint:collect handler."""
        @event_handler("checkpoint:collect")
        async def collect_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            try:
                # Call the service's collect method
                checkpoint_data = self.collect_checkpoint_data()
                
                # Handle both sync and async collect methods
                if asyncio.iscoroutine(checkpoint_data):
                    checkpoint_data = await checkpoint_data
                
                logger.info(f"Collected checkpoint data for {self.service_name}")
                
                return event_response_builder({
                    f"{self.service_name}_state": checkpoint_data
                }, context)
            except Exception as e:
                logger.error(f"Failed to collect {self.service_name} checkpoint: {e}")
                return event_response_builder({
                    f"{self.service_name}_state": {}
                }, context)
        
        return collect_handler
    
    def _create_restore_handler(self):
        """Create the checkpoint:restore handler."""
        @event_handler("checkpoint:restore")
        async def restore_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            checkpoint_data = data.get(f"{self.service_name}_state", {})
            
            if not checkpoint_data:
                logger.info(f"No {self.service_name} state in checkpoint to restore")
                return event_response_builder({
                    "status": f"no_{self.service_name}_state"
                }, context)
            
            try:
                # Call the service's restore method
                result = self.restore_from_checkpoint(checkpoint_data)
                
                # Handle both sync and async restore methods
                if asyncio.iscoroutine(result):
                    await result
                
                logger.info(f"Restored {self.service_name} state from checkpoint")
                
                return event_response_builder({
                    "status": "restored",
                    "service": self.service_name
                }, context)
            except Exception as e:
                logger.error(f"Failed to restore {self.service_name} checkpoint: {e}")
                return event_response_builder({
                    "status": "error",
                    "service": self.service_name,
                    "error": str(e)
                }, context)
        
        return restore_handler
    
    def collect_checkpoint_data(self) -> Dict[str, Any]:
        """Collect data to include in checkpoint.
        
        Subclasses must implement this method.
        
        Returns:
            Dictionary of data to checkpoint
        """
        raise NotImplementedError("Subclasses must implement collect_checkpoint_data")
    
    def restore_from_checkpoint(self, data: Dict[str, Any]) -> None:
        """Restore service state from checkpoint data.
        
        Subclasses must implement this method.
        
        Args:
            data: Checkpoint data for this service
        """
        raise NotImplementedError("Subclasses must implement restore_from_checkpoint")


def checkpoint_participant(service_name: str) -> Callable[[type[T]], type[T]]:
    """Decorator to make a class a checkpoint participant.
    
    The decorated class must implement:
    - collect_checkpoint_data() -> Dict[str, Any]
    - restore_from_checkpoint(data: Dict[str, Any]) -> None
    
    Args:
        service_name: Unique name for this service in checkpoints
        
    Returns:
        Class decorator
        
    Example:
        @checkpoint_participant("my_service")
        class MyService:
            def collect_checkpoint_data(self):
                return {"state": self.state}
                
            def restore_from_checkpoint(self, data):
                self.state = data.get("state", {})
    """
    def decorator(cls: type[T]) -> type[T]:
        # Store original __init__
        original_init = cls.__init__
        
        # Create wrapper that adds checkpoint handlers
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Call original init
            original_init(self, *args, **kwargs)
            
            # Create and register handlers
            @event_handler("checkpoint:collect")
            async def collect_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                try:
                    # Call the instance's collect method
                    checkpoint_data = self.collect_checkpoint_data()
                    
                    # Handle both sync and async collect methods
                    if asyncio.iscoroutine(checkpoint_data):
                        checkpoint_data = await checkpoint_data
                    
                    logger.info(f"Collected checkpoint data for {service_name}")
                    
                    return event_response_builder({
                        f"{service_name}_state": checkpoint_data
                    }, context)
                except Exception as e:
                    logger.error(f"Failed to collect {service_name} checkpoint: {e}")
                    return event_response_builder({
                        f"{service_name}_state": {}
                    }, context)
            
            @event_handler("checkpoint:restore")
            async def restore_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                checkpoint_data = data.get(f"{service_name}_state", {})
                
                if not checkpoint_data:
                    logger.info(f"No {service_name} state in checkpoint to restore")
                    return event_response_builder({
                        "status": f"no_{service_name}_state"
                    }, context)
                
                try:
                    # Call the instance's restore method
                    result = self.restore_from_checkpoint(checkpoint_data)
                    
                    # Handle both sync and async restore methods
                    if asyncio.iscoroutine(result):
                        await result
                    
                    logger.info(f"Restored {service_name} state from checkpoint")
                    
                    return event_response_builder({
                        "status": "restored",
                        "service": service_name
                    }, context)
                except Exception as e:
                    logger.error(f"Failed to restore {service_name} checkpoint: {e}")
                    return event_response_builder({
                        "status": "error",
                        "service": service_name,
                        "error": str(e)
                    }, context)
            
            # Store handler references on the instance
            self._checkpoint_collect_handler = collect_handler
            self._checkpoint_restore_handler = restore_handler
            self._checkpoint_service_name = service_name
        
        # Replace __init__
        cls.__init__ = new_init
        
        # Add marker to indicate this class is checkpoint-enabled
        cls._checkpoint_participant = True
        cls._checkpoint_service_name = service_name
        
        return cls
    
    return decorator


# Utility functions for manual checkpoint participation

async def register_checkpoint_handlers(
    service_name: str,
    collect_fn: Callable[[], Dict[str, Any]],
    restore_fn: Callable[[Dict[str, Any]], None]
) -> Dict[str, Any]:
    """Register checkpoint handlers for a service manually.
    
    This is useful for services that can't use the decorator or base class.
    
    Args:
        service_name: Unique name for this service in checkpoints
        collect_fn: Function to collect checkpoint data
        restore_fn: Function to restore from checkpoint data
        
    Returns:
        Dictionary with handler references
        
    Example:
        async def setup_my_service():
            def collect():
                return {"state": my_state}
                
            def restore(data):
                global my_state
                my_state = data.get("state", {})
                
            await register_checkpoint_handlers("my_service", collect, restore)
    """
    @event_handler("checkpoint:collect")
    async def collect_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            # Call the collect function
            checkpoint_data = collect_fn()
            
            # Handle both sync and async functions
            if asyncio.iscoroutine(checkpoint_data):
                checkpoint_data = await checkpoint_data
            
            logger.info(f"Collected checkpoint data for {service_name}")
            
            return event_response_builder({
                f"{service_name}_state": checkpoint_data
            }, context)
        except Exception as e:
            logger.error(f"Failed to collect {service_name} checkpoint: {e}")
            return event_response_builder({
                f"{service_name}_state": {}
            }, context)
    
    @event_handler("checkpoint:restore")
    async def restore_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        checkpoint_data = data.get(f"{service_name}_state", {})
        
        if not checkpoint_data:
            logger.info(f"No {service_name} state in checkpoint to restore")
            return event_response_builder({
                "status": f"no_{service_name}_state"
            }, context)
        
        try:
            # Call the restore function
            result = restore_fn(checkpoint_data)
            
            # Handle both sync and async functions
            if asyncio.iscoroutine(result):
                await result
            
            logger.info(f"Restored {service_name} state from checkpoint")
            
            return event_response_builder({
                "status": "restored",
                "service": service_name
            }, context)
        except Exception as e:
            logger.error(f"Failed to restore {service_name} checkpoint: {e}")
            return event_response_builder({
                "status": "error",
                "service": service_name,
                "error": str(e)
            }, context)
    
    return {
        "collect_handler": collect_handler,
        "restore_handler": restore_handler,
        "service_name": service_name
    }