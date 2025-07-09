#!/usr/bin/env python3
"""
Event Discovery Module - Simplified Pure Event-Based Version

Provides essential discovery capabilities:
- List all events with parameters
- Show which events trigger other events
- Automatic extraction from implementation code
"""

from typing import Any, Dict

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

logger = get_bound_logger("discovery", version="2.0.0")


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize discovery service."""
    logger.info("Discovery service started")
    return {"status": "discovery_ready"}


@event_handler("system:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
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
            # Extract implementation details via AST
            analysis = analyze_handler(handler.func, event_name)
            handler_info.update(analysis)

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
    return build_discovery_response(formatted_events, style=format_style)


@event_handler("system:help")
async def handle_help(data: Dict[str, Any]) -> Dict[str, Any]:
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

    # Get detailed analysis
    analysis = analyze_handler(handler.func, event_name)
    handler_info.update(analysis)

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


@event_handler("module:list_events")
async def handle_module_list_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get list of events handled by a specific module.

    Parameters:
        module_name (str): The full module name (e.g., "ksi_daemon.core.discovery")
        detail (bool): Include event details like parameters and triggers (default: False)
        format_style (str): Output format - verbose, compact, ultra_compact (default: verbose)

    Returns:
        Dictionary with module name and its events
    """
    module_name = data.get("module_name")
    if not module_name:
        return {"error": "module_name parameter required"}

    include_detail = data.get("detail", False)
    format_style = data.get("format_style", FORMAT_VERBOSE)

    from ksi_daemon.event_system import get_router

    router = get_router()

    # Get module info
    module_info = router.inspect_module(module_name)
    if not module_info:
        return {"error": f"Module not found: {module_name}"}

    # Build event info for each handler in the module
    events = {}
    for handler_data in module_info["handlers"]:
        event_name = handler_data["event"]

        # Get the actual handler object
        if event_name in router._handlers:
            handler = router._handlers[event_name][0]

            handler_info = {
                "module": handler.module,
                "handler": handler.name,
                "async": handler.is_async,
                "summary": extract_summary(handler.func),
            }

            if include_detail:
                # Get detailed analysis
                analysis = analyze_handler(handler.func, event_name)
                handler_info.update(analysis)

            # Format the event info
            events[event_name] = format_event_info(
                event_name,
                handler_info,
                style=format_style,
                include_params=include_detail,
                include_triggers=include_detail,
            )

    # Build response
    response = {"module": module_name, "events": events, "count": len(events)}

    # Add module summary if available
    if "docstring" in module_info:
        response["description"] = module_info["docstring"].split("\n")[0].strip()

    return response


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean shutdown."""
    logger.info("Discovery service stopped")
