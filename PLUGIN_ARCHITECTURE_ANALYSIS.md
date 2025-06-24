# KSI Daemon Plugin Architecture Analysis

## Overview

The KSI daemon uses a sophisticated plugin architecture based on `pluggy` (the same plugin system used by pytest). After analyzing the codebase, I've identified multiple plugin patterns and the intended architecture.

## Plugin Loading Process

1. **Discovery**: The `PluginLoader` searches for plugins in:
   - Built-in plugins: `ksi_daemon/plugins/`
   - User plugins: `~/.ksi/plugins/`
   - Local plugins: `./ksi_plugins/`
   - Installed packages with entry points under `ksi.plugins`

2. **Loading**: The loader looks for:
   - Modules with `ksi_plugin = True` marker
   - Classes inheriting from `KSIPlugin` base classes
   - Explicit `plugin` variable containing an instance
   - Modules with functions decorated with `@hookimpl`

3. **Registration**: Plugins are registered with pluggy's PluginManager using either:
   - The module itself (for pure function plugins)
   - A plugin instance (for class-based plugins)

## Plugin Patterns

### 1. Pure Function Pattern (test_minimal.py)

This is the simplest pattern using module-level functions with hook decorators:

```python
import pluggy

hookimpl = pluggy.HookimplMarker("ksi")

# Simple metadata
PLUGIN_INFO = {
    "name": "test_minimal",
    "version": "1.0.0",
    "description": "Minimal test plugin"
}

@hookimpl
def ksi_startup(config):
    """Called on startup."""
    return {"plugin.test_minimal": {"loaded": True}}

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle test events."""
    if event_name == "test:ping":
        return {"pong": True, "echo": data.get("message")}
    return None

# Module marker for discovery
ksi_plugin = True
```

**Characteristics**:
- No classes or instances
- Module itself is registered as the plugin
- Simple, stateless operations
- Best for simple plugins that don't need state

### 2. Class Instance Pattern (claude_cli.py, health_check.py, shutdown.py)

This pattern uses a class instance that inherits from base classes:

```python
from ksi_daemon.plugin_base import ServicePlugin, hookimpl

class ClaudeCompletionService(ServicePlugin):
    def __init__(self):
        super().__init__(
            name="claude_cli_completion",
            service_name="completion",
            version="1.0.0",
            description="Claude CLI completion provider"
        )
        # Instance state
        self.running_processes = {}
        self.sessions = {}
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        """Handle completion events."""
        # Implementation...
        
# Plugin instance created at module level
plugin = ClaudeCompletionService()
```

**Characteristics**:
- Class-based with state management
- Instance created at module level
- Inherits from base classes (ServicePlugin, EventHandlerPlugin, etc.)
- Lifecycle methods (on_start, on_stop, cleanup)
- Best for complex plugins with state, services, or resources

### 3. Base Class Patterns

The system provides several base classes for common plugin types:

#### BasePlugin
- Basic plugin functionality
- Provides logging, config, context
- Lifecycle methods: initialize(), cleanup()

#### EventHandlerPlugin
- For plugins that handle specific events
- Automatic pattern matching
- Declares handled events in constructor

#### ServicePlugin
- For plugins providing services
- Service lifecycle management (start/stop)
- Status reporting
- Service discovery hooks

#### TransportPlugin
- For communication transports
- Factory pattern for creating transports

## Hook Categories

### 1. Lifecycle Hooks
- `ksi_startup(config)` - Daemon startup
- `ksi_ready()` - Daemon ready
- `ksi_shutdown()` - Daemon shutdown
- `ksi_plugin_loaded(plugin_name, plugin_instance)` - Plugin loaded

### 2. Event Processing Hooks
- `ksi_pre_event(event_name, data, context)` - Pre-process events
- `ksi_handle_event(event_name, data, context)` - Main event handling (firstresult)
- `ksi_post_event(event_name, result, context)` - Post-process results
- `ksi_event_error(event_name, error, context)` - Error handling

