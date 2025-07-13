#!/usr/bin/env python3
"""
Completion Service Module V4 - Modular Architecture

Refactored completion service using focused components:
- QueueManager: Per-session queue management
- ProviderManager: Provider selection and failover
- ConversationTracker: Session continuity, locking, and automatic tracking
- TokenTracker: Usage analytics
- RetryManager: Failure recovery
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, Optional, List, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, EventPriority, emit_event, get_router
from ksi_common import timestamp_utc, create_completion_response, parse_completion_response, get_response_session_id
from ksi_common.completion_format import get_response_text
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Import modular components
from ksi_daemon.completion.queue_manager import CompletionQueueManager
from ksi_daemon.completion.provider_manager import ProviderManager
from ksi_daemon.completion.conversation_tracker import ConversationTracker
from ksi_daemon.completion.token_tracker import TokenTracker
from ksi_daemon.completion.retry_manager import RetryManager, RetryPolicy, extract_error_type
from ksi_common.json_extraction import extract_and_emit_json_events
from ksi_daemon.completion.litellm import handle_litellm_completion


logger = get_bound_logger("completion_service", version="4.0.0")

# Module components
queue_manager: Optional[CompletionQueueManager] = None
provider_manager: Optional[ProviderManager] = None
conversation_tracker: Optional[ConversationTracker] = None
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

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup", priority=EventPriority.LOW)
async def handle_startup(config_data: SystemStartupData) -> Dict[str, Any]:
    """Initialize completion service on startup."""
    global queue_manager, provider_manager, conversation_tracker, token_tracker
    
    logger.info("Completion service startup handler called")
    
    ensure_directories()
    
    # Initialize components
    queue_manager = CompletionQueueManager()
    provider_manager = ProviderManager()
    conversation_tracker = ConversationTracker()
    token_tracker = TokenTracker()
    
    logger.info("Completion service started with modular architecture")
    logger.info(
        f"Components initialized: queue={queue_manager is not None}, "
        f"conversation={conversation_tracker is not None}, "
        f"provider={provider_manager is not None}, token={token_tracker is not None}"
    )
    
    return {"status": "completion_service_ready", "version": "4.0.0"}


class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(context: SystemContextData) -> None:
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
                        if conversation_tracker:
                            conversation_tracker.cleanup_expired_locks()
                            conversation_tracker.cleanup_inactive_sessions()
                            
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


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for this handler
    pass


@event_handler("system:ready")
async def handle_ready(data: SystemReadyData) -> Optional[Dict[str, Any]]:
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


class ClearAgentSessionData(TypedDict):
    """Clear agent session data."""
    agent_id: Required[str]  # Agent ID to clear session for


@event_handler("completion:clear_agent_session")
async def handle_clear_agent_session(data: ClearAgentSessionData) -> Dict[str, Any]:
    """Clear an agent's session mapping when the agent is terminated."""
    if not conversation_tracker:
        return {"error": "Conversation tracker not initialized"}
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "agent_id required"}
    
    # Clear the agent's session mapping
    if agent_id in conversation_tracker._agent_sessions:
        old_session = conversation_tracker._agent_sessions.pop(agent_id)
        logger.info(f"Cleared session mapping for terminated agent {agent_id} (was: {old_session})")
        return {"status": "cleared", "old_session": old_session}
    else:
        logger.debug(f"No session mapping found for agent {agent_id}")
        return {"status": "not_found"}


class CompletionAsyncData(TypedDict):
    """Async completion request."""
    request_id: NotRequired[str]  # Request ID (auto-generated if not provided)
    session_id: NotRequired[str]  # Session ID for conversation continuity
    agent_id: NotRequired[str]  # Agent making the request
    model: NotRequired[str]  # Model to use (defaults to config.completion_default_model)
    messages: NotRequired[List[Dict[str, Any]]]  # Conversation messages
    prompt: NotRequired[str]  # Simple prompt (converted to messages)
    stream: NotRequired[bool]  # Whether to stream response
    temperature: NotRequired[float]  # Sampling temperature
    max_tokens: NotRequired[int]  # Maximum tokens to generate
    conversation_lock: NotRequired[Dict[str, Any]]  # Lock configuration
    injection_config: NotRequired[Dict[str, Any]]  # Injection configuration
    circuit_breaker_config: NotRequired[Dict[str, Any]]  # Circuit breaker config
    extra_body: NotRequired[Dict[str, Any]]  # Provider-specific parameters
    originator_id: NotRequired[str]  # Original requester ID
    conversation_id: NotRequired[str]  # Conversation ID (auto-generated if not provided)


