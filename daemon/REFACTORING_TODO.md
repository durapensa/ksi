# Daemon Refactoring TODO List

## Current Progress: 7/29 Commands Migrated (24%)

### ✅ Completed Commands
- **Process Control**: CLEANUP, SPAWN
- **System Status**: HEALTH_CHECK, GET_COMMANDS, GET_PROCESSES  
- **State Management**: SET_SHARED, GET_SHARED

### 📋 Remaining Commands to Migrate (22)

#### Priority 1: Agent Management (4 commands)
- [ ] REGISTER_AGENT - Agent registration
- [ ] GET_AGENTS - List agents (use new list_agents() API)
- [ ] SPAWN_AGENT - Spawn agent process
- [ ] ROUTE_TASK - Route task to capable agent

#### Priority 2: Message Bus (2 commands)
- [ ] SUBSCRIBE - Subscribe to events
- [ ] PUBLISH - Publish events

#### Priority 3: Identity Management (5 commands)
- [ ] CREATE_IDENTITY - Create identity
- [ ] UPDATE_IDENTITY - Update identity
- [ ] GET_IDENTITY - Get identity
- [ ] LIST_IDENTITIES - List all (use new list_identities() API)
- [ ] REMOVE_IDENTITY - Remove identity

#### Priority 4: Composition System (5 commands)
- [ ] GET_COMPOSITIONS - List available compositions
- [ ] GET_COMPOSITION - Get specific composition
- [ ] VALIDATE_COMPOSITION - Validate composition
- [ ] LIST_COMPONENTS - List prompt components
- [ ] COMPOSE_PROMPT - Compose a prompt

#### Priority 5: System Control (3 commands)
- [ ] RELOAD - Reload module
- [ ] RELOAD_DAEMON - Hot reload daemon
- [ ] SHUTDOWN - Graceful shutdown

#### Priority 6: Other (3 commands)
- [ ] LOAD_STATE - Load saved state
- [ ] MESSAGE_BUS_STATS - Get stats
- [ ] AGENT_CONNECTION - Handle connections

## Migration Pattern

For each command:

1. Create file: `daemon/commands/{command_name}.py`
2. Define Pydantic parameter model
3. Use `@command_handler("COMMAND_NAME")` decorator
4. Implement `handle()` method
5. Add `get_help()` classmethod
6. Import in `daemon/commands/__init__.py`
7. Test the command

### Template:
```python
#!/usr/bin/env python3
"""
{COMMAND} command handler - {Description}
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel, Field

class {Command}Parameters(BaseModel):
    """Parameters for {COMMAND} command"""
    # Define parameters here

@command_handler("{COMMAND}")
class {Command}Handler(CommandHandler):
    """Handles {COMMAND} command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute {command} operation"""
        # Validate parameters
        try:
            params = {Command}Parameters(**parameters)
        except Exception as e:
            return ResponseFactory.error("{COMMAND}", "INVALID_PARAMETERS", str(e))
        
        # Implementation here
        
        return ResponseFactory.success("{COMMAND}", result)
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "{COMMAND}",
            "description": "{Description}",
            "parameters": {
                # Define parameter help
            },
            "examples": [
                # Add examples
            ]
        }
```

## Manager API Notes

All managers now follow standardized API:
- `list_x()` → List[Dict] - List all items
- `get_x(id)` → Optional[Dict] - Get one item  
- `create_x(data)` → str - Create, return ID
- `update_x(id, data)` → bool - Update existing
- `remove_x(id)` → bool - Delete one
- `clear_x()` → int - Clear all, return count

Use these new methods in command handlers instead of legacy methods.

## Final Steps

Once all commands migrated:
1. Remove legacy handler dictionary from `command_handler.py`
2. Delete `json_handlers.py` 
3. Update hot reload to support new command classes
4. Performance testing
5. Update documentation

## Testing

Test each batch with a script like:
```python
async def test_command(command_name, parameters=None):
    socket_path = "sockets/claude_daemon.sock"
    reader, writer = await asyncio.open_unix_connection(socket_path)
    
    command = {
        "command": command_name,
        "version": "2.0",
        "parameters": parameters or {}
    }
    
    writer.write(json.dumps(command).encode() + b'\n')
    await writer.drain()
    
    response_data = await reader.readline()
    response = json.loads(response_data.decode())
    
    writer.close()
    await writer.wait_closed()
    
    return response
```

## Notes for Next Session

- Manager APIs are standardized and ready
- Command registry pattern is proven and working
- Pydantic validation is integrated
- All infrastructure is in place for rapid migration
- Focus on batching similar commands together