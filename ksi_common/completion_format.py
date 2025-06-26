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
from .timestamps import TimestampManager


class CompletionResponse:
    """
    Standardized completion response wrapper.
    
    Provides provider-agnostic access to completion data while preserving
    the original provider response format.
    """
    
    def __init__(self, provider: str, raw_response: Dict[str, Any], 
                 request_id: Optional[str] = None, client_id: Optional[str] = None,
                 duration_ms: Optional[int] = None):
        """
        Create a standardized completion response.
        
        Args:
            provider: Provider name (e.g., "claude-cli", "openai", "anthropic-api")
            raw_response: Untouched response from the provider
            request_id: KSI request identifier
            client_id: KSI client identifier  
            duration_ms: Request duration in milliseconds
        """
        self.data = {
            "ksi": {
                "provider": provider,
                "request_id": request_id or str(uuid.uuid4()),
                "timestamp": TimestampManager.timestamp_utc(),
                "duration_ms": duration_ms
            },
            "response": raw_response
        }
        
        # Add client_id if provided
        if client_id:
            self.data["ksi"]["client_id"] = client_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Get the complete standardized response."""
        return self.data
    
    def get_provider(self) -> str:
        """Get the provider name."""
        return self.data["ksi"]["provider"]
    
    def get_raw_response(self) -> Dict[str, Any]:
        """Get the untouched provider response."""
        return self.data["response"]
    
    def get_request_id(self) -> str:
        """Get the KSI request ID."""
        return self.data["ksi"]["request_id"]
    
    def get_timestamp(self) -> str:
        """Get the ISO 8601 UTC timestamp."""
        return self.data["ksi"]["timestamp"]
    
    def get_duration_ms(self) -> Optional[int]:
        """Get request duration in milliseconds."""
        return self.data["ksi"].get("duration_ms")
    
    def get_client_id(self) -> Optional[str]:
        """Get the client ID if available."""
        return self.data["ksi"].get("client_id")
    
    # Provider-agnostic extraction methods
    
    def get_text(self) -> str:
        """Extract response text using provider-specific logic."""
        return ProviderHelpers.extract_text(self.get_provider(), self.get_raw_response())
    
    def get_session_id(self) -> Optional[str]:
        """Extract session ID using provider-specific logic."""
        return ProviderHelpers.extract_session_id(self.get_provider(), self.get_raw_response())
    
    def get_usage(self) -> Optional[Dict[str, Any]]:
        """Extract usage statistics using provider-specific logic."""
        return ProviderHelpers.extract_usage(self.get_provider(), self.get_raw_response())
    
    def get_cost(self) -> Optional[float]:
        """Extract cost information using provider-specific logic."""
        return ProviderHelpers.extract_cost(self.get_provider(), self.get_raw_response())
    
    def get_model(self) -> Optional[str]:
        """Extract model name using provider-specific logic."""
        return ProviderHelpers.extract_model(self.get_provider(), self.get_raw_response())


class ProviderHelpers:
    """
    Provider-specific extraction helpers.
    
    These methods know how to extract common fields from different
    LLM provider response formats.
    """
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
                             **kwargs) -> CompletionResponse:
    """
    Convenience function to create a standardized completion response.
    
    Args:
        provider: Provider name
        raw_response: Raw provider response
        **kwargs: Additional metadata (request_id, client_id, duration_ms)
    
    Returns:
        CompletionResponse instance
    """
    return CompletionResponse(provider, raw_response, **kwargs)


def parse_completion_response(data: Dict[str, Any]) -> CompletionResponse:
    """
    Parse a standardized completion response from stored data.
    
    Args:
        data: Stored completion response data
        
    Returns:
        CompletionResponse instance
    """
    # Create a temporary response to wrap the parsed data
    response = CompletionResponse.__new__(CompletionResponse)
    response.data = data
    return response


# Export key functions for easier imports
__all__ = [
    "CompletionResponse",
    "ProviderHelpers", 
    "create_completion_response",
    "parse_completion_response"
]