@event_handler("completion:async")
async def handle_async_completion(data: CompletionAsyncData) -> Dict[str, Any]:
    """Handle async completion requests with smart queueing and automatic session continuity."""
    if not all([queue_manager, provider_manager, conversation_tracker]):
        return {"error": "Completion service not fully initialized"}
    
    # Preserve original request_id from agent, or generate new one if missing
    request_id = data.get("request_id", str(uuid.uuid4()))
    start_time = time.time()
    
    # Ensure request_id is set in data
    data["request_id"] = request_id
    
    # AUTOMATIC SESSION CONTINUITY: Resolve session_id based on agent_id if not explicitly provided
    agent_id = data.get("agent_id")
    requested_session_id = data.get("session_id")
    
    if requested_session_id:
        # Explicit session_id provided - use it
        session_id = requested_session_id
        logger.debug(f"Using explicit session_id {session_id} for agent {agent_id}")
    elif agent_id:
        # No explicit session - try to continue agent's current conversation
        agent_session = conversation_tracker.get_agent_session(agent_id)
        if agent_session:
            session_id = agent_session
            data["session_id"] = session_id  # Update the request data
            logger.info(f"Automatic session continuity: agent {agent_id} continuing session {session_id}")
        else:
            # Agent has no current session - new conversation
            session_id = None
            data["session_id"] = None
            logger.info(f"New conversation for agent {agent_id} (no current session)")
    else:
        # No agent_id - use provided session_id or None for new conversation
        session_id = requested_session_id
        logger.debug(f"No agent_id provided, using session_id {session_id}")
    
    logger.info(
        f"Received async completion request",
        request_id=request_id,
        session_id=session_id,
        agent_id=agent_id,
        automatic_continuity=bool(agent_id and not requested_session_id and session_id),
        model=data.get("model", config.completion_default_model)
    )
    
    # Track with conversation tracker for session continuity
    conversation_tracker.track_request(request_id, agent_id, session_id)
    
    # Save recovery data
    conversation_tracker.save_recovery_data(request_id, data)
    
    # Enqueue request (use "pending" as session key if session_id is None)
    queue_session_key = session_id or "pending"
    queue_status = await queue_manager.enqueue(queue_session_key, request_id, data)
    
    # Track active completion (preserved from original)
    active_completions[request_id] = {
        "session_id": session_id,
        "agent_id": agent_id,
        "status": "queued",
        "queued_at": timestamp_utc(),
        "data": dict(data),  # Store full request for potential retry
        "original_event": "completion:async"
    }
    
    # Start processor if needed - one processor per conversation
    if queue_manager.should_create_processor(queue_session_key):
        queue_manager.mark_session_active(queue_session_key)
        
        async def process_session():
            try:
                await process_session_queue(queue_session_key)
            finally:
                queue_manager.mark_session_inactive(queue_session_key)
        
        if completion_task_group:
            completion_task_group.create_task(process_session())
            logger.info(f"Created processor for session {queue_session_key}" + 
                       (f" (agent: {agent_id})" if agent_id else ""))
        else:
            # Fallback: create task directly if task group not ready
            logger.warning(f"Task group not ready, creating processor task directly for session {queue_session_key}")
            asyncio.create_task(process_session())
    
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
            result = await queue_manager.dequeue(session_id, timeout=queue_manager._queue_timeout)
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
        # Acquire conversation lock for existing conversations (session_id != None)
        # New conversations (session_id == None) don't need locking
        session_id_for_lock = data.get("session_id")
        if session_id_for_lock:
            conversation_lock = data.get("conversation_lock", {})
            lock_timeout = conversation_lock.get("timeout", 300)
            
            lock_result = await conversation_tracker.acquire_conversation_lock(
                session_id_for_lock,
                data.get("agent_id"),
                lock_timeout
            )
            
            if not lock_result.get("success"):
                raise Exception(f"Failed to acquire conversation lock: {lock_result.get('reason')}")
        else:
            # New conversation - no lock needed
            logger.debug(f"New conversation (session_id=None) - skipping conversation lock")
        
        # Select provider - use config default if not specified
        model = data.get("model", config.completion_default_model)
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
        
        # Ensure model is set in data for litellm
        if "model" not in data:
            data["model"] = model
        
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
        
        # Extract and emit JSON events from response (non-blocking)
        if event_emitter:
            response_text = get_response_text(standardized_response)
            if response_text:
                agent_id = data.get('agent_id')
                
                # Run extraction in background to avoid blocking
                async def extract_and_send_feedback():
                    try:
                        extraction_results = await extract_and_emit_json_events(
                            text=response_text,
                            event_emitter=event_emitter,
                            context={
                                'request_id': request_id,
                                'session_id': data.get('session_id'),
                                'model': model,
                                'provider': provider
                            },
                            agent_id=agent_id
                        )
                        
                        if extraction_results:
                            logger.info(f"Extracted {len(extraction_results)} events from completion response",
                                      request_id=request_id,
                                      agent_id=agent_id,
                                      events=[e['event'] for e in extraction_results])
                            
                            # Send feedback as separate completion:async if agent_id exists
                            if agent_id and extraction_results:
                                feedback_content = f"=== EVENT EMISSION RESULTS ===\n"
                                feedback_content += json.dumps(extraction_results, indent=2)
                                
                                # Send via completion:async - maintains loose coupling
                                await event_emitter("completion:async", {
                                    "messages": [{
                                        "role": "system",
                                        "content": feedback_content
                                    }],
                                    "agent_id": agent_id,
                                    "originator_id": agent_id,
                                    "model": model,  # Use same model as original
                                    "priority": "high",  # Feedback should be prompt
                                    "is_feedback": True,  # Flag to indicate this is event feedback
                                    "parent_request_id": request_id  # Link to original request
                                })
                                
                                logger.debug(f"Queued event emission feedback for agent {agent_id}")
                                
                    except Exception as e:
                        logger.error(f"Failed to extract JSON events: {e}",
                                   request_id=request_id,
                                   error=str(e))
                
                # Create task but don't await - non-blocking!
                asyncio.create_task(extract_and_send_feedback())
        
        # CRITICAL: Update session tracking with the NEW session_id from claude-cli
        if provider == "claude-cli":
            response_session_id = get_response_session_id(standardized_response)
            if response_session_id:
                # Update ConversationTracker for automatic session continuity
                conversation_tracker.update_request_session(request_id, response_session_id)
                
                logger.info(
                    f"Updated session tracking: request {request_id} -> session {response_session_id}",
                    original_session_id=data.get("session_id"),
                    agent_id=data.get("agent_id"),
                    automatic_continuity=True
                )
        
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
        conversation_tracker.complete_request(request_id)
        conversation_tracker.clear_recovery_data(request_id)
        
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
        logger.info(f"About to emit completion:result event", 
                   request_id=request_id,
                   has_result=bool(result_event_data.get("result")),
                   result_keys=list(result_event_data.get("result", {}).keys()) if isinstance(result_event_data.get("result"), dict) else None)
        
        try:
            await emit_event("completion:result", result_event_data)
            logger.info(f"Successfully emitted completion:result event", request_id=request_id)
        except Exception as e:
            logger.error(f"Failed to emit completion:result event", request_id=request_id, error=str(e), exc_info=True)
        
        # Unlock conversation if we acquired a lock
        if session_id_for_lock:
            await conversation_tracker.release_conversation_lock(
                session_id_for_lock,
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
        
        # Unlock conversation on error if we acquired a lock
        if 'session_id_for_lock' in locals() and session_id_for_lock:
            await conversation_tracker.release_conversation_lock(
                session_id_for_lock,
                data.get("agent_id")
            )
        
        return {"error": str(e), "request_id": request_id}


class CompletionStatusData(TypedDict):
    """Get completion service status."""
    # No specific fields - returns overall status
    pass


@event_handler("completion:status")
async def handle_completion_status(data: CompletionStatusData) -> Dict[str, Any]:
    """Get status of completion service and components."""
    # Debug logging
    logger.debug(
        f"Status check - components initialized: "
        f"queue={queue_manager is not None}, "
        f"conversation={conversation_tracker is not None}, "
        f"provider={provider_manager is not None}, "
        f"token={token_tracker is not None}"
    )
    
    if not all([queue_manager, conversation_tracker, provider_manager, token_tracker]):
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
        "sessions": conversation_tracker.get_all_sessions_status(),
        "providers": provider_manager.get_all_provider_status(),
        "token_usage": token_tracker.get_summary_statistics(),
        "retry_manager": retry_manager.get_retry_stats() if retry_manager else None
    }


