#!/usr/bin/env python3
"""
Discovery-Powered Error Handler

Enhances event system error messages using discovery data to provide
actionable guidance when events fail.

Function-based implementation following KSI patterns.
"""

import re
from typing import Dict, Any, List, Optional
from difflib import get_close_matches

from ksi_common.logging import get_bound_logger
from ksi_common.event_utils import build_error_response, build_success_response

logger = get_bound_logger("error_handler")

# Module-level state (following config_manager pattern)
_router = None


def initialize_error_handler(router):
    """
    Initialize the error handler with event router for discovery access.
    
    Args:
        router: Event router instance for accessing discovery data
    """
    global _router
    _router = router
    logger.debug("Error handler initialized with router")


async def enhance_error(
    event_name: str, 
    provided_params: Dict[str, Any], 
    original_error: Exception,
    verbosity: str = "medium"
) -> Dict[str, Any]:
    """
    Enhance an error with discovery-powered guidance.
    
    Args:
        event_name: The event that failed
        provided_params: Parameters that were provided
        original_error: The original exception
        verbosity: Error detail level (minimal, medium, verbose)
        
    Returns:
        Enhanced error dict with suggestions and guidance
    """
    error_str = str(original_error)
    
    # Classify the error type
    error_type = _classify_error(error_str)
    
    # Get event information from discovery if available
    event_info = await _get_event_info(event_name)
    
    # Generate enhanced error based on type and verbosity
    if error_type == "missing_parameter":
        return await _handle_missing_parameter(
            event_name, provided_params, error_str, event_info, verbosity
        )
    elif error_type == "type_mismatch":
        return await _handle_type_mismatch(
            event_name, provided_params, error_str, event_info, verbosity
        )
    elif error_type == "unknown_event":
        return await _handle_unknown_event(
            event_name, provided_params, error_str, verbosity
        )
    elif error_type == "attribute_error":
        return await _handle_attribute_error(
            event_name, provided_params, error_str, event_info, verbosity
        )
    else:
        # Generic enhancement
        return await _handle_generic_error(
            event_name, provided_params, error_str, event_info, verbosity
        )


async def handle_unknown_event(
    event_name: str, provided_params: Dict[str, Any], verbosity: str
) -> Dict[str, Any]:
    """Handle unknown event with discovery guidance."""
    
    # Get all available events
    all_events = list(_router._handlers.keys()) if _router else []
    
    # Find similar events using fuzzy matching
    similar = get_close_matches(event_name, all_events, n=3, cutoff=0.6)
    
    # Extract unique namespaces
    namespaces = sorted(set(event.split(':')[0] for event in all_events if ':' in event))
    
    # Build details for enhanced error response
    details = {}
    
    if similar:
        details["similar"] = similar
        
    if verbosity in ["medium", "verbose"] and namespaces:
        details["namespaces"] = namespaces
    
    return build_error_response(f"Unknown event: {event_name}", details if details else None)


def _classify_error(error_str: str) -> str:
    """Classify the error type based on error message patterns."""
    # AttributeError pattern - check this first as it's commonly misclassified
    if "'list' object has no attribute" in error_str or "'dict' object has no attribute" in error_str:
        return "attribute_error"
    elif "'object has no attribute" in error_str:
        return "attribute_error"
    elif "AttributeError:" in error_str:
        return "attribute_error"
    elif "Missing required parameter" in error_str:
        return "missing_parameter"
    elif error_str.startswith("'") and error_str.endswith("'"):
        # KeyError pattern: 'parameter_name'
        return "missing_parameter"
    elif "expected" in error_str and "got" in error_str:
        return "type_mismatch"
    elif "Event not found" in error_str or "Unknown event" in error_str:
        return "unknown_event"
    elif "must be one of" in error_str:
        return "invalid_value"
    else:
        return "generic"


async def _get_event_info(event_name: str) -> Optional[Dict[str, Any]]:
    """Get event information from discovery system."""
    if not _router or event_name not in _router._handlers:
        return None
        
    try:
        from ksi_daemon.core.discovery import UnifiedHandlerAnalyzer, extract_summary
        
        handler = _router._handlers[event_name][0]
        
        # Use the same analysis as system:help
        handler_info = {
            "module": handler.module,
            "handler": handler.name,
            "async": handler.is_async,
            "summary": extract_summary(handler.func),
        }
        
        analyzer = UnifiedHandlerAnalyzer(handler.func, event_name=event_name)
        analysis_result = analyzer.analyze()
        handler_info.update(analysis_result)
        
        return handler_info
        
    except Exception as e:
        logger.warning(f"Could not get event info for {event_name}: {e}")
        return None


