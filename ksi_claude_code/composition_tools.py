"""
Composition tools for working with KSI's dynamic composition system.

These tools allow exploring and using agent compositions that define
capabilities and behaviors.
"""

from typing import Dict, Any, List, Optional
from .ksi_base_tool import KSIBaseTool
import logging

logger = logging.getLogger(__name__)


class CompositionTool(KSIBaseTool):
    """Work with KSI's composition system"""
    
    name = "ksi_composition"
    description = "List, get, and validate agent compositions"
    
    async def list_compositions(
        self,
        type: Optional[str] = None
    ) -> List[str]:
        """
        List available compositions
        
        Args:
            type: Filter by type ('profile', 'prompt', 'all')
            
        Returns:
            List of composition names
        """
        list_data = {}
        if type:
            list_data["type"] = type
        
        response = await self.send_event(
            "composition:list",
            list_data
        )
        
        if not response.get("success", False):
            logger.error(f"Failed to list compositions: {response.get('error')}")
            return []
        
        # Extract composition names from response
        compositions = response.get("compositions", [])
        
        # Return just names for simplicity
        if isinstance(compositions, list):
            return compositions
        elif isinstance(compositions, dict):
            # Might be organized by type
            all_names = []
            for comp_list in compositions.values():
                if isinstance(comp_list, list):
                    all_names.extend(comp_list)
            return all_names
        
        return []
    
    async def get_composition(
        self,
        name: str,
        type: str = "profile"
    ) -> Dict[str, Any]:
        """
        Get details of a specific composition
        
        Args:
            name: Composition name
            type: Composition type
            
        Returns:
            Composition details including capabilities
        """
        response = await self.send_event(
            "composition:get",
            {
                "name": name,
                "type": type
            }
        )
        
        if not response.get("success", False):
            logger.error(f"Failed to get composition {name}: {response.get('error')}")
            return {}
        
        return response.get("composition", {})
    
    async def validate_composition(
        self,
        name: str,
        type: str = "profile"
    ) -> Dict[str, Any]:
        """
        Validate a composition
        
        Args:
            name: Composition name
            type: Composition type
            
        Returns:
            Validation results
        """
        response = await self.send_event(
            "composition:validate",
            {
                "name": name,
                "type": type
            }
        )
        
        return {
            "valid": response.get("success", False),
            "errors": response.get("errors", []),
            "warnings": response.get("warnings", [])
        }
    
    async def get_capabilities(
        self,
        profile_name: str
    ) -> Dict[str, bool]:
        """
        Get capabilities of a profile composition
        
        Args:
            profile_name: Profile name
            
        Returns:
            Dictionary of capability -> enabled
        """
        composition = await self.get_composition(profile_name, "profile")
        
        # Extract capabilities
        capabilities = {}
        
        # Check if composition has direct capabilities
        if "capabilities" in composition:
            capabilities.update(composition["capabilities"])
        
        # Check components for capabilities
        components = composition.get("components", [])
        for component in components:
            if component.get("name") == "capabilities":
                inline_caps = component.get("inline", {})
                capabilities.update(inline_caps)
        
        return capabilities
    
    async def find_profiles_with_capability(
        self,
        capability: str
    ) -> List[str]:
        """
        Find all profiles that have a specific capability
        
        Args:
            capability: Capability to search for (e.g., 'spawn_agents')
            
        Returns:
            List of profile names with that capability
        """
        profiles = await self.list_compositions(type="profile")
        matching = []
        
        for profile in profiles:
            caps = await self.get_capabilities(profile)
            if caps.get(capability, False):
                matching.append(profile)
        
        return matching
    
    async def get_composition_hierarchy(
        self,
        name: str
    ) -> Dict[str, Any]:
        """
        Get the inheritance hierarchy of a composition
        
        Args:
            name: Composition name
            
        Returns:
            Hierarchy information
        """
        composition = await self.get_composition(name)
        
        hierarchy = {
            "name": name,
            "extends": composition.get("extends"),
            "components": len(composition.get("components", [])),
            "capabilities": await self.get_capabilities(name)
        }
        
        # Recursively get parent if exists
        if hierarchy["extends"]:
            parent_hierarchy = await self.get_composition_hierarchy(hierarchy["extends"])
            hierarchy["parent"] = parent_hierarchy
        
        return hierarchy
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "validate", "get_capabilities"],
                        "description": "Action to perform"
                    },
                    "name": {
                        "type": "string",
                        "description": "Composition name (for get/validate)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["profile", "prompt", "all"],
                        "description": "Composition type"
                    }
                },
                "required": ["action"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute composition operation"""
        action = kwargs.get("action", "list")
        
        if action == "list":
            compositions = await self.list_compositions(kwargs.get("type"))
            return {"compositions": compositions}
        
        elif action == "get":
            name = kwargs.get("name")
            if not name:
                raise ValueError("Name required for get action")
            
            composition = await self.get_composition(
                name,
                kwargs.get("type", "profile")
            )
            return {"composition": composition}
        
        elif action == "validate":
            name = kwargs.get("name")
            if not name:
                raise ValueError("Name required for validate action")
            
            return await self.validate_composition(
                name,
                kwargs.get("type", "profile")
            )
        
        elif action == "get_capabilities":
            name = kwargs.get("name")
            if not name:
                raise ValueError("Name required for get_capabilities action")
            
            capabilities = await self.get_capabilities(name)
            return {"capabilities": capabilities}
        
        else:
            raise ValueError(f"Unknown action: {action}")