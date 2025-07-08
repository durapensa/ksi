#!/usr/bin/env python3
"""
Completion utilities for evaluation modules.

Provides helpers for working with async completions.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional

from ksi_daemon.event_system import emit_event
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("evaluation.completion_utils")


async def wait_for_completion(request_id: str) -> Dict[str, Any]:
    """
    Wait for an async completion to finish using event system.
    
    This uses the event system's wait_for_event capability instead of polling,
    eliminating the event cascade from completion:status polling.
    
    The completion service is responsible for handling timeouts and will emit
    completion:result with status="timeout" if needed.
    
    Args:
        request_id: The completion request ID
        
    Returns:
        Dict containing completion result or error
    """
    # Get event router for wait_for_event
    from ksi_daemon.event_system import get_router
    router = get_router()
    
    # Wait for completion:result event with matching request_id
    logger.debug(f"Waiting for completion:result for request {request_id}")
    
    result = await router.wait_for_event(
        "completion:result",
        lambda data: data.get("request_id") == request_id
    )
    
    # Got completion result - check status
    session_id = result.get("session_id")
    status = result.get("status", "completed")
    
    if status == "error":
        return {
            "status": "error",
            "error": result.get("error", "Unknown error"),
            "request_id": request_id
        }
    elif status == "timeout":
        return {
            "status": "timeout",
            "error": result.get("error", "Completion timed out"),
            "request_id": request_id
        }
    elif session_id:
        # Read the response file
        response_text = await read_completion_response(session_id)
        return {
            "status": "completed",
            "session_id": session_id,
            "response": response_text,
            "request_id": request_id,
            "provider": result.get("provider"),
            "model": result.get("model")
        }
    else:
        return {
            "status": "error",
            "error": "Completed but no session_id",
            "request_id": request_id
        }


async def read_completion_response(session_id: str) -> str:
    """
    Read completion response from file.
    
    Args:
        session_id: The session ID of the completion
        
    Returns:
        The response text
    """
    response_file = config.response_log_dir / f"{session_id}.jsonl"
    
    if not response_file.exists():
        logger.error(f"Response file not found: {response_file}")
        return ""
    
    try:
        # Read all lines and find the final response
        lines = response_file.read_text().strip().split('\n')
        
        # Look for completion events
        response_text = ""
        for line in lines:
            try:
                data = json.loads(line)
                event = data.get("event", {})
                
                # Check for different response formats
                if event.get("type") == "completion":
                    response_text = event.get("data", {}).get("response", "")
                elif event.get("type") == "agent:message":
                    # Handle agent message format
                    content = event.get("data", {}).get("content", "")
                    if isinstance(content, list):
                        # Extract text from content blocks
                        text_parts = []
                        for block in content:
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        response_text = "\n".join(text_parts)
                    else:
                        response_text = str(content)
                elif "response" in data:
                    # Direct response format
                    response_text = data.get("response", "")
                    
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in response file: {line}")
                continue
        
        return response_text
        
    except Exception as e:
        logger.error(f"Error reading response file: {e}")
        return ""


async def send_completion_and_wait(prompt: str,
                                 model: str = None,
                                 agent_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send a completion request and wait for the result.
    
    Combines completion:async and wait_for_completion into one call.
    Timeouts are handled by the completion service itself.
    
    Args:
        prompt: The prompt text
        model: Model to use (defaults to config)
        agent_config: Agent configuration
        
    Returns:
        Dict with status, response, and metadata
    """
    # Prepare request
    request_data = {
        "prompt": prompt,
        "metadata": {
            "source": "evaluation"
        }
    }
    
    if model:
        request_data["model"] = model
    if agent_config:
        request_data["agent_config"] = agent_config
    
    # Send completion request
    completion_responses = await emit_event("completion:async", request_data)
    
    if not completion_responses:
        return {
            "status": "error",
            "error": "No response from completion:async"
        }
    
    completion_response = completion_responses[0]
    request_id = completion_response.get("request_id")
    
    if not request_id:
        return {
            "status": "error",
            "error": "No request_id in completion response",
            "response_data": completion_response
        }
    
    # Wait for completion
    return await wait_for_completion(request_id)