async def _handle_missing_parameter(
    event_name: str, provided_params: Dict[str, Any], 
    error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
) -> Dict[str, Any]:
    """Handle missing parameter errors."""
    
    # Extract parameter name from error
    param_match = re.search(r"Missing required parameter: (\w+)", error_str)
    if param_match:
        missing_param = param_match.group(1)
    elif error_str.startswith("'") and error_str.endswith("'"):
        # KeyError pattern: 'parameter_name'
        missing_param = error_str.strip("'")
    else:
        return build_error_response(error_str)
        
    if not missing_param:
        return build_error_response(error_str)
    
    # Build enhanced error message
    error_message = f"Missing required parameter: {missing_param}"
    details = {}
    
    if event_info and verbosity in ["medium", "verbose"]:
        # Get available parameters
        parameters = event_info.get("parameters", {})
        if parameters:
            param_names = list(parameters.keys())
            details["available"] = param_names
            
            # Add type info if we have it for the missing parameter
            if missing_param in parameters:
                param_info = parameters[missing_param]
                param_type = param_info.get("type", "unknown")
                error_message = f"Missing required parameter: {missing_param} ({param_type})"
    
    if verbosity == "verbose" and event_info:
        # Add full parameter help
        details["help"] = f"Use: help {event_name}"
        
    return build_error_response(error_message, details if details else None)


async def _handle_type_mismatch(
    event_name: str, provided_params: Dict[str, Any],
    error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
) -> Dict[str, Any]:
    """Handle type mismatch errors."""
    
    details = {}
    
    if verbosity in ["medium", "verbose"] and event_info:
        # Could add type examples here
        parameters = event_info.get("parameters", {})
        if parameters:
            details["help"] = f"Use: help {event_name}"
    
    return build_error_response(error_str, details if details else None)


async def _handle_unknown_event(
    event_name: str, provided_params: Dict[str, Any],
    error_str: str, verbosity: str
) -> Dict[str, Any]:
    """Handle unknown event errors."""
    
    details = {}
    
    if verbosity in ["medium", "verbose"] and _router:
        # Find similar event names
        all_events = list(_router._handlers.keys())
        similar = get_close_matches(event_name, all_events, n=3, cutoff=0.6)
        
        if similar:
            details["similar"] = similar
    
    return build_error_response(error_str, details if details else None)


async def _handle_generic_error(
    event_name: str, provided_params: Dict[str, Any],
    error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
) -> Dict[str, Any]:
    """Handle generic errors."""
    
    details = {}
    
    if verbosity == "verbose" and event_info:
        details["help"] = f"Use: help {event_name}"
        
    return build_error_response(error_str, details if details else None)


async def _handle_attribute_error(
    event_name: str, provided_params: Dict[str, Any],
    error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
) -> Dict[str, Any]:
    """Handle attribute errors (e.g., 'list' object has no attribute 'get')."""
    
    # Extract what type was received and what attribute was missing
    type_match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_str)
    
    if type_match:
        received_type = type_match.group(1)
        missing_attr = type_match.group(2)
        error_message = f"Type error: Received {received_type} but expected a dict-like object with '{missing_attr}' method"
    else:
        error_message = f"Attribute error: {error_str}"
    
    details = {}
    
    if verbosity in ["medium", "verbose"]:
        details["error_type"] = "type_mismatch"
        details["received"] = f"Handler received wrong data type"
        
        if type_match:
            details["expected"] = "dict"
            details["actual"] = received_type
            
        if provided_params:
            details["provided_params"] = provided_params
    
    if verbosity == "verbose" and event_info:
        # Add parameter information
        parameters = event_info.get("parameters", {})
        if parameters:
            details["expected_params"] = list(parameters.keys())
            details["help"] = f"Use: help {event_name}"
    
    return build_error_response(error_message, details if details else None)


def get_error_handler_router():
    """Get the current router (for debugging/testing)."""
    return _router