class CompletionSessionStatusData(TypedDict):
    """Get status for a specific session."""
    session_id: Required[str]  # Session ID to query


@event_handler("completion:session_status")
async def handle_session_status(data: CompletionSessionStatusData) -> Dict[str, Any]:
    """Get detailed status for a specific session."""
    if not all([queue_manager, conversation_tracker]):
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
        "session": conversation_tracker.get_session_status(session_id)
    }


class CompletionProviderStatusData(TypedDict):
    """Get provider status."""
    provider: NotRequired[str]  # Specific provider name (optional)


@event_handler("completion:provider_status")
async def handle_provider_status(data: CompletionProviderStatusData) -> Dict[str, Any]:
    """Get provider status and health information."""
    if not provider_manager:
        return {"error": "Provider manager not initialized"}
    
    provider = data.get("provider")
    if provider:
        return provider_manager.get_provider_status(provider)
    else:
        return provider_manager.get_all_provider_status()


class CompletionTokenUsageData(TypedDict):
    """Get token usage analytics."""
    agent_id: NotRequired[str]  # Filter by agent ID
    model: NotRequired[str]  # Filter by model
    hours: NotRequired[int]  # Time window in hours


@event_handler("completion:token_usage")
async def handle_token_usage(data: CompletionTokenUsageData) -> Dict[str, Any]:
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


