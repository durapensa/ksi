#!/usr/bin/env python3
"""
Profile loader compatibility layer for migrating from JSON profiles to composition system.

Provides backward compatibility for interfaces that still load profiles from JSON files.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Load profiles using the new composition system with backward compatibility."""
    
    def __init__(self, event_client):
        """Initialize with an event client for composition loading."""
        self.event_client = event_client
        
    async def load_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a profile by name, first trying composition system, then legacy JSON.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Profile data dictionary or None if not found
        """
        # Try loading from composition system first
        try:
            result = await self.event_client.emit_event("composition:profile", {
                "name": profile_name
            })
            
            if result and result.get("status") == "success":
                profile = result.get("profile", {})
                # Convert composition format to legacy format for compatibility
                return {
                    "role": profile.get("role", "assistant"),
                    "model": profile.get("model", "sonnet"),
                    "capabilities": profile.get("capabilities", []),
                    "enable_tools": profile.get("enable_tools", False),
                    "description": profile.get("description", ""),
                    "prompt_template": profile.get("composed_prompt", "")
                }
        except Exception as e:
            logger.warning(f"Failed to load profile from composition system: {e}")
        
        # Fallback to legacy JSON loading if composition system fails
        # This provides migration path for interfaces not yet updated
        legacy_paths = [
            Path("var/agent_profiles") / f"{profile_name}.json",
            Path("var/lib/compositions/profiles/agents") / f"{profile_name}.json"
        ]
        
        for path in legacy_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        logger.info(f"Loaded legacy profile from {path}")
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load legacy profile from {path}: {e}")
        
        logger.warning(f"Profile {profile_name} not found in composition system or legacy paths")
        return None
    
    @staticmethod
    def convert_to_composition_format(legacy_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert legacy JSON profile format to composition format.
        
        This is used when migrating old profiles to the new system.
        """
        return {
            "name": legacy_profile.get("name", "unnamed"),
            "type": "profile",
            "version": "1.0.0",
            "description": legacy_profile.get("description", "Migrated profile"),
            "components": [
                {
                    "name": "agent_config",
                    "inline": {
                        "role": legacy_profile.get("role", "assistant"),
                        "model": legacy_profile.get("model", "sonnet"),
                        "capabilities": legacy_profile.get("capabilities", []),
                        "enable_tools": legacy_profile.get("enable_tools", False)
                    }
                }
            ],
            "metadata": {
                "tags": ["migrated"],
                "original_format": "json"
            }
        }