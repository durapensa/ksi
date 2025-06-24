# KSI Daemon Architecture Simplification Guide

## Overview

This guide documents the simplification of the KSI daemon architecture, removing unnecessary complexity from inheritance hierarchies and event routing layers.

## Key Changes

### 1. Plugin Base Classes → Simple Functions

**Before**: Complex inheritance hierarchy
```python
class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(name="my_plugin", version="1.0.0")
    
    async def on_initialize(self):
        # Complex initialization
        pass
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        # Handle event
        pass
```

**After**: Simple module with functions
```python
from plugin_utils import get_logger, plugin_metadata
import pluggy

# Plugin metadata
plugin_metadata("my_plugin", version="1.0.0")

# Hook marker
hookimpl = pluggy.HookimplMarker("ksi")

# Simple module-level state
logger = get_logger("my_plugin")

@hookimpl
def ksi_startup(config):
    """Initialize plugin."""
    logger.info("Plugin started")
    return {"status": "ready"}

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle events."""
    if event_name == "my:event":
        return {"result": "handled"}
    return None

# Module marker
ksi_plugin = True
```

### 2. Event Routing Simplification

**Before**: Complex multi-layer routing
- Transport → Event Emitter → Event Bus → Plugin Manager → Plugins
- Multiple subscription systems
- Complex correlation handling

**After**: Direct routing
- Transport → Event Router → Plugins
- Single routing layer
- Simple correlation handling

### 3. Removed Components

- **BasePlugin, EventHandlerPlugin, ServicePlugin, TransportPlugin**: Replaced with simple functions
- **EventBus**: Merged into SimpleEventRouter
- **Complex Plugin Manager**: Simplified to direct hook calls
- **EventContext**: Replaced with simple dict
- **ServiceProvider interface**: Removed

## Migration Steps

### Step 1: Convert Class-Based Plugins

1. Remove class inheritance from BasePlugin
2. Convert class methods to module-level functions
3. Add @hookimpl decorator to hook functions
4. Move initialization to ksi_startup hook
5. Add `ksi_plugin = True` module marker

### Step 2: Simplify Event Handling

1. Remove pattern matching from plugins (handled by router)
2. Use simple event_name checking
3. Return responses directly (no emit/subscribe)

### Step 3: Update Transport Plugins

1. Remove TransportPlugin inheritance
2. Implement ksi_create_transport hook
3. Use set_event_emitter for routing

## Benefits

1. **Less Code**: ~40% reduction in boilerplate
2. **Easier to Understand**: Direct function calls instead of abstract patterns
3. **Better Performance**: Fewer layers of indirection
4. **Simpler Testing**: Test functions directly
5. **Easier Debugging**: Clear call stack

## Examples

### State Service (Before: 500 lines → After: 250 lines)

The state service was simplified by:
- Removing BasePlugin inheritance
- Using module-level state
- Direct function implementations
- Simplified persistence helpers

### Unix Socket Transport (Before: 300 lines → After: 150 lines)

The transport was simplified by:
- Removing complex base class
- Direct socket handling
- Simple event emitter injection

## Compatibility

The simplified architecture maintains compatibility with existing APIs:
- Same hook names and signatures
- Same event patterns
- Same response formats

## Next Steps

1. Gradually migrate existing plugins to simplified pattern
2. Remove deprecated base classes once migration complete
3. Update documentation with new patterns
4. Simplify test suite

## Summary

The simplification removes unnecessary abstraction layers while maintaining all functionality. Plugins become simple modules with functions, and event routing becomes direct and transparent.