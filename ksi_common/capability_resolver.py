#!/usr/bin/env python3
"""
Capability resolver that uses declarative YAML mappings.

This is the single source of truth for event→capability relationships.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("capability_resolver")


class CapabilityResolver:
    """Resolves capabilities from declarative YAML mapping."""
    
    def __init__(self, mapping_file: Optional[Path] = None):
        """Initialize with capability mapping file."""
        if mapping_file:
            self.mapping_file = mapping_file
        else:
            # Check for v2 first, fall back to v1
            v2_path = config.lib_dir / "capabilities" / "capability_mappings_v2.yaml"
            v1_path = config.lib_dir / "capabilities" / "capability_mappings.yaml"
            
            if v2_path.exists():
                self.mapping_file = v2_path
                logger.info("Using capability mappings v2")
            else:
                self.mapping_file = v1_path
                
        self.mappings = self._load_mappings()
        self._build_reverse_index()
        
    def _load_mappings(self) -> Dict[str, Any]:
        """Load capability mappings from YAML."""
        try:
            with open(self.mapping_file) as f:
                data = yaml.safe_load(f)
                logger.info(f"Loaded capability mappings v{data.get('version', '?')}")
                return data
        except Exception as e:
            logger.error(f"Failed to load capability mappings: {e}")
            # Return minimal fallback
            return {
                "capabilities": {
                    "base": {
                        "events": ["system:health"],
                        "always_enabled": True
                    }
                }
            }
            
    def _build_reverse_index(self):
        """Build event→capability reverse index for fast lookups."""
        self.event_to_capability = {}
        
        for cap_name, cap_def in self.mappings.get("capabilities", {}).items():
            for event in cap_def.get("events", []):
                self.event_to_capability[event] = cap_name
                
    def resolve_capabilities_for_profile(self, capabilities: Dict[str, bool]) -> Dict[str, Any]:
        """
        Resolve capability flags to concrete event and tool lists.
        
        Args:
            capabilities: Dict of capability_name → enabled
            
        Returns:
            Dict with allowed_events, allowed_claude_tools, expanded_capabilities
        """
        # Start with enabled capabilities
        enabled = set()
        
        # Always include base
        enabled.add("base")
        
        # Add explicitly enabled
        for cap, is_enabled in capabilities.items():
            if is_enabled:
                enabled.add(cap)
                
        # Expand with dependencies
        enabled = self._expand_dependencies(enabled)
        
        # Collect events
        allowed_events = set()
        for cap in enabled:
            cap_def = self.mappings.get("capabilities", {}).get(cap, {})
            allowed_events.update(cap_def.get("events", []))
            
        # Collect Claude tools from capability-tool mappings
        allowed_claude_tools = set()
        for tool_group, tool_def in self.mappings.get("claude_tools", {}).items():
            if tool_group in enabled:  # Use enabled set, not just explicit capabilities
                allowed_claude_tools.update(tool_def.get("tools", []))
                
        return {
            "allowed_events": sorted(allowed_events),
            "allowed_claude_tools": sorted(allowed_claude_tools),
            "expanded_capabilities": sorted(enabled)
        }
        
    def _expand_dependencies(self, capabilities: Set[str]) -> Set[str]:
        """Expand capability set to include all dependencies."""
        expanded = set(capabilities)
        changed = True
        
        while changed:
            changed = False
            for cap in list(expanded):
                cap_def = self.mappings["capabilities"].get(cap, {})
                for required in cap_def.get("requires", []):
                    if required not in expanded:
                        expanded.add(required)
                        changed = True
                        
        return expanded
        
    def get_capability_for_event(self, event: str) -> Optional[str]:
        """Get which capability an event belongs to."""
        return self.event_to_capability.get(event)
        
    def validate_event_access(self, agent_capabilities: List[str], event: str) -> bool:
        """Check if agent with given capabilities can access an event."""
        # Expand capabilities with dependencies
        expanded = self._expand_dependencies(set(agent_capabilities))
        
        # Check if event's capability is in agent's expanded set
        event_cap = self.get_capability_for_event(event)
        if not event_cap:
            logger.warning(f"Unknown event: {event}")
            return False
            
        return event_cap in expanded
        
    def resolve_tier(self, tier_name: str) -> Dict[str, Any]:
        """
        Resolve a v2 tier to concrete events and tools.
        
        Args:
            tier_name: Name of the tier (e.g., 'communicator', 'executor')
            
        Returns:
            Dict with allowed_events, allowed_claude_tools, expanded_capabilities
        """
        # Check if we have v2 tiers
        tiers = self.mappings.get("tiers", {})
        if tier_name not in tiers:
            logger.warning(f"Unknown tier: {tier_name}")
            # Return minimal permissions
            return {
                "allowed_events": ["system:health", "system:help", "system:discover"],
                "allowed_claude_tools": [],
                "expanded_capabilities": ["system_access"]
            }
            
        tier = tiers[tier_name]
        
        # Build capability list from inheritance chain
        all_capabilities = set()
        current_tier = tier_name
        
        while current_tier:
            tier_def = tiers.get(current_tier, {})
            
            # Add capabilities from this tier
            all_capabilities.update(tier_def.get("capabilities", []))
            all_capabilities.update(tier_def.get("additional_capabilities", []))
            
            # Move to parent tier
            current_tier = tier_def.get("inherits")
            
        # Now resolve these capabilities to events
        allowed_events = set()
        for cap in all_capabilities:
            cap_def = self.mappings.get("capabilities", {}).get(cap, {})
            allowed_events.update(cap_def.get("events", []))
            
        # Resolve Claude tools (if defined in v2)
        allowed_claude_tools = set()
        # V2 doesn't define claude_tools directly, so we'll use a basic set
        # based on the tier level
        if tier_name in ["executor", "coordinator", "orchestrator", "administrator", "overseer"]:
            # Higher tiers get more tools
            allowed_claude_tools.update(["Task", "Bash", "Glob", "Grep", "LS", "Read", "Edit", "Write"])
        elif tier_name in ["communicator"]:
            # Mid-tier gets read-only tools
            allowed_claude_tools.update(["Read", "LS", "Grep", "Glob"])
        elif tier_name in ["observer"]:
            # Low tier gets minimal tools
            allowed_claude_tools.update(["Read", "LS"])
            
        return {
            "allowed_events": sorted(allowed_events),
            "allowed_claude_tools": sorted(allowed_claude_tools),
            "expanded_capabilities": sorted(all_capabilities)
        }
        
    def get_security_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get a predefined security profile."""
        profiles = self.mappings.get("security_profiles", {})
        profile = profiles.get(profile_name)
        
        if not profile:
            return None
            
        # Handle inheritance
        if "inherits" in profile:
            base = self.get_security_profile(profile["inherits"])
            if base:
                # Merge capabilities
                merged_caps = list(base.get("capabilities", []))
                merged_caps.extend(profile.get("additional_capabilities", []))
                
                merged_tools = list(base.get("claude_tools", []))
                merged_tools.extend(profile.get("additional_claude_tools", []))
                
                profile["capabilities"] = merged_caps
                profile["claude_tools"] = merged_tools
                
        return profile
        
    def expand_pattern(self, pattern: str) -> List[str]:
        """Expand event pattern (e.g., 'message:*') to concrete events."""
        patterns = self.mappings.get("event_patterns", {})
        return patterns.get(pattern, [])
        
    def get_mcp_tools_for_events(self, events: List[str]) -> List[Dict[str, Any]]:
        """
        Generate MCP tool definitions for given events.
        
        This is how Claude tools are dynamically generated from our events!
        """
        tools = []
        
        for event in events:
            # Skip internal events
            if event.startswith("system:internal"):
                continue
                
            tool = {
                "name": f"ksi_{event.replace(':', '_')}",
                "description": self._get_event_description(event),
                "inputSchema": {
                    "type": "object",
                    "properties": {}  # Would be filled from event discovery
                }
            }
            tools.append(tool)
            
        return tools
        
    def _get_event_description(self, event: str) -> str:
        """Get human-readable description for an event."""
        # Could be enhanced with actual descriptions from handlers
        cap = self.get_capability_for_event(event)
        if cap:
            cap_def = self.mappings["capabilities"].get(cap, {})
            return f"{cap_def.get('description', cap)} - {event}"
        return f"Execute {event} event"


# Global instance
_resolver = None

def get_capability_resolver() -> CapabilityResolver:
    """Get or create the global capability resolver."""
    global _resolver
    if _resolver is None:
        _resolver = CapabilityResolver()
    return _resolver