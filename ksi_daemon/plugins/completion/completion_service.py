#!/usr/bin/env python3
"""
Completion Service Plugin V2

Enhanced completion service that integrates with:
- Async completion queue with priority support
- Conversation lock management
- Event-driven injection routing
- Circuit breaker safety mechanisms
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import pluggy

import anyio
import litellm

from ksi_common.logging import get_logger
from ksi_daemon.plugin_utils import plugin_metadata
from ksi_common import TimestampManager, create_completion_response, parse_completion_response
from ksi_daemon.config import config
from ksi_daemon.event_taxonomy import CLAUDE_EVENTS, format_claude_event

# Import injection systems
from ksi_daemon.plugins.injection.injection_router import queue_completion_with_injection
from ksi_daemon.plugins.injection.circuit_breakers import check_completion_allowed

# Import claude_cli_litellm_provider to ensure provider registration
from ksi_daemon.plugins.completion import claude_cli_litellm_provider

# Plugin metadata
plugin_metadata("completion_service", version="3.0.0",
                description="Enhanced LLM completion service with queue and injection support")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("completion_service")
active_completions: Dict[str, Dict[str, Any]] = {}

# Per-session queue management for fork prevention
session_processors: Dict[str, asyncio.Queue] = {}  # session_id -> Queue
active_sessions: set = set()  # Currently processing sessions

# Structured concurrency with anyio - created on demand
completion_task_group = None
task_group_context = None

# Event emitter reference (set during startup)
event_emitter = None


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
        session_id = completion_response.get_session_id()
        
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


# Hook implementations
@hookimpl(trylast=True)  # Run after core services are ready  
def ksi_startup(config):
    """Initialize completion service on startup."""
    ensure_directories()
    logger.info("Smart hybrid completion service with anyio structured concurrency - event-driven with per-session fork prevention")
    return {"status": "completion_service_anyio_smart_hybrid_ready"}



async def manage_completion_service():
    """Long-running service to manage anyio task group for completions."""
    global completion_task_group, task_group_context
    
    try:
        # Create and enter the task group context
        async with anyio.create_task_group() as tg:
            completion_task_group = tg
            logger.info("Completion service ready")
            
            # Keep the service running until cancelled
            await anyio.sleep_forever()
            
    except anyio.get_cancelled_exc_class():
        raise
    except Exception as e:
        logger.error(f"Completion service error: {e}", exc_info=True)
        raise
    finally:
        completion_task_group = None


@hookimpl
def ksi_ready():
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




@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle completion-related events."""
    
    if event_name == "completion:async":
        # Smart hybrid: event-driven + per-session fork prevention
        # Create a coroutine wrapper for consistent async handling
        async def _handle_async():
            return await handle_async_completion_smart(data, context)
        return _handle_async()
    
    elif event_name == "completion:cancel":
        # Cancel an active completion
        request_id = data.get("request_id")
        if request_id in active_completions:
            # Cancellation with queue not yet implemented
            del active_completions[request_id]
            return {"status": "cancelled"}
        return {"status": "not_found"}
    
    elif event_name == "completion:status":
        # anyio smart hybrid architecture status
        return {
            "architecture": "anyio_smart_hybrid",
            "task_group_active": completion_task_group is not None,
            "active_count": len(active_completions),
            "active_requests": list(active_completions.keys()),
            "active_sessions": list(active_sessions),
            "session_queues": {
                session_id: queue.qsize() 
                for session_id, queue in session_processors.items()
            },
            "session_queue_count": len(session_processors)
        }
    
    elif event_name == "completion:session_status":
        # Detailed per-session status
        session_id = data.get("session_id")
        if not session_id:
            return {"error": "session_id required"}
            
        return {
            "session_id": session_id,
            "active": session_id in active_sessions,
            "queued": session_processors.get(session_id, asyncio.Queue()).qsize() if session_id in session_processors else 0,
            "has_queue": session_id in session_processors
        }
    
    return None


