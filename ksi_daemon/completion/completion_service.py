#!/usr/bin/env python3
"""
Completion Service Plugin V4 - Modular Architecture

Refactored completion service using focused components:
- QueueManager: Per-session queue management
- ProviderManager: Provider selection and failover
- SessionManager: Session continuity and locking
- TokenTracker: Usage analytics
- RetryManager: Failure recovery (existing)
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from ksi_daemon.event_system import event_handler, EventPriority, emit_event, get_router
from ksi_common import timestamp_utc, create_completion_response, parse_completion_response, get_response_session_id
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Import modular components
from ksi_daemon.completion.queue_manager import CompletionQueueManager
from ksi_daemon.completion.provider_manager import ProviderManager
from ksi_daemon.completion.session_manager import SessionManager
from ksi_daemon.completion.token_tracker import TokenTracker
from ksi_daemon.completion.retry_manager import RetryManager, RetryPolicy, extract_error_type
from ksi_daemon.completion.litellm import handle_litellm_completion


logger = get_bound_logger("completion_service", version="4.0.0")

# Module components
queue_manager: Optional[CompletionQueueManager] = None
provider_manager: Optional[ProviderManager] = None
session_manager: Optional[SessionManager] = None
token_tracker: Optional[TokenTracker] = None
retry_manager: Optional[RetryManager] = None

# Active completions tracking (preserved from original)
active_completions: Dict[str, Dict[str, Any]] = {}

# Task tracking for cancellation support
active_tasks: Dict[str, asyncio.Task] = {}  # request_id -> task

# Event emitter and shutdown references
event_emitter = None
shutdown_event = None

# Asyncio task management
completion_task_group = None


def ensure_directories():
    """Ensure required directories exist."""
    config.ensure_directories()


def save_completion_response(response_data: Dict[str, Any]) -> None:
    """Save standardized completion response to session file."""
    try:
        completion_response = parse_completion_response(response_data)
        session_id = get_response_session_id(completion_response)
        
        if not session_id:
            logger.warning("No session_id in completion response, cannot save to session file")
            return
        
        responses_dir = config.response_log_dir
        responses_dir.mkdir(parents=True, exist_ok=True)
        
        session_file = responses_dir / f"{session_id}.jsonl"
        
        with open(session_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(response_data) + '\n')
        
        logger.debug(f"Saved completion response to {session_file}")
        
    except Exception as e:
        logger.error(f"Failed to save completion response: {e}", exc_info=True)


# Event handlers

@event_handler("system:startup", priority=EventPriority.LOW)
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize completion service on startup."""
    global queue_manager, provider_manager, session_manager, token_tracker
    
    logger.info("Completion service startup handler called")
    
    ensure_directories()
    
    # Initialize components
    queue_manager = CompletionQueueManager()
    provider_manager = ProviderManager()
    session_manager = SessionManager()
    token_tracker = TokenTracker()
    
    logger.info("Completion service started with modular architecture")
    logger.info(
        f"Components initialized: queue={queue_manager is not None}, "
        f"session={session_manager is not None}, provider={provider_manager is not None}, "
        f"token={token_tracker is not None}"
    )
    
    return {"status": "completion_service_ready", "version": "4.0.0"}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive runtime context."""
    global event_emitter, shutdown_event, retry_manager
    
    event_emitter = context.get("emit_event")
    shutdown_event = context.get("shutdown_event")
    
    if event_emitter:
        logger.info("Completion service received event emitter")
        
        # Initialize retry manager
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
        async with asyncio.TaskGroup() as tg:
            completion_task_group = tg
            logger.info("Completion service ready")
            
            # Periodic cleanup task
            async def cleanup_task():
                while not shutdown_event.is_set():
                    try:
                        # Clean up every 5 minutes
                        await asyncio.sleep(300)
                        
                        if queue_manager:
                            queue_manager.cleanup_empty_queues()
                        if session_manager:
                            session_manager.cleanup_expired_locks()
                            session_manager.cleanup_inactive_sessions()
                            
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Cleanup task error: {e}")
            
            tg.create_task(cleanup_task())
            
            await shutdown_event.wait()
            logger.info("Shutdown event received, completion service exiting gracefully")
            
    except* Exception as eg:
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
    """Handle async completion requests with smart queueing."""
    if not all([queue_manager, session_manager, provider_manager]):
        return {"error": "Completion service not fully initialized"}
    
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    data["request_id"] = request_id
    session_id = data.get("session_id", "default")
    
    logger.info(
        f"Received async completion request",
        request_id=request_id,
        session_id=session_id,
        model=data.get("model", "unknown")
    )
    
    # Register with session manager
    session_manager.register_request(session_id, request_id, data.get("agent_id"))
    
    # Save recovery data
    session_manager.save_recovery_data(session_id, request_id, data)
    
    # Enqueue request
    queue_status = await queue_manager.enqueue(session_id, request_id, data)
    
    # Track active completion (preserved from original)
    active_completions[request_id] = {
        "session_id": session_id,
        "status": "queued",
        "queued_at": timestamp_utc(),
        "data": dict(data),  # Store full request for potential retry
        "original_event": "completion:async"
    }
    
    # Start processor if needed
    if queue_manager.should_create_processor(session_id):
        queue_manager.mark_session_active(session_id)
        
        async def process_session():
            try:
                await process_session_queue(session_id)
            finally:
                queue_manager.mark_session_inactive(session_id)
        
        completion_task_group.create_task(process_session())
    
    return {
        "request_id": request_id,
        "status": "queued",
        "message": "Completion request queued for processing",
        **queue_status
    }


async def process_session_queue(session_id: str):
    """Process completion requests for a specific session."""
    while True:
        try:
            # Get next request
            result = await queue_manager.dequeue(session_id, timeout=1.0)
            if not result:
                # No requests, check if we should exit
                if queue_manager.get_queue_status(session_id).get("is_empty", True):
                    logger.debug(f"Session processor {session_id} idle, exiting")
                    break
                continue
            
            request_id, data = result
            
            # Process the completion
            await process_completion_request(request_id, data)
            
        except Exception as e:
            logger.error(f"Error processing session queue: {e}", exc_info=True)


async def process_completion_request(request_id: str, data: Dict[str, Any]):
    """Process a single completion request using modular components."""
    try:
        # Register current task for cancellation support
        current_task = asyncio.current_task()
        if current_task:
            active_tasks[request_id] = current_task
        
        # Update status to processing
        if request_id in active_completions:
            active_completions[request_id]["status"] = "processing"
            active_completions[request_id]["started_at"] = timestamp_utc()
        # Handle conversation lock if needed
        conversation_lock = data.get("conversation_lock", {})
        if conversation_lock.get("enabled", False):
            lock_result = await session_manager.acquire_conversation_lock(
                data.get("session_id"),
                data.get("agent_id"),
                conversation_lock.get("timeout", 300)
            )
            
            if not lock_result.get("locked"):
                raise Exception(f"Failed to acquire conversation lock: {lock_result.get('reason')}")
        
        # Select provider
        model = data.get("model", "unknown")
        require_mcp = bool(data.get("extra_body", {}).get("ksi", {}).get("mcp_config_path"))
        provider_name, provider_config = provider_manager.select_provider(
            model, 
            require_mcp=require_mcp,
            prefer_streaming=data.get("stream", False)
        )
        
        # Emit progress event
        await emit_event("completion:progress", {
            "request_id": request_id,
            "session_id": data.get("session_id"),
            "status": "calling_provider",
            "provider": provider_name
        })
        
        # Call completion
        start_time = time.time()
        
        # Add conversation_id if not present
        if "conversation_id" not in data:
            data["conversation_id"] = f"ksi-{request_id}"
        
        # Call through provider (currently only litellm handler)
        provider, raw_response = await handle_litellm_completion(data)
        
        # Track success
        latency_ms = int((time.time() - start_time) * 1000)
        provider_manager.record_success(provider_name, latency_ms)
        
        # Create standardized response
        standardized_response = create_completion_response(
            provider=provider,
            raw_response=raw_response,
            request_id=request_id,
            client_id=data.get("originator_id"),  # Completion format uses client_id internally
            duration_ms=latency_ms
        )
        
        # Save to session log
        save_completion_response(standardized_response)
        
        # Track token usage
        if provider == "claude-cli" and "response" in standardized_response:
            raw_resp = standardized_response["response"]
            if isinstance(raw_resp, dict):
                usage = raw_resp.get("usage", {})
                if usage:
                    token_tracker.record_usage({
                        "request_id": request_id,
                        "session_id": data.get("session_id"),
                        "agent_id": data.get("agent_id"),
                        "model": model,
                        "provider": provider_name,
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                        "has_mcp": require_mcp
                    })
        
        # Clean up tracking
        session_manager.complete_request(data.get("session_id"), request_id)
        session_manager.clear_recovery_data(request_id)
        
        # Remove from active completions (with delayed cleanup)
        if request_id in active_completions:
            active_completions[request_id]["status"] = "completed"
            active_completions[request_id]["completed_at"] = timestamp_utc()
            
            async def cleanup():
                await asyncio.sleep(60)  # Keep for 1 minute
                active_completions.pop(request_id, None)
                active_tasks.pop(request_id, None)  # Clean up task tracking
            asyncio.create_task(cleanup())
        
        # Handle injection if needed
        result_event_data = {
            "request_id": request_id,
            "result": standardized_response
        }
        
        injection_config = data.get("injection_config")
        if injection_config and injection_config.get('enabled') and event_emitter:
            injection_result = await event_emitter("injection:process_result", {
                "request_id": request_id,
                "result": standardized_response,
                "injection_metadata": {
                    "injection_config": injection_config,
                    "circuit_breaker_config": data.get('circuit_breaker_config', {})
                }
            })
            
            if injection_result and isinstance(injection_result, dict) and "result" in injection_result:
                result_event_data["result"] = injection_result["result"]
        
        # Emit result
        await emit_event("completion:result", result_event_data)
        
        # Unlock conversation
        if conversation_lock.get("enabled", False):
            await session_manager.release_conversation_lock(
                data.get("session_id"),
                data.get("agent_id")
            )
        
        return standardized_response
        
    except asyncio.CancelledError:
        logger.info(f"Completion {request_id} cancelled")
        if request_id in active_completions:
            active_completions[request_id]["status"] = "cancelled"
        # Clean up task tracking immediately on cancellation
        active_tasks.pop(request_id, None)
        await emit_event("completion:cancelled", {"request_id": request_id})
        raise
        
    except Exception as e:
        logger.error(f"Completion {request_id} failed: {e}", exc_info=True)
        if request_id in active_completions:
            active_completions[request_id]["status"] = "failed"
            active_completions[request_id]["error"] = str(e)
        
        # Clean up task tracking on failure
        active_tasks.pop(request_id, None)
        
        # Record provider failure if we got that far
        if 'provider_name' in locals():
            provider_manager.record_failure(provider_name, str(e))
        
        # Emit error event
        await emit_event("completion:error", {
            "request_id": request_id,
            "error": str(e),
            "session_id": data.get("session_id")
        })
        
        # Unlock conversation on error
        if conversation_lock.get("enabled", False):
            await session_manager.release_conversation_lock(
                data.get("session_id"),
                data.get("agent_id")
            )
        
        return {"error": str(e), "request_id": request_id}


@event_handler("completion:status")
async def handle_completion_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get status of completion service and components."""
    # Debug logging
    logger.debug(
        f"Status check - components initialized: "
        f"queue={queue_manager is not None}, "
        f"session={session_manager is not None}, "
        f"provider={provider_manager is not None}, "
        f"token={token_tracker is not None}"
    )
    
    if not all([queue_manager, session_manager, provider_manager, token_tracker]):
        return {"error": "Completion service not fully initialized"}
    
    # Build status summary (preserving original functionality)
    status_counts = {}
    for completion in active_completions.values():
        status = completion["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "service_ready": completion_task_group is not None,
        "active_completions": len(active_completions),
        "active_tasks": len(active_tasks),
        "status_counts": status_counts,
        "queues": queue_manager.get_all_queue_status(),
        "sessions": session_manager.get_all_sessions_status(),
        "providers": provider_manager.get_all_provider_status(),
        "token_usage": token_tracker.get_summary_statistics(),
        "retry_manager": retry_manager.get_retry_stats() if retry_manager else None
    }


