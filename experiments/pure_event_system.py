#!/usr/bin/env python3
"""
Pure Event-Based System Prototype

Demonstrates how KSI could work without pluggy, using only
events and async patterns.
"""

import asyncio
import inspect
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, TypeVar, get_type_hints
from functools import wraps
import sys

# Type definitions
T = TypeVar('T')


class EventRouter:
    """Pure async event router - the heart of the system."""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._modules: Dict[str, Any] = {}
        self._middleware: List[Callable] = []
        
    async def emit(self, event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Emit event to all handlers."""
        handlers = self._handlers.get(event, [])
        
        if not handlers:
            return []
        
        # Apply middleware
        for mw in self._middleware:
            data = await mw(event, data, context)
        
        # Run handlers concurrently
        tasks = []
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                tasks.append(handler(data))
            else:
                # Wrap sync handlers
                tasks.append(asyncio.create_task(asyncio.to_thread(handler, data)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions but log them
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                print(f"Handler error for {event}: {r}")
            else:
                valid_results.append(r)
        
        return valid_results
    
    def on(self, event: str):
        """Decorator for registering event handlers."""
        def decorator(func: Callable) -> Callable:
            self.register_handler(event, func)
            return func
        return decorator
    
    def register_handler(self, event: str, handler: Callable):
        """Register an event handler."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        print(f"Registered handler for {event}: {handler.__name__}")
    
    def use_middleware(self, middleware: Callable):
        """Add middleware for all events."""
        self._middleware.append(middleware)


class ModuleLoader:
    """Simple module discovery and loading."""
    
    def __init__(self, router: EventRouter):
        self.router = router
        self.modules = {}
        
    async def load_module(self, module_path: Path):
        """Load a module and register its handlers."""
        # Dynamic import
        spec = importlib.util.spec_from_file_location(
            f"ksi_module_{module_path.stem}", 
            module_path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        
        # Find all event handlers
        handlers_found = 0
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, '_event_name'):
                event = obj._event_name
                self.router.register_handler(event, obj)
                handlers_found += 1
        
        # Module lifecycle - initialize
        if hasattr(module, 'initialize'):
            await module.initialize(self.router)
        
        self.modules[module_path.stem] = module
        print(f"Loaded module {module_path.stem} with {handlers_found} handlers")
        
        # Emit module loaded event
        await self.router.emit("module:loaded", {
            "name": module_path.stem,
            "handlers": handlers_found
        })
    
    async def unload_module(self, name: str):
        """Unload a module."""
        if name in self.modules:
            module = self.modules[name]
            
            # Module lifecycle - shutdown
            if hasattr(module, 'shutdown'):
                await module.shutdown()
            
            del self.modules[name]
            
            # Emit module unloaded event
            await self.router.emit("module:unloaded", {"name": name})


# Event handler decorator
def event_handler(event_name: str):
    """Decorator for marking event handlers."""
    def decorator(func):
        func._event_name = event_name
        return func
    return decorator


# Global router instance (would be injected in real system)
_global_router: Optional[EventRouter] = None


async def emit_event(event: str, data: Any) -> List[Any]:
    """Emit an event through the global router."""
    if _global_router:
        return await _global_router.emit(event, data)
    return []


# Example modules to demonstrate the system

# Module 1: State Manager
STATE_CONTENT = '''
from typing import Dict, Any

# Module state
_state: Dict[str, Dict[str, Any]] = {}

@event_handler("state:set")
async def handle_state_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set a value in state."""
    namespace = data.get("namespace", "default")
    key = data["key"]
    value = data["value"]
    
    if namespace not in _state:
        _state[namespace] = {}
    
    _state[namespace][key] = value
    
    # Emit state changed event
    await emit_event("state:changed", {
        "namespace": namespace,
        "key": key,
        "value": value
    })
    
    return {"status": "set", "namespace": namespace, "key": key}

@event_handler("state:get")
async def handle_state_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a value from state."""
    namespace = data.get("namespace", "default")
    key = data["key"]
    
    value = _state.get(namespace, {}).get(key)
    return {"value": value, "found": value is not None}

async def initialize(router):
    """Initialize module."""
    print("State manager initialized")
    await router.emit("module:ready", {"module": "state_manager"})
'''

# Module 2: Logger
LOGGER_CONTENT = '''
from datetime import datetime
from typing import Dict, Any

@event_handler("*")  # Special pattern for all events
async def log_all_events(data: Dict[str, Any]):
    """Log all events."""
    # In real implementation, would check event context for actual event name
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] Event received with data: {data}")

@event_handler("state:changed")
async def log_state_changes(data: Dict[str, Any]):
    """Log state changes specifically."""
    print(f"State changed: {data['namespace']}.{data['key']} = {data['value']}")
'''


async def demo():
    """Demonstrate the pure event system."""
    # Create router
    router = EventRouter()
    global _global_router
    _global_router = router
    
    # Add middleware
    async def timing_middleware(event: str, data: Any, context: Any) -> Any:
        # In real system, would measure timing
        print(f"-> Event: {event}")
        return data
    
    router.use_middleware(timing_middleware)
    
    # Create loader
    loader = ModuleLoader(router)
    
    # Create example module files
    state_module = Path("state_manager.py")
    state_module.write_text(STATE_CONTENT)
    
    logger_module = Path("logger_module.py") 
    logger_module.write_text(LOGGER_CONTENT)
    
    try:
        # Load modules
        await loader.load_module(state_module)
        await loader.load_module(logger_module)
        
        print("\n--- Testing Events ---")
        
        # Test state management
        result = await router.emit("state:set", {
            "namespace": "config",
            "key": "debug",
            "value": True
        })
        print(f"Set result: {result}")
        
        result = await router.emit("state:get", {
            "namespace": "config",
            "key": "debug"
        })
        print(f"Get result: {result}")
        
        # Test unknown event
        result = await router.emit("unknown:event", {"test": "data"})
        print(f"Unknown event result: {result}")
        
        print("\n--- Module Management ---")
        
        # Unload a module
        await loader.unload_module("logger_module")
        
        # Test after unload
        print("\nAfter unloading logger:")
        await router.emit("state:set", {
            "namespace": "config",
            "key": "verbose",
            "value": False
        })
        
    finally:
        # Cleanup
        state_module.unlink(missing_ok=True)
        logger_module.unlink(missing_ok=True)


def main():
    """Run the demo."""
    print("Pure Event-Based System Demo")
    print("=" * 40)
    asyncio.run(demo())


if __name__ == "__main__":
    # Make event_handler and emit_event available to loaded modules
    import builtins
    builtins.event_handler = event_handler
    builtins.emit_event = emit_event
    
    main()