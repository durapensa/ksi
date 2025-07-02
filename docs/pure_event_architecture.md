# Pure Event-Based Architecture for KSI

## Executive Summary

This document outlines how KSI could be reimplemented as a pure event-driven system without pluggy, using modern Python async patterns and explicit event registration.

## Architecture Overview

### Core Components

1. **Event Router** - Central message broker
2. **Module Registry** - Simple module discovery and loading
3. **Event Handlers** - Pure async functions with decorators
4. **Event Schema** - TypedDict-based event definitions
5. **Module Lifecycle** - Explicit initialization/shutdown

### Key Differences from Pluggy

| Aspect | Pluggy-based | Pure Event-based |
|--------|--------------|------------------|
| Discovery | Hook specs | Event decorators |
| Loading | Plugin manager | Module imports |
| Communication | Hooks + events | Events only |
| Lifecycle | Hooks (startup, ready) | Event subscriptions |
| Dependencies | Implicit via hooks | Explicit via events |
| Async | Wrapper complexity | Native async/await |

## Implementation Design

### 1. Module Structure

```python
# Each module is a simple Python file with event handlers
# modules/completion.py

from ksi.events import event_handler, emit_event
from ksi.types import CompletionRequest, CompletionResponse

@event_handler("completion:request")
async def handle_completion(data: CompletionRequest) -> CompletionResponse:
    """Handle completion requests."""
    # Process request
    result = await process_completion(data)
    
    # Emit result event
    await emit_event("completion:result", result)
    
    return result
```

### 2. Event Router (Core)

```python
# ksi/router.py

class EventRouter:
    """Pure async event router."""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._modules: Dict[str, Any] = {}
        
    async def emit(self, event: str, data: Any) -> List[Any]:
        """Emit event to all handlers."""
        handlers = self._handlers.get(event, [])
        
        # Run handlers concurrently
        if handlers:
            tasks = [handler(data) for handler in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            return [r for r in results if not isinstance(r, Exception)]
        
        return []
    
    def register_handler(self, event: str, handler: Callable):
        """Register an event handler."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
```

### 3. Module Loading

```python
# ksi/loader.py

class ModuleLoader:
    """Simple module discovery and loading."""
    
    def __init__(self, router: EventRouter):
        self.router = router
        self.modules = {}
        
    async def load_module(self, path: Path):
        """Load a module and register its handlers."""
        spec = importlib.util.spec_from_file_location("module", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find all event handlers
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, '_event_handler'):
                event = obj._event_handler
                self.router.register_handler(event, obj)
        
        # Initialize module if needed
        if hasattr(module, 'initialize'):
            await module.initialize(self.router)
        
        self.modules[path.stem] = module
```

### 4. Event Decorators

```python
# ksi/events.py

def event_handler(event: str):
    """Decorator for event handlers."""
    def decorator(func):
        func._event_handler = event
        return func
    return decorator

# Global router instance
_router = None

async def emit_event(event: str, data: Any) -> List[Any]:
    """Emit an event through the global router."""
    if _router:
        return await _router.emit(event, data)
    return []
```

### 5. Type-Safe Events

```python
# ksi/types.py

from typing import TypedDict, Literal, Any

class CompletionRequest(TypedDict):
    prompt: str
    model: str
    temperature: float
    
class StateUpdate(TypedDict):
    namespace: str
    key: str
    value: Any
    operation: Literal["set", "get", "delete"]
```

## Migration Path

### Phase 1: Parallel Implementation
- Implement pure event router alongside pluggy
- Create adapter layer for existing plugins
- Test with select modules

### Phase 2: Module Conversion
- Convert plugins to pure modules one by one
- Maintain backward compatibility via adapters
- Validate functionality at each step

### Phase 3: Remove Pluggy
- Remove pluggy dependencies
- Clean up adapter code
- Simplify initialization

## Benefits

1. **Simplicity**
   - No hook specs to maintain
   - Direct async/await patterns
   - Clear event flow

2. **Performance**
   - Native async execution
   - No synchronous bottlenecks
   - Efficient event routing

3. **Type Safety**
   - TypedDict event schemas
   - Static type checking
   - Better IDE support

4. **Flexibility**
   - Dynamic event registration
   - Runtime module loading
   - Easy testing

5. **Debugging**
   - Clear stack traces
   - Event flow visualization
   - Simpler profiling

## Example: Complete Module

```python
# modules/state_manager.py

from ksi.events import event_handler, emit_event
from ksi.types import StateUpdate, StateQuery
from typing import Dict, Any

# Module state
_state: Dict[str, Dict[str, Any]] = {}

@event_handler("state:update")
async def handle_state_update(data: StateUpdate) -> Dict[str, Any]:
    """Handle state updates."""
    namespace = data["namespace"]
    key = data["key"]
    
    if namespace not in _state:
        _state[namespace] = {}
    
    if data["operation"] == "set":
        _state[namespace][key] = data["value"]
        await emit_event("state:changed", {
            "namespace": namespace,
            "key": key,
            "value": data["value"]
        })
        return {"status": "set"}
        
    elif data["operation"] == "get":
        value = _state.get(namespace, {}).get(key)
        return {"value": value}
        
    elif data["operation"] == "delete":
        if namespace in _state and key in _state[namespace]:
            del _state[namespace][key]
            await emit_event("state:deleted", {
                "namespace": namespace,
                "key": key
            })
        return {"status": "deleted"}

@event_handler("module:shutdown")
async def handle_shutdown(data: Dict[str, Any]):
    """Clean shutdown."""
    # Persist state if needed
    await emit_event("state:persisting", {"namespaces": list(_state.keys())})
    # Clean up resources
    _state.clear()
```

## Considerations

### Pros
- Simpler mental model
- Better async support
- Easier testing
- More Pythonic
- Better type safety

### Cons
- Loss of pluggy ecosystem
- Need to rebuild some features
- Migration effort
- Less battle-tested

## Recommendation

Given that:
1. KSI already uses events for most communication
2. Pluggy's sync-first design causes complexity
3. The team is open to breaking changes
4. Type safety is valuable

**Recommendation**: Proceed with pure event-based architecture. The benefits of simplicity, performance, and type safety outweigh the migration costs.

## Next Steps

1. Prototype core event router
2. Create migration adapter
3. Convert one plugin as proof of concept
4. Measure performance differences
5. Plan phased migration