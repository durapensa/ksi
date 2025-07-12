# TypedDict-Based Discovery System Migration Plan

## Overview

This document outlines the migration from docstring-based parameter documentation to a TypedDict-based discovery system. This will make KSI's event system more type-safe, maintainable, and self-documenting.

## Goals

1. **Replace docstring instructions** with type-based introspection
2. **Improve discovery accuracy** by understanding optional vs required parameters
3. **Enable variant-aware discovery** for complex handlers with multiple usage patterns
4. **Reduce docstrings** to single-line descriptions
5. **Improve IDE support** through proper type annotations

## Migration Status (2025-07-11)

### ✅ Successfully Implemented

1. **Type Discovery System**: Created `ksi_daemon/core/type_discovery.py` with runtime type introspection
2. **Discovery Integration**: Updated `system:discover` and `system:help` to use TypedDict analysis
3. **Co-located TypedDict Pattern**: Established pattern of defining TypedDict near handlers (not centralized)
4. **Cross-module Resolution**: Type discovery works across module imports via `get_type_hints()`

### ✅ Completed Modules (81 handlers across 6 modules)
- **composition/composition_service.py** - 22 handlers ✓
- **agent/agent_service.py** - 26 handlers ✓  
- **config/config_service.py** - 7 handlers ✓
- **conversation/conversation_service.py** - 8 handlers ✓
- **evaluation/prompt_evaluation.py** - 6 handlers ✓
- **core/state.py** - 12 handlers ✓ (8 TypedDict, 4 Dict due to 'from' keyword)

### 📋 Migration Progress: 32% Complete
- **Total handlers**: 254 across 36 modules
- **Migrated**: 81 handlers (32%)
- **Remaining**: 173 handlers (68%)

### Known Limitations
- **Python keyword parameters**: Handlers with parameters named 'from', 'import', 'class' etc. cannot use TypedDict
- **Affected state.py handlers**: `relationship:create`, `relationship:delete`, `relationship:query`, `graph:traverse`

### Problems Solved

1. ✅ **Discovery accuracy**: TypedDict provides correct required/optional detection
2. ✅ **Cross-module types**: Runtime introspection resolves imported TypedDict definitions  
3. ✅ **Variant support**: Union types enable "if X then Y is required" patterns
4. ✅ **Maintenance burden**: Types are the documentation, no docstring drift

### Remaining Problems

1. **Incomplete coverage**: 185 handlers still use `Dict[str, Any]`
2. **Mixed patterns**: Some modules use centralized types, others don't use TypedDict at all
3. **Legacy discovery**: AST-based discovery still used as fallback

### Example of Current Pattern

```python
@event_handler("composition:create")
async def handle_create_composition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a dynamic composition in memory (not saved to disk).
    
    Parameters:
        name (str, optional): Composition name (auto-generated if not provided)
        type (str, optional): Composition type (profile, orchestration, etc)
        extends (str, optional): Base composition to extend
        content (dict, optional): Full composition content (overrides other params)
        save (bool, optional): Whether to save to disk (default: False)
        
    Returns:
        dict: Created composition with status
    """
```

## Proposed TypedDict Architecture

### Base Pattern

```python
from typing import TypedDict, Optional, Union, Literal, Required, NotRequired
from typing_extensions import NotRequired  # For Python < 3.11

class EventDataBase(TypedDict):
    """Base class for all event data"""
    _source: NotRequired[str]  # Event source metadata
    _timestamp: NotRequired[float]  # Event timestamp

class CompositionCreateBase(TypedDict):
    """Common parameters for composition creation"""
    name: NotRequired[str]
    type: NotRequired[Literal['profile', 'prompt', 'orchestration']]
    description: NotRequired[str]
    author: NotRequired[str]
    metadata: NotRequired[dict]

class CompositionCreateWithContent(CompositionCreateBase):
    """Create composition from full content"""
    content: Required[dict]  # Full composition structure

class CompositionCreateProfile(CompositionCreateBase):
    """Create profile composition with components"""
    type: Required[Literal['profile']]
    model: NotRequired[str]
    capabilities: NotRequired[list[str]]
    prompt: NotRequired[str]

# Union type for all variants
CompositionCreateData = Union[
    CompositionCreateWithContent,
    CompositionCreateProfile,
    CompositionCreateBase
]

@event_handler("composition:create")
async def handle_create_composition(data: CompositionCreateData) -> Dict[str, Any]:
    """Create and save a composition."""  # One-line docstring
    # Implementation...
```

### Complex Event Pattern

```python
class OrchestrationMessageBase(TypedDict):
    """Base message routing data"""
    orchestration_id: Required[str]
    message: Required[dict]

class OrchestrationMessageDirect(OrchestrationMessageBase):
    """Direct message to specific agent"""
    target_agent: Required[str]

class OrchestrationMessageBroadcast(OrchestrationMessageBase):
    """Broadcast to all agents"""
    broadcast: Required[Literal[True]]
    
OrchestrationMessageData = Union[
    OrchestrationMessageDirect,
    OrchestrationMessageBroadcast
]
```

