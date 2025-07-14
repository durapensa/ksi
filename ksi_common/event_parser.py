#!/usr/bin/env python3
"""
Event parser for KSI event handlers.

Core KSI functionality: The event system enriches all events with originator 
information (originator_id, agent_id, session_id, etc.) to ensure complete 
event traceability and context awareness throughout the system.

This module provides the standard utilities for handlers to work with enriched
events, cleanly separating handler-specific data from system-injected metadata.
This is the expected pattern for all event handlers in KSI.

Usage:
    from ksi_common.event_parser import parse_event_data
    
    @event_handler("my:event")
    async def handle_my_event(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
        # Standard pattern: extract handler-specific data
        data = parse_event_data(raw_data, MyEventData)
        
        # Process with clean, type-safe data
        result = process_my_event(data)
        
        # Return response with originator context
        return build_response(result, "my_handler", "my:event", context)
"""
from typing import Any, Dict, TypeVar, Type, Optional, Set, get_type_hints, get_args, get_origin
from typing_extensions import TypedDict, NotRequired, Required

T = TypeVar('T')

# Standard system metadata fields injected by event system
# NOTE: session_id is NOT included - it's private to completion system
# NOTE: correlation_id is NOT included - it's internal to modules that use it
SYSTEM_METADATA_FIELDS = {
    "_agent_id",
    "_client_id",
    "_event_id",
    "_event_timestamp"
}


def event_format_linter(raw_data: Dict[str, Any], expected_type: Type[T] = None) -> Dict[str, Any]:
    """Strip system metadata from event data, returning clean handler data.
    
    Args:
        raw_data: The raw event data potentially containing injected system fields
        expected_type: Optional TypedDict type for validation/filtering
        
    Returns:
        Clean data dictionary without injected system metadata fields
    """
    if not isinstance(raw_data, dict):
        # Non-dict data is returned as-is
        return raw_data
    
    # Separate originator fields from actual data
    clean_data = {}
    
    if expected_type:
        # If we have a type, only include expected fields
        expected_fields = get_expected_fields(expected_type)
        for key, value in raw_data.items():
            if key in expected_fields:
                clean_data[key] = value
    else:
        # No type specified, remove known system metadata fields
        for key, value in raw_data.items():
            if key not in SYSTEM_METADATA_FIELDS:
                clean_data[key] = value
                
    return clean_data


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


def extract_system_handler_data(raw_data: Dict[str, Any], expected_type: Type[T] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract clean business data and system metadata for system infrastructure handlers.
    
    This is the standard utility for system infrastructure handlers (monitor, event_system, 
    transport) that need to work with both clean business data and system metadata.
    Uses SYSTEM_METADATA_FIELDS as the single source of truth.
    
    Args:
        raw_data: The raw enriched event data from the event system
        expected_type: Optional TypedDict type for validation
        
    Returns:
        Tuple of (clean_business_data, system_metadata_dict)
    """
    clean_data = event_format_linter(raw_data, expected_type)
    system_metadata = extract_system_metadata(raw_data)
    return clean_data, system_metadata


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