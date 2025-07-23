#!/usr/bin/env python3
"""
Standardized Completion Response Format and Provider Helpers

This module defines the provider-agnostic format for storing completion responses
and provides extraction helpers for different LLM providers.

Standard format:
{
  "ksi": {
    "provider": "claude-cli",
    "request_id": "req_123", 
    "client_id": "chat_001",
    "timestamp": "2025-06-26T18:30:00Z", 
    "duration_ms": 5000
  },
  "response": { /* untouched provider response */ }
}
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from .timestamps import timestamp_utc


def create_standardized_response(provider: str, raw_response: Dict[str, Any], 
                                request_id: Optional[str] = None, client_id: Optional[str] = None,
                                duration_ms: Optional[int] = None, agent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a standardized completion response dictionary.
    
    Args:
        provider: Provider name (e.g., "claude-cli", "openai", "anthropic-api")
        raw_response: Untouched response from the provider
        request_id: KSI request identifier
        client_id: KSI client identifier  
        duration_ms: Request duration in milliseconds
        agent_id: ID of the agent that spawned this completion
        
    Returns:
        Standardized response dictionary
    """
    result = {
        "ksi": {
            "provider": provider,
            "request_id": request_id or str(uuid.uuid4()),
            "timestamp": timestamp_utc(),
            "duration_ms": duration_ms
        },
        "response": raw_response
    }
    
    # Add client_id if provided
    if client_id:
        result["ksi"]["client_id"] = client_id
    
    # Add agent_id if provided
    if agent_id:
        result["ksi"]["agent_id"] = agent_id
    
    return result


# Helper functions to extract data from standardized response
def _normalize_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize input to standardized response format.
    
    Handles both:
    - Standardized format: {"ksi": {...}, "response": {...}}
    - Completion:result event format: {"result": {"ksi": {...}, "response": {...}}}
    
    Returns:
        Standardized response format
    """
    # Handle completion:result event format
    if "result" in response and isinstance(response["result"], dict) and "ksi" in response["result"]:
        return response["result"]
    # Already in standardized format
    return response


def get_provider(response: Dict[str, Any]) -> str:
    """Get the provider name from standardized response or completion:result event."""
    normalized = _normalize_response(response)
    return normalized["ksi"]["provider"]


def get_raw_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Get the untouched provider response."""
    return response["response"]


def get_request_id(response: Dict[str, Any]) -> str:
    """Get the KSI request ID."""
    return response["ksi"]["request_id"]


def get_timestamp(response: Dict[str, Any]) -> str:
    """Get the ISO 8601 UTC timestamp."""
    return response["ksi"]["timestamp"]


def get_duration_ms(response: Dict[str, Any]) -> Optional[int]:
    """Get request duration in milliseconds."""
    return response["ksi"].get("duration_ms")


def get_client_id(response: Dict[str, Any]) -> Optional[str]:
    """Get the client ID if available."""
    return response["ksi"].get("client_id")


def get_agent_id(response: Dict[str, Any]) -> Optional[str]:
    """Get the agent ID if available."""
    normalized = _normalize_response(response)
    return normalized["ksi"].get("agent_id")


# Provider-agnostic extraction functions
def get_response_text(response: Dict[str, Any]) -> str:
    """Extract response text using provider-specific logic."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    return extract_text(provider, raw_response)


def get_response_session_id(response: Dict[str, Any]) -> Optional[str]:
    """Extract session ID using provider-specific logic."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    return extract_session_id(provider, raw_response)


