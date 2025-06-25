#!/usr/bin/env python3
"""
Completion Service Plugin

Provides LLM completion functionality without complex inheritance.
Handles completion requests through events rather than direct method calls.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import pluggy

import litellm

from ...plugin_utils import get_logger, plugin_metadata
from ...timestamp_utils import TimestampManager
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
    # Legacy directories for agent profiles
    os.makedirs('agent_profiles', exist_ok=True)


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
        # Synchronous completion request
        return handle_completion_request(data, context)
    
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
    
    if not prompt:
        return {"error": "No prompt provided"}
    
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
        
        # Extract response
        content = response.choices[0].message.content
        
        # Get session ID from response if available
        response_session_id = session_id
        if hasattr(response, '_hidden_params') and 'session_id' in response._hidden_params:
            response_session_id = response._hidden_params['session_id']
        
        return {
            "status": "success",
            "response": content,
            "session_id": response_session_id,
            "model": model,
            "usage": response.usage.model_dump() if hasattr(response, 'usage') else None
        }
        
    except Exception as e:
        logger.error(f"Completion error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


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