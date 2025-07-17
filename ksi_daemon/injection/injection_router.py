#!/usr/bin/env python3
"""
Injection Router Module - Event-Based Version

Routes async completion results through system-reminder injection to enable
autonomous agent coordination through completion chains.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common import timestamp_utc
from ksi_common.completion_format import parse_completion_result_event
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.injection.injection_types import (
    InjectionRequest,
    InjectionMode,
    InjectionPosition,
    InjectionResult,
    InjectionError
)

# Module state
logger = get_bound_logger("injection_router", version="2.0.0")
injection_queue = None  # Will be initialized as asyncio.Queue when event loop is available
injection_metadata_store: Dict[str, Dict[str, Any]] = {}

# Event emitter reference (set during startup)
event_emitter = None

# Import prompt composer when available
try:
    from prompts.composer import PromptComposer
    composer = PromptComposer()
except ImportError:
    logger.warning("PromptComposer not available, using fallback injection formatting")
    composer = None


class InjectionCircuitBreaker:
    """Basic circuit breaker for injection safety."""
    
    def __init__(self):
        self.request_depth_tracker: Dict[str, int] = {}
        self.blocked_requests = set()
    
    def check_injection_allowed(self, metadata: Dict[str, Any]) -> bool:
        """Check if injection should be allowed based on circuit breaker rules."""
        request_id = metadata.get('id')
        
        # Check if already blocked
        if request_id in self.blocked_requests:
            return False
        
        # Check depth
        circuit_config = metadata.get('circuit_breaker_config', {})
        parent_id = circuit_config.get('parent_request_id')
        max_depth = circuit_config.get('max_depth', 5)
        
        if parent_id:
            parent_depth = self.request_depth_tracker.get(parent_id, 0)
            current_depth = parent_depth + 1
            
            if current_depth >= max_depth:
                logger.warning(f"Injection blocked: depth {current_depth} exceeds max {max_depth}")
                self.blocked_requests.add(request_id)
                return False
            
            self.request_depth_tracker[request_id] = current_depth
        else:
            self.request_depth_tracker[request_id] = 0
        
        return True
    
    def get_status(self, parent_request_id: Optional[str]) -> Dict[str, Any]:
        """Get current circuit breaker status for a request chain."""
        if not parent_request_id:
            return {
                'depth': 0,
                'max_depth': 5,
                'tokens_used': 0,
                'token_budget': 50000,
                'time_elapsed': 0,
                'time_window': 3600
            }
        
        depth = self.request_depth_tracker.get(parent_request_id, 0) + 1
        
        return {
            'depth': depth,
            'max_depth': 5,
            'tokens_used': 0,  # Token tracking not yet implemented
            'token_budget': 50000,
            'time_elapsed': 0,  # Time tracking not yet implemented
            'time_window': 3600
        }


# Global circuit breaker instance
circuit_breaker = InjectionCircuitBreaker()


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


# System event handlers
@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Store event emitter reference."""
    data = event_format_linter(raw_data, SystemContextData)
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Injection router received context, event_emitter configured")


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for injection router
    pass


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize injection router."""
    data = event_format_linter(raw_data, SystemStartupData)
    logger.info("Injection router started")
    return event_response_builder({"status": "injection_router_ready"}, context)


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for this handler
    pass


@event_handler("system:ready")
async def handle_ready(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return async task to process injection queue."""
    data = event_format_linter(raw_data, SystemReadyData)
    global injection_queue
    
    # Initialize asyncio.Queue now that event loop is available
    injection_queue = asyncio.Queue()
    
    logger.info("Injection router ready - initializing queue processor task")
    
    async def process_injection_queue():
        """Process queued injections."""
        logger.info("Starting injection queue processor")
        
        while True:
            try:
                # Get next injection request (truly async, no polling!)
                injection_request = await injection_queue.get()
                
                if injection_request is None:  # Shutdown signal
                    logger.info("Injection queue processor shutting down")
                    break
                
                logger.debug(f"Processing injection for session {injection_request.get('session_id')}")
                
                # Execute the injection
                if event_emitter:
                    logger.debug(f"Executing injection with data: {injection_request}")
                    result = await execute_injection(injection_request)
                    logger.debug(f"Injection result: {result}")
                else:
                    logger.error("Event emitter not available for injection processing")
                    
            except asyncio.CancelledError:
                logger.info("Injection queue processor cancelled")
                raise
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid injection data: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause on error
        
        logger.info("Injection queue processor stopped")
    
    return event_response_builder({
        "service": "injection_router",
        "tasks": [
            {
                "name": "injection_queue_processor",
                "coroutine": process_injection_queue()
            }
        ]
    }, context)


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:shutdown")
async def handle_shutdown(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    data = event_format_linter(raw_data, SystemShutdownData)
    # Signal queue processor to stop
    if injection_queue:
        try:
            await injection_queue.put(None)
        except Exception as e:
            logger.warning(f"Error signaling injection queue shutdown: {e}")
    
    logger.info("Injection router stopped")


# Injection event handlers
class InjectionStatusData(TypedDict):
    """Get injection router status."""
    # No specific fields - returns overall status
    pass


@event_handler("injection:status")
async def handle_injection_status(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get injection router status."""
    data = event_format_linter(raw_data, InjectionStatusData)
    return event_response_builder({
        "queued_count": injection_queue.qsize() if injection_queue else 0,
        "metadata_count": len(injection_metadata_store),
        "blocked_count": len(circuit_breaker.blocked_requests),
        "event_emitter_available": event_emitter is not None
    }, context)


class InjectionInjectData(TypedDict):
    """Unified injection request."""
    content: Required[str]  # Content to inject
    mode: NotRequired[Literal["direct", "next"]]  # Injection mode (default: "next")
    position: NotRequired[Literal["before_prompt", "after_prompt", "system_reminder"]]  # Position (default: "before_prompt")
    session_id: NotRequired[str]  # Session ID (required for next mode)
    priority: NotRequired[Literal["high", "normal", "low"]]  # Priority (default: "normal")
    metadata: NotRequired[Dict[str, Any]]  # Additional metadata


@event_handler("injection:inject")
async def handle_injection_inject(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle unified injection request."""
    data = event_format_linter(raw_data, InjectionInjectData)
    # Unified injection handler - convert to typed interface
    try:
        # Parse mode and position enums
        mode = InjectionMode(data.get("mode", "next"))
        position = InjectionPosition(data.get("position", "before_prompt"))
        
        # Create typed request
        request = InjectionRequest(
            content=data.get("content", ""),
            mode=mode,
            position=position,
            session_id=data.get("session_id"),
            priority=data.get("priority", "normal"),
            metadata=data.get("metadata", {})
        )
        
        # Process using typed interface
        result = await process_injection(request)
        return event_response_builder(result.to_dict(), context)
    except ValueError as e:
        return error_response(str(e), context)


class InjectionQueueData(TypedDict):
    """Queue injection metadata."""
    id: NotRequired[str]  # Request ID (auto-generated if not provided)
    injection_config: NotRequired[Dict[str, Any]]  # Injection configuration
    circuit_breaker_config: NotRequired[Dict[str, Any]]  # Circuit breaker config


@event_handler("injection:queue")
async def handle_injection_queue(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle queue injection metadata request from completion service."""
    data = event_format_linter(raw_data, InjectionQueueData)
    # This replaces the direct function call from completion service
    request_id = _queue_completion_with_injection(data)
    return event_response_builder({"request_id": request_id}, context)


class InjectionBatchData(TypedDict):
    """Batch injection request."""
    injections: Required[List[Dict[str, Any]]]  # List of injection requests


@event_handler("injection:batch")
async def handle_injection_batch(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle batch injection request."""
    data = event_format_linter(raw_data, InjectionBatchData)
    injections = data.get("injections", [])
    result = await inject_batch(injections)
    return event_response_builder(result, context)


class InjectionListData(TypedDict):
    """List pending injections."""
    session_id: NotRequired[str]  # Session to query (omit for all)


@event_handler("injection:list")
async def handle_injection_list(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle list injections request."""
    data = event_format_linter(raw_data, InjectionListData)
    session_id = data.get("session_id")
    result = await list_pending_injections(session_id)
    return event_response_builder(result, context)


class InjectionClearData(TypedDict):
    """Clear pending injections."""
    session_id: Required[str]  # Session to clear
    mode: NotRequired[Literal["direct", "next"]]  # Mode filter (omit for all)


@event_handler("injection:clear")
async def handle_injection_clear(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle clear injections request."""
    data = event_format_linter(raw_data, InjectionClearData)
    session_id = data.get("session_id")
    mode = data.get("mode")
    result = await clear_injections(session_id, mode)
    return event_response_builder(result, context)


class InjectionProcessResultData(TypedDict):
    """Process completion result for injection."""
    request_id: Required[str]  # Request ID
    result: Required[Dict[str, Any]]  # Completion result data
    injection_metadata: Required[Dict[str, Any]]  # Injection metadata


@event_handler("injection:process_result")
async def handle_injection_process_result(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Process a completion result for injection - explicitly called by completion service."""
    data = event_format_linter(raw_data, InjectionProcessResultData)
    
    request_id = data.get('request_id')
    result_data = data.get('result', {})
    injection_metadata = data.get('injection_metadata', {})
    
    # Use shared utility to parse completion result consistently
    # Function auto-detects format and handles both event and direct response formats
    parsed_result = parse_completion_result_event(result_data)
    
    # Check for error responses using standardized parsing
    if parsed_result["status"] == "error":
        logger.warning(f"Completion error for {request_id}: {parsed_result.get('error', 'Unknown error')}, skipping injection")
        return event_response_builder({"status": "skipped", "reason": "completion_error"}, context)
    
    # Extract completion text from parsed result
    completion_text = parsed_result.get("response", "")
    
    if not injection_metadata:
        logger.error(f"No injection metadata provided for {request_id}")
        return error_response("Missing injection metadata", context)
    
    injection_config = injection_metadata.get('injection_config', {})
    
    if not injection_config.get('enabled'):
        logger.debug(f"Injection not enabled for {request_id}")
        return event_response_builder({"status": "skipped", "reason": "not_enabled"}, context)
    
    # Check if this is already an injection (prevent recursion)
    if injection_metadata.get('is_injection'):
        logger.debug(f"Skipping injection for injected completion {request_id}")
        return event_response_builder({"status": "skipped", "reason": "is_injection"}, context)
    
    # Store metadata for circuit breaker
    store_injection_metadata(request_id, injection_metadata)
    
    # Check circuit breakers
    if not circuit_breaker.check_injection_allowed(injection_metadata):
        logger.warning(f"Injection blocked by circuit breaker for {request_id}")
        
        # Emit blocked event
        if event_emitter:
            await event_emitter("injection:blocked", {
                "request_id": request_id,
                "reason": "circuit_breaker"
            })
        
        return event_response_builder({"status": "blocked", "reason": "circuit_breaker", "request_id": request_id}, context)
    
    # Compose injection content
    try:
        injection_content = compose_injection_content(
            completion_text, result_data, injection_metadata
        )
    except Exception as e:
        logger.error(f"Failed to compose injection for {request_id}: {e}")
        return error_response(f"Injection composition failed: {e}", context)
    
    # Determine injection mode
    injection_mode = injection_config.get('mode', 'next')  # Default to "next" mode
    position = injection_config.get('position', 'prepend')  # Default to prepend
    
    # Handle based on mode
    if injection_mode == 'direct':
        # Direct mode: Queue for immediate completion (original behavior)
        target_sessions = injection_config.get('target_sessions', ['originating'])
        queued_count = 0
        
        for session_id in target_sessions:
            injection_request = {
                'session_id': session_id,
                'content': injection_content,
                'parent_request_id': request_id,
                'is_injection': True,  # Prevent recursive injection
                'timestamp': timestamp_utc()
            }
            
            await injection_queue.put(injection_request)
            queued_count += 1
            
            # Emit queued event
            if event_emitter:
                await event_emitter("injection:queued", {
                    "request_id": request_id,
                    "session_id": session_id,
                    "mode": "direct"
                })
        
        logger.info(f"Queued {queued_count} direct injections for request {request_id}")
        
        return event_response_builder({
            "status": "queued",
            "request_id": request_id,
            "target_count": queued_count,
            "mode": "direct"
        }, context)
    
    else:  # next mode
        # Next mode: Store in async state for next request
        target_sessions = injection_config.get('target_sessions', ['originating'])
        stored_count = 0
        
        for session_id in target_sessions:
            # Store injection in async state
            injection_data = {
                'content': injection_content,
                'position': position,
                'parent_request_id': request_id,
                'timestamp': timestamp_utc(),
                'trigger_type': injection_config.get('trigger_type', 'general')
            }
            
            # Use async_state API
            if event_emitter:
                result = await event_emitter("async_state:push", {
                    "namespace": "injection",
                    "key": session_id,
                    "data": injection_data,
                    "ttl_seconds": 3600  # 1 hour TTL
                })
                
                if result and not result.get("error"):
                    stored_count += 1
                    
                    # Emit stored event
                    await event_emitter("injection:stored", {
                        "request_id": request_id,
                        "session_id": session_id,
                        "mode": "next",
                        "position": position
                    })
                else:
                    logger.error(f"Failed to store injection for session {session_id}: {result}")
        
        logger.info(f"Stored {stored_count} next-mode injections for request {request_id}")
        
        return event_response_builder({
            "status": "stored",
            "request_id": request_id,
            "target_count": stored_count,
            "mode": "next"
        }, context)


class InjectionExecuteData(TypedDict):
    """Execute a queued injection."""
    content: Required[str]  # Content to inject
    request_id: NotRequired[str]  # Original request ID
    agent_id: NotRequired[str]  # Target agent (completion system resolves session)
    model: NotRequired[str]  # Model to use (default: 'claude-cli/sonnet')
    priority: NotRequired[Literal["high", "normal", "low"]]  # Priority
    injection_type: NotRequired[str]  # Type of injection (default: 'system_reminder')


@event_handler("injection:execute")
async def execute_injection(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a queued injection by creating a new completion request."""
    data = event_format_linter(raw_data, InjectionExecuteData)
    
    agent_id = data.get('agent_id')
    content = data.get('content')
    request_id = data.get('request_id')
    
    if not content:
        logger.error("No content provided for injection")
        return error_response("No content provided", context)
    
    if not event_emitter:
        logger.error("Event emitter not available for injection")
        return error_response("Event emitter not available", context)
    
    if not agent_id:
        logger.error("No agent_id provided for injection")
        return error_response("No agent_id provided", context)
    
    logger.info(f"Executing injection for agent {agent_id}")
    
    try:
        # Construct the completion request - let completion system handle session
        completion_data = {
            "prompt": content,
            "agent_id": agent_id,  # Let completion system resolve session internally
            "model": data.get('model', 'claude-cli/sonnet'),
            "originator_id": "injection_router",
            "request_id": f"inj_{request_id}_{agent_id}" if request_id else f"inj_{int(time.time() * 1000)}_{agent_id}",
            "priority": data.get('priority', 'normal'),
            "injection_metadata": {
                "source_request": request_id,
                "injection_type": data.get('injection_type', 'system_reminder'),
                "timestamp": time.time()
            }
        }
        
        # Emit the completion request
        result = await event_emitter("completion:async", completion_data)
        
        logger.info(f"Injected completion request {completion_data['request_id']} for agent {agent_id}")
        
        return event_response_builder({
            "status": "injection_executed",
            "agent_id": agent_id,
            "request_id": completion_data["request_id"],
            "result": result
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to inject for agent {agent_id}: {e}")
        return error_response(f"Failed to inject for agent {agent_id}: {e}", context)


# Unified injection helper functions

async def inject_content(
    session_id: str,
    content: str,
    mode: str = "next",
    position: str = "prepend",
    trigger_type: str = "general",
    ttl_seconds: int = 3600,
    target_sessions: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Inject content into one or more sessions.
    
    Args:
        session_id: Primary session ID
        content: Content to inject
        mode: 'direct' for immediate injection, 'next' for next request
        position: 'prepend', 'postscript', 'system_reminder', etc.
        trigger_type: Type of trigger for composition
        ttl_seconds: TTL for next-mode injections
        target_sessions: List of target sessions (defaults to [session_id])
        **kwargs: Additional options
        
    Returns:
        Result dictionary with injection status
    """
    # Validate parameters
    error = validate_injection_request(session_id, content, mode, position)
    if error:
        return {"status": "error", "error": error}
    
    # Default target sessions
    if not target_sessions:
        target_sessions = [session_id]
    
    # Handle system_reminder position by wrapping content
    if position == "system_reminder" and not content.startswith("<system-reminder>"):
        content = f"<system-reminder>\n{content}\n</system-reminder>"
    
    if mode == "direct":
        # Direct mode: Queue for immediate execution
        queued_count = 0
        
        for target in target_sessions:
            injection_request = {
                'session_id': target,
                'content': content,
                'parent_request_id': kwargs.get('parent_request_id'),
                'is_injection': True,
                'timestamp': timestamp_utc(),
                'position': position,
                'trigger_type': trigger_type
            }
            
            await injection_queue.put(injection_request)
            queued_count += 1
            
            if event_emitter:
                await event_emitter("injection:queued", {
                    "session_id": target,
                    "mode": "direct",
                    "position": position
                })
        
        return {
            "status": "success",
            "mode": "direct",
            "queued_count": queued_count,
            "target_sessions": target_sessions
        }
    
    else:  # next mode
        # Store in async state for next request
        stored_count = 0
        
        for target in target_sessions:
            injection_data = {
                'content': content,
                'position': position,
                'timestamp': timestamp_utc(),
                'trigger_type': trigger_type
            }
            
            if event_emitter:
                result = await event_emitter("async_state:push", {
                    "namespace": "injection",
                    "key": target,
                    "data": injection_data,
                    "ttl_seconds": ttl_seconds
                })
                
                if result and not result.get("error"):
                    stored_count += 1
                    
                    await event_emitter("injection:stored", {
                        "session_id": target,
                        "mode": "next",
                        "position": position
                    })
        
        return {
            "status": "success",
            "mode": "next",
            "stored_count": stored_count,
            "target_sessions": target_sessions,
            "ttl_seconds": ttl_seconds
        }


async def inject_batch(injections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process multiple injections efficiently.
    
    Args:
        injections: List of injection requests
        
    Returns:
        Summary of batch injection results
    """
    results = []
    
    for injection in injections:
        try:
            result = await inject_content(**injection)
            results.append({
                "session_id": injection.get("session_id"),
                "status": result.get("status"),
                "result": result
            })
        except Exception as e:
            results.append({
                "session_id": injection.get("session_id"),
                "status": "error",
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    
    return {
        "status": "batch_complete",
        "total": len(results),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }


async def list_pending_injections(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    List pending next-mode injections.
    
    Args:
        session_id: Session to query (if None, list all sessions)
        
    Returns:
        List of pending injections or all sessions with injections
    """
    if not event_emitter:
        return {"status": "error", "error": "State service not available"}
    
    # If no session_id, list all sessions with injections
    if not session_id:
        # Get all keys in injection namespace
        result = await event_emitter("async_state:get_keys", {
            "namespace": "injection"
        })
        
        if result and not result.get("error"):
            keys = result.get("keys", [])
            queues = {}
            
            # Get queue length for each session
            for key in keys:
                queue_result = await event_emitter("async_state:queue_length", {
                    "namespace": "injection",
                    "key": key
                })
                if queue_result and not queue_result.get("error"):
                    length = queue_result.get("length", 0)
                    if length > 0:
                        queues[key] = length
            
            return {
                "status": "success",
                "total_sessions": len(queues),
                "injection_queues": queues
            }
        
        return {
            "status": "success",
            "total_sessions": 0,
            "injection_queues": {}
        }
    
    # Get all injections from async state
    result = await event_emitter("async_state:get_queue", {
        "namespace": "injection",
        "key": session_id
    })
    
    if result and not result.get("error"):
        injections = result.get("data", [])
        return {
            "status": "success",
            "session_id": session_id,
            "pending_count": len(injections),
            "injections": injections
        }
    
    return {
        "status": "success",
        "session_id": session_id,
        "pending_count": 0,
        "injections": []
    }


async def clear_injections(session_id: str, mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear pending injections for a session.
    
    Args:
        session_id: Session to clear
        mode: Optional mode filter ('next' or 'direct')
        
    Returns:
        Number of cleared injections
    """
    if not session_id:
        return {"status": "error", "error": "session_id required"}
    
    cleared_count = 0
    
    # Clear next-mode injections from async state
    if mode in [None, "next"]:
        if event_emitter:
            result = await event_emitter("async_state:delete", {
                "namespace": "injection",
                "key": session_id
            })
            
            if result and not result.get("error"):
                cleared_count += result.get("deleted", 0)
    
    # Clear direct-mode injections from queue
    if mode in [None, "direct"]:
        # This is more complex as we'd need to filter the queue
        # For now, we'll note this as a limitation
        logger.warning("Clearing direct-mode injections from queue not yet implemented")
    
    return {
        "status": "success",
        "session_id": session_id,
        "cleared_count": cleared_count,
        "mode": mode or "all"
    }


def validate_injection_request(
    session_id: str,
    content: str,
    mode: str,
    position: str
) -> Optional[str]:
    """
    Validate injection parameters.
    
    Returns:
        Error message if invalid, None if valid
    """
    if not session_id:
        return "session_id is required"
    
    if not content:
        return "content is required"
    
    if mode not in ["direct", "next"]:
        return f"Invalid mode '{mode}'. Must be 'direct' or 'next'"
    
    valid_positions = [
        "prepend", "postscript", "system_reminder",
        "before_prompt", "after_prompt"
    ]
    if position not in valid_positions:
        return f"Invalid position '{position}'. Must be one of: {', '.join(valid_positions)}"
    
    return None


def get_injection_metadata(request_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve injection metadata for a request."""
    
    # First check our local store
    if request_id in injection_metadata_store:
        return injection_metadata_store[request_id]
    
    # Check persistent storage or state service (future enhancement)
    
    return None


def store_injection_metadata(request_id: str, metadata: Dict[str, Any]):
    """Store injection metadata for a request."""
    injection_metadata_store[request_id] = metadata


def compose_injection_content(completion_text: str, result_data: Dict[str, Any], 
                             metadata: Dict[str, Any]) -> str:
    """Compose injection content using prompt composition system."""
    
    injection_config = metadata.get('injection_config', {})
    circuit_breaker_config = metadata.get('circuit_breaker_config', {})
    
    # Calculate circuit breaker status
    cb_status = circuit_breaker.get_status(
        circuit_breaker_config.get('parent_request_id')
    )
    
    # If composer is available, use it
    if composer:
        try:
            # Prepare composition context
            composition_context = {
                'completion_result': completion_text,
                'completion_attributes': result_data.get('attributes', {}),
                'trigger_type': injection_config.get('trigger_type', 'general'),
                'follow_up_guidance': injection_config.get('follow_up_guidance'),
                'circuit_breaker_status': cb_status,
                'pending_completion_result': True
            }
            
            # Use specified template or default
            template_name = injection_config.get('composition_template', 'async_completion_result')
            
            # Compose using template system
            injection_prompt = composer.compose(template_name, composition_context)
            
            # Check if we need to wrap in system-reminder tags
            position = injection_config.get('position', 'prepend')
            if position == 'system_reminder' or injection_config.get('wrap_system_reminder'):
                return f"<system-reminder>\n{injection_prompt}\n</system-reminder>"
            
            return injection_prompt
            
        except Exception as e:
            logger.error(f"Composer failed: {e}, using fallback")
    
    # Fallback formatting
    trigger_type = injection_config.get('trigger_type', 'general')
    follow_up_guidance = injection_config.get('follow_up_guidance', 
                                             'Consider if this requires any follow-up actions.')
    
    # Generate trigger boilerplate based on type
    trigger_boilerplate = get_trigger_boilerplate(trigger_type)
    
    # Format circuit breaker status
    cb_status_text = ""
    if cb_status and cb_status['depth'] > 0:
        cb_status_text = f"""
## Circuit Breaker Status
- Ideation Depth: {cb_status['depth']}/{cb_status['max_depth']}
- Token Budget: {cb_status['tokens_used']}/{cb_status['token_budget']}
- Time Window: {cb_status['time_elapsed']}/{cb_status['time_window']}s
"""
    
    content = f"""## Async Completion Result

An asynchronous completion has returned with the following result:

{completion_text}

{trigger_boilerplate}

{follow_up_guidance}
{cb_status_text}"""
    
    # Wrap based on position
    position = injection_config.get('position', 'prepend')
    if position == 'system_reminder':
        return f"<system-reminder>\n{content}\n</system-reminder>"
    
    return content


def get_trigger_boilerplate(trigger_type: str) -> str:
    """Get boilerplate text for different trigger types."""
    
    triggers = {
        'antThinking': """
## Analytical Thinking Trigger

This notification requires careful analytical consideration. Please think step-by-step about:

1. **Implications**: What are the broader implications of this result?
2. **Dependencies**: Which other agents or systems might be affected?
3. **Actions**: What follow-up actions, if any, should be taken?
4. **Risks**: Are there any risks or concerns to address?

Consider whether to:
- Send messages to specific agents
- Initiate further research
- Update organizational state
- Document findings in collective memory
""",
        
        'coordination': """
## Coordination Trigger

This result has coordination implications. Consider:

1. **Agent Notification**: Which agents need this information?
2. **Organizational Impact**: How does this affect current coordination patterns?
3. **Capability Changes**: Are there new capabilities to leverage?
4. **Synchronization**: What state needs to be synchronized?

Coordination actions to consider:
- Broadcast to relevant agent groups
- Update coordination patterns
- Reallocate capabilities
- Form new agent coalitions
""",
        
        'research': """
## Research Continuation Trigger

These findings suggest additional research opportunities:

1. **Follow-up Questions**: What new questions arise from these results?
2. **Knowledge Gaps**: What gaps in understanding remain?
3. **Research Paths**: Which research directions seem most promising?
4. **Resource Allocation**: What resources would be needed?

Research actions available:
- Queue additional research tasks
- Consult collective memory
- Engage specialist agents
- Synthesize with existing knowledge
""",
        
        'memory': """
## Memory Integration Trigger

This information may be valuable for collective memory:

1. **Significance**: Is this finding significant enough to preserve?
2. **Generalization**: Can this be generalized for future use?
3. **Indexing**: How should this be categorized for retrieval?
4. **Relationships**: How does this relate to existing memories?

Memory actions:
- Store in experience library
- Update pattern recognition
- Link to related memories
- Tag for future retrieval
""",
        
        'general': """
## General Consideration

Please consider whether this result warrants any follow-up actions or communications.
"""
    }
    
    return triggers.get(trigger_type, triggers['general'])


# Internal function - now only accessed via injection:queue event
def _queue_completion_with_injection(request: Dict[str, Any]) -> str:
    """Queue a completion request with injection metadata (internal)."""
    
    # Generate request ID if not provided
    request_id = request.get('id') or f"req_{int(time.time() * 1000)}"
    
    # Extract injection config
    injection_config = request.get('injection_config', {})
    
    # Store metadata
    metadata = {
        'id': request_id,
        'injection_config': injection_config,
        'circuit_breaker_config': request.get('circuit_breaker_config', {}),
        'timestamp': timestamp_utc()
    }
    
    store_injection_metadata(request_id, metadata)
    
    return request_id


# Process injection using typed interface
async def process_injection(request: InjectionRequest) -> InjectionResult:
    """Process an injection request using typed interface."""
    
    # Validate request
    if request.mode == InjectionMode.NEXT and not request.session_id:
        return InjectionResult(
            success=False,
            mode=request.mode,
            error="session_id required for next mode injection",
            error_type=InjectionError.NO_SESSION
        )
    
    # Handle based on mode
    if request.mode == InjectionMode.DIRECT:
        # Direct mode - emit immediately
        if not event_emitter:
            return InjectionResult(
                success=False,
                mode=request.mode,
                error="Event emitter not available",
                error_type=InjectionError.STATE_ERROR
            )
        
        # Create injection data based on position
        injection_data = {
            "content": request.content,
            "position": request.position.value,
            "metadata": request.metadata
        }
        
        # Emit completion result
        result = await event_emitter("claude:completion:result", {
            "session_id": request.session_id,
            "injection": injection_data,
            "timestamp": timestamp_utc()
        })
        
        return InjectionResult(
            success=True,
            mode=request.mode,
            position=request.position,
            session_id=request.session_id,
            request_id=result.get("request_id") if isinstance(result, dict) else None
        )
    
    else:  # NEXT mode
        # Queue for next completion
        if not event_emitter:
            return InjectionResult(
                success=False,
                mode=request.mode,
                error="Event emitter not available",
                error_type=InjectionError.STATE_ERROR
            )
        
        # Push to injection queue
        queue_data = {
            "content": request.content,
            "position": request.position.value,
            "priority": request.priority,
            "metadata": request.metadata,
            "timestamp": timestamp_utc()
        }
        
        try:
            # Use event system for async state operations
            result = await event_emitter("async_state:push", {
                "namespace": "injection",
                "key": request.session_id,
                "data": queue_data,
                "ttl_seconds": 3600  # 1 hour TTL
            })
            
            if result and not result.get("error"):
                return InjectionResult(
                    success=True,
                    mode=request.mode,
                    position=request.position,
                    session_id=request.session_id,
                    queued=True,
                    queue_position=result.get("position", 0)
                )
            else:
                error_msg = result.get("error", "Unknown error") if result else "No event emitter"
                logger.error(f"Failed to push injection: {error_msg}")
                return InjectionResult(
                    success=False,
                    mode=request.mode,
                    error=error_msg,
                    error_type=InjectionError.STATE_ERROR
                )
        except Exception as e:
            logger.error(f"Failed to queue injection: {e}")
            return InjectionResult(
                success=False,
                mode=request.mode,
                error=str(e),
                error_type=InjectionError.STATE_ERROR
            )