async def handle_completion_request(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle completion request (original logic preserved)."""
    
    prompt = data.get("prompt", "")
    model = data.get("model", "claude-cli/sonnet")
    session_id = data.get("session_id")
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("max_tokens", 4096)
    client_id = data.get("client_id")
    request_id = data.get("request_id", str(uuid.uuid4()))
    
    if not prompt:
        return {"error": "No prompt provided"}
    
    # Check for pending injections if session_id provided
    if session_id and event_emitter:
        prepend_injections = []
        append_injections = []
        before_prompt_injections = []
        after_prompt_injections = []
        
        # Pop all pending injections for this session
        while True:
            result = await event_emitter("async_state:pop", {
                "namespace": "injection",
                "key": session_id
            })
            
            if not result or not result.get("found"):
                break
                
            injection_data = result.get("data", {})
            position = injection_data.get("position", "prepend")
            content = injection_data.get("content", "")
            
            if position == "prepend":
                prepend_injections.append(content)
            elif position == "postscript":
                append_injections.append(content)
            elif position == "before_prompt":
                before_prompt_injections.append(content)
            elif position == "after_prompt":
                after_prompt_injections.append(content)
            else:  # Default to prepend for unknown positions
                prepend_injections.append(content)
        
        # Apply injections to prompt
        original_prompt = prompt
        parts = []
        
        # Add prepend injections
        if prepend_injections:
            parts.extend(prepend_injections)
            logger.info(f"Applied {len(prepend_injections)} prepend injections to session {session_id}")
        
        # Add before_prompt injections
        if before_prompt_injections:
            parts.extend(before_prompt_injections)
            logger.info(f"Applied {len(before_prompt_injections)} before_prompt injections to session {session_id}")
        
        # Add original prompt
        parts.append(original_prompt)
        
        # Add after_prompt injections
        if after_prompt_injections:
            parts.extend(after_prompt_injections)
            logger.info(f"Applied {len(after_prompt_injections)} after_prompt injections to session {session_id}")
        
        # Add postscript injections
        if append_injections:
            parts.extend(append_injections)
            logger.info(f"Applied {len(append_injections)} postscript injections to session {session_id}")
        
        # Join all parts with double newlines
        prompt = "\n\n".join(parts)
    
    start_time = time.time()
    
    try:
        # Prepare messages
        messages = data.get("messages", [])
        if not messages and prompt:
            messages = [{"role": "user", "content": prompt}]
        
        # Just pass model through - no mapping
        # Prepare litellm parameters
        completion_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Add session ID as metadata for claude-cli provider
        if session_id:
            completion_params["metadata"] = {"session_id": session_id}
        
        # Call LiteLLM
        response = await litellm.acompletion(**completion_params)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Extract response
        raw_response = {}
        
        if model.startswith("claude-cli/"):
            # Claude CLI returns JSON string in content
            content = response.choices[0].message.content
            if isinstance(content, str) and content.strip().startswith('{'):
                try:
                    raw_response = json.loads(content)
                except json.JSONDecodeError:
                    raw_response = {
                        "result": content,
                        "session_id": session_id,
                        "model": model
                    }
            else:
                raw_response = {
                    "result": content,
                    "session_id": session_id,
                    "model": model
                }
        else:
            # Other providers
            raw_response = response.model_dump() if hasattr(response, 'model_dump') else dict(response)
        
        # Create standardized response
        completion_response = create_completion_response(
            provider="claude-cli" if model.startswith("claude-cli/") else "unknown",
            raw_response=raw_response,
            request_id=request_id,
            client_id=client_id,
            duration_ms=duration_ms
        )
        
        # Save response to session file
        response_data = completion_response.to_dict()
        save_completion_response(response_data)
        
        # Extract actual session_id from response (may differ due to forking)
        actual_session_id = raw_response.get('session_id', session_id)
        response_data['session_id'] = actual_session_id
        
        return response_data
        
    except Exception as e:
        logger.error(f"Completion error: {e}", exc_info=True)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Return error in standardized format
        error_response = create_completion_response(
            provider="claude-cli" if model.startswith("claude-cli/") else "unknown",
            raw_response={
                "error": str(e),
                "error_type": type(e).__name__
            },
            request_id=request_id,
            client_id=client_id,
            duration_ms=duration_ms
        )
        
        result = error_response.to_dict()
        result["error"] = str(e)
        result["status"] = "error"
        
        save_completion_response(result)
        
        return result


async def handle_async_completion_smart(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Smart hybrid completion handling - event-driven + per-session fork prevention."""
    
    # Generate request ID if not provided
    request_id = data.get('request_id', str(uuid.uuid4()))
    data['request_id'] = request_id
    session_id = data.get('session_id')
    
    # Check if injection is requested
    injection_config = data.get("injection_config")
    if injection_config and injection_config.get('enabled'):
        # Store injection metadata with injection router
        request_id = queue_completion_with_injection(data)
        data['request_id'] = request_id
    
    # Smart routing based on session state
    if not session_id:
        # No session ID = no fork risk = immediate processing
        task_group = get_completion_task_group()
        task_group.start_soon(process_single_completion, data, context)
        logger.info(f"Processing sessionless completion {request_id} immediately")
        
        return {
            "request_id": request_id,
            "status": "processing",
            "reason": "no_session",
            "message": "Processing immediately - no fork risk"
        }
    
    elif session_id in active_sessions:
        # Session busy = queue to prevent fork
        if session_id not in session_processors:
            # Create per-session queue on demand
            session_processors[session_id] = asyncio.Queue()
            task_group = get_completion_task_group()
            task_group.start_soon(process_session_queue, session_id)
            logger.info(f"Created queue processor for session {session_id}")
        
        # Queue the request
        await session_processors[session_id].put(data)
        logger.info(f"Queued completion {request_id} for busy session {session_id}")
        
        return {
            "request_id": request_id,
            "status": "queued",
            "reason": "session_busy",
            "session_id": session_id,
            "message": "Queued to prevent conversation fork"
        }
    
    else:
        # Session free = immediate processing with lock
        task_group = get_completion_task_group()
        task_group.start_soon(process_completion_with_session_lock, data, context)
        logger.info(f"Processing completion {request_id} for free session {session_id}")
        
        return {
            "request_id": request_id,
            "status": "processing", 
            "session_id": session_id,
            "message": "Processing immediately"
        }


async def process_session_queue(session_id: str) -> None:
    """Process queued requests for a specific session - prevents forks."""
    
    logger.info(f"Starting session queue processor for {session_id}")
    queue = session_processors[session_id]
    
    try:
        while True:
            # Wait for next request for this session
            request_data = await queue.get()
            
            logger.info(f"Processing queued request for session {session_id}")
            
            # Process with session lock
            await process_completion_with_session_lock(request_data, {})
            
            # Mark task done
            queue.task_done()
            
    except asyncio.CancelledError:
        logger.info(f"Session queue processor for {session_id} cancelled")
        raise
    except Exception as e:
        logger.error(f"Session queue error for {session_id}: {e}", exc_info=True)
        # Continue processing queue
    finally:
        # Cleanup session queue when done
        if session_id in session_processors:
            del session_processors[session_id]
        logger.info(f"Session queue processor for {session_id} stopped")


async def process_completion_with_session_lock(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Process completion with session locking to prevent forks."""
    
    session_id = data.get('session_id')
    request_id = data.get('request_id', str(uuid.uuid4()))
    
    try:
        # Acquire session lock
        if session_id:
            active_sessions.add(session_id)
            logger.debug(f"Acquired session lock for {session_id}")
            
        # Process the completion
        await process_single_completion(data, context)
        
    finally:
        # Always release session lock
        if session_id:
            active_sessions.discard(session_id)
            logger.debug(f"Released session lock for {session_id}")


async def process_single_completion(data: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Process a single completion request - core logic."""
    
    request_id = data.get('request_id', str(uuid.uuid4()))
    
    logger.info(f"Processing completion request {request_id}")
    
    try:
        # Store as active
        active_completions[request_id] = {
            "data": data,
            "started_at": TimestampManager.timestamp_utc()
        }
        
        # Emit progress event
        if event_emitter and callable(event_emitter):
            await event_emitter("completion:progress", {
                "request_id": request_id,
                "status": "processing",
                "message": "Processing completion"
            }, {})
        
        # Process the completion
        result = await handle_completion_request(data, context)
        
        # Add request ID to result
        result["request_id"] = request_id
        
        # Emit result event (will trigger injection router)
        if event_emitter and callable(event_emitter):
            await event_emitter("completion:result", result, {})
        
        logger.info(f"Completed request {request_id}")
        
    except Exception as e:
        logger.error(f"Completion error for {request_id}: {e}", exc_info=True)
        # Emit error event
        if event_emitter and callable(event_emitter):
            await event_emitter("completion:error", {
                "request_id": request_id,
                "error": str(e)
            }, {})
    
    finally:
        # Clean up
        active_completions.pop(request_id, None)



@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event emitter."""
    global event_emitter
    event_emitter = context.get("emit_event")


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info(f"anyio smart hybrid completion service stopped - {len(active_completions)} active tasks, {len(session_processors)} session queues")
    
    return {
        "status": "completion_service_anyio_smart_hybrid_stopped",
        "active_tasks": len(active_completions),
        "session_queues": len(session_processors),
        "architecture": "anyio_smart_hybrid"
    }


# Module-level marker for plugin discovery
ksi_plugin = True