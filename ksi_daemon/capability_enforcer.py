#!/usr/bin/env python3
"""
Daemon-specific capability enforcement and runtime security.

This handles the security boundary enforcement and agent spawn validation.
"""

from typing import Dict, Any, List, Optional
from ksi_common.capability_resolver import get_capability_resolver
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("capability_enforcer")


class CapabilityEnforcer:
    """Enforces capability-based security boundaries at runtime."""
    
    def __init__(self):
        self.resolver = get_capability_resolver()
        
    def validate_agent_spawn(self, profile_capabilities: Dict[str, bool]) -> Dict[str, Any]:
        """
        Validate and resolve capabilities for agent spawning.
        
        Args:
            profile_capabilities: Dict of capability_name → enabled
            
        Returns:
            Dict with allowed_events, allowed_claude_tools, expanded_capabilities
            
        Raises:
            SecurityError: If capabilities are invalid or dangerous
        """
        # Use resolver to get concrete permissions
        resolved = self.resolver.resolve_capabilities_for_profile(profile_capabilities)
        
        # Log security decision
        logger.info(
            f"Agent spawn authorized",
            expanded_capabilities=resolved["expanded_capabilities"],
            allowed_events=len(resolved["allowed_events"]),
            allowed_claude_tools=len(resolved["allowed_claude_tools"])
        )
        
        return resolved
        
    def validate_event_access(self, agent_capabilities: List[str], event: str) -> bool:
        """
        Runtime validation that agent can access an event.
        
        Args:
            agent_capabilities: List of capability names agent has
            event: Event name to validate
            
        Returns:
            True if access granted, False otherwise
        """
        # Delegate to resolver for the actual logic
        is_allowed = self.resolver.validate_event_access(agent_capabilities, event)
        
        if not is_allowed:
            logger.warning(
                f"Event access denied",
                event=event,
                agent_capabilities=agent_capabilities
            )
            
        return is_allowed
        
    def get_security_boundaries(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get security profile with runtime enforcement context.
        
        Args:
            profile_name: Name of security profile
            
        Returns:
            Security profile with enforcement metadata
        """
        profile = self.resolver.get_security_profile(profile_name)
        
        if profile:
            # Add runtime enforcement metadata
            profile["_enforcement"] = {
                "validated_at": "runtime",
                "enforcer_version": "1.0.0"
            }
            
        return profile
        
    def audit_capability_usage(self, agent_id: str, capability: str, event: str):
        """
        Audit capability usage for security monitoring.
        
        Args:
            agent_id: ID of agent using capability
            capability: Capability being used
            event: Specific event being accessed
        """
        logger.info(
            f"Capability usage",
            agent_id=agent_id,
            capability=capability,
            event=event,
            audit=True
        )


# Global enforcer instance
_enforcer = None

def get_capability_enforcer() -> CapabilityEnforcer:
    """Get or create the global capability enforcer."""
    global _enforcer
    if _enforcer is None:
        _enforcer = CapabilityEnforcer()
    return _enforcer