class CompletionCancelData(TypedDict):
    """Cancel an in-progress completion."""
    request_id: Required[str]  # Request ID to cancel


@event_handler("completion:cancel")
async def handle_cancel_completion(data: CompletionCancelData) -> Dict[str, Any]:
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


class CompletionRetryStatusData(TypedDict):
    """Get retry manager status."""
    # No specific fields - returns overall retry status
    pass


@event_handler("completion:retry_status")
async def handle_retry_status(data: CompletionRetryStatusData) -> Dict[str, Any]:
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


class CompletionFailedData(TypedDict):
    """Handle completion failure."""
    request_id: Required[str]  # Failed request ID
    message: NotRequired[str]  # Error message
    reason: NotRequired[str]  # Failure reason (e.g., 'daemon_restart')
    completion_data: NotRequired[Dict[str, Any]]  # Original completion data for recovery


@event_handler("completion:failed")
async def handle_completion_failed(data: CompletionFailedData) -> Dict[str, Any]:
    """Handle completion failures and attempt retries if appropriate."""
    request_id = data.get("request_id")
    if not request_id:
        logger.warning("Completion failure without request_id", data=data)
        return {"error": "Missing request_id"}
    
    # Get recovery data from conversation tracker
    recovery_data = conversation_tracker.get_recovery_data(request_id) if conversation_tracker else None
    
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


class CheckpointCollectData(TypedDict):
    """Collect checkpoint data."""
    # No specific fields - collects all completion state
    pass


@event_handler("checkpoint:collect")
async def collect_checkpoint_data(data: CheckpointCollectData) -> Dict[str, Any]:
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
        "conversation_tracker": conversation_tracker is not None,
        "token_tracker": token_tracker is not None,
        "retry_manager": retry_manager is not None
    }
    
    logger.info(
        f"Collected checkpoint data",
        active_completions=len(checkpoint_data["active_completions"]),
        session_queues=len(checkpoint_data["session_queues"])
    )
    
    return checkpoint_data


class CheckpointRestoreData(TypedDict):
    """Restore from checkpoint data."""
    active_completions: NotRequired[Dict[str, Any]]  # Completions to restore
    session_queues: NotRequired[Dict[str, Any]]  # Session queues to restore


@event_handler("checkpoint:restore")
async def restore_checkpoint_data(data: CheckpointRestoreData) -> Dict[str, Any]:
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


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
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
    
    if conversation_tracker:
        # Cancel any active locks
        stats["sessions"] = conversation_tracker.get_all_sessions_status()
    
    if provider_manager:
        stats["providers"] = provider_manager.get_all_provider_status()
    
    if token_tracker:
        stats["tokens"] = token_tracker.get_summary_statistics()
    
    logger.info("Completion service shutdown complete", stats=stats)