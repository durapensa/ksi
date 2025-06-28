#!/usr/bin/env python3
"""
Simple LiteLLM Completion Plugin

Handles completion requests using LiteLLM with claude_cli provider.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
import pluggy

# Import claude_cli_litellm_provider to ensure provider registration
from . import claude_cli_litellm_provider
import litellm

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MODEL = "claude-cli/sonnet"  # Use the correct provider name
COMPLETION_TIMEOUT = 900.0  # 15 minutes - reasonable for Claude

# Module state
active_completions = {}


async def handle_completion_async(prompt: str, model: str = None, 
                          session_id: Optional[str] = None,
                          request_id: Optional[str] = None) -> Dict[str, Any]:
    """Handle a completion request using LiteLLM asynchronously."""
    model = model or DEFAULT_MODEL
    request_id = request_id or str(uuid.uuid4())
    
    # Track active completion
    active_completions[request_id] = {
        "status": "running",
        "started_at": time.time()
    }
    
    try:
        # Prepare messages
        messages = [{"role": "user", "content": prompt}]
        
        # Prepare kwargs for LiteLLM
        kwargs = {
            "model": model,
            "messages": messages,
            "timeout": COMPLETION_TIMEOUT
        }
        
        # Add session_id if provided
        if session_id:
            kwargs["session_id"] = session_id
        
        logger.info(f"Starting LiteLLM completion: model={model}, session_id={session_id}")
        
        # Call litellm asynchronously
        response = await litellm.acompletion(**kwargs)
        
        # Extract response
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
            
            # If content looks like JSON from Claude CLI, parse it
            if isinstance(content, str) and content.strip().startswith('{'):
                try:
                    parsed = json.loads(content)
                    if 'result' in parsed:
                        content = parsed['result']
                    # Also try to get session_id from parsed response
                    if 'session_id' in parsed and not session_id:
                        session_id = parsed['session_id']
                except json.JSONDecodeError:
                    pass  # Keep original content
        else:
            content = str(response)
        
        # Get session_id from response if available
        response_session_id = None
        if hasattr(response, '_hidden_params'):
            response_session_id = response._hidden_params.get('session_id', session_id)
        
        result = {
            "status": "success",
            "response": content,
            "session_id": response_session_id or session_id or str(uuid.uuid4()),
            "model": model,
            "request_id": request_id
        }
        
        logger.info(f"Completion successful: {len(content)} chars")
        return result
        
    except Exception as e:
        logger.error(f"Completion error: {e}", exc_info=True)
        return {
            "status": "error", 
            "error": str(e),
            "request_id": request_id
        }
    finally:
        # Clean up tracking
        active_completions.pop(request_id, None)


@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle completion events."""
    # Disabled - completion_service.py handles completion:request
    # This plugin now only provides the completion backend
    return None
    
    # Extract parameters
    prompt = data.get("prompt", "")
    model = data.get("model", DEFAULT_MODEL)
    session_id = data.get("session_id")
    request_id = data.get("request_id", str(uuid.uuid4()))
    
    if not prompt:
        return {
            "status": "error",
            "error": "No prompt provided",
            "request_id": request_id
        }
    
    # Ensure model is prefixed for claude-cli provider
    if model in ["sonnet", "haiku", "opus"]:
        model = f"claude-cli/{model}"
    elif not model.startswith("claude-cli/"):
        # Replace claude_cli with claude-cli if present
        if model.startswith("claude_cli/"):
            model = model.replace("claude_cli/", "claude-cli/")
        else:
            model = f"claude-cli/{model}"
    
    # Create and return a task if we're in an event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Create task and return it - daemon will handle awaiting
        task = asyncio.create_task(
            handle_completion_async(prompt, model, session_id, request_id)
        )
        return task
    else:
        # Not in event loop - shouldn't happen in daemon context
        logger.error("Not in event loop - this shouldn't happen")
        return {
            "status": "error",
            "error": "Not in event loop",
            "request_id": request_id
        }


@hookimpl  
def ksi_startup(config):
    """Initialize plugin."""
    # Configure litellm
    litellm.drop_params = True  # Don't error on custom params
    litellm.suppress_debug_info = True
    
    logger.info("LiteLLM simple completion plugin started")
    return {"plugin.litellm_simple": {"loaded": True}}


# Module-level marker for plugin discovery
ksi_plugin = True