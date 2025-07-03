#!/usr/bin/env python3
"""
LiteLLM Module - Event-Based Version

Handles completion requests using LiteLLM with claude_cli provider.
"""

import asyncio
import json
import os
from ksi_common.logging import get_bound_logger
import time
import uuid
from typing import Dict, Any, Optional, Tuple

# Disable LiteLLM's HTTP request for model pricing on startup
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'true'

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


async def handle_litellm_completion(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Handle a completion request using LiteLLM.
    
    Args:
        data: The completion request data (with all LiteLLM parameters)
        
    Returns:
        Tuple of (provider, raw_response) where raw_response is JSON-serializable
    """
    start_time = time.time()
    
    # Extract key parameters for logging
    model = data.get("model", DEFAULT_MODEL)
    session_id = data.get("session_id")
    request_id = data.get("request_id", str(uuid.uuid4()))
    
    logger.info(f"Starting LiteLLM completion: model={model}, session_id={session_id}")
    
    try:
        # Convert prompt to messages if needed
        if "prompt" in data and "messages" not in data:
            data["messages"] = [{"role": "user", "content": data.pop("prompt")}]
        
        # Call litellm asynchronously
        response = await litellm.acompletion(**data)
        
        # Determine provider
        provider = "claude-cli" if model.startswith("claude-cli/") else "litellm"
        
        # Extract appropriate response data based on provider
        if provider == "claude-cli" and hasattr(response, '_claude_metadata'):
            # For claude-cli, return the metadata directly - it has everything we need
            raw_response = response._claude_metadata
        else:
            # For other providers, extract only what we need
            raw_response = {
                "result": "",  # The actual response text
                "model": getattr(response, 'model', model),
                "usage": None
            }
            
            # Extract response text
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    raw_response["result"] = choice.message.content
            
            # Extract usage if available
            if hasattr(response, 'usage'):
                raw_response["usage"] = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0)
                }
        
        duration = time.time() - start_time
        logger.info(f"LiteLLM completion successful: provider={provider}, duration={duration:.2f}s")
        
        return provider, raw_response
        
    except Exception as e:
        logger.error(f"LiteLLM completion error: {e}", exc_info=True)
        raise


# Event handlers for litellm provider
# Note: This module now only provides the completion backend
# completion_service.py handles completion:request events


def shutdown_claude_provider():
    """Shutdown the Claude CLI provider if it exists."""
    try:
        # Access the provider instance from litellm's custom_provider_map
        for provider_config in litellm.custom_provider_map:
            if provider_config.get("provider") == "claude-cli":
                handler = provider_config.get("custom_handler")
                if handler and hasattr(handler, "shutdown"):
                    logger.info("Shutting down Claude CLI provider")
                    handler.shutdown()
                break
    except Exception as e:
        logger.error(f"Error shutting down Claude CLI provider: {e}")


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize litellm provider."""
    # Configure litellm
    litellm.drop_params = True  # Don't error on custom params
    litellm.suppress_debug_info = True
    
    logger.info("LiteLLM simple completion provider started")
    return {"status": "litellm_provider_ready"}


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up litellm resources on shutdown."""
    logger.info("LiteLLM provider shutting down")
    shutdown_claude_provider()