### 3. Service Hooks
- `ksi_provide_service(service_name)` - Provide service implementation
- `ksi_service_dependencies()` - Declare dependencies
- `ksi_register_namespace(namespace, description)` - Register event namespaces

### 4. Extension Hooks
- `ksi_register_commands()` - Legacy command mapping
- `ksi_register_validators()` - Pydantic model registration
- `ksi_metrics_collected(metrics)` - Add plugin metrics

## Best Practices

### 1. When to Use Each Pattern

**Use Pure Functions When**:
- Plugin is stateless
- Simple event transformations
- No resource management needed
- Minimal dependencies

**Use Class Instances When**:
- Need to maintain state
- Managing resources (processes, connections)
- Providing services
- Complex initialization/cleanup

### 2. Plugin Structure

**At Module Level**:
- Plugin should be instantiated at module level, not inside functions
- Use `plugin = PluginClass()` for class-based plugins
- Use `ksi_plugin = True` marker for pure function plugins

**Import Handling**:
- Use try/except for imports to handle different loading contexts
- Support both absolute and relative imports
- Add proper __package__ handling for relative imports

### 3. Event Handling

**Event Names**:
- Use namespaced events: `namespace:action` (e.g., `completion:request`)
- Register namespaces with `ksi_register_namespace`
- Use wildcards for patterns: `completion:*`

**Event Context**:
- Use context.emit() to send events
- Use context.subscribe() for dynamic subscriptions
- Access config via context.config

### 4. Service Plugins

**Service Lifecycle**:
- Implement on_start() and on_stop()
- Clean up resources in on_stop()
- Report status via get_service_status()

**Service Discovery**:
- Services are discovered via `ksi_provide_service` hook
- Only one plugin should provide each service
- Services can declare dependencies

## Example Plugin Structures

### Minimal Stateless Plugin
```python
import pluggy
hookimpl = pluggy.HookimplMarker("ksi")

PLUGIN_INFO = {"name": "my_plugin", "version": "1.0.0"}

@hookimpl
def ksi_handle_event(event_name, data, context):
    if event_name == "my:event":
        return {"result": "processed"}
    return None

ksi_plugin = True
```

### Stateful Service Plugin
```python
from ksi_daemon.plugin_base import ServicePlugin, hookimpl

class MyService(ServicePlugin):
    def __init__(self):
        super().__init__(
            name="my_service",
            service_name="myservice",
            version="1.0.0"
        )
        self.state = {}
    
    async def on_start(self):
        # Initialize resources
        pass
    
    async def on_stop(self):
        # Clean up resources
        pass
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        # Handle events
        pass

plugin = MyService()
```

## Key Insights

1. **Module-Level Instantiation**: Plugins must be instantiated at module level, not dynamically. The plugin loader expects to find either a module with hook functions or a `plugin` variable with an instance.

2. **Flexible Discovery**: The loader is smart about finding plugins - it looks for various patterns including class instances, modules with hooks, and explicit markers.

3. **Event-Driven Core**: Everything flows through events. Even legacy commands are mapped to events via `ksi_register_commands`.

4. **Service Abstraction**: Services provide a clean abstraction for stateful components with lifecycle management.

5. **Hook Priority**: The `firstresult=True` on `ksi_handle_event` means the first plugin to return non-None handles the event - this creates a priority system based on registration order.

## Recommendations

1. **For New Plugins**: Start with pure functions if possible, move to classes only when you need state or lifecycle management.

2. **For Complex Plugins**: Use the appropriate base class (ServicePlugin for services, EventHandlerPlugin for event processors).

3. **For Resource Management**: Always implement proper cleanup in stop/cleanup methods.

4. **For Event Handling**: Be specific about which events you handle to avoid conflicts.

5. **For Testing**: The test_minimal.py pattern is perfect for unit testing individual hooks.