## Discovery System Updates

### Type Introspection Module

```python
# ksi_daemon/core/type_discovery.py

import inspect
from typing import get_type_hints, get_origin, get_args, Union
from typing_extensions import TypedDict, Required, NotRequired

class TypeAnalyzer:
    """Analyze TypedDict definitions for parameter discovery."""
    
    def analyze_handler(self, handler_func) -> HandlerMetadata:
        """Extract parameter metadata from type annotations."""
        # Get type hints
        hints = get_type_hints(handler_func, include_extras=True)
        
        # Find data parameter type
        data_type = hints.get('data')
        if not data_type:
            return self.fallback_to_ast(handler_func)
        
        # Handle Union types
        if get_origin(data_type) is Union:
            return self.analyze_union_type(data_type)
        
        # Handle single TypedDict
        if self.is_typed_dict(data_type):
            return self.analyze_typed_dict(data_type)
    
    def analyze_typed_dict(self, td_class) -> ParameterSet:
        """Extract parameters from TypedDict."""
        params = {}
        
        # Get all fields including inherited
        for field, field_type in td_class.__annotations__.items():
            if field.startswith('_'):  # Skip metadata fields
                continue
                
            param_info = {
                'type': self.format_type(field_type),
                'required': self.is_required_field(td_class, field),
                'description': self.extract_field_description(td_class, field),
            }
            
            # Check for literal values
            if get_origin(field_type) is Literal:
                param_info['allowed_values'] = list(get_args(field_type))
            
            params[field] = param_info
        
        return params
```

### Integration with Discovery

```python
# Update discovery.py

@event_handler("system:discover")
async def handle_discover(data: SystemDiscoverData) -> Dict[str, Any]:
    """Discover available events and their parameters."""
    analyzer = TypeAnalyzer()
    
    for event_name, handlers in event_handlers.items():
        for handler in handlers:
            # Try type-based discovery first
            metadata = analyzer.analyze_handler(handler['handler'])
            
            if metadata:
                event_info['parameters'] = metadata.parameters
                event_info['variants'] = metadata.variants
            else:
                # Fallback to current AST/docstring parsing
                event_info['parameters'] = legacy_extract_parameters(handler)
```

## Updated Migration Strategy (2025-07-11)

### Foundation Phase ✅ COMPLETED
1. ✅ Implemented TypeAnalyzer in discovery system
2. ✅ Established co-located TypedDict pattern (not centralized)
3. ✅ Updated discovery to prefer type annotations with fallback
4. ✅ Added backwards compatibility for unannotated handlers

### Current Migration Plan: Systematic Service-by-Service

**Phase 1: Critical Foundation** (In Progress)
1. ✅ `core/state.py` - 12 handlers (Foundation for all state operations)
2. 🔄 `completion/completion_service.py` - 14 handlers (Core LLM functionality)  
3. ⏳ `event_system.py` - 12 handlers (Event infrastructure)

**Phase 2: High-Traffic Services**
4. ⏳ `orchestration/orchestration_service.py` - 11 handlers (Multi-agent coordination)
5. ⏳ `permissions/permission_service.py` - 12 handlers (Security infrastructure)
6. ⏳ `messaging/message_bus.py` - 10 handlers (Inter-service communication)

**Phase 3: Transport & Monitoring**
7. ⏳ `transport/unix_socket.py` - 9 handlers (External communication)
8. ⏳ `core/monitor.py` - 11 handlers (System monitoring)
9. ⏳ `injection/injection_router.py` - 12 handlers (Event injection)

**Phase 4: Observation & Support**
10. ⏳ Observation modules - 18 handlers (observation_manager, replay, historical)
11. ⏳ Core utilities - 16 handlers (correlation, checkpoint, discovery)
12. ⏳ Supporting services - 14 handlers (transformer, daemon_core)

**Phase 5: Specialized Features**
13. ⏳ Evaluation modules - 22 handlers (Various evaluation functionality)
14. ⏳ Utility modules - 12 handlers (health, mcp, litellm, etc.)

### Migration Pattern Established

For each module:
1. **Co-locate TypedDict definitions** with their event handlers
2. **Import typing dependencies** (`Union`, `Literal`, `Required`, `NotRequired`)
3. **Define TypedDict classes** immediately before related handlers
4. **Update handler signatures** to use specific TypedDict types
5. **Test discovery output** to verify types are detected correctly

## Implementation Checklist

### Immediate Tasks
- [ ] Create ksi_daemon/core/type_discovery.py
- [ ] Create ksi_common/event_types.py for common TypedDicts
- [ ] Update composition:create to always save
- [ ] Fix composition:create parameter discovery

