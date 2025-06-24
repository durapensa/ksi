# KSI Daemon Dependency Injection Refactoring

## Overview

This document describes the comprehensive refactoring of the KSI daemon to implement proper dependency injection using the `aioinject` library. The refactoring addressed architectural issues, improved testability, and established clear separation of concerns between stateful managers and stateless handlers.

## Motivation

The original implementation had several issues:
1. **Manual dependency management** - Handlers cached instances manually with ad-hoc initialization
2. **Mixed concerns** - Handlers contained background workers and queues (stateful behavior)
3. **Hardcoded timeouts** - Timeout values scattered throughout the codebase
4. **Complex handler lifecycle** - Manual `initialize()` calls and instance caching
5. **Inconsistent response handling** - Mix of dict and Pydantic model returns

## Architecture Changes

### 1. Dependency Injection Container

Created `ksi_daemon/di_container.py` implementing a centralized DI container using aioinject:

```python
class DaemonContainer:
    """Container for all daemon dependencies"""
    
    def __init__(self):
        self.container = aioinject.Container()
        self._setup_managers()  # Register singleton services
        self._core_daemon = None
```

Key design decisions:
- **Managers as Singletons**: State management, message bus, completion manager, etc. are long-lived singletons
- **Handlers as Transients**: Command handlers are created fresh per request (stateless)
- **Factory Functions**: Complex services use factory functions with proper type annotations
- **No @injectable decorator**: aioinject doesn't use decorators - we use direct registration

### 2. Handler Simplification

Transformed handlers from stateful singletons to stateless request processors:

**Before** (completion.py with background worker):
```python
class CompletionHandler(CommandHandler):
    def __init__(self, context):
        super().__init__(context)
        self.completion_queue = asyncio.Queue()
        self.worker_task = None
    
    async def initialize(self, context):
        # Start background worker
        self.worker_task = asyncio.create_task(self._completion_worker())
```

**After** (simplified stateless handler):
```python
class CompletionHandler(CommandHandler):
    async def handle(self, parameters, writer, full_command):
        # Validate input
        # Delegate to manager
        # Return response
        asyncio.create_task(self._delegate_to_manager(request_id, params))
        return SocketResponse.success(command_name, ack.model_dump())
```

The completion queue and worker pattern was removed. All stateful operations moved to managers.

### 3. Configuration Centralization

Added comprehensive timeout configuration to `ksi_daemon/config.py`:

```python
# Completion timeouts (in seconds)
completion_timeout_default: int = 300  # 5 minutes default
completion_timeout_min: int = 60       # 1 minute minimum
completion_timeout_max: int = 1800     # 30 minutes maximum

# Claude CLI progressive timeouts (in seconds)
claude_timeout_attempts: list[int] = [300, 900, 1800]  # 5min, 15min, 30min
claude_progress_timeout: int = 300     # 5 minutes without progress

# Test timeouts (in seconds)
test_completion_timeout: int = 120     # 2 minutes for tests
```

All timeouts are now configurable via environment variables (e.g., `KSI_COMPLETION_TIMEOUT_DEFAULT`).

### 4. Response Handling Standardization

Fixed inconsistent response handling:

**Issue**: SocketResponse factory methods return dicts, not Pydantic models
**Solution**: Updated command_registry.py to handle both cases:

```python
if isinstance(response, dict):
    await self.send_response(writer, response)
elif hasattr(response, 'model_dump'):
    await self.send_response(writer, response.model_dump())
```

### 5. Registry Pattern Enhancement

Enhanced SimplifiedCommandHandler to use DI for handler creation:

```python
# Create fresh handler instance using DI container
from .di_container import daemon_container
handler = await daemon_container.create_handler(handler_class)
```

Removed the `_handler_instances` cache - handlers are now created fresh per request.

## Bug Fixes

### 1. Structlog Conflict

**Issue**: `log_event()` was passing duplicate 'event' keys causing:
```
TypeError: _make_filtering_bound_logger.<locals>.make_method.<locals>.meth() got multiple values for argument 'event'
```

**Fix**: Modified `log_event()` to remove duplicate 'event' key:
```python
def log_event(logger, event_name, **event_data):
    if 'event' in event_data:
        event_data.pop('event')
    logger.info(event_name, **event_data)
```

### 2. Completion Response Mapping

**Issue**: CompletionManager returns `output['result']` but handler expected `result['response']`
**Fix**: Updated completion handler to map correctly:
```python
'response': result.get('result', ''),  # Claude CLI returns 'result' not 'response'
```

### 3. Event Subscription

**Issue**: Client tried targeted subscription "COMPLETION_RESULT:client_id" but daemon publishes to "COMPLETION_RESULT"
**Fix**: Updated client to subscribe to general event type and filter by client_id:
```python
subscribe_cmd = CommandBuilder.build_subscribe_command(
    self.client_id, 
    ["COMPLETION_RESULT"]  # General subscription, filter in handler
)
```

### 4. Handler Initialization

**Issue**: Handlers with `initialize()` methods weren't being called
**Fix**: Added initialization check in command_registry.py (later removed when handlers became stateless)

## Implementation Details

### Manager Registration

Managers are registered as singletons with proper factory functions:

```python
def _setup_managers(self):
    # Simple singletons
    self.container.register(aioinject.Singleton(StateManager))
    self.container.register(aioinject.Singleton(MessageBus))
    
    # Factory for manager with dependencies
    async def create_completion_manager(state_manager: StateManager) -> CompletionManager:
        return CompletionManager(state_manager)
    
    self.container.register(aioinject.Singleton(create_completion_manager))
```

### Handler Creation

Handlers are created on-demand with injected dependencies:

```python
async def create_handler(self, handler_class: Type[CommandHandler]) -> Optional[CommandHandler]:
    async with self.container.context() as ctx:
        # Resolve all dependencies
        state_manager = await ctx.resolve(StateManager)
        completion_manager = await ctx.resolve(CompletionManager)
        # ... etc
        
        # Create context object
        context = HandlerContext()
        context.state_manager = state_manager
        # ... etc
        
        # Create handler (no initialization!)
        return handler_class(context)
```

### Integration with Existing Code

The refactoring maintains backward compatibility:
- All existing handler interfaces preserved
- Command registration via decorators still works
- Manager APIs unchanged
- Only internal implementation details modified

## Testing Results

After the refactoring:
- Completion tests pass with proper timeouts
- No more timeout errors due to configurable values
- Clean shutdown without hanging workers
- Proper event delivery via message bus

## Migration Path

For existing handlers:
1. Remove background workers and queues
2. Move stateful operations to managers
3. Remove `initialize()` methods
4. Ensure handlers are stateless
5. Use manager methods for async operations

## Benefits

1. **Testability**: Easy to mock dependencies for unit tests
2. **Maintainability**: Clear separation of concerns
3. **Configuration**: All timeouts centralized and configurable
4. **Performance**: No unnecessary singleton handlers in memory
5. **Flexibility**: Easy to add new managers or handlers
6. **Type Safety**: Proper type annotations throughout

## Future Considerations

### Phase 2: Plugin System with Pluggy
- Convert command handlers to plugins
- Dynamic handler loading
- Third-party handler support

### Phase 3: SocketIO Integration  
- Real-time bidirectional communication
- WebSocket support for web clients
- Event streaming capabilities

## Additional Fixes (2025-06-24)

### 1. HandlerContext Type Safety
**Issue**: HandlerContext was created as an empty inline class without type annotations
**Fix**: Created `handler_context.py` with a proper dataclass including:
- Type annotations for all managers
- Post-init validation
- Clear documentation

### 2. TimestampManager DI Consistency  
**Issue**: TimestampManager was registered as singleton but manually instantiated
**Fix**: Updated `di_container.py` to resolve TimestampManager from container in both `create_handler_factory` and `create_handler` methods

### 3. ReloadModuleHandler Stateful Pattern
**Issue**: Handler had instance variables storing module state
**Fix**: Refactored to use StateManager for tracking loaded modules:
- Removed `self.modules_dir` and `self.loaded_modules`
- Store module tracking in shared state via StateManager
- Handler is now completely stateless

### 4. Shutdown Handler Response Bug
**Issue**: Called `.model_dump()` on dict response from `SocketResponse.success()`
**Fix**: Removed erroneous `.model_dump()` calls - response is already a dict

### 5. Terminology Consistency
**Verified**: No instances of "reply" found - all uses "response" consistently

## Validation Results

All refactoring objectives achieved:
- ✅ Zero manual instantiations in handlers
- ✅ All handlers stateless (no queues, workers, or state)
- ✅ Handlers created fresh per request via DI
- ✅ Consistent response handling
- ✅ All tests passing
- ✅ Clean daemon shutdown
- ✅ Proper separation of concerns

## Conclusion

The aioinject refactoring successfully modernized the KSI daemon's architecture while maintaining full backward compatibility. The system now follows established dependency injection patterns, making it more maintainable, testable, and extensible.