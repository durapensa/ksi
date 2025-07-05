#!/usr/bin/env python3
"""
Example of how the capability system would integrate with KSI.

Shows wildcard expansion, Claude tool mapping, and profile resolution.
"""

from typing import Dict, Any, List, Set, Tuple
import re

# Simulated event registry (would be built from decorated handlers)
EVENT_REGISTRY = {
    "message:subscribe": {"capability": "agent_messaging"},
    "message:unsubscribe": {"capability": "agent_messaging"},
    "message:publish": {"capability": "agent_messaging"},
    "message:subscriptions": {"capability": "agent_messaging"},
    "agent:spawn": {"capability": "spawn_agents"},
    "agent:terminate": {"capability": "spawn_agents"},
    "agent:list": {"capability": "spawn_agents"},
    "agent:status": {"capability": "spawn_agents"},
    "agent:send_message": {"capability": "agent_messaging"},
    "state:get": {"capability": "state_read"},
    "state:set": {"capability": "state_write"},
    "state:delete": {"capability": "state_write"},
    "state:list": {"capability": "state_read"},
    "system:health": {"capability": "base"},
    "system:help": {"capability": "base"},
    "system:discover": {"capability": "base"},
}

# Capability definitions with patterns and Claude tools
CAPABILITIES = {
    "base": {
        "description": "Essential system access",
        "event_patterns": ["system:health", "system:help", "system:discover"],
        "claude_tools": [],  # No Claude tools needed
        "always_enabled": True
    },
    
    "state_read": {
        "description": "Read shared state",
        "event_patterns": ["state:get", "state:list"],
        "claude_tools": []
    },
    
    "state_write": {
        "description": "Write shared state",
        "event_patterns": ["state:set", "state:delete"],
        "requires": ["state_read"],
        "claude_tools": []
    },
    
    "agent_messaging": {
        "description": "Inter-agent communication",
        "event_patterns": [
            "message:*",  # Wildcard pattern
            "agent:send_message"
        ],
        "claude_tools": []
    },
    
    "spawn_agents": {
        "description": "Create and manage agents",
        "event_patterns": ["agent:spawn", "agent:terminate", "agent:list", "agent:status"],
        "requires": ["agent_messaging"],
        "claude_tools": []
    },
    
    "multi_agent_todo": {
        "description": "Shared task lists",
        "event_patterns": [],  # No KSI events
        "claude_tools": ["TodoRead", "TodoWrite"]  # Only Claude tools
    },
    
    "network_access": {
        "description": "External web access",
        "event_patterns": [],
        "claude_tools": ["WebFetch", "WebSearch"]
    }
}


