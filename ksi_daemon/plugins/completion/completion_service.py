#!/usr/bin/env python3
"""
Completion Service Plugin

Provides LLM completion functionality without complex inheritance.
Handles completion requests through events rather than direct method calls.
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

# Import claude_cli_litellm_provider to ensure provider registration
import claude_cli_litellm_provider

# Plugin metadata
plugin_metadata("completion_service", version="2.0.0",
                description="Simplified LLM completion service")

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
    # Agent profiles now managed in var/agent_profiles via config


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
    logger.info("Completion service started")
    return {"status": "completion_service_ready"}


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle completion-related events."""
    
    if event_name == "completion:request":
        # Create async task for completion request
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Return the coroutine for the daemon to await
            return handle_completion_request(data, context)
        else:
            # Fallback - shouldn't happen in daemon context
            return {"error": "No event loop available"}
    
    elif event_name == "completion:async":
        # Asynchronous completion request
        request_id = handle_async_completion(data, context)
        return {"request_id": request_id, "status": "processing"}
    
    elif event_name == "completion:cancel":
        # Cancel an active completion
        request_id = data.get("request_id")
        if request_id in active_completions:
            # TODO: Implement cancellation logic
            del active_completions[request_id]
            return {"status": "cancelled"}
        return {"status": "not_found"}
    
    elif event_name == "completion:status":
        # Get status of active completions
        return {
            "active_count": len(active_completions),
            "active_requests": list(active_completions.keys())
        }
    
    return None


async def handle_completion_request(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle synchronous completion request."""
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
        
        # Extract response - Claude CLI returns JSON, other providers return structured response
        raw_response = {}
        
        if model.startswith("claude-cli/"):
            # Claude CLI returns JSON string in content
            content = response.choices[0].message.content
            if isinstance(content, str) and content.strip().startswith('{'):
                try:
                    raw_response = json.loads(content)
                except json.JSONDecodeError:
                    # If JSON parsing fails, treat as plain text
                    raw_response = {
                        "result": content,
                        "session_id": session_id,
                        "model": model
                    }
            else:
                # Plain text response from Claude CLI
                raw_response = {
                    "result": content,
                    "session_id": session_id,
                    "model": model
                }
        else:
            # Other providers (OpenAI, etc.) - preserve their response format
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
        
        # Add error flag for easier detection
        result = error_response.to_dict()
        result["error"] = str(e)
        result["status"] = "error"
        
        # Save error response to session file if possible
        save_completion_response(result)
        
        return result


def handle_async_completion(data: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Handle asynchronous completion request."""
    request_id = data.get("request_id") or f"req_{uuid.uuid4().hex[:8]}"
    
    # Store request
    active_completions[request_id] = {
        "data": data,
        "context": context,
        "started_at": TimestampManager.format_for_logging()
    }
    
    # Start async processing
    asyncio.create_task(process_async_completion(request_id, data, context))
    
    return request_id


async def process_async_completion(request_id: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Process async completion in background."""
    try:
        # Emit progress event
        if event_emitter:
            await event_emitter("completion:progress", {
                "request_id": request_id,
                "status": "processing",
                "message": "Starting completion"
            })
        
        # Process completion
        result = await handle_completion_request(data, context)
        
        # Add request ID to result
        result["request_id"] = request_id
        
        # Emit result event
        if event_emitter:
            await event_emitter("completion:result", result)
        
    except Exception as e:
        logger.error(f"Async completion error: {e}", exc_info=True)
        
        # Emit error event
        if event_emitter:
            await event_emitter("completion:result", {
                "request_id": request_id,
                "status": "error",
                "error": str(e)
            })
    
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
    logger.info(f"Completion service stopped - {len(active_completions)} active completions")
    
    return {
        "status": "completion_service_stopped",
        "active_completions": len(active_completions)
    }


# Module-level marker for plugin discovery
ksi_plugin = True