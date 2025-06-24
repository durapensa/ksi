# KSI Plugin Development Guide

## Overview

The KSI daemon uses a plugin-based architecture built on [pluggy](https://pluggy.readthedocs.io/) (the plugin system used by pytest). All functionality is provided through plugins that handle events and implement hooks.

## Quick Start

### 1. Minimal Plugin Example

```python
#!/usr/bin/env python3
"""My first KSI plugin."""

from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="my_plugin",
                version="1.0.0",
                description="My first plugin"
            )
        )
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        if event_name == "hello:world":
            return {"message": "Hello from my plugin!"}

# Required: Create plugin instance
plugin = MyPlugin()
```

### 2. Place Your Plugin

Save your plugin in one of these locations:
- `ksi_daemon/plugins/` - Built-in plugins
- `~/.ksi/plugins/` - User plugins (future)
- Any directory in `KSI_PLUGIN_PATH` environment variable

### 3. Test Your Plugin

```python
# Test directly
from ksi_daemon.plugin_manager import PluginManager

manager = PluginManager()
manager.pm.register(plugin)

# Send event
results = manager.pm.hook.ksi_handle_event(
    event_name="hello:world",
    data={},
    context={}
)
print(results)  # [{"message": "Hello from my plugin!"}]
```

## Plugin Architecture

### Core Concepts

1. **Hooks**: Special methods that the daemon calls at specific points
2. **Events**: Named messages with data that flow through the system
3. **Services**: Functionality that plugins provide to other plugins
4. **Namespaces**: Event categorization (e.g., `/system`, `/completion`)

### Available Hooks

```python
@hookimpl
def ksi_startup(self):
    """Called when daemon starts."""
    return {"status": "plugin_started"}

@hookimpl
def ksi_shutdown(self):
    """Called when daemon stops."""
    return {"status": "plugin_stopped"}

@hookimpl
def ksi_plugin_context(self, context):
    """Receive plugin context with event bus, config, etc."""
    self._event_bus = context.get("event_bus")

@hookimpl
def ksi_handle_event(self, event_name, data, context):
    """Handle an event. Main plugin logic goes here."""
    if event_name == "my:event":
        return {"handled": True}

@hookimpl
def ksi_filter_event(self, event_name, data):
    """Filter/modify events before processing."""
    # Return modified data or None to block
    return data

@hookimpl
def ksi_validate_event(self, event_name, data):
    """Validate event data."""
    # Raise exception if invalid
    if "required_field" not in data:
        raise ValueError("Missing required field")

@hookimpl
def ksi_metrics_collected(self, metrics):
    """Add plugin metrics."""
    metrics["my_plugin"] = {"events_handled": 42}
    return metrics
```

## Plugin Types

### 1. Command Handler Plugin

Handles specific commands/events:

```python
class HealthCheckPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="health_check",
                version="1.0.0"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/system"],
                commands=["system:health"]
            )
        )
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        if event_name == "system:health":
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat()
            }
```

### 2. Service Plugin

Provides services to other plugins:

```python
class DatabasePlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(name="database"),
            capabilities=PluginCapabilities(
                provides_services=["database"]
            )
        )
        self.db = {}  # Simple in-memory DB
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        if event_name == "db:get":
            key = data.get("key")
            return {"value": self.db.get(key)}
        
        elif event_name == "db:set":
            key = data.get("key")
            value = data.get("value")
            self.db[key] = value
            return {"status": "set"}
```

### 3. Transport Plugin

Handles external connections:

```python
class WebSocketPlugin(TransportPlugin):
    def __init__(self):
        super().__init__(
            name="websocket_transport",
            transport_type="websocket"
        )
    
    @hookimpl
    def ksi_startup(self):
        # Start WebSocket server
        self.server = await websocket.serve(
            self.handle_connection, 
            "localhost", 
            8765
        )
    
    async def handle_connection(self, websocket, path):
        # Convert WebSocket messages to events
        async for message in websocket:
            event = json.loads(message)
            await self.emit_event(event["name"], event["data"])
```

## Event Patterns

### Event Naming Convention

Events use a namespace:action format:
- `system:health` - System health check
- `completion:request` - Request completion
- `agent:spawn` - Spawn an agent
- `state:set` - Set state value

### Event Flow

```python
# 1. Plugin receives event
@hookimpl
def ksi_handle_event(self, event_name, data, context):
    if event_name == "user:login":
        user_id = data["user_id"]
        
        # 2. Process event
        if self.validate_user(user_id):
            
            # 3. Emit new events
            asyncio.create_task(
                context.emit("user:authenticated", {
                    "user_id": user_id,
                    "timestamp": datetime.now()
                })
            )
            
            # 4. Return response
            return {"status": "logged_in"}
```

### Request/Response Pattern

Use correlation IDs for request/response:

```python
# Send request with correlation ID
correlation_id = str(uuid.uuid4())
await event_bus.publish("service:request", {
    "action": "process",
    "correlation_id": correlation_id
})

# Listen for correlated response
async def response_handler(event_name, data):
    if data.get("correlation_id") == correlation_id:
        # Handle response
        process_result(data["result"])
```

## Best Practices

### 1. Plugin Structure

```
my_plugin/
├── __init__.py
├── plugin.py        # Main plugin class
├── handlers.py      # Event handlers
├── models.py        # Data models (Pydantic)
├── utils.py         # Helper functions
└── tests/
    └── test_plugin.py
```

### 2. Error Handling

```python
@hookimpl
def ksi_handle_event(self, event_name, data, context):
    try:
        # Process event
        result = self.process(data)
        return {"status": "success", "result": result}
        
    except ValueError as e:
        # Return error response
        return {
            "status": "error",
            "error": {
                "code": "INVALID_INPUT",
                "message": str(e)
            }
        }
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error: {e}")
        return {
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An error occurred"
            }
        }
```

### 3. Async Operations

```python
@hookimpl
def ksi_handle_event(self, event_name, data, context):
    if event_name == "async:operation":
        # Schedule async work
        task_id = str(uuid.uuid4())
        asyncio.create_task(
            self._async_operation(task_id, data, context)
        )
        return {"task_id": task_id, "status": "started"}

async def _async_operation(self, task_id, data, context):
    # Do async work
    result = await long_running_operation(data)
    
    # Emit completion event
    await context.emit("async:complete", {
        "task_id": task_id,
        "result": result
    })
```

### 4. Configuration

```python
@hookimpl
def ksi_plugin_context(self, context):
    # Get plugin-specific config
    config = context.get("config", {})
    self.my_setting = config.get("my_plugin", {}).get("setting", "default")
```

### 5. Testing

```python
import pytest
from ksi_daemon.plugin_manager import PluginManager

def test_my_plugin():
    manager = PluginManager()
    plugin = MyPlugin()
    manager.pm.register(plugin)
    
    # Test event handling
    results = manager.pm.hook.ksi_handle_event(
        event_name="test:event",
        data={"value": 42},
        context={}
    )
    
    assert len(results) == 1
    assert results[0]["processed"] == 42
```

## Advanced Topics

### Hook Ordering

Control hook execution order:

```python
@hookimpl(tryfirst=True)  # Run before other plugins
def ksi_filter_event(self, event_name, data):
    # Pre-process all events
    data["timestamp"] = datetime.now()
    return data

@hookimpl(trylast=True)  # Run after other plugins
def ksi_handle_event(self, event_name, data, context):
    # Clean up after other handlers
    pass
```

### Plugin Dependencies

Declare dependencies on other plugins:

```python
class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="my_plugin",
                version="1.0.0",
                dependencies=["database", "auth"]
            )
        )
```

### Dynamic Plugin Loading

```python
# Load plugin from file
import importlib.util

spec = importlib.util.spec_from_file_location("custom_plugin", "/path/to/plugin.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

manager.pm.register(module.plugin)
```

## Debugging

### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Trace Event Flow

```python
@hookimpl
def ksi_handle_event(self, event_name, data, context):
    logger.debug(f"Plugin {self.name} handling {event_name}")
    logger.debug(f"Data: {data}")
    
    result = self.process(data)
    
    logger.debug(f"Result: {result}")
    return result
```

### 3. Use Event History

```python
# Get recent events
history = event_bus.get_event_history(namespace="/my_plugin")
for event in history:
    print(f"{event['timestamp']}: {event['name']} - {event['data']}")
```

## Examples

See the `ksi_daemon/plugins/` directory for complete examples:
- `test_minimal.py` - Simplest possible plugin
- `core/health_check.py` - Basic command handler
- `completion/completion_service.py` - Complex service plugin
- `transport/unix_socket.py` - Transport plugin

## Resources

- [Pluggy Documentation](https://pluggy.readthedocs.io/)
- [KSI Event Catalog](EVENT_CATALOG.md)
- [Plugin API Reference](API_REFERENCE.md)

---
*Last updated: 2025-06-24*