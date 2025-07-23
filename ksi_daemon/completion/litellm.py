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

# Import CLI providers to ensure registration
from ksi_daemon.completion import claude_cli_litellm_provider
from ksi_daemon.completion import gemini_cli_litellm_provider
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common.sandbox_manager import SandboxManager, SandboxConfig, SandboxMode
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
COMPLETION_TIMEOUT = 900.0  # 15 minutes - reasonable for Claude

# Module state
active_completions = {}
sandbox_manager = None  # Initialized on first use


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
    model = data.get("model")
    if not model:
        raise ValueError("No model specified")
    
    session_id = data.get("session_id")
    request_id = data.get("request_id", str(uuid.uuid4()))
    agent_id = data.get("agent_id")
    
    logger.info(
        f"Starting LiteLLM completion: model={model}, session_id={session_id}",
        data_keys=list(data.keys()),
        has_session_id="session_id" in data
    )
    
    try:
        # Convert prompt to messages if needed
        if "prompt" in data and "messages" not in data:
            data["messages"] = [{"role": "user", "content": data.pop("prompt")}]
        
        # Handle sandbox directory for CLI providers
        if model.startswith(("claude-cli/", "gemini-cli/")):
            extra_body = data.get("extra_body", {})
            ksi_params = extra_body.get("ksi", {})
            
            # Only handle sandbox if not already specified
            if "sandbox_dir" not in ksi_params and getattr(config, "sandbox_enabled", True):
                # Create sandbox - use sandbox_uuid for agents, request_id for temporary
                global sandbox_manager
                if not sandbox_manager:
                    sandbox_manager = SandboxManager(config.sandbox_dir)
                
                sandbox_config = SandboxConfig(
                    mode=SandboxMode.ISOLATED
                    # Both agent and temporary sandboxes are isolated
                )
                
                # Check for sandbox_uuid from agent
                sandbox_uuid = ksi_params.get("sandbox_uuid")
                
                if sandbox_uuid:
                    # Agent sandbox - use UUID for consistent location
                    sandbox_id = sandbox_uuid  # Just the UUID, sandbox_manager will add the agents/ prefix
                    logger.debug(f"Using agent sandbox UUID {sandbox_uuid} for agent {agent_id}")
                elif agent_id:
                    # This is an error - agents should always have sandbox_uuid
                    raise ValueError(f"Agent {agent_id} missing required sandbox_uuid - this indicates a bug in agent creation")
                else:
                    # Temporary sandbox for non-agent requests
                    sandbox_id = f"temp/{request_id}"
                    logger.debug(f"Creating temporary sandbox for request {request_id}")
                
                # Check if sandbox already exists (for agents with persistent sandboxes)
                sandbox = sandbox_manager.get_sandbox(sandbox_id)
                if not sandbox:
                    sandbox = sandbox_manager.create_sandbox(sandbox_id, sandbox_config)
                else:
                    logger.debug(f"Using existing sandbox for {sandbox_id}")
                sandbox_dir = str(sandbox.path.absolute())
                
                if agent_id:
                    logger.info(f"Using agent sandbox", agent_id=agent_id, sandbox_dir=sandbox_dir)
                else:
                    logger.info(f"Created temporary sandbox", request_id=request_id, sandbox_dir=sandbox_dir)
                    
                    # Schedule cleanup only for temporary sandboxes
                    async def mock_cleanup():
                        await asyncio.sleep(getattr(config, "sandbox_temp_ttl", 3600))
                        logger.info(f"[MOCK] Would clean up temporary sandbox", 
                                   request_id=request_id, sandbox_dir=sandbox_dir)
                        # In production: sandbox_manager.remove_sandbox(sandbox_id)
                    
                    asyncio.create_task(mock_cleanup())
                
                # Add sandbox_dir to extra_body
                if "extra_body" not in data:
                    data["extra_body"] = {}
                if "ksi" not in data["extra_body"]:
                    data["extra_body"]["ksi"] = {}
                data["extra_body"]["ksi"]["sandbox_dir"] = sandbox_dir
                logger.debug(f"Added sandbox_dir to extra_body", sandbox_dir=sandbox_dir)
        
        # Ensure session_id is passed to custom providers via extra_body
        if "session_id" in data and data["session_id"]:
            if "extra_body" not in data:
                data["extra_body"] = {}
            if "ksi" not in data["extra_body"]:
                data["extra_body"]["ksi"] = {}
            data["extra_body"]["ksi"]["session_id"] = data["session_id"]
            logger.info(f"Added session_id to extra_body for custom provider", 
                       session_id=data["session_id"],
                       agent_id=agent_id,
                       ksi_keys=list(data.get("extra_body", {}).get("ksi", {}).keys()))
        else:
            logger.warning(f"No session_id in data to pass to provider",
                          agent_id=agent_id,
                          has_session_id="session_id" in data,
                          session_id_value=data.get("session_id"))
        
        # Call litellm asynchronously
        response = await litellm.acompletion(**data)
        
        # Determine provider
        if model.startswith("claude-cli/"):
            provider = "claude-cli"
        elif model.startswith("gemini-cli/"):
            provider = "gemini-cli"
        else:
            provider = "litellm"
        
        # Extract appropriate response data based on provider
        if provider == "claude-cli" and hasattr(response, '_claude_metadata'):
            # For claude-cli, return the metadata directly - it has everything we need
            raw_response = response._claude_metadata
        elif provider == "gemini-cli" and hasattr(response, '_gemini_metadata'):
            # For gemini-cli, return the metadata directly - it has everything we need
            raw_response = response._gemini_metadata
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
        # Add provider context to errors based on model routing
        if model and model.startswith("claude-cli/"):
            # Enhance the error with provider context for KSI error handling
            if hasattr(e, '__dict__'):
                e.llm_provider = "claude-cli"
            else:
                # For exceptions that don't allow attribute setting, wrap them
                logger.error(f"LiteLLM completion error (claude-cli provider): {e}", exc_info=True)
                raise RuntimeError(f"Claude CLI provider error: {e}") from e
        
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


