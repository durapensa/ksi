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
                                duration_ms: Optional[int] = None) -> Dict[str, Any]:
    """
    Create a standardized completion response dictionary.
    
    Args:
        provider: Provider name (e.g., "claude-cli", "openai", "anthropic-api")
        raw_response: Untouched response from the provider
        request_id: KSI request identifier
        client_id: KSI client identifier  
        duration_ms: Request duration in milliseconds
        
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
    
    return result


# Helper functions to extract data from standardized response
def get_provider(response: Dict[str, Any]) -> str:
    """Get the provider name from standardized response."""
    return response["ksi"]["provider"]


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


# Deprecated: CompletionResponse class for backward compatibility
# TODO: Remove after migrating all usages
class CompletionResponse:
    """DEPRECATED: Use create_standardized_response() and helper functions instead."""
    
    def __init__(self, provider: str, raw_response: Dict[str, Any], 
                 request_id: Optional[str] = None, client_id: Optional[str] = None,
                 duration_ms: Optional[int] = None):
        self.data = create_standardized_response(provider, raw_response, request_id, client_id, duration_ms)
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data
    
    def get_provider(self) -> str:
        return get_provider(self.data)
    
    def get_raw_response(self) -> Dict[str, Any]:
        return get_raw_response(self.data)
    
    def get_request_id(self) -> str:
        return get_request_id(self.data)
    
    def get_timestamp(self) -> str:
        return get_timestamp(self.data)
    
    def get_duration_ms(self) -> Optional[int]:
        return get_duration_ms(self.data)
    
    def get_client_id(self) -> Optional[str]:
        return get_client_id(self.data)
    
    def get_text(self) -> str:
        return get_response_text(self.data)
    
    def get_session_id(self) -> Optional[str]:
        return get_response_session_id(self.data)
    
    def get_usage(self) -> Optional[Dict[str, Any]]:
        return get_response_usage(self.data)
    
    def get_cost(self) -> Optional[float]:
        return get_response_cost(self.data)
    
    def get_model(self) -> Optional[str]:
        return get_response_model(self.data)


def extract_text(provider: str, response: Dict[str, Any]) -> str:
    """Extract response text from provider response."""
    if provider == "claude-cli":
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


def extract_session_id(provider: str, response: Dict[str, Any]) -> Optional[str]:
    """Extract session ID from provider response."""
    if provider == "claude-cli":
        return response.get("session_id")
    
    elif provider in ["openai", "anthropic-api"]:
        # These providers typically don't have built-in session tracking
        return None
    
    else:
        # Fallback: try common field names
        return (response.get("session_id") or 
               response.get("sessionId") or
               response.get("conversation_id"))


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


# Deprecated: ProviderHelpers class for backward compatibility
# TODO: Remove after migrating all usages
class ProviderHelpers:
    """DEPRECATED: Use module-level functions instead"""
    extract_text = staticmethod(extract_text)
    extract_session_id = staticmethod(extract_session_id)
    extract_usage = staticmethod(extract_usage)
    extract_cost = staticmethod(extract_cost)
    extract_model = staticmethod(extract_model)


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


# Export key functions for easier imports
__all__ = [
    # Main functions
    "create_standardized_response",
    "create_completion_response",
    "parse_completion_response",
    
    # Helper functions for standardized responses
    "get_provider",
    "get_raw_response",
    "get_request_id",
    "get_timestamp",
    "get_duration_ms",
    "get_client_id",
    "get_response_text",
    "get_response_session_id",
    "get_response_usage",
    "get_response_cost",
    "get_response_model",
    
    # Provider extraction functions
    "extract_text",
    "extract_session_id",
    "extract_usage",
    "extract_cost",
    "extract_model",
    
    # Deprecated classes
    "CompletionResponse",
    "ProviderHelpers",
]