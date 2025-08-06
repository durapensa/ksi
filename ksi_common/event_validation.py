#!/usr/bin/env python3
"""
Event Validation Utilities

Provides validation functions to check if events are handled by real handlers
or transformers, excluding universal broadcast patterns.
"""

from typing import Optional, Dict, Any, List, Tuple
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_validation", version="1.0.0")


def matches_pattern(event: str, pattern: str) -> bool:
    """
    Check if event matches pattern (supports * wildcard).
    
    Extracted from EventRouter._matches_pattern for consistency.
    
    Args:
        event: Event name to check
        pattern: Pattern to match against
        
    Returns:
        True if event matches pattern, False otherwise
    """
    if pattern == "*":
        return True
        
    parts = pattern.split(":")
    event_parts = event.split(":")
    
    if len(parts) != len(event_parts):
        return False
        
    for p, e in zip(parts, event_parts):
        if p != "*" and p != e:
            return False
            
    return True


def is_universal_broadcast_transformer(transformer_def: Dict[str, Any]) -> bool:
    """
    Check if a transformer is the universal broadcast transformer.
    
    The universal broadcast transformer has:
    - source: "*"
    - target: "monitor:broadcast_event"
    
    Args:
        transformer_def: Transformer definition dictionary
        
    Returns:
        True if this is the universal broadcast transformer
    """
    source = transformer_def.get("source", "")
    target = transformer_def.get("target", "")
    
    return source == "*" and target == "monitor:broadcast_event"


def is_event_handled(event_name: str, router=None) -> bool:
    """
    Check if an event has actual processing (Python handlers or transformers).
    
    Excludes universal broadcast transformers to avoid false positives.
    This uses the exact same logic as EventRouter.emit() for consistency.
    
    Args:
        event_name: The event name to check
        router: EventRouter instance, or None to get global router
        
    Returns:
        True if event has actual processing, False if only universal broadcast
    """
    if router is None:
        # Import here to avoid circular dependency
        try:
            from ksi_daemon.event_system import get_router
            router = get_router()
        except ImportError:
            logger.warning("Cannot import router, event validation unavailable")
            return False
    
    # Check direct Python handlers
    if hasattr(router, '_handlers') and event_name in router._handlers:
        handlers = router._handlers[event_name]
        if handlers:  # Non-empty list
            logger.debug(f"Event {event_name} has {len(handlers)} direct handlers")
            return True
    
    # Check pattern matching Python handlers  
    if hasattr(router, '_pattern_handlers'):
        for pattern, handler in router._pattern_handlers:
            if matches_pattern(event_name, pattern):
                logger.debug(f"Event {event_name} matches handler pattern {pattern}")
                return True
    
    # Check direct transformers (excluding universal broadcast)
    if hasattr(router, '_transformers') and event_name in router._transformers:
        transformers = router._transformers[event_name]
        real_transformers = [t for t in transformers if not is_universal_broadcast_transformer(t)]
        if real_transformers:
            logger.debug(f"Event {event_name} has {len(real_transformers)} direct transformers")
            return True
    
    # Check pattern transformers (excluding universal broadcast)
    if hasattr(router, '_pattern_transformers'):
        for pattern, transformer_def in router._pattern_transformers:
            if matches_pattern(event_name, pattern) and not is_universal_broadcast_transformer(transformer_def):
                logger.debug(f"Event {event_name} matches transformer pattern {pattern}")
                return True
    
    logger.debug(f"Event {event_name} has no actual processing (only universal broadcast or nothing)")
    return False


def get_event_handlers(event_name: str, router=None) -> Dict[str, Any]:
    """
    Get detailed information about what handles an event.
    
    Args:
        event_name: The event name to analyze
        router: EventRouter instance, or None to get global router
        
    Returns:
        Dictionary with handler and transformer information
    """
    if router is None:
        try:
            from ksi_daemon.event_system import get_router
            router = get_router()
        except ImportError:
            return {"error": "Cannot import router"}
    
    result = {
        "event": event_name,
        "direct_handlers": 0,
        "pattern_handlers": [],
        "direct_transformers": 0,
        "pattern_transformers": [],
        "universal_broadcast": False,
        "is_handled": False
    }
    
    # Count direct handlers
    if hasattr(router, '_handlers') and event_name in router._handlers:
        result["direct_handlers"] = len(router._handlers[event_name])
    
    # Check pattern handlers
    if hasattr(router, '_pattern_handlers'):
        for pattern, handler in router._pattern_handlers:
            if matches_pattern(event_name, pattern):
                result["pattern_handlers"].append({
                    "pattern": pattern,
                    "handler": str(handler)
                })
    
    # Count direct transformers (excluding universal broadcast)
    if hasattr(router, '_transformers') and event_name in router._transformers:
        transformers = router._transformers[event_name]
        real_transformers = []
        for t in transformers:
            if is_universal_broadcast_transformer(t):
                result["universal_broadcast"] = True
            else:
                real_transformers.append(t)
        result["direct_transformers"] = len(real_transformers)
    
    # Check pattern transformers
    if hasattr(router, '_pattern_transformers'):
        for pattern, transformer_def in router._pattern_transformers:
            if matches_pattern(event_name, pattern):
                if is_universal_broadcast_transformer(transformer_def):
                    result["universal_broadcast"] = True
                else:
                    result["pattern_transformers"].append({
                        "pattern": pattern,
                        "source": transformer_def.get("source"),
                        "target": transformer_def.get("target")
                    })
    
    # Determine if event has actual processing (excluding universal broadcast)
    result["is_handled"] = (
        result["direct_handlers"] > 0 or 
        len(result["pattern_handlers"]) > 0 or
        result["direct_transformers"] > 0 or
        len(result["pattern_transformers"]) > 0
    )
    
    return result