# Daemon Refactoring Migration Guide

This guide explains how to gradually migrate the existing daemon codebase to use the new refactored patterns.

## Overview of Changes

### 1. **Pydantic Models** (`models.py`)
- Replaces manual JSON validation
- Provides type safety and automatic validation
- Reduces command_schemas.py complexity from 600+ lines to ~300 lines

### 2. **Base Manager** (`base_manager.py`)
- Eliminates duplicate code across managers
- Provides common patterns via inheritance
- Adds useful decorators for error handling and logging

### 3. **Command Registry** (`command_registry.py`)
- Replaces large if/elif chains in command routing
- Self-registering command pattern
- Each command is a separate class (easier to test)

### 4. **File Operations** (`file_operations.py`)
- Centralizes all file I/O operations
- Adds retry logic and atomic writes
- Consistent error handling

### 5. **Refactored Utils** (`utils_refactored.py`)
- Strategy pattern replaces 50+ line if/elif chain
- Extensible cleanup strategies
- Cleaner code organization

## Migration Steps

### Phase 1: Add New Dependencies (No Breaking Changes)
```bash
# Update requirements.txt
pip install -r requirements.txt
```

### Phase 2: Introduce Models Gradually

1. Start using Pydantic models for new commands:
```python
# In existing code, add:
from daemon.models import CommandFactory, ResponseFactory

# Use for new commands:
response = ResponseFactory.success("COMMAND", result_data)
```

2. Update command validation one command at a time:
```python
# Replace manual validation:
if 'mode' not in parameters or parameters['mode'] not in ['sync', 'async']:
    return error_response

# With Pydantic validation:
from daemon.models import SpawnParameters
try:
    params = SpawnParameters(**parameters)
except ValidationError as e:
    return error_response
```

### Phase 3: Migrate Managers to Base Class

1. Start with one manager (e.g., StateManager):
```python
# Old:
class StateManager:
    def __init__(self):
        self.sessions = {}
        os.makedirs('shared_state', exist_ok=True)

# New:
from daemon.base_manager import BaseManager

class StateManager(BaseManager):
    def __init__(self):
        super().__init__("state", ["shared_state"])
        
    def _initialize(self):
        self.sessions = {}
```

2. Add decorators gradually:
```python
# Add to existing methods:
@with_error_handling("set_shared_state")
@log_operation()
def set_shared_state(self, key: str, value: str):
    # existing code
```

### Phase 4: Migrate Command Handlers

1. Create new handler classes alongside existing code:
```python
# New handler:
@command_handler("CLEANUP")
class CleanupHandler(CommandHandler):
    async def handle(self, parameters, writer, full_command):
        # Migrate logic from json_handlers._handle_cleanup
```

2. Update command router to check registry first:
```python
# In _route_command:
handler_class = CommandRegistry.get_handler(command_name)
if handler_class:
    handler = handler_class(self)
    response = await handler.handle(parameters, writer, full_command)
    return await self.send_response(writer, response.model_dump())
else:
    # Fall back to old handlers dict
```

### Phase 5: Replace File Operations

1. Import file_operations in existing code:
```python
from daemon.file_operations import FileOperations, LogEntry
```

2. Replace file I/O gradually:
```python
# Old:
with open(log_file, 'a') as f:
    f.write(json.dumps(entry) + '\n')

# New:
FileOperations.append_jsonl(log_file, entry)
```

3. Use LogEntry for consistent formatting:
```python
# Old:
entry = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "type": "human",
    "content": prompt
}

# New:
entry = LogEntry.human(prompt)
```

### Phase 6: Update Utils Manager

1. Replace utils.py with utils_refactored.py:
```python
# In imports:
# from daemon.utils import UtilsManager
from daemon.utils_refactored import UtilsManager
```

2. The interface remains the same, so no code changes needed!

## Testing During Migration

1. **Unit Tests**: Write tests for new components
```python
def test_spawn_parameters():
    # Test valid parameters
    params = SpawnParameters(mode="async", type="claude", prompt="test")
    assert params.mode == "async"
    
    # Test validation
    with pytest.raises(ValidationError):
        SpawnParameters(mode="invalid", type="claude", prompt="test")
```

2. **Integration Tests**: Ensure old and new code work together
```python
async def test_mixed_handlers():
    # Test that both old and new handlers work
    validator = CommandValidator()
    
    # Old style command
    old_cmd = {"command": "GET_AGENTS", "version": "2.0"}
    is_valid, _, _ = validator.validate_command(old_cmd)
    assert is_valid
    
    # New style with Pydantic
    new_cmd = CommandFactory.create_command("SPAWN", {...})
    assert new_cmd.version == "2.0"
```

3. **Gradual Rollout**: Use feature flags if needed
```python
USE_NEW_VALIDATOR = os.getenv("USE_PYDANTIC_VALIDATION", "false").lower() == "true"

if USE_NEW_VALIDATOR:
    from daemon.command_validator_refactored import validate_command
else:
    from daemon.command_validator import validate_command
```

## Benefits After Migration

### Code Reduction
- **command_validator.py**: 326 lines → 150 lines (54% reduction)
- **utils.py**: 110 lines → 75 lines (32% reduction)
- **Removed duplication**: ~200 lines across managers

### Improved Patterns
- **No more if/elif chains**: Strategy and registry patterns
- **Type safety**: Pydantic validates at boundaries
- **Better errors**: Detailed validation messages
- **Easier testing**: Each component is isolated

### Performance
- **Faster validation**: Pydantic is optimized
- **Retry logic**: File operations are more reliable
- **Caching**: Validators are pre-compiled

## Rollback Plan

If issues arise:

1. **Keep old files**: Don't delete original files immediately
2. **Use imports**: Switch back by changing imports
3. **Database compatible**: State serialization format unchanged
4. **Protocol compatible**: JSON protocol remains the same

## Next Steps

After migration:

1. **Add more decorators**: 
   - `@rate_limit` for command throttling
   - `@validate_permissions` for access control
   - `@cache_result` for expensive operations

2. **Enhance models**:
   - Add computed fields
   - Custom validators
   - Model inheritance

3. **Extend patterns**:
   - More command handlers
   - Additional strategies
   - Plugin system using registry

## Summary

This migration can be done gradually without breaking existing functionality. Start with Phase 1-2 (models and validation) as they provide immediate benefits with minimal risk. Then proceed through the remaining phases as time permits.

The refactored code is:
- **More maintainable**: Clear patterns and separation
- **More extensible**: Easy to add new features
- **More reliable**: Better error handling and validation
- **More Pythonic**: Uses modern Python patterns