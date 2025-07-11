# TypedDict-Based Discovery System Migration Plan

## Overview

This document outlines the migration from docstring-based parameter documentation to a TypedDict-based discovery system. This will make KSI's event system more type-safe, maintainable, and self-documenting.

## Goals

1. **Replace docstring instructions** with type-based introspection
2. **Improve discovery accuracy** by understanding optional vs required parameters
3. **Enable variant-aware discovery** for complex handlers with multiple usage patterns
4. **Reduce docstrings** to single-line descriptions
5. **Improve IDE support** through proper type annotations

## Current State Analysis

### Problems with Current System

1. **Discovery inaccuracy**: All `data.get()` calls marked as required parameters
2. **Docstring parsing**: Complex instructions buried in docstrings
3. **No variant support**: Can't express "if X then Y is required"
4. **Maintenance burden**: Docstrings drift from implementation

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

## Migration Strategy

### Phase 1: Foundation (Week 1)
1. Implement TypeAnalyzer in discovery system
2. Create common TypedDict base classes
3. Update discovery to prefer type annotations
4. Add backwards compatibility for unannotated handlers

### Phase 2: Core Events (Week 2)
1. Annotate system events (health, discover, help)
2. Annotate state management events
3. Annotate agent lifecycle events
4. Remove docstring parameters

### Phase 3: Service Events (Week 3)
1. Annotate composition service
2. Annotate orchestration service
3. Annotate evaluation service
4. Update tests

### Phase 4: Cleanup (Week 4)
1. Remove docstring parsing code
2. Update documentation
3. Add type checking to CI
4. Performance optimization

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

1. **Discovery Accuracy**: 100% correct required/optional detection
2. **Docstring Reduction**: 90% reduction in docstring size
3. **Type Coverage**: 100% of event handlers annotated
4. **Developer Experience**: Improved autocomplete and error detection

## Example: Migrated composition:create

```python
# Before: 30+ line docstring, confusing parameters
# After: Clean types, one-line docstring

@event_handler("composition:create")
async def handle_create_composition(data: CompositionCreateData) -> CompositionResult:
    """Create and save a composition."""
    
    # Type checker ensures valid data
    if 'content' in data:
        composition = data['content']  # Type: dict
    else:
        # Build from components
        composition = build_composition(data)  # Type-safe access
    
    # Always save (no in-memory option)
    return await save_composition(composition)
```

## Next Steps

1. Review and approve this plan
2. Create type_discovery.py module
3. Start with composition:create as proof of concept
4. Gradually migrate all services
5. Remove legacy discovery code

---

*This migration will transform KSI's event system from string-based to type-based, improving reliability, maintainability, and developer experience.*