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