@event_handler("completion:session_status")
async def handle_session_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed status for a specific session."""
    if not all([queue_manager, session_manager]):
        return {"error": "Completion service not fully initialized"}
    
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    
    # Find completions for this session (preserving original functionality)
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
    
    return {
        "session_id": session_id,
        "completions": session_completions,
        "queue": queue_manager.get_queue_status(session_id),
        "session": session_manager.get_session_status(session_id)
    }


@event_handler("completion:provider_status")
async def handle_provider_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get provider status and health information."""
    if not provider_manager:
        return {"error": "Provider manager not initialized"}
    
    provider = data.get("provider")
    if provider:
        return provider_manager.get_provider_status(provider)
    else:
        return provider_manager.get_all_provider_status()


@event_handler("completion:token_usage")
async def handle_token_usage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get token usage analytics."""
    if not token_tracker:
        return {"error": "Token tracker not initialized"}
    
    agent_id = data.get("agent_id")
    model = data.get("model")
    
    if agent_id:
        return token_tracker.get_agent_usage(agent_id, data.get("hours"))
    elif model:
        return token_tracker.get_model_usage(model)
    else:
        return token_tracker.get_summary_statistics()


@event_handler("completion:cancel")
async def handle_cancel_completion(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel an in-progress completion."""
    request_id = data.get("request_id")
    if not request_id:
        return {"error": "request_id required"}
    
    if request_id not in active_completions:
        return {"error": f"Unknown request_id: {request_id}"}
    
    completion = active_completions[request_id]
    
    if completion["status"] in ["completed", "failed", "cancelled"]:
        return {"error": f"Request {request_id} already {completion['status']}"}
    
    # Implement actual cancellation logic
    completion["status"] = "cancelled"
    
    # Cancel the actual asyncio task if it's still running
    if request_id in active_tasks:
        task = active_tasks[request_id]
        if not task.done():
            logger.debug(f"Cancelling asyncio task for request {request_id}")
            task.cancel()
            # Task cleanup will happen in the CancelledError handler
        else:
            # Task already finished, just clean up tracking
            active_tasks.pop(request_id, None)
    else:
        logger.warning(f"No active task found for request {request_id} - may have already completed")
    
    logger.info(f"Cancelled completion {request_id}")
    
    return {
        "request_id": request_id,
        "status": "cancelled"
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
    
    # Get recovery data from session manager
    recovery_data = session_manager.get_recovery_data(request_id) if session_manager else None
    
    # If no recovery data, check active completions (fallback)
    if not recovery_data and request_id in active_completions:
        completion = active_completions.pop(request_id)
        recovery_data = {
            "request_data": completion.get("data", {})
        }
    
    if not recovery_data:
        # Check if this is from checkpoint restore
        if data.get("reason") == "daemon_restart" and "completion_data" in data:
            recovery_data = {
                "request_data": data["completion_data"].get("data", {})
            }
            logger.info("Processing checkpoint restore failure", request_id=request_id)
        else:
            logger.debug("No recovery data found for failed request", request_id=request_id)
            return {"status": "not_found"}
    
    if retry_manager:
        # Extract error information
        error_type = extract_error_type(data)
        error_message = data.get("message", "Unknown error")
        
        # Attempt retry with original request data
        original_data = recovery_data.get("request_data", {})
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


@event_handler("checkpoint:collect")
async def collect_checkpoint_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Collect completion service state for checkpoint."""
    checkpoint_data = {
        "session_queues": {},
        "active_completions": dict(active_completions)  # Copy current state
    }
    
    # Extract queue contents if queue_manager exists
    if queue_manager:
        for session_id, queue in queue_manager._session_queues.items():
            queue_items = []
            
            # Copy queue contents without draining
            # Note: This is a simplified approach - in production you might want
            # to use a different strategy
            try:
                # Get queue size
                queue_size = queue.qsize()
                if queue_size > 0:
                    logger.warning(f"Cannot safely extract {queue_size} items from session {session_id} queue")
            except Exception as e:
                logger.debug(f"Error getting queue size for session {session_id}: {e}")
            
            checkpoint_data["session_queues"][session_id] = {
                "items": queue_items,  # Empty for now - can't safely extract from asyncio.Queue
                "is_active": queue_manager.is_session_active(session_id)
            }
    
    # Add component states
    checkpoint_data["components"] = {
        "queue_manager": queue_manager is not None,
        "provider_manager": provider_manager is not None,
        "session_manager": session_manager is not None,
        "token_tracker": token_tracker is not None,
        "retry_manager": retry_manager is not None
    }
    
    logger.info(
        f"Collected checkpoint data",
        active_completions=len(checkpoint_data["active_completions"]),
        session_queues=len(checkpoint_data["session_queues"])
    )
    
    return checkpoint_data


@event_handler("checkpoint:restore")
async def restore_checkpoint_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Restore completion service state from checkpoint."""
    global active_completions
    
    if not data:
        return {"restored": 0}
    
    # Restore active completions
    restored_completions = data.get("active_completions", {})
    active_completions.update(restored_completions)
    
    # Note: We cannot restore queue contents as they need to be re-processed
    # The retry mechanism will handle any interrupted requests
    
    logger.info(
        f"Restored checkpoint data",
        active_completions=len(restored_completions)
    )
    
    return {
        "restored": len(restored_completions),
        "message": "Active completions restored, queued items will be retried if needed"
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Completion service shutting down")
    
    # Stop retry manager
    if retry_manager:
        await retry_manager.stop()
        logger.info("Retry manager stopped")
    
    # Cancel all active completions and tasks
    for request_id in list(active_completions.keys()):
        completion = active_completions[request_id]
        if completion["status"] in ["queued", "processing"]:
            completion["status"] = "cancelled"
            
            # Cancel the actual task if it exists
            if request_id in active_tasks:
                task = active_tasks[request_id]
                if not task.done():
                    logger.debug(f"Shutdown: cancelling task for request {request_id}")
                    task.cancel()
            
            await emit_event("completion:cancelled", {"request_id": request_id})
    
    # Clear task tracking
    active_tasks.clear()
    
    # Get shutdown statistics
    stats = {}
    
    if queue_manager:
        stats["queue"] = queue_manager.shutdown()
    
    if session_manager:
        # Cancel any active locks
        stats["sessions"] = session_manager.get_all_sessions_status()
    
    if provider_manager:
        stats["providers"] = provider_manager.get_all_provider_status()
    
    if token_tracker:
        stats["tokens"] = token_tracker.get_summary_statistics()
    
    logger.info("Completion service shutdown complete", stats=stats)