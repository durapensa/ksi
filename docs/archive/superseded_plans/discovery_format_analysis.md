# Discovery System Format Analysis

## Current State

### 1. Output Format Comparison

#### system:discover (with detail=true)
```json
{
  "events": {
    "system:help": {
      "module": "ksi_daemon.core.discovery",
      "handler": "handle_help",
      "async": true,
      "summary": "Get detailed help for a specific event.",
      "parameters": {
        "event": {
          "type": "Any",
          "required": true,
          "default": null,
          "description": "The event name to get help for (required)"
        }
      },
      "triggers": []
    }
  },
  "total": 1,
  "namespaces": ["system"]
}
```

#### system:help (for a specific event)
```json
{
  "event": "system:discover",
  "summary": "Universal discovery endpoint...",
  "module": "ksi_daemon.core.discovery",
  "async": true,
  "parameters": { /* same format as above */ },
  "triggers": [],
  "usage": {
    "event": "system:discover",
    "data": {
      "detail": "<Any>"
    }
  }
}
```

#### module:list_events (new handler)
```json
{
  "module": "ksi_daemon.core.discovery",
  "events": { /* same format as system:discover */ },
  "count": 5
}
```

### 2. Code Duplication Issues

#### Duplicated Logic

1. **Parameter extraction** - The `analyze_handler()` function is used by all three handlers
2. **Event filtering** - Both `handle_discover` and `handle_module_list_events` have similar filtering logic
3. **Detail fetching** - `handle_module_list_events` calls `handle_discover` to get event details

#### Specific Duplications

1. **handle_help** (lines 91-119):
   - Calls `handle_discover` to get event details
   - Reformats the same data with added `usage` field
   - Could share formatting logic

2. **handle_module_list_events** (lines 324-372):
   - Calls `handle_discover` for each event when detail=true
   - Duplicates the event info structure
   - Could reuse common formatting

### 3. Format Inconsistencies

1. **Parameter format** is consistent across all endpoints (verbose format)
2. **Top-level structure** varies:
   - system:discover returns `events`, `total`, `namespaces`
   - system:help returns flat structure with `event`, `summary`, etc.
   - module:list_events returns `module`, `events`, `count`

3. **No format style options** - All handlers use the same verbose parameter format

### 4. Missing Utilities

The following utility functions could reduce duplication:

```python
# Proposed utilities for discovery_utils.py

def format_event_info(event_name: str, handler_info: HandlerInfo, include_detail: bool = True) -> Dict[str, Any]:
    """Format event information consistently."""
    
def format_parameter(param_name: str, param_info: Dict[str, Any], style: str = "verbose") -> Dict[str, Any]:
    """Format parameter based on style (verbose, compact, ultra-compact)."""
    
def build_usage_example(event_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Build usage example from parameters."""
    
def filter_events(handlers: Dict[str, List[HandlerInfo]], namespace: Optional[str] = None, 
                  event: Optional[str] = None, module: Optional[str] = None) -> Dict[str, List[HandlerInfo]]:
    """Apply filters to event handlers."""
```

## Recommendations

### 1. Create discovery_utils.py

Create a new module `ksi_daemon/core/discovery_utils.py` with shared utilities:

```python
# discovery_utils.py
from typing import Dict, Any, List, Optional, Literal

FormatStyle = Literal["verbose", "compact", "ultra-compact"]

def format_parameter(name: str, info: Dict[str, Any], style: FormatStyle = "verbose") -> Any:
    """Format parameter based on style."""
    if style == "verbose":
        return info  # Current format
    elif style == "compact":
        return [info.get('type', 'Any'), info.get('required', False), 
                info.get('default'), info.get('description', '')]
    elif style == "ultra-compact":
        # Return notation string like "event:str*" or "detail:bool=true"
        return build_param_notation(name, info)

def format_event_info(handler: HandlerInfo, include_detail: bool = True, 
                      format_style: FormatStyle = "verbose") -> Dict[str, Any]:
    """Format event information with consistent structure."""
    base_info = {
        'module': handler.module,
        'handler': handler.name,
        'async': handler.is_async,
        'summary': extract_summary(handler.func)
    }
    
    if include_detail:
        analysis = analyze_handler(handler.func, handler.event)
        if format_style != "verbose":
            # Convert parameters to requested format
            analysis['parameters'] = {
                name: format_parameter(name, info, format_style)
                for name, info in analysis['parameters'].items()
            }
        base_info.update(analysis)
    
    return base_info
```

### 2. Standardize Output Structures

Define consistent response structures:

```python
# Standard discovery response
{
  "events": { /* event_name: event_info */ },
  "metadata": {
    "total": int,
    "namespaces": List[str],
    "format": "verbose|compact|ultra-compact"
  }
}

# Standard help response  
{
  "event": str,
  "info": { /* event_info */ },
  "usage": { /* usage example */ }
}
```

### 3. Add Format Style Parameter

Add `format_style` parameter to all discovery endpoints:

```python
@event_handler("system:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parameters:
        detail: Include parameters and triggers (default: True)
        namespace: Filter by namespace (optional)
        event: Get details for specific event (optional)
        format_style: Output format - verbose, compact, ultra-compact (default: verbose)
    """
    format_style = data.get('format_style', 'verbose')
    # Use format_style in formatting functions
```

### 4. Refactor Handlers to Use Utilities

Refactor the three handlers to use shared utilities:

```python
# Simplified handle_discover
events = {}
filtered_handlers = filter_events(router._handlers, namespace, event, module)

for event_name, handlers in filtered_handlers.items():
    handler = handlers[0]
    events[event_name] = format_event_info(handler, include_detail, format_style)

# Simplified handle_help  
event_info = format_event_info(handler, True, format_style)
return {
    'event': event_name,
    'info': event_info,
    'usage': build_usage_example(event_name, event_info['parameters'])
}
```

### 5. Benefits

1. **DRY code** - No duplication of formatting logic
2. **Consistent formats** - All endpoints use same formatting utilities
3. **Flexible output** - Support for different format styles
4. **Easier maintenance** - Changes to formatting in one place
5. **Better testing** - Can unit test formatting utilities separately

## Implementation Priority

1. **Phase 1**: Create discovery_utils.py with basic utilities
2. **Phase 2**: Refactor existing handlers to use utilities
3. **Phase 3**: Add format_style parameter support
4. **Phase 4**: Add tests for utilities and format consistency