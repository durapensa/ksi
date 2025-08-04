#!/usr/bin/env python3
"""
Agent context utilities for KSI event system.

Provides utilities for propagating agent context through event emissions,
ensuring proper attribution of agent-originated events.
"""
from typing import Dict, Any, Optional


def propagate_agent_context(context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Propagate agent context for event emissions.
    
    The presence of _agent_id in the context is the single source of truth
    for agent origination. This function creates a minimal context containing
    only the agent ID for emission to downstream events.
    
    Args:
        context: The incoming event context, which may contain _agent_id
        
    Returns:
        A minimal context dict with _agent_id if present, or None if no agent context
        
    Examples:
        # Agent-originated event
        >>> context = {"_agent_id": "agent_123", "other": "data"}
        >>> propagate_agent_context(context)
        {"_agent_id": "agent_123"}
        
        # System-originated event
        >>> context = {"other": "data"}
        >>> propagate_agent_context(context)
        None
        
        # No context
        >>> propagate_agent_context(None)
        None
    """
    if not context:
        return None
        
    agent_id = context.get("_agent_id")
    if not agent_id:
        return None
        
    # Return minimal context with only agent ID
    return {"_agent_id": agent_id}


def is_agent_context(context: Optional[Dict[str, Any]]) -> bool:
    """
    Determine if a request originates from a KSI agent vs external tool.
    
    This is used by the discovery system and other components to provide
    different JSON formats based on the consumer:
    - KSI agents get ksi_tool_use format (reliable for LLM emission)
    - CLI tools get standard event JSON format
    
    Args:
        context: Event context dictionary
        
    Returns:
        True if request is from an agent, False otherwise
        
    Examples:
        # Agent context
        >>> is_agent_context({"_agent_id": "agent_123"})
        True
        
        # CLI context
        >>> is_agent_context({"_client_id": "ksi-cli"})
        False
        
        # Claude Code coordination (treated as agent)
        >>> is_agent_context({"_client_id": "claude-code"})
        True
    """
    if not context:
        return False
    
    # Primary check: Agent ID presence is definitive
    if context.get("_agent_id"):
        return True
    
    # Secondary check: Client ID patterns
    client_id = context.get("_client_id", "")
    
    # Known CLI tools (not agents)
    if client_id in ["ksi-cli", "ksi-client", "web-ui"]:
        return False
    
    # Claude Code coordination is treated as agent context
    if client_id == "claude-code":
        return True
    
    # Default: No agent markers means CLI/external tool
    return False