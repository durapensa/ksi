#!/usr/bin/env python3
"""
Completion Service Plugin V3 - Event-Based Version

Enhanced completion service using pure event system:
- Async completion queue with priority support
- Conversation lock management
- Event-driven injection routing
- Circuit breaker safety mechanisms
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, TypedDict
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler, EventPriority, emit_event, get_router
# Metadata functionality now integrated into event_handler
from ksi_common import timestamp_utc, create_completion_response, parse_completion_response, get_response_session_id
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Import litellm module for LiteLLM-specific handling
from ksi_daemon.completion.litellm import handle_litellm_completion

# Import retry manager for failure recovery
from ksi_daemon.completion.retry_manager import RetryManager, RetryPolicy, extract_error_type

# Module state
logger = get_bound_logger("completion_service", version="3.0.0")
active_completions: Dict[str, Dict[str, Any]] = {}

# Per-session queue management for fork prevention
session_processors: Dict[str, asyncio.Queue] = {}  # session_id -> Queue
active_sessions: set = set()  # Currently processing sessions

# Structured concurrency with asyncio - created on demand
completion_task_group = None
task_group_context = None

# Event emitter reference (set during startup)
event_emitter = None

# Shutdown event reference (set during startup)
shutdown_event = None

# Retry manager (initialized when event emitter is available)
retry_manager = None


# Module TypedDict definitions (optional type safety)
class CompletionCancelData(TypedDict):
    """Type-safe data for completion:cancel."""
    request_id: str

class CompletionStatusData(TypedDict):
    """Type-safe data for completion:status."""
    pass  # No parameters

class CompletionSessionStatusData(TypedDict):
    """Type-safe data for completion:session_status."""
    session_id: str


def get_completion_task_group():
    """Get the completion task group (must be called after service startup)."""
    if completion_task_group is None:
        raise RuntimeError("Completion service not ready - task group not available")
    return completion_task_group


def ensure_directories():
    """Ensure required directories exist."""
    config.ensure_directories()


def save_completion_response(response_data: Dict[str, Any]) -> None:
    """
    Save standardized completion response to session file.
    
    Args:
        response_data: Standardized completion response from create_completion_response
    """
    try:
        # Parse the completion response to extract session_id
        completion_response = parse_completion_response(response_data)
        session_id = get_response_session_id(completion_response)
        
        if not session_id:
            logger.warning("No session_id in completion response, cannot save to session file")
            return
        
        # Ensure responses directory exists
        responses_dir = config.response_log_dir
        responses_dir.mkdir(parents=True, exist_ok=True)
        
        # Session file path
        session_file = responses_dir / f"{session_id}.jsonl"
        
        # Append response to session file
        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(response_data) + '\n')
        
        logger.debug(f"Saved completion response to {session_file}")
        
    except Exception as e:
        logger.error(f"Failed to save completion response: {e}", exc_info=True)


# Event handlers

@event_handler("system:startup", priority=EventPriority.LOW)  # Run after core services
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize completion service on startup."""
    ensure_directories()
    logger.info("Completion service started with asyncio structured concurrency")
    return {"status": "completion_service_ready"}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive runtime context."""
    global event_emitter, shutdown_event, retry_manager
    
    event_emitter = context.get("emit_event")
    shutdown_event = context.get("shutdown_event")
    
    if event_emitter:
        logger.info("Completion service received event emitter")
        
        # Initialize retry manager with event emitter
        retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=60.0,
            backoff_multiplier=2.0
        )
        retry_manager = RetryManager(event_emitter, retry_policy)
        await retry_manager.start()
        logger.info("Retry manager initialized")
        
    if shutdown_event:
        logger.info("Completion service received shutdown event")


async def manage_completion_service():
    """Long-running service to manage asyncio task group for completions."""
    global completion_task_group
    
    if not shutdown_event:
        logger.error("No shutdown event available - service cannot start properly")
        raise RuntimeError("Shutdown event not provided via module context")
    
    try:
        # Create and enter the task group context
        async with asyncio.TaskGroup() as tg:
            completion_task_group = tg
            logger.info("Completion service ready")
            
            # Keep the service running until shutdown event is set
            await shutdown_event.wait()
            logger.info("Shutdown event received, completion service exiting gracefully")
            
    except* Exception as eg:
        # TaskGroup raises ExceptionGroup when tasks fail
        logger.error(f"Completion service task group error: {eg!r}")
        raise
    finally:
        completion_task_group = None


@event_handler("system:ready")
async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the completion service manager task."""
    logger.info("Completion service requesting service manager task")
    
    return {
        "service": "completion_service",
        "tasks": [
            {
                "name": "service_manager",
                "coroutine": manage_completion_service()
            }
        ]
    }


