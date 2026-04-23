# KSI Parameter Parsing Guide

This guide explains when and how to use `parse_json_parameter` in the KSI system.

## Overview

The `parse_json_parameter` function is a boundary utility that converts JSON strings from external sources (like the CLI) into Python objects. It's designed to handle the fact that complex data structures must be passed as JSON strings through command-line interfaces.

## The Problem It Solves

When users interact with KSI via the CLI, they need to pass complex data:

```bash
# User wants to filter by multiple criteria
ksi send composition:list --filter '{"type": "orchestration", "author": "ksi"}'

# User wants to create entity with properties  
ksi send state:entity:create --type agent --id my_agent --properties '{"status": "active", "config": {"timeout": 30}}'
```

The CLI passes these as strings, but internally KSI needs them as Python dictionaries.

## When to Use parse_json_parameter

### ✅ DO Use It: At System Boundaries

Use `parse_json_parameter` in event handlers that receive data from external sources:

```python
# composition_service.py - Event handler for CLI commands
def handle_composition_list(raw_data):
    from ksi_common.json_utils import parse_json_parameter
    
    data = event_format_linter(raw_data, CompositionListData)
    
    # Parse JSON string parameters from CLI
    parse_json_parameter(data, 'filter')  # Converts '{"type": "orchestration"}' to dict
    
    # Now data['filter'] is a proper Python dict
    # Pass to internal service
    return composition_index.list_compositions(data)
```

### ✅ DO Use It: For These Common Parameters

Parameters that commonly need JSON parsing:
- `filter` - Complex query criteria
- `properties` - Nested configuration objects  
- `metadata` - Arbitrary structured data
- `vars` - Variable dictionaries for orchestrations
- `context` - Nested context objects

### ❌ DON'T Use It: In Internal Functions

Never use it after the initial parsing:

```python
# composition_index.py - Internal service
def list_compositions(filters):
    # DON'T DO THIS - filters is already a dict!
    # parse_json_parameter(filters, 'type')  # WRONG!
    
    # Just use the already-parsed data
    comp_type = filters.get('type')
    author = filters.get('author')
```

### ❌ DON'T Use It: For Simple Parameters

Simple scalar values don't need JSON parsing:

```python
def handle_agent_info(raw_data):
    data = event_format_linter(raw_data, AgentInfoData)
    
    # These are simple strings/ints, not JSON
    agent_id = data.get('agent_id')  # Don't parse
    limit = data.get('limit', 10)    # Don't parse
    
    # Only parse if expecting JSON string
    # parse_json_parameter(data, 'agent_id')  # WRONG!
```

## How It Works

The function:
1. Checks if the parameter exists and is a string
2. Attempts to parse it as JSON
3. If successful and `merge_into_data=True`, merges the result into the data dict
4. Removes the original string parameter to avoid confusion

```python
# Before parse_json_parameter
data = {
    "filter": '{"type": "orchestration", "author": "ksi"}',
    "limit": 10
}

# After parse_json_parameter(data, 'filter')  
data = {
    "type": "orchestration",
    "author": "ksi", 
    "limit": 10
}
```

## Best Practices

### 1. Parse at Entry Points Only

```python
# ✅ GOOD: Parse in event handler
def handle_state_entity_create(raw_data):
    data = event_format_linter(raw_data, StateEntityCreateData)
    parse_json_parameter(data, 'properties')
    return state_service.create_entity(data)

# ✅ GOOD: Internal service uses parsed data
def create_entity(data):
    properties = data.get('properties', {})
    # properties is already a dict, use it directly
```

### 2. Handle Both String and Dict Forms

Your TypedDict should document both possibilities:

```python
from typing import Union, Dict, Any

class StateEntityCreateData(TypedDict):
    type: str
    id: str
    properties: NotRequired[Union[str, Dict[str, Any]]]  # String from CLI, dict internally
```

### 3. Let It Handle Edge Cases

The function is robust:
- Returns None if parameter missing
- Ignores non-string parameters  
- Logs warnings for invalid JSON

```python
# Safe to call even if parameter might not exist
parse_json_parameter(data, 'optional_filter')

# Safe even if already parsed
data = {"filter": {"type": "agent"}}  # Already a dict
parse_json_parameter(data, 'filter')  # Does nothing, safe
```

### 4. Common Anti-Patterns to Avoid

```python
# ❌ ANTI-PATTERN: Double parsing
def process_data(data):
    # If data came from an event handler, it's already parsed!
    parse_json_parameter(data, 'filter')  # Probably wrong!

# ❌ ANTI-PATTERN: Re-stringifying internally  
def internal_function(filter_dict):
    # Don't convert back to JSON string internally
    filter_str = json.dumps(filter_dict)
    other_function(filter=filter_str)  # Wrong!

# ❌ ANTI-PATTERN: Using for non-JSON parameters
parse_json_parameter(data, 'agent_id')  # agent_id is just a string
parse_json_parameter(data, 'count')     # count is just an integer
```

## Real Examples from KSI

### Composition List Handler

```python
# composition_service.py
def handle_composition_list(raw_data):
    data = event_format_linter(raw_data, CompositionListData)
    
    # Parse filter from CLI: --filter '{"type": "orchestration"}'
    parse_json_parameter(data, 'filter')
    
    # Now data might look like:
    # {"type": "orchestration", "limit": 10, "sort_by": "name"}
    
    return composition_index.list_compositions(data)
```

### State Entity Creation

```python  
# state.py
def handle_state_entity_create(raw_data):
    data = event_format_linter(raw_data, StateEntityCreateData)
    
    # Parse properties from CLI: --properties '{"status": "active"}'
    parse_json_parameter(data, 'properties')
    
    # data['properties'] is now a dict, not a string
    entity = state_manager.create_entity(
        entity_type=data["type"],
        entity_id=data["id"],
        properties=data.get("properties", {})
    )
```

### Orchestration Start

```python
# orchestration_service.py  
def handle_orchestration_start(raw_data):
    data = event_format_linter(raw_data, OrchestrationStartData)
    
    # Parse vars from CLI: --vars '{"target": "production", "mode": "fast"}'
    parse_json_parameter(data, 'vars')
    
    # Vars are now available as a dict for the orchestration
    return orchestration_manager.start_orchestration(
        pattern=data["pattern"],
        variables=data.get("vars", {})
    )
```

## Summary

- **Use `parse_json_parameter` only at system boundaries** (event handlers)
- **Parse once, use everywhere** - Don't re-parse internally
- **It's for CLI parameters that need complex structures**
- **Document which parameters accept JSON strings in your TypedDict**
- **Trust the function to handle edge cases gracefully**

Remember: This is a boundary concern. Once data enters your system, keep it as Python objects!