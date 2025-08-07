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
from pathlib import Path

# Disable LiteLLM's HTTP request for model pricing on startup
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'true'

# Import CLI providers to ensure registration
from ksi_daemon.completion import claude_cli_litellm_provider
from ksi_daemon.completion import gemini_cli_litellm_provider
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common.service_lifecycle import service_startup, service_shutdown
from ksi_common.task_management import create_tracked_task
from ksi_common.sandbox_manager import SandboxConfig, SandboxMode
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


def append_to_conversation_index(conversation_id: str, response_id: str) -> None:
    """Append a response_id to the conversation index (append-only log).
    
    The conversation index is a simple newline-delimited file containing
    response_ids in chronological order. This allows fast reconstruction
    of conversation history without scanning directories.
    
    Args:
        conversation_id: The conversation identifier (typically agent_id)
        response_id: The response identifier to append
    """
    if not conversation_id or not response_id:
        return
    
    try:
        # Create conversations directory if needed
        config.conversation_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Append response_id to conversation index
        index_file = config.conversation_log_dir / f"{conversation_id}.jsonl"
        with open(index_file, 'a') as f:
            f.write(f"{response_id}\n")
        
        logger.debug(f"Appended {response_id} to conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to append to conversation index: {e}", exc_info=True)


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
    
    session_id = data.get("session_id")  # For claude-cli, this is the actual session
    request_id = data.get("request_id", str(uuid.uuid4()))
    agent_id = data.get("agent_id")
    
    # For stateless providers, determine conversation_id from agent_id
    conversation_id = None
    if agent_id and not model.startswith("claude-cli/"):
        # Use agent_id as conversation_id for simplicity
        conversation_id = agent_id
    
    logger.info(
        f"Starting LiteLLM completion: model={model}, session_id={session_id}",
        data_keys=list(data.keys()),
        has_session_id="session_id" in data
    )
    
    try:
        # Convert prompt to messages if needed
        if "prompt" in data and "messages" not in data:
            logger.debug(f"Converting prompt to messages for agent {agent_id}")
            data["messages"] = [{"role": "user", "content": data.pop("prompt")}]
        elif "prompt" in data and "messages" in data:
            logger.warning(f"Both prompt and messages present for agent {agent_id}, using messages")
        
        # Debug: log the messages being sent to litellm
        if "messages" in data:
            logger.info(f"Sending {len(data['messages'])} messages to litellm for agent {agent_id}",
                       first_msg=data["messages"][0] if data["messages"] else None,
                       last_msg=data["messages"][-1] if data["messages"] else None,
                       has_prompt="prompt" in data)
        
        # Handle sandbox directory for CLI providers
        if model.startswith(("claude-cli/", "gemini-cli/")):
            extra_body = data.get("extra_body", {})
            ksi_params = extra_body.get("ksi", {})
            
            # Only handle sandbox if not already specified
            if "sandbox_dir" not in ksi_params and getattr(config, "sandbox_enabled", True):
                # Use the shared sandbox manager instance
                from ksi_common.sandbox_manager import sandbox_manager as shared_sandbox_manager
                global sandbox_manager
                sandbox_manager = shared_sandbox_manager
                
                sandbox_config = SandboxConfig(
                    mode=SandboxMode.ISOLATED
                    # Both agent and temporary sandboxes are isolated
                )
                
                # Check for sandbox_uuid from agent
                sandbox_uuid = ksi_params.get("sandbox_uuid")
                
                if sandbox_uuid:
                    # Agent sandbox - get existing sandbox created at spawn time
                    sandbox = sandbox_manager.get_sandbox(sandbox_uuid)
                    
                    if not sandbox:
                        # This shouldn't happen - agent sandboxes are created at spawn
                        logger.error(
                            "Agent sandbox not found - this indicates a bug in agent spawn",
                            agent_id=agent_id,
                            sandbox_uuid=sandbox_uuid
                        )
                        # Create it as a fallback to avoid breaking the request
                        sandbox = sandbox_manager.create_sandbox(sandbox_uuid, sandbox_config)
                    else:
                        logger.debug(f"Using existing agent sandbox", 
                                   agent_id=agent_id, 
                                   sandbox_uuid=sandbox_uuid)
                    
                    sandbox_dir = str(sandbox.path.absolute())
                elif agent_id:
                    # This is an error - agents should always have sandbox_uuid
                    raise ValueError(f"Agent {agent_id} missing required sandbox_uuid - this indicates a bug in agent creation")
                else:
                    # Temporary sandbox for non-agent requests
                    sandbox_id = f"temp/{request_id}"
                    logger.debug(f"Creating temporary sandbox for request {request_id}")
                    
                    # Create temporary sandbox
                    sandbox = sandbox_manager.create_sandbox(sandbox_id, sandbox_config)
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
                    
                    create_tracked_task("litellm_provider", mock_cleanup(), task_name="sandbox_cleanup")
                
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
        
        # Don't automatically add response_format for ollama - it causes double JSON parsing
        # The issue is that response_format makes ollama return JSON, but then litellm's
        # transformation.py tries to json.loads() it again causing "Expecting value" errors
        # Instead, rely on prompt engineering in the agent components to request JSON output
        # Reference: https://github.com/BerriAI/litellm/issues/7355
        
        # Generate response ID for non-CLI providers
        # CRITICAL: For claude-cli, session_id IS the response_id (server manages conversation)
        # For stateless providers, we generate a response_id per request
        response_id = None
        if not model.startswith(("claude-cli/", "gemini-cli/")):
            # Generate response_id with model info for better debugging/analysis
            # Convert model name to filesystem-safe format
            model_slug = model.replace("/", "-").replace(":", "-").replace(".", "-")
            response_id = f"{model_slug}-{uuid.uuid4().hex[:12]}"
            # Examples:
            # ollama-phi4-mini-abc123def456
            # openai-gpt-4-1-789xyz123456
            
            # Store in extra_body for downstream use
            if "extra_body" not in data:
                data["extra_body"] = {}
            if "ksi" not in data["extra_body"]:
                data["extra_body"]["ksi"] = {}
            data["extra_body"]["ksi"]["response_id"] = response_id
            data["extra_body"]["ksi"]["conversation_id"] = conversation_id
            logger.debug(f"Generated response_id for {model}", response_id=response_id, conversation_id=conversation_id)
        
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
            # CRITICAL: claude-cli calls it 'session_id' but we treat it as response_id
            raw_response = response._claude_metadata
            # Ensure we have response_id in metadata for consistency
            if "metadata" not in raw_response:
                raw_response["metadata"] = {}
            raw_response["metadata"]["response_id"] = raw_response.get("session_id")
            # Note: session_id field preserved for backward compatibility
        elif provider == "gemini-cli" and hasattr(response, '_gemini_metadata'):
            # For gemini-cli, return the metadata directly - it has everything we need
            raw_response = response._gemini_metadata
            # Gemini-cli also might have session_id that's really a response_id
            if "metadata" not in raw_response:
                raw_response["metadata"] = {}
            raw_response["metadata"]["response_id"] = raw_response.get("session_id")
        else:
            # For other providers (ollama, openai, etc.), build comprehensive response
            # Get the response_id and conversation_id from extra_body
            ksi_data = data.get("extra_body", {}).get("ksi", {})
            response_id_to_use = ksi_data.get("response_id")
            conversation_id_to_use = ksi_data.get("conversation_id")
            
            raw_response = {
                "result": "",  # The actual response text
                "model": getattr(response, 'model', model),
                "usage": None,
                "session_id": response_id_to_use,  # CRITICAL: session_id field = response_id for compatibility
                "metadata": {
                    "provider": provider,
                    "timestamp": time.time(),
                    "response_id": response_id_to_use,  # Explicit response_id in metadata
                    "conversation_id": conversation_id_to_use,  # Track conversation
                    "generated_response_id": True,  # Flag to indicate this is KSI-generated
                    "request_id": data.get("request_id", request_id),
                    "agent_id": agent_id
                }
            }
            
            # Extract response text
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    raw_response["result"] = choice.message.content
            
            # Extract usage if available (includes thinking tokens for models that support it)
            if hasattr(response, 'usage'):
                usage_data = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0)
                }
                
                # Check for thinking tokens (o1, o3 models)
                if hasattr(response.usage, 'prompt_tokens_details'):
                    details = response.usage.prompt_tokens_details
                    if hasattr(details, 'cached_tokens'):
                        usage_data["cached_tokens"] = details.cached_tokens
                
                if hasattr(response.usage, 'completion_tokens_details'):
                    details = response.usage.completion_tokens_details
                    if hasattr(details, 'reasoning_tokens'):
                        usage_data["reasoning_tokens"] = details.reasoning_tokens
                
                raw_response["usage"] = usage_data
            
            # Extract additional metadata from response
            if hasattr(response, 'id'):
                raw_response["metadata"]["response_id"] = response.id
            if hasattr(response, 'created'):
                raw_response["metadata"]["created"] = response.created
            if hasattr(response, 'system_fingerprint'):
                raw_response["metadata"]["system_fingerprint"] = response.system_fingerprint
        
        # Append to conversation index for stateless providers
        if provider == "litellm" and conversation_id and response_id:
            append_to_conversation_index(conversation_id, response_id)
        
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


@service_startup("litellm_provider", load_transformers=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize litellm provider."""
    # Configure litellm
    litellm.drop_params = True  # Don't error on custom params
    litellm.suppress_debug_info = True
    
    logger.info("LiteLLM simple completion provider started")
    return {"status": "litellm_provider_ready"}


@service_shutdown("litellm_provider")
async def handle_shutdown(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up litellm resources on shutdown."""
    logger.info("LiteLLM provider shutting down")
    shutdown_claude_provider()


