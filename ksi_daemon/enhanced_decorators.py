#!/usr/bin/env python3
"""
Enhanced decorators for KSI event handlers with rich metadata support.

Provides decorators that capture comprehensive metadata including:
- Parameter descriptions and constraints
- Examples with context
- Performance characteristics  
- Best practices
"""

from typing import Dict, Any, Optional, Callable, List, Type, TypedDict
from dataclasses import dataclass, field
from functools import wraps

from ksi_daemon.plugin_utils import _extract_metadata, _registry

@dataclass
class EventParameter:
    """Rich parameter definition."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    allowed_values: Optional[List[Any]] = None
    example: Any = None
    constraints: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to discovery format."""
        result = {
            "type": self.type,
            "description": self.description,
            "required": self.required
        }
        if self.default is not None:
            result["default"] = self.default
        if self.allowed_values:
            result["allowed_values"] = self.allowed_values
        if self.example is not None:
            result["example"] = self.example
        if self.constraints:
            result["constraints"] = self.constraints
        return result

@dataclass
class EventExample:
    """Rich example definition."""
    description: str
    data: Dict[str, Any]
    context: Optional[str] = None
    expected_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to discovery format."""
        result = {
            "description": self.description,
            "data": self.data
        }
        if self.context:
            result["context"] = self.context
        if self.expected_result:
            result["expected_result"] = self.expected_result
        return result

def enhanced_event_handler(
    event_name: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[List[EventParameter]] = None,
    examples: Optional[List[EventExample]] = None,
    data_type: Optional[Type[TypedDict]] = None,
    # Declarative metadata
    tags: Optional[List[str]] = None,
    # Performance hints
    async_response: bool = False,
    typical_duration_ms: Optional[int] = None,
    has_side_effects: bool = True,
    idempotent: bool = False,
    # Cost/resource hints
    has_cost: bool = False,
    requires_auth: bool = False,
    rate_limited: bool = False,
    # Best practices
    best_practices: Optional[List[str]] = None,
    common_errors: Optional[List[str]] = None,
    related_events: Optional[List[str]] = None
):
    """
    Enhanced event handler decorator with comprehensive metadata.
    
    This decorator captures rich metadata for better discovery and documentation,
    enabling Claude and other consumers to understand not just what parameters
    an event accepts, but also performance characteristics, best practices, and
    common pitfalls.
    
    Args:
        event_name: The event name (e.g., "state:set")
        summary: Brief one-line summary
        description: Detailed description
        parameters: List of EventParameter definitions
        examples: List of EventExample definitions
        data_type: Optional TypedDict for type safety
        tags: Optional list of declarative tags for categorization
        async_response: Whether this returns immediately with async processing
        typical_duration_ms: Typical execution time in milliseconds
        has_side_effects: Whether this modifies system state
        idempotent: Whether calling multiple times has same effect as once
        has_cost: Whether this incurs monetary cost (e.g., LLM calls)
        requires_auth: Whether authentication is required
        rate_limited: Whether rate limits apply
        best_practices: List of best practice tips
        common_errors: List of common error scenarios
        related_events: List of related event names
    """
    def decorator(func: Callable) -> Callable:
        # Extract base metadata (AST, TypedDict, docstring)
        base_metadata = _extract_metadata(func, event_name, data_type)
        
        # Override with explicit parameters if provided
        if parameters:
            param_dict = {p.name: p.to_dict() for p in parameters}
            base_metadata["parameters"] = param_dict
        
        # Add enhanced metadata
        enhanced_metadata = {
            **base_metadata,
            "performance": {
                "async_response": async_response,
                "typical_duration_ms": typical_duration_ms,
                "has_side_effects": has_side_effects,
                "idempotent": idempotent
            },
            "requirements": {
                "has_cost": has_cost,
                "requires_auth": requires_auth,
                "rate_limited": rate_limited
            }
        }
        
        # Add optional fields
        if summary:
            enhanced_metadata["summary"] = summary
        if description:
            enhanced_metadata["description"] = description
        if examples:
            enhanced_metadata["examples"] = [ex.to_dict() for ex in examples]
        if tags:
            enhanced_metadata["tags"] = tags
        if best_practices:
            enhanced_metadata["best_practices"] = best_practices
        if common_errors:
            enhanced_metadata["common_errors"] = common_errors
        if related_events:
            enhanced_metadata["related_events"] = related_events
        
        # Register with enhanced metadata
        _registry.register_event(event_name, enhanced_metadata)
        
        # Mark function with metadata
        func._ksi_event_name = event_name
        func._ksi_event_metadata = enhanced_metadata
        func._ksi_data_type = data_type
        
        # Keep backward compatibility
        func._event_patterns = [event_name]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator