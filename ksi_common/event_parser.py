#!/usr/bin/env python3
"""
Event parser for KSI event handlers.

Core KSI functionality: The event system enriches all events with originator 
information (originator_id, agent_id, session_id, etc.) to ensure complete 
event traceability and context awareness throughout the system.

This module provides constants and utilities for the unified _ksi_context pattern.
All system metadata is now contained within the _ksi_context field of event data.

Usage:
    from typing_extensions import TypedDict, NotRequired
    
    class MyEventData(TypedDict):
        field: str
        _ksi_context: NotRequired[Dict[str, Any]]  # Include in all TypedDicts
    
    @event_handler("my:event")
    async def handle_my_event(data: MyEventData, context: Optional[Dict[str, Any]] = None):
        # Direct data access - no extraction needed
        result = process_my_event(data)
        
        # Return response
        return build_response(result, "my_handler", "my:event", context)
"""
from typing import Any, Dict, TypeVar, Type, Optional, Set, get_type_hints, get_args, get_origin
from typing_extensions import TypedDict, NotRequired, Required

T = TypeVar('T')

# Standard system metadata fields injected by event system
# NOTE: session_id is NOT included - it's private to completion system
SYSTEM_METADATA_FIELDS = {
    "_agent_id",
    "_client_id",
    "_event_id",
    "_event_timestamp",
    "_correlation_id",    # Tracks related events across the system
    "_parent_event_id",   # Links events in causal chains
    "_root_event_id",     # Original event that started the chain
    "_event_depth"        # How deep in the event chain (0 = root)
}


def extract_system_metadata(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract system metadata from event data.
    
    Args:
        raw_data: The raw event data containing injected fields
        
    Returns:
        Dictionary containing only system metadata fields
    """
    if not isinstance(raw_data, dict):
        return {}
        
    metadata_info = {}
    for field in SYSTEM_METADATA_FIELDS:
        if field in raw_data:
            metadata_info[field] = raw_data[field]
            
    return metadata_info


def get_expected_fields(typed_dict_class: Type[Any]) -> Set[str]:
    """Extract field names from a TypedDict class.
    
    Args:
        typed_dict_class: The TypedDict class
        
    Returns:
        Set of expected field names
    """
    # Get type hints which includes all fields
    hints = get_type_hints(typed_dict_class)
    fields = set(hints.keys())
    
    # Also check __annotations__ for runtime access
    if hasattr(typed_dict_class, '__annotations__'):
        fields.update(typed_dict_class.__annotations__.keys())
        
    # Check for __required_keys__ and __optional_keys__ (Python 3.9+)
    if hasattr(typed_dict_class, '__required_keys__'):
        fields.update(typed_dict_class.__required_keys__)
    if hasattr(typed_dict_class, '__optional_keys__'):
        fields.update(typed_dict_class.__optional_keys__)
        
    return fields


def validate_event_data(raw_data: Dict[str, Any], expected_type: Type[T]) -> tuple[bool, Optional[str]]:
    """Validate event data against expected TypedDict.
    
    Only validates that required fields are present, ignoring extra fields
    (since originator fields will be injected).
    
    Args:
        raw_data: The raw event data
        expected_type: TypedDict type to validate against
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(raw_data, dict):
        return False, "Data must be a dictionary"
        
    # Get required fields
    required_fields = set()
    if hasattr(expected_type, '__required_keys__'):
        required_fields = expected_type.__required_keys__
    else:
        # Fallback: assume all fields without NotRequired are required
        hints = get_type_hints(expected_type)
        for field, field_type in hints.items():
            # Check if NotRequired is used
            origin = get_origin(field_type)
            if origin is not NotRequired:
                required_fields.add(field)
    
    # Check required fields are present
    missing_fields = required_fields - set(raw_data.keys())
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
        
    return True, None


# Convenience functions for common patterns

def get_field(raw_data: Dict[str, Any], field: str, default: Any = None) -> Any:
    """Get a field value, checking both data and originator sections.
    
    Args:
        raw_data: The raw event data
        field: Field name to retrieve
        default: Default value if not found
        
    Returns:
        Field value or default
    """
    return raw_data.get(field, default)


def has_system_metadata(raw_data: Dict[str, Any]) -> bool:
    """Check if event data contains system metadata.
    
    Args:
        raw_data: The raw event data
        
    Returns:
        True if any system metadata fields are present
    """
    if not isinstance(raw_data, dict):
        return False
        
    return any(field in raw_data for field in SYSTEM_METADATA_FIELDS)