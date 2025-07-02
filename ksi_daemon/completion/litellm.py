#!/usr/bin/env python3
"""
LiteLLM Module - Event-Based Version

Handles completion requests using LiteLLM with claude_cli provider.
"""

import asyncio
import json
from ksi_common.logging import get_bound_logger
import time
import uuid
from typing import Dict, Any, Optional

# Import claude_cli_litellm_provider to ensure provider registration
from ksi_daemon.completion import claude_cli_litellm_provider
from ksi_daemon.event_system import event_handler, get_router
import litellm

# Suppress LiteLLM's console logging to maintain JSON format
import logging
litellm.suppress_debug_info = True
litellm.set_verbose = False
# Disable LiteLLM's internal logging to console
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("litellm").setLevel(logging.CRITICAL)

logger = get_bound_logger("litellm_provider", version="1.0.0")

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


# Event handlers for litellm provider
# Note: This module now only provides the completion backend
# completion_service.py handles completion:request events


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize litellm provider."""
    # Configure litellm
    litellm.drop_params = True  # Don't error on custom params
    litellm.suppress_debug_info = True
    
    logger.info("LiteLLM simple completion provider started")
    return {"status": "litellm_provider_ready"}


