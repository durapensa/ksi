# KSI Daemon Documentation

## Overview

KSI (Knowledge System Interface) is a plugin-based daemon for managing Claude processes with conversation continuity. It uses an event-driven architecture built on Pluggy (pytest's plugin system) to provide a flexible, extensible framework for AI agent management.

## Architecture

### Core Components

1. **Plugin-Based Architecture**: Uses Pluggy for plugin management with well-defined hooks
2. **Event-Driven Communication**: All communication via events, no polling or timers
3. **Single Unix Socket**: `/tmp/ksi/daemon.sock` for all client connections
4. **JSON Event Protocol**: `{"event": "...", "data": {...}, "correlation_id": "..."}`

### Plugin System

The daemon uses a plugin architecture with the following components:

- **Plugin Manager**: Loads and manages plugins using Pluggy
- **Event Bus**: Routes events between plugins
- **Hook Specifications**: Define plugin extension points
- **Base Plugin Class**: Standard interface for all plugins

### Available Plugins

1. **Transport Plugin** (`unix_socket`): Handles client connections via Unix socket
2. **Completion Plugin**: Manages Claude process spawning and completions
3. **State Plugin**: Provides persistent state storage
4. **Agent Plugin**: Manages agent lifecycle and registration
5. **Prompts Plugin**: Handles prompt composition from modular components

## Event Protocol

### Event Format

```json
{
    "event": "namespace:action",
    "data": { ... },
    "correlation_id": "optional-uuid",
    "timestamp": "2025-06-24T12:00:00Z"
}
```

### Common Events

- `system:health` - Health check
- `system:shutdown` - Graceful shutdown
- `completion:request` - Request Claude completion
- `agent:register` - Register new agent
- `agent:list` - List registered agents
- `state:get` - Get persistent state
- `state:set` - Set persistent state
- `prompts:compose` - Compose prompt from recipe

## Configuration

Configuration is managed via environment variables with KSI_ prefix:

- `KSI_SOCKET_PATH` - Unix socket path (default: `/tmp/ksi/daemon.sock`)
- `KSI_LOG_LEVEL` - Logging level (default: INFO)
- `KSI_LOG_DIR` - Log directory (default: `var/logs/daemon`)
- `KSI_DB_PATH` - SQLite database path (default: `var/db/agent_shared_state.db`)

## Plugin Development

### Creating a Plugin

1. Create a new Python module in `ksi_daemon/plugins/`
2. Inherit from `BasePlugin`
3. Implement required hooks
4. Define capabilities and metadata

Example:

```python
from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata, PluginCapabilities

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="my_plugin",
                version="1.0.0",
                description="My custom plugin",
                author="Me"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/myplugin"],
                commands=[],
                provides_services=["myplugin:service"]
            )
        )
    
    @hookimpl
    def ksi_startup(self):
        """Called when daemon starts"""
        return {"status": "my_plugin_ready"}
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        """Handle events in my namespace"""
        if event_name.startswith("myplugin:"):
            # Handle the event
            return {"result": "handled"}
        return None

# Plugin instance
plugin = MyPlugin()
```

### Available Hooks

- `ksi_startup()` - Called on daemon startup
- `ksi_shutdown()` - Called on daemon shutdown
- `ksi_handle_event(event_name, data, context)` - Handle events
- `ksi_plugin_context(context)` - Receive daemon context
- `ksi_register_routes(router)` - Register HTTP routes (if applicable)

## Client Library

The `ksi_client` package provides event-based client interfaces:

```python
from ksi_client import AsyncClient

async def main():
    client = AsyncClient(client_id="my-app")
    await client.connect()
    
    # Health check
    health = await client.health_check()
    
    # Create completion
    response = await client.create_completion(
        prompt="Explain quantum computing",
        model="sonnet",
        session_id="optional-session-id"
    )
    
    await client.disconnect()
```

## Deployment

### Starting the Daemon

```bash
# Using control script (recommended)
./daemon_control.py start

# Direct execution
python ksi-daemon.py
```

### Managing the Daemon

```bash
# Check status
./daemon_control.py status

# Check health
./daemon_control.py health

# Stop daemon
./daemon_control.py stop

# View logs
./daemon_control.py logs
```

## Migration from Legacy Architecture

The daemon has been fully migrated from a command-based multi-socket architecture to an event-driven single-socket plugin architecture. All legacy code has been removed.

### Key Changes

1. **Single Socket**: Replaced 5 separate sockets with one `/tmp/ksi/daemon.sock`
2. **Event Protocol**: Replaced command protocol with event-based messaging
3. **Plugin Architecture**: All functionality now provided by plugins
4. **No Backward Compatibility**: Clean break from legacy system

## Troubleshooting

### Common Issues

1. **Socket Connection Failed**
   - Ensure daemon is running: `./daemon_control.py status`
   - Check socket exists: `ls -la /tmp/ksi/daemon.sock`
   - Check permissions on socket directory

2. **Plugin Not Loading**
   - Check plugin has `plugin` instance at module level
   - Verify plugin implements required hooks
   - Check logs for import errors

3. **Event Not Handled**
   - Verify event name matches plugin's namespace
   - Check plugin is loaded: use `system:plugins` event
   - Ensure plugin's `ksi_handle_event` returns non-None for handled events

## Security Considerations

- Unix socket provides local-only access
- No authentication currently implemented
- File permissions control access to socket
- Consider using socket permissions for multi-user systems

## Performance

- Event-driven architecture eliminates polling
- Async/await throughout for non-blocking operations
- Plugin isolation prevents one plugin from blocking others
- Connection pooling for database operations

## Future Enhancements

- HTTP/WebSocket transport plugin for remote access
- Authentication and authorization system
- Plugin dependency management
- Hot-reload for plugin updates
- Distributed deployment support