def get_response_usage(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract usage statistics using provider-specific logic."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    return extract_usage(provider, raw_response)


def get_response_cost(response: Dict[str, Any]) -> Optional[float]:
    """Extract cost information using provider-specific logic."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    return extract_cost(provider, raw_response)


def get_response_model(response: Dict[str, Any]) -> Optional[str]:
    """Extract model name using provider-specific logic."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    return extract_model(provider, raw_response)


def is_error_during_execution(response: Dict[str, Any]) -> bool:
    """Check if response indicates error_during_execution."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    
    if provider == "claude-cli":
        return raw_response.get("subtype") == "error_during_execution"
    
    # Other providers don't have this specific error type
    return False


def get_response_error_info(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract error information from response if present."""
    provider = get_provider(response)
    raw_response = get_raw_response(response)
    
    if provider == "claude-cli":
        if raw_response.get("subtype") == "error_during_execution":
            return {
                "type": "error_during_execution",
                "is_error": raw_response.get("is_error", False),
                "message": "Claude encountered an error during execution but did not provide details"
            }
        elif raw_response.get("is_error", False):
            return {
                "type": "error",
                "is_error": True,
                "message": raw_response.get("error", "Unknown error")
            }
    
    return None


def extract_text(provider: str, response: Dict[str, Any]) -> str:
    """Extract response text from provider response."""
    if provider == "claude-cli":
        # Handle error_during_execution subtype which doesn't have a result field
        if response.get("subtype") == "error_during_execution":
            # Return empty string for error_during_execution
            # The actual error should be handled by checking is_error or subtype
            return ""
        return response.get("result", "")
    
    elif provider == "openai":
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
    
    elif provider == "anthropic-api":
        content = response.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return ""
    
    else:
        # Fallback: try common field names
        return (response.get("result") or 
               response.get("text") or 
               response.get("content") or 
               str(response))


def extract_session_id(provider: str, response: Union[Dict[str, Any], Any]) -> Optional[str]:
    """Extract session ID from provider response."""
    if provider == "claude-cli":
        # Claude CLI always returns session_id in its JSON response
        if isinstance(response, dict):
            return response.get("session_id")
        return None
    
    elif provider == "litellm":
        # LiteLLM response object should have session_id as attribute (snake_case)
        if hasattr(response, "session_id"):
            return response.session_id
        # Check if it's a dict-like response
        if isinstance(response, dict):
            return response.get("session_id")
        return None
    
    elif provider in ["openai", "anthropic-api"]:
        # These providers typically don't have built-in session tracking
        return None
    
    else:
        # Fallback: try standard snake_case field
        if isinstance(response, dict):
            return response.get("session_id")
        return None


def extract_usage(provider: str, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract token usage statistics from provider response."""
    if provider == "claude-cli":
        return response.get("usage")
    
    elif provider == "openai":
        return response.get("usage")
    
    elif provider == "anthropic-api":
        return response.get("usage")
    
    else:
        # Fallback: try common field names
        return response.get("usage")


def extract_cost(provider: str, response: Dict[str, Any]) -> Optional[float]:
    """Extract cost information from provider response."""
    if provider == "claude-cli":
        return response.get("total_cost_usd")
    
    elif provider == "openai":
        # OpenAI doesn't typically include cost in response
        return None
    
    elif provider == "anthropic-api":
        # Would need to calculate from usage and pricing
        return None
    
    else:
        # Fallback: try common field names
        return (response.get("total_cost_usd") or
               response.get("cost") or
               response.get("cost_usd"))


def extract_model(provider: str, response: Dict[str, Any]) -> Optional[str]:
    """Extract model name from provider response."""
    if provider == "claude-cli":
        return response.get("model")
    
    elif provider == "openai":
        return response.get("model")
    
    elif provider == "anthropic-api":
        return response.get("model")
    
    else:
        # Fallback: try common field names
        return response.get("model")


def create_completion_response(provider: str, raw_response: Dict[str, Any], 
                             **kwargs) -> Dict[str, Any]:
    """
    Convenience function to create a standardized completion response.
    
    Args:
        provider: Provider name
        raw_response: Raw provider response
        **kwargs: Additional metadata (request_id, client_id, duration_ms)
    
    Returns:
        Standardized response dictionary
    """
    return create_standardized_response(provider, raw_response, **kwargs)


def parse_completion_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a standardized completion response from stored data.
    
    Args:
        data: Stored completion response data
        
    Returns:
        Standardized response dictionary (same as input, for consistency)
    """
    # Validate that it has the expected structure
    if "ksi" not in data or "response" not in data:
        raise ValueError("Invalid completion response format")
    return data


def parse_completion_result_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a completion:result event or standardized response into a useful summary.
    
    Handles both formats:
    - Full event format: {"request_id": "...", "result": {...}}
    - Direct standardized response: {"ksi": {...}, "response": {...}}
    
    Args:
        event_data: completion:result event data OR standardized response
        
    Returns:
        Dict with status, session_id, response, request_id, etc.
    """
    # Check for direct error in event
    if "error" in event_data:
        return {
            "status": "error",
            "error": event_data.get("error", "Unknown error"),
            "request_id": event_data.get("request_id")
        }
    
    # Auto-detect format: if it has "ksi" key, it's a direct standardized response
    if "ksi" in event_data:
        # Direct standardized response format
        standardized_response = event_data
        request_id = event_data.get("ksi", {}).get("request_id")
    else:
        # Full event format - extract standardized response from event
        standardized_response = event_data.get("result", {})
        request_id = event_data.get("request_id")
        
        if not standardized_response:
            return {
                "status": "error",
                "error": "No completion result data",
                "request_id": request_id
            }
    
    # Use existing utility functions to parse the standardized response
    try:
        # Check for error_during_execution first
        error_info = get_response_error_info(standardized_response)
        if error_info:
            return {
                "status": "error",
                "error": error_info["message"],
                "error_type": error_info["type"],
                "request_id": request_id,
                "session_id": get_response_session_id(standardized_response),  # Still try to get session_id
                "usage": get_response_usage(standardized_response),  # Still get usage for cost tracking
                "cost": get_response_cost(standardized_response)
            }
        
        session_id = get_response_session_id(standardized_response)
        response_text = get_response_text(standardized_response)
        usage = get_response_usage(standardized_response)
        cost = get_response_cost(standardized_response)
        model = get_response_model(standardized_response)
        provider = get_provider(standardized_response)
        
        if session_id:
            return {
                "status": "completed",
                "session_id": session_id,
                "response": response_text,
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "usage": usage,
                "cost": cost
            }
        else:
            return {
                "status": "error",
                "error": "Completed but no session_id",
                "request_id": request_id
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to parse completion result: {e}",
            "request_id": request_id
        }


# Export key functions for easier imports
__all__ = [
    # Main functions
    "create_standardized_response",
    "create_completion_response",
    "parse_completion_response",
    "parse_completion_result_event",
    
    # Helper functions for standardized responses
    "get_provider",
    "get_raw_response",
    "get_request_id",
    "get_timestamp",
    "get_duration_ms",
    "get_client_id",
    "get_agent_id",
    "get_response_text",
    "get_response_session_id",
    "get_response_usage",
    "get_response_cost",
    "get_response_model",
    "is_error_during_execution",
    "get_response_error_info",
    
    # Provider extraction functions
    "extract_text",
    "extract_session_id",
    "extract_usage",
    "extract_cost",
    "extract_model",
]