class CapabilityResolver:
    """Resolves capabilities to concrete tool lists."""
    
    def __init__(self, event_registry: Dict, capabilities: Dict):
        self.event_registry = event_registry
        self.capabilities = capabilities
        
    def resolve_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve a profile's capabilities into allowed tools.
        
        Input profile:
        {
            "capabilities": {
                "agent_messaging": true,
                "spawn_agents": true
            },
            "tool_overrides": {
                "additional_tools": ["custom:event"],
                "disallowed_tools": ["agent:terminate"]
            }
        }
        
        Output:
        {
            "allowed_events": [...],
            "allowed_claude_tools": [...],
            "capabilities_expanded": {...}
        }
        """
        enabled_capabilities = set()
        allowed_events = set()
        allowed_claude_tools = set()
        
        # Always include base
        enabled_capabilities.add("base")
        
        # Get explicitly enabled capabilities
        profile_caps = profile.get("capabilities", {})
        for cap, enabled in profile_caps.items():
            if enabled and cap in self.capabilities:
                enabled_capabilities.add(cap)
                
        # Expand capabilities including dependencies
        expanded_caps = self._expand_with_dependencies(enabled_capabilities)
        
        # Collect events and tools from all enabled capabilities
        for cap in expanded_caps:
            cap_def = self.capabilities.get(cap, {})
            
            # Add event patterns
            for pattern in cap_def.get("event_patterns", []):
                if "*" in pattern:
                    # Expand wildcard
                    allowed_events.update(self._expand_wildcard(pattern))
                else:
                    allowed_events.add(pattern)
                    
            # Add Claude tools
            allowed_claude_tools.update(cap_def.get("claude_tools", []))
            
        # Apply overrides
        overrides = profile.get("tool_overrides", {})
        allowed_events.update(overrides.get("additional_tools", []))
        allowed_events -= set(overrides.get("disallowed_tools", []))
        
        return {
            "allowed_events": sorted(allowed_events),
            "allowed_claude_tools": sorted(allowed_claude_tools),
            "capabilities_expanded": sorted(expanded_caps)
        }
        
    def _expand_with_dependencies(self, capabilities: Set[str]) -> Set[str]:
        """Expand capabilities to include all dependencies."""
        expanded = set(capabilities)
        changed = True
        
        while changed:
            changed = False
            for cap in list(expanded):
                cap_def = self.capabilities.get(cap, {})
                for required in cap_def.get("requires", []):
                    if required not in expanded:
                        expanded.add(required)
                        changed = True
                        
        return expanded
        
    def _expand_wildcard(self, pattern: str) -> List[str]:
        """Expand wildcard pattern to matching events."""
        # Convert wildcard to regex
        regex_pattern = pattern.replace("*", ".*")
        regex = re.compile(f"^{regex_pattern}$")
        
        matching = []
        for event in self.event_registry:
            if regex.match(event):
                matching.append(event)
                
        return matching
        
    def get_capability_for_event(self, event: str) -> str:
        """Get which capability an event belongs to."""
        return self.event_registry.get(event, {}).get("capability", "unknown")
        
    def validate_agent_access(self, agent_caps: List[str], event: str) -> bool:
        """Check if agent with given capabilities can access an event."""
        required_cap = self.get_capability_for_event(event)
        if required_cap == "unknown":
            return False
            
        # Check if agent has the capability (including dependencies)
        agent_expanded = self._expand_with_dependencies(set(agent_caps))
        return required_cap in agent_expanded


# Example usage
def demo_capability_resolution():
    resolver = CapabilityResolver(EVENT_REGISTRY, CAPABILITIES)
    
    print("=== Example 1: Basic Agent ===")
    basic_profile = {
        "capabilities": {
            "state_read": True
        }
    }
    result = resolver.resolve_profile(basic_profile)
    print(f"Capabilities: {result['capabilities_expanded']}")
    print(f"Allowed events: {result['allowed_events']}")
    print(f"Claude tools: {result['allowed_claude_tools']}")
    
    print("\n=== Example 2: Multi-Agent Orchestrator ===")
    orchestrator_profile = {
        "capabilities": {
            "spawn_agents": True,
            "multi_agent_todo": True
        }
    }
    result = resolver.resolve_profile(orchestrator_profile)
    print(f"Capabilities: {result['capabilities_expanded']}")
    print(f"Allowed events: {result['allowed_events']}")
    print(f"Claude tools: {result['allowed_claude_tools']}")
    
    print("\n=== Example 3: With Overrides ===")
    custom_profile = {
        "capabilities": {
            "agent_messaging": True
        },
        "tool_overrides": {
            "additional_tools": ["custom:special_event"],
            "disallowed_tools": ["message:publish"]  # More restrictive
        }
    }
    result = resolver.resolve_profile(custom_profile)
    print(f"Capabilities: {result['capabilities_expanded']}")
    print(f"Allowed events: {result['allowed_events']}")
    print(f"Claude tools: {result['allowed_claude_tools']}")
    
    print("\n=== Validation Examples ===")
    agent_caps = ["base", "agent_messaging"]
    print(f"Can agent with {agent_caps} use 'message:publish'? "
          f"{resolver.validate_agent_access(agent_caps, 'message:publish')}")
    print(f"Can agent with {agent_caps} use 'agent:spawn'? "
          f"{resolver.validate_agent_access(agent_caps, 'agent:spawn')}")


if __name__ == "__main__":
    demo_capability_resolution()