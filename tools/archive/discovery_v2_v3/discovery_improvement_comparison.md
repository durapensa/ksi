# KSI Discovery System Improvements

## Before: Old Discovery System

The original documentation showed:
- ~94 events (missing many)
- **"Parameters: None"** for every event
- No implementation details
- No event relationships
- Based on outdated pluggy system

Example from old documentation:
```
### `completion:async`
Async completion request

Parameters: None
```

## After: Enhanced Discovery System with AST Analysis

The new documentation shows:
- **141 events** (complete coverage)
- **Detailed parameters** with types, descriptions, defaults
- **Implementation analysis** via AST
- **Event relationships** (what triggers what)
- **Complexity metrics**
- Based on pure event-driven architecture

Example from new documentation:
```
#### `state:set`

**Summary**: Handle state:set event

**Description**:
> Set a value in shared state.
> 
> Args:
>     namespace (str): The namespace to set in (default: "global")
>     key (str): The key to set (required)
>     value (any): The value to store (required)
>     metadata (dict): Optional metadata to attach (default: {})

**Parameters**:
- `namespace` (str, optional): The namespace to set in (default: "global") [default: global]
- `key` (str, required): The key to set (required)
- `value` (any, required): The value to store (required)
- `metadata` (dict, optional): Optional metadata to attach (default: {})

**Complexity**: 5
```

## Key Enhancements

### 1. New `discovery:usage` Event
Provides multiple discovery patterns:
- `full` - Complete metadata and implementation analysis
- `by_module` - Events organized by module
- `event_names` - Quick capability check
- `parameters` - Detailed parameter info
- `implementation` - AST analysis results
- `relationships` - Event trigger graph
- `capabilities` - System capabilities
- `reference` - Formatted documentation

### 2. Enhanced `system:discover`
Added `detail` parameter with levels:
- `summary` - Basic info (default)
- `parameters` - Include parameter details
- `full` - All metadata
- `cached` - Pre-cached comprehensive data

### 3. AST Implementation Analysis
Automatically extracts from handler code:
- **Parameters** - From data.get() calls
- **Triggers** - Events emitted by handlers
- **State mutations** - State changes
- **File operations** - File I/O
- **Error patterns** - Exception handling
- **Data flow** - How data moves through handler
- **Complexity** - Cyclomatic complexity

### 4. Event Relationships
Shows which events trigger other events:
```
- config:set → config:changed
- config:reload → daemon:config_reload, plugins:reload, composition:reload
- config:rollback → config:rolled_back
```

## Implementation Details

The system now uses comprehensive AST analysis (`ImplementationAnalyzer` class) that visits the abstract syntax tree of each event handler to extract:
- Direct dictionary access patterns (`data["key"]`)
- Method calls with `.get()` patterns
- Event emissions
- State mutations
- Error handling
- Control flow complexity

This provides a single source of truth - the actual implementation code - rather than relying on decorators or manual documentation.