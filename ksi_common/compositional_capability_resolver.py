#!/usr/bin/env python3
"""
Compositional capability resolver that mirrors the component system architecture.

This resolver handles atomic capabilities, mixins, and profiles with full
dependency resolution - just like the component system.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("compositional_capability_resolver")


class CompositionalCapabilityResolver:
    """Resolves capabilities using compositional patterns like the component system."""
    
    def __init__(self, mapping_file: Optional[Path] = None):
        """Initialize with capability system file."""
        if mapping_file:
            self.mapping_file = mapping_file
        else:
            # Check for v3 compositional system first
            v3_path = config.lib_dir / "capabilities" / "capability_system_v3.yaml"
            v2_path = config.lib_dir / "capabilities" / "capability_mappings_v2.yaml"
            v1_path = config.lib_dir / "capabilities" / "capability_mappings.yaml"
            
            if v3_path.exists():
                self.mapping_file = v3_path
                logger.info("Using compositional capability system v3")
            elif v2_path.exists():
                self.mapping_file = v2_path
                logger.info("Using capability mappings v2")
            else:
                self.mapping_file = v1_path
                logger.info("Using legacy capability mappings v1")
                
        self.system = self._load_system()
        self._build_indexes()
        
        # Load legacy profile mappings
        self.profile_mapping = {
            # Legacy permission profiles to v3 capability profiles
            "restricted": "observer",
            "standard": "communicator", 
            "trusted": "coordinator",
            "researcher": "orchestrator"
        }
        
    def _load_system(self) -> Dict[str, Any]:
        """Load capability system from YAML."""
        try:
            with open(self.mapping_file) as f:
                data = yaml.safe_load(f)
                version = data.get('version', '1.0')
                logger.info(f"Loaded capability system v{version}")
                return data
        except Exception as e:
            logger.error(f"Failed to load capability system: {e}")
            # Return minimal fallback
            return {
                "version": "fallback",
                "atomic_capabilities": {
                    "health_check": {
                        "events": ["system:health"],
                        "description": "Basic health check"
                    }
                }
            }
            
    def _build_indexes(self):
        """Build reverse indexes for fast lookups."""
        self.event_to_capability = {}
        
        # Index atomic capabilities
        for cap_name, cap_def in self.system.get("atomic_capabilities", {}).items():
            for event in cap_def.get("events", []):
                self.event_to_capability[event] = cap_name
                
        # For v1/v2 compatibility, index old-style capabilities
        for cap_name, cap_def in self.system.get("capabilities", {}).items():
            for event in cap_def.get("events", []):
                self.event_to_capability[event] = cap_name
                
    def resolve_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Resolve a capability profile to concrete events and tools.
        
        This handles:
        - Profile inheritance
        - Mixin resolution
        - Atomic capability inclusion
        - Dependency resolution
        - Event deduplication
        """
        # Check if this is a legacy permission profile name
        if profile_name in self.profile_mapping:
            mapped_name = self.profile_mapping[profile_name]
            logger.info(f"Mapping legacy profile {profile_name} to {mapped_name}")
            profile_name = mapped_name
            
        profiles = self.system.get("capability_profiles", {})
        profile = profiles.get(profile_name)
        
        # Handle legacy profiles from v1/v2
        if not profile:
            profile = self._resolve_legacy_profile(profile_name)
            
        if not profile:
            logger.warning(f"Unknown profile: {profile_name}")
            return self._minimal_profile()
            
        # Resolve all capabilities for this profile
        all_capabilities = set()
        all_events = set()
        
        # 1. Handle inheritance
        if "inherits" in profile:
            parent = self.resolve_profile(profile["inherits"])
            all_events.update(parent.get("allowed_events", []))
            
        # 2. Add atomic capabilities
        for atom in profile.get("atoms", []):
            atom_events = self._resolve_atom(atom)
            all_events.update(atom_events)
            all_capabilities.add(atom)
            
        # 3. Resolve mixins (with dependency resolution)
        for mixin in profile.get("mixins", []):
            mixin_caps, mixin_events = self._resolve_mixin(mixin)
            all_capabilities.update(mixin_caps)
            all_events.update(mixin_events)
            
        # 4. Add any additional events
        all_events.update(profile.get("additional_events", []))
        
        # 5. Resolve Claude tools
        claude_tools = self._resolve_claude_tools(profile)
        
        return {
            "allowed_events": sorted(all_events),
            "allowed_claude_tools": sorted(claude_tools),
            "expanded_capabilities": sorted(all_capabilities),
            "profile_name": profile_name,
            "resolved_from": "compositional_v3"
        }
        
    def _resolve_atom(self, atom_name: str) -> Set[str]:
        """Resolve an atomic capability to its events."""
        atoms = self.system.get("atomic_capabilities", {})
        atom = atoms.get(atom_name, {})
        return set(atom.get("events", []))
        
    def _resolve_mixin(self, mixin_name: str, visited: Optional[Set[str]] = None) -> Tuple[Set[str], Set[str]]:
        """
        Resolve a mixin to its capabilities and events.
        Handles recursive dependency resolution.
        """
        if visited is None:
            visited = set()
            
        if mixin_name in visited:
            logger.warning(f"Circular dependency detected: {mixin_name}")
            return set(), set()
            
        visited.add(mixin_name)
        
        mixins = self.system.get("capability_mixins", {})
        mixin = mixins.get(mixin_name, {})
        
        capabilities = {mixin_name}
        events = set()
        
        # Resolve dependencies (both atomic and mixin)
        for dep in mixin.get("dependencies", []):
            # Check if it's a mixin first
            if dep in self.system.get("capability_mixins", {}):
                # It's a mixin - resolve recursively
                dep_caps, dep_events = self._resolve_mixin(dep, visited)
                capabilities.update(dep_caps)
                events.update(dep_events)
            else:
                # It's an atomic capability
                atom_events = self._resolve_atom(dep)
                events.update(atom_events)
                capabilities.add(dep)
            
        # Resolve mixin dependencies (recursive) - for backwards compatibility
        for dep_mixin in mixin.get("mixin_dependencies", []):
            dep_caps, dep_events = self._resolve_mixin(dep_mixin, visited)
            capabilities.update(dep_caps)
            events.update(dep_events)
            
        # Add any additional events
        events.update(mixin.get("additional_events", []))
        
        return capabilities, events
        
    def _resolve_claude_tools(self, profile: Dict[str, Any]) -> Set[str]:
        """Resolve Claude tools for a profile."""
        tools = set()
        
        # Get tool groups from profile
        tool_groups = profile.get("claude_tools", [])
        if isinstance(tool_groups, str):
            tool_groups = [tool_groups]
            
        # Resolve each tool group
        claude_tools = self.system.get("claude_tools", {})
        for group in tool_groups:
            group_def = claude_tools.get(group, {})
            tools.update(group_def.get("tools", []))
            
        return tools
        
    def _resolve_legacy_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Handle legacy v1/v2 profiles."""
        # Check v2 tier system
        tiers = self.system.get("tiers", {})
        if profile_name in tiers:
            return self._convert_tier_to_profile(profile_name)
            
        # Check v1/v2 security profiles
        security_profiles = self.system.get("security_profiles", {})
        return security_profiles.get(profile_name)
        
    def _convert_tier_to_profile(self, tier_name: str) -> Dict[str, Any]:
        """Convert v2 tier to v3 profile format."""
        tiers = self.system.get("tiers", {})
        tier = tiers.get(tier_name, {})
        
        # Build profile from tier
        profile = {
            "description": tier.get("description", ""),
            "atoms": [],
            "mixins": []
        }
        
        # Handle inheritance chain
        if "inherits" in tier:
            profile["inherits"] = tier["inherits"]
            
        # Map v2 capabilities to v3 atoms/mixins
        for cap in tier.get("capabilities", []):
            # Check if it's a known mixin
            if cap in self.system.get("capability_mixins", {}):
                profile["mixins"].append(cap)
            else:
                # Assume it's an atom or legacy capability
                profile["atoms"].append(cap)
                
        return profile
        
    def _minimal_profile(self) -> Dict[str, Any]:
        """Return absolute minimal profile."""
        return {
            "allowed_events": ["system:health", "system:help", "system:discover"],
            "allowed_claude_tools": [],
            "expanded_capabilities": ["minimal"],
            "profile_name": "minimal",
            "resolved_from": "fallback"
        }
        
    def validate_event_access(self, capabilities: List[str], event: str) -> bool:
        """Check if given capabilities allow access to an event."""
        # Build event set from capabilities
        allowed_events = set()
        
        for cap in capabilities:
            # Check if it's an atom
            atom_events = self._resolve_atom(cap)
            allowed_events.update(atom_events)
            
            # Check if it's a mixin
            _, mixin_events = self._resolve_mixin(cap)
            allowed_events.update(mixin_events)
            
            # Check legacy capabilities
            legacy_cap = self.system.get("capabilities", {}).get(cap, {})
            allowed_events.update(legacy_cap.get("events", []))
            
        return event in allowed_events
        
    def get_capability_for_event(self, event: str) -> Optional[str]:
        """Get which capability an event belongs to."""
        return self.event_to_capability.get(event)


# Singleton instance
_resolver = None

def get_compositional_capability_resolver() -> CompositionalCapabilityResolver:
    """Get or create the singleton capability resolver."""
    global _resolver
    if _resolver is None:
        _resolver = CompositionalCapabilityResolver()
    return _resolver