### Service Updates
- [ ] Agent service TypedDicts
- [ ] Completion service TypedDicts
- [ ] Orchestration service TypedDicts
- [ ] State service TypedDicts
- [ ] Transformer service TypedDicts

### Discovery Updates
- [ ] Add type introspection to discovery
- [ ] Support Union type variants
- [ ] Extract Required/NotRequired metadata
- [ ] Format type information for output

### Documentation Updates
- [ ] Update event handler guide
- [ ] Create TypedDict patterns guide
- [ ] Update discovery documentation
- [ ] Add migration guide for contributors

## TypedDict Patterns Library

### Simple CRUD Pattern
```python
class EntityCreateData(TypedDict):
    """Create entity data."""
    name: Required[str]
    type: Required[str]
    properties: NotRequired[dict]

class EntityUpdateData(TypedDict):
    """Update entity data."""
    id: Required[str]
    properties: Required[dict]
    merge: NotRequired[bool]
```

### Query Pattern
```python
class QueryData(TypedDict):
    """Query with filters."""
    filters: NotRequired[dict]
    limit: NotRequired[int]
    offset: NotRequired[int]
    order_by: NotRequired[str]
```

### Action Pattern
```python
class ActionData(TypedDict):
    """Action with context."""
    action: Required[Literal['start', 'stop', 'restart']]
    target_id: Required[str]
    force: NotRequired[bool]
    timeout: NotRequired[float]
```

## Benefits

1. **Type Safety**: Catch errors at development time
2. **Better IDE Support**: Autocomplete and type checking
3. **Self-Documenting**: Types are the documentation
4. **Variant Support**: Express complex parameter relationships
5. **Maintainability**: Single source of truth

## Success Metrics

### Current Achievements ✅
1. **Discovery Accuracy**: 100% correct required/optional detection for migrated modules
2. **Type Coverage**: 27% complete (69/254 handlers)
3. **Developer Experience**: Rich type information in `ksi help` commands
4. **Cross-module Resolution**: TypedDict imports work correctly

### Target Goals
1. **Type Coverage**: 100% of event handlers annotated (185 remaining)
2. **Performance**: Type discovery preferred over AST parsing
3. **Documentation**: Self-documenting event interfaces
4. **IDE Support**: Full autocomplete across all services

## Example: Successful Migration Result

### Before Migration
```bash
ksi help composition:create
composition:create
Create and save a composition.

Parameters:
  --name (optional)        # No type info, unclear requirements
  --type (optional) 
  --content (optional)     # No validation or constraints
```

### After Migration ✅
```bash
ksi help composition:create
composition:create
Create and save a composition.

Parameters:
  --name: str (optional)
  --type: Literal['profile', 'prompt', 'orchestration', 'evaluation'] (optional)
      Allowed: profile, prompt, orchestration, evaluation
  --description: str (optional)
  --author: str (optional)
  --metadata: dict[str, Any] (optional)
  --overwrite: bool (optional)
  --content: dict[str, Any] (optional)
  --model: str (optional)
  --capabilities: list[str] (optional)
  --tools: list[str] (optional)
  --role: str (optional)
  --prompt: str (optional)
  --category: str (optional)
```

### Code Implementation
```python
# Co-located TypedDict definitions
class CompositionCreateData(Union[
    CompositionCreateWithContent,
    CompositionCreateProfile, 
    CompositionCreatePrompt,
    CompositionCreateBase
]):
    """Multiple variants supported via Union types."""

@event_handler("composition:create")
async def handle_create_composition(data: CompositionCreateData) -> CompositionResult:
    """Create and save a composition."""
    # Type checker ensures valid data, rich discovery info
```

## Next Steps

### Immediate (Phase 1: Critical Foundation)
1. 🔄 Complete `core/state.py` migration (12 handlers)
2. ⏳ Migrate `completion/completion_service.py` (14 handlers)  
3. ⏳ Migrate `event_system.py` (12 handlers)
4. ⏳ Test all Tier 1 services with `ksi help` commands

### Medium-term (Phases 2-3: Infrastructure)
5. ⏳ Migrate orchestration, permissions, messaging services
6. ⏳ Migrate transport, monitoring, injection services
7. ⏳ Establish automated testing for type discovery

### Long-term (Phases 4-5: Completion)
8. ⏳ Migrate observation and utility modules
9. ⏳ Migrate specialized evaluation modules
10. ⏳ Remove legacy AST-based discovery fallback
11. ⏳ Add type checking to CI pipeline

### Success Criteria for Each Migration
- [ ] TypedDict definitions co-located with handlers
- [ ] All parameters show correct types in `ksi help <event>`
- [ ] Required/optional status accurate
- [ ] Literal values show as "Allowed:" constraints
- [ ] Union types supported for variant handlers

---

*This migration will transform KSI's event system from string-based to type-based, improving reliability, maintainability, and developer experience.*