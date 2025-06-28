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

import litellm

from ...plugin_utils import get_logger, plugin_metadata
from ksi_common import TimestampManager, create_completion_response, parse_completion_response
from ...config import config
from ...event_taxonomy import CLAUDE_EVENTS, format_claude_event

# Import new queue and injection systems
from .completion_queue import (
    enqueue_completion, 
    get_next_completion,
    mark_completion_done,
    get_queue_status,
    Priority
)
from ..injection.injection_router import queue_completion_with_injection
from ..injection.circuit_breakers import check_completion_allowed

# Import claude_cli_litellm_provider to ensure provider registration
import claude_cli_litellm_provider

# Plugin metadata
plugin_metadata("completion_service", version="3.0.0",
                description="Enhanced LLM completion service with queue and injection support")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("completion_service")
active_completions: Dict[str, Dict[str, Any]] = {}

# Event emitter reference (set during startup)
event_emitter = None


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
@hookimpl
def ksi_startup(config):
    """Initialize completion service on startup."""
    ensure_directories()
    logger.info("Completion service v3 started with queue and injection support")
    
    # Start queue processor task
    asyncio.create_task(process_completion_queue())
    
    return {"status": "completion_service_v3_ready"}


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle completion-related events."""
    
    if event_name == "completion:async":
        # Queue async completion with injection support
        # Create a coroutine wrapper for consistent async handling
        async def _handle_async():
            return await handle_async_completion_queued(data, context)
        return _handle_async()
    
    elif event_name == "completion:cancel":
        # Cancel an active completion
        request_id = data.get("request_id")
        if request_id in active_completions:
            # TODO: Implement proper cancellation with queue
            del active_completions[request_id]
            return {"status": "cancelled"}
        return {"status": "not_found"}
    
    elif event_name == "completion:status":
        # Get enhanced status including queue
        async def _get_status():
            queue_status = await get_queue_status()
            return {
                "active_count": len(active_completions),
                "active_requests": list(active_completions.keys()),
                "queue_status": queue_status
            }
        return _get_status()
    
    elif event_name == "completion:queue_status":
        # Detailed queue status - return coroutine
        return get_queue_status()
    
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
    
    start_time = time.time()
    
    try:
        # Prepare messages
        messages = data.get("messages", [])
        if not messages and prompt:
            messages = [{"role": "user", "content": prompt}]
        
        # Ensure model is prefixed for claude-cli provider
        if model in ["sonnet", "haiku", "opus"]:
            model = f"claude-cli/{model}"
        elif model.startswith("claude_cli/"):
            model = model.replace("claude_cli/", "claude-cli/")
        
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


async def handle_async_completion_queued(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async completion request with queue and injection support."""
    
    # Extract priority
    priority_str = data.get("priority", "normal")
    priority_map = {
        'critical': Priority.CRITICAL,
        'high': Priority.HIGH,
        'normal': Priority.NORMAL,
        'low': Priority.LOW,
        'background': Priority.BACKGROUND
    }
    priority = priority_map.get(priority_str.lower(), Priority.NORMAL)
    
    # Check if injection is requested
    injection_config = data.get("injection_config")
    if injection_config and injection_config.get('enabled'):
        # Store injection metadata
        request_id = queue_completion_with_injection(data)
        data['request_id'] = request_id
    
    # Queue the request
    queue_result = await enqueue_completion(data, priority_str)
    
    return queue_result


async def process_completion_queue():
    """Background task to process queued completions."""
    
    logger.info("Starting completion queue processor")
    
    while True:
        try:
            # Get next completion from queue
            next_request = await get_next_completion()
            
            if not next_request:
                # No requests ready, wait a bit
                await asyncio.sleep(0.1)
                continue
            
            request_id = next_request['request_id']
            request_data = next_request['data']
            
            logger.info(f"Processing queued completion {request_id}")
            
            # Store as active
            active_completions[request_id] = {
                "data": request_data,
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
            result = await handle_completion_request(request_data, {})
            
            # Add request ID to result
            result["request_id"] = request_id
            
            # Mark completion done in queue (handles lock release and fork detection)
            queue_complete_result = await mark_completion_done(request_id, result)
            
            # Handle fork if detected
            if queue_complete_result.get('fork_info'):
                fork_info = queue_complete_result['fork_info']
                logger.warning(f"Fork detected: {fork_info}")
                result['fork_detected'] = True
                result['fork_info'] = fork_info
            
            # Emit result event (will trigger injection router)
            if event_emitter and callable(event_emitter):
                await event_emitter("completion:result", result, {})
            
            # Clean up
            active_completions.pop(request_id, None)
            
        except Exception as e:
            logger.error(f"Queue processor error: {e}", exc_info=True)
            await asyncio.sleep(1)  # Back off on error



@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event emitter."""
    global event_emitter
    event_emitter = context.get("emit_event")


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info(f"Completion service v3 stopped - {len(active_completions)} active completions")
    
    # Get queue status synchronously (it's not actually async)
    queue_status = get_queue_status()
    
    return {
        "status": "completion_service_v3_stopped",
        "active_completions": len(active_completions),
        "queue_status": queue_status
    }


# Module-level marker for plugin discovery
ksi_plugin = True