@event_handler("completion:async")
async def handle_async_completion(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle async completion requests with smart queueing.
    
    Uses hybrid approach:
    - Event-driven for multi-session parallelism
    - Queue-based for per-session fork prevention
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Add request_id to data for tracking
    data["request_id"] = request_id
    
    # Extract session_id for queue management
    session_id = data.get("session_id", "default")
    
    # Log the request
    logger.info(f"Received async completion request",
                request_id=request_id,
                session_id=session_id,
                model=data.get("model", "unknown"))
    
    # Debug log to check extra_body
    if "extra_body" in data:
        logger.debug(f"Completion request has extra_body: {data['extra_body']}")
    else:
        logger.debug("Completion request has NO extra_body")
    
    # Get or create session processor
    if session_id not in session_processors:
        session_processors[session_id] = asyncio.Queue()
        logger.debug(f"Created new session processor for {session_id}")
    
    queue = session_processors[session_id]
    
    # Add to queue and process
    await queue.put((request_id, data))
    
    # If this session isn't being processed, start processing
    if session_id not in active_sessions:
        active_sessions.add(session_id)
        
        # Get the task group and create task
        tg = get_completion_task_group()
        
        async def process_session():
            try:
                await process_session_queue(session_id)
            finally:
                active_sessions.discard(session_id)
        
        tg.create_task(process_session())
    
    # Track active completion with full request data for recovery
    active_completions[request_id] = {
        "session_id": session_id,
        "status": "queued",
        "queued_at": timestamp_utc(),
        "data": dict(data),  # Store full request for potential retry
        "original_event": "completion:async"
    }
    
    # Return immediate acknowledgment
    return {
        "request_id": request_id,
        "status": "queued",
        "message": "Completion request queued for processing"
    }


async def process_session_queue(session_id: str):
    """Process completion requests for a specific session."""
    queue = session_processors[session_id]
    
    while True:
        try:
            # Get next request with timeout
            request_id, data = await asyncio.wait_for(queue.get(), timeout=1.0)
            
            # Update status
            if request_id in active_completions:
                active_completions[request_id]["status"] = "processing"
                active_completions[request_id]["started_at"] = timestamp_utc()
            
            # Process the completion
            await process_completion_request(request_id, data)
            
        except asyncio.TimeoutError:
            # No requests for 1 second, check if we should exit
            if queue.empty() and session_id not in active_sessions:
                logger.debug(f"Session processor {session_id} idle, exiting")
                break
        except Exception as e:
            logger.error(f"Error processing session queue: {e}", exc_info=True)


async def process_completion_request(request_id: str, data: Dict[str, Any]):
    """Process a single completion request."""
    try:
        # Lock conversation if needed
        conversation_lock = data.get("conversation_lock", {})
        if conversation_lock.get("enabled", False):
            lock_result = await emit_event("conversation:lock", {
                "session_id": data.get("session_id"),
                "agent_id": data.get("agent_id"),
                "timeout": conversation_lock.get("timeout", 300)
            })
        
        # Call LiteLLM
        start_time = time.time()
        
        # Add conversation_id if not present
        if "conversation_id" not in data:
            data["conversation_id"] = f"ksi-{request_id}"
        
        # Emit progress event
        await emit_event("completion:progress", {
            "request_id": request_id,
            "session_id": data.get("session_id"),
            "status": "calling_llm"
        })
        
        # Call completion through litellm module
        provider, raw_response = await handle_litellm_completion(data)
        
        # Create standardized response
        standardized_response = create_completion_response(
            provider=provider,
            raw_response=raw_response,
            request_id=data.get("request_id"),
            client_id=data.get("client_id"),
            duration_ms=int((time.time() - start_time) * 1000)
        )
        
        # Save to session log
        save_completion_response(standardized_response)
        
        # Log token usage if available (especially for MCP handshake analysis)
        if provider == "claude-cli" and "response" in standardized_response:
            raw_resp = standardized_response["response"]
            if isinstance(raw_resp, dict):
                usage = raw_resp.get("usage", {})
                if usage:
                    # Check if this was an MCP-enabled request
                    has_mcp = bool(data.get("extra_body", {}).get("ksi", {}).get("mcp_config_path"))
                    
                    logger.info(
                        "Completion token usage",
                        request_id=request_id,
                        has_mcp=has_mcp,
                        input_tokens=usage.get("input_tokens", 0),
                        cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        session_id=data.get("session_id"),
                        agent_id=data.get("agent_id")
                    )
        
        # Clean up tracking - remove completed request
        if request_id in active_completions:
            active_completions.pop(request_id)
        
        # Emit result event
        result_event_data = {
            "request_id": request_id,
            "result": standardized_response
        }
        
        # Check if injection processing is needed
        injection_config = data.get("injection_config")
        if injection_config and injection_config.get('enabled') and event_emitter:
            # Explicitly tell injection to process this result
            injection_result = await event_emitter("injection:process_result", {
                "request_id": request_id,
                "result": standardized_response,
                "injection_metadata": {
                    "injection_config": injection_config,
                    "circuit_breaker_config": data.get('circuit_breaker_config', {})
                }
            })
            
            # If injection returns a modified result, use that
            if injection_result:
                logger.debug(f"Injection processed result for {request_id}")
                if isinstance(injection_result, dict) and "result" in injection_result:
                    result_event_data["result"] = injection_result["result"]
        
        # Emit the final result
        await emit_event("completion:result", result_event_data)
        
        # Unlock conversation if needed
        if conversation_lock.get("enabled", False):
            await emit_event("conversation:unlock", {
                "session_id": data.get("session_id"),
                "agent_id": data.get("agent_id")
            })
        
        return standardized_response
        
    except asyncio.CancelledError:
        # Handle cancellation
        logger.info(f"Completion {request_id} cancelled")
        if request_id in active_completions:
            active_completions[request_id]["status"] = "cancelled"
        await emit_event("completion:cancelled", {"request_id": request_id})
        raise
    except Exception as e:
        # Handle errors
        logger.error(f"Completion {request_id} failed: {e}", exc_info=True)
        if request_id in active_completions:
            active_completions[request_id]["status"] = "failed"
            active_completions[request_id]["error"] = str(e)
        
        await emit_event("completion:error", {
            "request_id": request_id,
            "error": str(e),
            "session_id": data.get("session_id")
        })
        
        # Unlock conversation on error
        conversation_lock = data.get("conversation_lock", {})
        if conversation_lock.get("enabled", False):
            await emit_event("conversation:unlock", {
                "session_id": data.get("session_id"),
                "agent_id": data.get("agent_id")
            })
        
        return {"error": str(e), "request_id": request_id}
    finally:
        # Clean up tracking after delay
        if request_id in active_completions:
            async def cleanup():
                await asyncio.sleep(60)  # Keep for 1 minute
                active_completions.pop(request_id, None)
            asyncio.create_task(cleanup())


@event_handler("completion:cancel")
async def handle_cancel_completion(data: CompletionCancelData) -> Dict[str, Any]:
    """Cancel an in-progress completion."""
    request_id = data["request_id"]
    
    if request_id not in active_completions:
        return {"error": f"Unknown request_id: {request_id}"}
    
    completion = active_completions[request_id]
    
    if completion["status"] in ["completed", "failed", "cancelled"]:
        return {"error": f"Request {request_id} already {completion['status']}"}
    
    # TODO: Implement actual cancellation logic
    # For now, just mark as cancelled
    completion["status"] = "cancelled"
    
    logger.info(f"Cancelled completion {request_id}")
    
    return {
        "request_id": request_id,
        "status": "cancelled"
    }


@event_handler("completion:status")
async def handle_completion_status(data: CompletionStatusData) -> Dict[str, Any]:
    """Get status of all active completions."""
    
    # Build status summary
    status_counts = {}
    for completion in active_completions.values():
        status = completion["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Get session info
    session_info = {}
    for session_id, queue in session_processors.items():
        session_info[session_id] = {
            "queue_size": queue.qsize(),
            "is_active": session_id in active_sessions
        }
    
    return {
        "active_completions": len(active_completions),
        "status_counts": status_counts,
        "sessions": session_info,
        "service_ready": completion_task_group is not None
    }


@event_handler("completion:session_status")
async def handle_session_status(data: CompletionSessionStatusData) -> Dict[str, Any]:
    """Get detailed status for a specific session."""
    session_id = data["session_id"]
    
    # Find completions for this session
    session_completions = []
    for request_id, completion in active_completions.items():
        if completion.get("session_id") == session_id:
            session_completions.append({
                "request_id": request_id,
                "status": completion["status"],
                "queued_at": completion.get("queued_at"),
                "started_at": completion.get("started_at"),
                "completed_at": completion.get("completed_at")
            })
    
    # Get queue info
    queue_info = None
    if session_id in session_processors:
        queue = session_processors[session_id]
        queue_info = {
            "queue_size": queue.qsize(),
            "is_processing": session_id in active_sessions
        }
    
    return {
        "session_id": session_id,
        "completions": session_completions,
        "queue": queue_info
    }


@event_handler("completion:retry_status")
async def handle_retry_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get retry manager status and statistics."""
    if not retry_manager:
        return {"error": "Retry manager not available"}
    
    stats = retry_manager.get_retry_stats()
    retrying_requests = retry_manager.list_retrying_requests()
    
    return {
        "retry_manager": "active",
        "stats": stats,
        "retrying_requests": retrying_requests
    }


@event_handler("completion:failed")
async def handle_completion_failed(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle completion failures and attempt retries if appropriate."""
    request_id = data.get("request_id")
    if not request_id:
        logger.warning("Completion failure without request_id", data=data)
        return {"error": "Missing request_id"}
    
    # Extract error information
    error_type = extract_error_type(data)
    error_message = data.get("message", "Unknown error")
    
    logger.warning(
        "Completion failed",
        request_id=request_id,
        error_type=error_type,
        error_message=error_message
    )
    
    # Clean up active completion
    completion = active_completions.pop(request_id, None)
    
    # If no active completion, check if this is from checkpoint restore
    if not completion:
        # For checkpoint restore, the completion data is included in the event
        if data.get("reason") == "daemon_restart" and "completion_data" in data:
            completion = data["completion_data"]
            logger.info("Processing checkpoint restore failure", request_id=request_id)
        else:
            logger.debug("No active completion found for failed request", request_id=request_id)
            return {"status": "not_found"}
    
    if retry_manager:
        # Attempt retry with original request data
        original_data = completion.get("data", {})
        retry_attempted = retry_manager.add_retry_candidate(
            request_id=request_id,
            original_data=original_data,
            error_type=error_type,
            error_message=error_message
        )
        
        if retry_attempted:
            logger.info("Retry scheduled for failed completion", request_id=request_id)
            return {"status": "retry_scheduled"}
        else:
            logger.warning("Completion not retryable", request_id=request_id, error_type=error_type)
            return {"status": "not_retryable"}
    else:
        logger.warning("Retry manager not available")
        return {"status": "retry_unavailable"}


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Completion service shutting down")
    
    # Stop retry manager first
    if retry_manager:
        await retry_manager.stop()
        logger.info("Retry manager stopped")
    
    # Cancel all active completions
    for request_id in list(active_completions.keys()):
        completion = active_completions[request_id]
        if completion["status"] in ["queued", "processing"]:
            completion["status"] = "cancelled"
            await emit_event("completion:cancelled", {"request_id": request_id})
    
    # Clear session processors
    session_processors.clear()
    active_sessions.clear()


