#!/usr/bin/env python3
"""
Event Discovery Module - Simplified Pure Event-Based Version

Provides essential discovery capabilities:
- List all events with parameters
- Show which events trigger other events
- Automatic extraction from implementation code
"""

from typing import Any, Dict, TypedDict, Literal
from typing_extensions import NotRequired

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler

from .discovery_utils import (
    FORMAT_MCP,
    FORMAT_VERBOSE,
    analyze_handler,
    build_discovery_response,
    extract_summary,
    filter_events,
    format_event_info,
    generate_usage_example,
)
from .type_discovery import analyze_handler as type_analyze_handler

logger = get_bound_logger("discovery", version="2.0.0")


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for discovery service
    pass


class SystemDiscoverData(TypedDict):
    """Universal discovery endpoint - everything you need to understand KSI."""
    detail: NotRequired[bool]  # Include parameters and triggers (default: False)
    namespace: NotRequired[str]  # Filter by namespace (optional)
    event: NotRequired[str]  # Get details for specific event (optional)
    module: NotRequired[str]  # Filter by module name (optional)
    format_style: NotRequired[Literal['verbose', 'compact', 'ultra_compact', 'mcp']]  # Output format (default: verbose)


class SystemHelpData(TypedDict):
    """Get detailed help for a specific event."""
    event: str  # The event name to get help for (required)
    format_style: NotRequired[Literal['verbose', 'compact', 'mcp']]  # Output format (default: verbose)


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:startup")
async def handle_startup(config: SystemStartupData) -> Dict[str, Any]:
    """Initialize discovery service."""
    logger.info("Discovery service started")
    return {"status": "discovery_ready"}


@event_handler("system:discover")
async def handle_discover(data: SystemDiscoverData) -> Dict[str, Any]:
    """
    Universal discovery endpoint - everything you need to understand KSI.

    Parameters:
        detail (bool): Include parameters and triggers (default: False)
        namespace (str): Filter by namespace (optional)
        event (str): Get details for specific event (optional)
        module (str): Filter by module name (optional)
        format_style (str): Output format - verbose, compact, ultra_compact, mcp (default: verbose)

    Returns:
        Dictionary with events, their parameters, and what they trigger
    """
    include_detail = data.get("detail", False)
    namespace_filter = data.get("namespace")
    event_filter = data.get("event")
    module_filter = data.get("module")
    format_style = data.get("format_style", FORMAT_VERBOSE)

    from ksi_daemon.event_system import get_router

    router = get_router()

    all_events = {}

    # Gather all events first
    for event_name, handlers in router._handlers.items():
        handler = handlers[0]  # Use first handler

        handler_info = {
            "module": handler.module,
            "handler": handler.name,
            "async": handler.is_async,
            "summary": extract_summary(handler.func),
        }

        if include_detail:
            # Always try type-based discovery first
            type_metadata = type_analyze_handler(handler.func)
            
            # Always run AST analysis for additional info
            ast_analysis = analyze_handler(handler.func, event_name)
            
            if type_metadata and type_metadata.get('parameters'):
                # Start with type-based parameters (accurate types)
                handler_info['parameters'] = type_metadata['parameters'].copy()
                
                # Enhance with AST-discovered info
                ast_params = ast_analysis.get('parameters', {})
                for param_name, ast_info in ast_params.items():
                    if param_name in handler_info['parameters']:
                        # Merge descriptions if AST has one and TypedDict doesn't
                        if ast_info.get('comment') and not handler_info['parameters'][param_name].get('description'):
                            handler_info['parameters'][param_name]['description'] = ast_info['comment']
                    else:
                        # Parameter found by AST but not TypedDict (e.g., dynamic access)
                        handler_info['parameters'][param_name] = {
                            'type': ast_info.get('type', 'Any'),
                            'required': ast_info.get('required', False),
                            'description': ast_info.get('comment'),
                            'default': ast_info.get('default')
                        }
                
                # Always get triggers from AST
                handler_info['triggers'] = ast_analysis.get('triggers', [])
            else:
                # Fallback to pure AST analysis
                handler_info.update(ast_analysis)

        all_events[event_name] = handler_info

    # Apply filters
    filtered_events = filter_events(all_events, namespace=namespace_filter, module=module_filter, pattern=event_filter)

    # Format events based on style
    formatted_events = {}
    for event_name, handler_info in filtered_events.items():
        formatted_events[event_name] = format_event_info(
            event_name, handler_info, style=format_style, include_params=include_detail, include_triggers=include_detail
        )

    # Build response
    response = build_discovery_response(formatted_events, style=format_style)
    
    # If filtering by module, add module description
    if module_filter:
        module_info = router.inspect_module(module_filter)
        if module_info and "docstring" in module_info:
            response["module_description"] = module_info["docstring"].split("\n")[0].strip()
    
    return response


@event_handler("system:help")
async def handle_help(data: SystemHelpData) -> Dict[str, Any]:
    """
    Get detailed help for a specific event.

    Parameters:
        event (str): The event name to get help for (required)
        format_style (str): Output format - verbose, compact, mcp (default: verbose)
    """
    event_name = data.get("event")
    if not event_name:
        return {"error": "event parameter required"}

    format_style = data.get("format_style", FORMAT_VERBOSE)

    from ksi_daemon.event_system import get_router

    router = get_router()

    # Find the event handler directly
    if event_name not in router._handlers:
        return {"error": f"Event not found: {event_name}"}

    handler = router._handlers[event_name][0]

    # Analyze the handler
    handler_info = {
        "module": handler.module,
        "handler": handler.name,
        "async": handler.is_async,
        "summary": extract_summary(handler.func),
    }

    # Always try type-based discovery first
    type_metadata = type_analyze_handler(handler.func)
    
    # Always run AST analysis for additional info
    ast_analysis = analyze_handler(handler.func, event_name)
    
    if type_metadata and type_metadata.get('parameters'):
        # Start with type-based parameters (accurate types)
        handler_info['parameters'] = type_metadata['parameters'].copy()
        
        # Enhance with AST-discovered info
        ast_params = ast_analysis.get('parameters', {})
        for param_name, ast_info in ast_params.items():
            if param_name in handler_info['parameters']:
                # Merge descriptions if AST has one and TypedDict doesn't
                if ast_info.get('comment') and not handler_info['parameters'][param_name].get('description'):
                    handler_info['parameters'][param_name]['description'] = ast_info['comment']
            else:
                # Parameter found by AST but not TypedDict
                handler_info['parameters'][param_name] = {
                    'type': ast_info.get('type', 'Any'),
                    'required': ast_info.get('required', False),
                    'description': ast_info.get('comment'),
                    'default': ast_info.get('default')
                }
        
        # Always get triggers from AST
        handler_info['triggers'] = ast_analysis.get('triggers', [])
    else:
        # Fallback to pure AST analysis
        handler_info.update(ast_analysis)

    # Format based on style
    if format_style == FORMAT_MCP:
        # Return MCP-compatible format
        return format_event_info(
            event_name, handler_info, style=FORMAT_MCP, include_params=True, include_triggers=False
        )
    else:
        # Standard help format
        formatted_info = format_event_info(
            event_name,
            handler_info,
            style=format_style,
            include_params=True,
            include_triggers=True,
            include_examples=True,
        )

        # Add usage example
        formatted_info["usage"] = generate_usage_example(event_name, handler_info.get("parameters", {}))

        return formatted_info




@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean shutdown."""
    logger.info("Discovery service stopped")
