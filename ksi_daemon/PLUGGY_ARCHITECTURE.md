# KSI Daemon Pluggy Architecture

## ✅ Correct Pluggy Usage

The KSI daemon follows pluggy best practices correctly:

### 1. Hook Specifications (hookspecs.py)
- Uses `hookspec = pluggy.HookspecMarker("ksi")` 
- Decorates **functions** (not methods) with `@hookspec`
- Clear naming convention: all hooks start with `ksi_`
- Well-documented parameters and return types

### 2. Plugin Implementation Pattern
```python
# Correct pattern used throughout KSI:
import pluggy

# Create marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module-level state (not classes)
some_state = {}

# Decorate functions (not methods)
@hookimpl
def ksi_startup(config):
    """Initialize plugin"""
    return {"status": "ready"}

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle events"""
    if event_name == "my:event":
        return handle_my_event(data)
    return None

# Mark module as plugin
ksi_plugin = True
```

### 3. Why This Is Best Practice

**Function-based plugins are preferred because:**
- Simpler and more Pythonic
- No unnecessary class boilerplate
- Clear separation of concerns
- Easy to test individual hooks
- Follows pytest's successful pattern

**Module-level state is appropriate because:**
- Plugins are singletons by nature
- State is encapsulated within the module
- No need for instance management
- Cleaner than class attributes

### 4. Plugin Discovery
The loader correctly handles multiple patterns:
- Modules with `ksi_plugin = True` marker (preferred)
- Legacy class-based plugins (for compatibility)
- Explicit `plugin` object exports

### 5. Hook Execution Model
- **First result wins**: For `ksi_handle_event`, first non-None return stops processing
- **Collect all**: For hooks like `ksi_metrics_collected`, all results are merged
- **Fire and forget**: For notification hooks like `ksi_agent_connected`

## Example: Minimal Plugin

```python
#!/usr/bin/env python3
"""Minimal KSI plugin example"""

import pluggy

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Plugin metadata (optional but recommended)
PLUGIN_INFO = {
    "name": "minimal_example",
    "version": "1.0.0",
    "description": "Minimal plugin example"
}

@hookimpl
def ksi_startup(config):
    """Initialize on startup"""
    print("Minimal plugin started!")
    return {"minimal": "ready"}

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle our custom event"""
    if event_name == "minimal:hello":
        return {"response": f"Hello, {data.get('name', 'World')}!"}
    return None

@hookimpl
def ksi_shutdown():
    """Clean up on shutdown"""
    print("Minimal plugin stopped!")

# Mark as plugin for discovery
ksi_plugin = True
```

## Comparison with Anti-Patterns

### ❌ Incorrect: Class-based with decorated methods
```python
# DON'T DO THIS - pluggy doesn't work with methods
class MyPlugin:
    @hookimpl  # This won't work!
    def ksi_startup(self, config):
        pass
```

### ❌ Incorrect: Missing module marker
```python
# Without ksi_plugin = True, the loader might not find it
@hookimpl
def ksi_startup(config):
    pass
# Missing: ksi_plugin = True
```

### ✅ Correct: KSI's approach
- Functions at module level
- Clear hook implementations
- Proper markers and metadata
- Module-level state management

The KSI daemon's plugin architecture is a textbook example of proper pluggy usage!