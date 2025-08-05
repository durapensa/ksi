#!/usr/bin/env python3
"""
Routing State Adapter

Provides state system integration for routing rules, replacing in-memory storage
with persistent state entities. Part of Stage 1.4 implementation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import json

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import get_router
from ksi_common.event_utils import extract_single_response

logger = get_bound_logger("routing_state_adapter", version="1.0.0")


class RoutingStateAdapter:
    """Adapts routing rules to use the state entity system."""
    
    ENTITY_TYPE = "routing_rule"
    
    def __init__(self):
        self.router = get_router()
        logger.info("RoutingStateAdapter initialized")
    
    async def create_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Create a routing rule in state system."""
        # Convert rule to state entity
        entity_data = {
            "type": self.ENTITY_TYPE,
            "id": rule["rule_id"],
            "properties": {
                "source_pattern": rule["source_pattern"],
                "target": rule["target"],
                "condition": rule.get("condition"),
                "mapping": rule.get("mapping"),
                "priority": rule.get("priority", 100),
                "ttl": rule.get("ttl"),
                "parent_scope": rule.get("parent_scope"),  # Add parent_scope
                "created_by": rule["created_by"],
                "created_at": rule["created_at"],
                "metadata": rule.get("metadata"),
                # Store expiry time if TTL is set
                "expires_at": self._calculate_expiry(rule.get("ttl")) if rule.get("ttl") else None
            }
        }
        
        # Create in state system
        result_list = await self.router.emit("state:entity:create", entity_data)
        result = extract_single_response(result_list)
        
        if result and result.get("status") == "success":
            logger.info(f"Created routing rule entity: {rule['rule_id']}")
            return {"status": "success", "rule": rule}
        else:
            error = result.get("error") if result else "Unknown error"
            logger.error(f"Failed to create routing rule entity: {error}")
            return {"status": "error", "error": error}
    
    async def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific routing rule from state system."""
        result = await self.router.emit("state:entity:get", {
            "type": self.ENTITY_TYPE,
            "id": rule_id
        })
        
        response = extract_single_response(result)
        if response and response.get("status") == "success":
            entity = response.get("data", {})
            return self._entity_to_rule(entity)
        return None
    
    async def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a routing rule in state system."""
        # Get current rule
        current_rule = await self.get_rule(rule_id)
        if not current_rule:
            return {"status": "error", "error": "Rule not found"}
        
        # Prepare property updates
        property_updates = {}
        
        # Map updates to properties
        if "source_pattern" in updates:
            property_updates["source_pattern"] = updates["source_pattern"]
        if "target" in updates:
            property_updates["target"] = updates["target"]
        if "condition" in updates:
            property_updates["condition"] = updates["condition"]
        if "mapping" in updates:
            property_updates["mapping"] = updates["mapping"]
        if "priority" in updates:
            property_updates["priority"] = updates["priority"]
        if "ttl" in updates:
            property_updates["ttl"] = updates["ttl"]
            property_updates["expires_at"] = self._calculate_expiry(updates["ttl"]) if updates["ttl"] else None
        if "parent_scope" in updates:
            property_updates["parent_scope"] = updates["parent_scope"]
        
        # Update in state system
        result = await self.router.emit("state:entity:update", {
            "type": self.ENTITY_TYPE,
            "id": rule_id,
            "properties": property_updates
        })
        
        response = extract_single_response(result)
        if response and response.get("status") == "success":
            logger.info(f"Updated routing rule entity: {rule_id}")
            return {"status": "success"}
        else:
            error = response.get("error") if response else "Unknown error"
            logger.error(f"Failed to update routing rule entity: {error}")
            return {"status": "error", "error": error}
    
    async def delete_rule(self, rule_id: str) -> Dict[str, Any]:
        """Delete a routing rule from state system."""
        result = await self.router.emit("state:entity:delete", {
            "type": self.ENTITY_TYPE,
            "id": rule_id
        })
        
        response = extract_single_response(result)
        if response and response.get("status") == "success":
            logger.info(f"Deleted routing rule entity: {rule_id}")
            return {"status": "success"}
        else:
            error = response.get("error") if response else "Unknown error"
            logger.error(f"Failed to delete routing rule entity: {error}")
            return {"status": "error", "error": error}
    
    async def list_rules(self, filter_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List all routing rules from state system."""
        # Build query
        query = {
            "type": self.ENTITY_TYPE,
            "include": ["properties"]
        }
        
        # Add filters if provided
        where = {}
        if filter_params:
            if filter_params.get("created_by"):
                where["properties.created_by"] = filter_params["created_by"]
            if filter_params.get("source_pattern"):
                where["properties.source_pattern"] = {"$like": f"{filter_params['source_pattern']}%"}
            if filter_params.get("target"):
                where["properties.target"] = filter_params["target"]
        
        if where:
            query["where"] = where
        
        # Query state system
        result_list = await self.router.emit("state:entity:query", query)
        result = extract_single_response(result_list)
        
        if result and result.get("status") == "success":
            entities = result.get("entities", [])  # Changed from 'data' to 'entities'
            rules = [self._entity_to_rule(entity) for entity in entities]
            # Filter out None values (expired rules)
            return [rule for rule in rules if rule is not None]
        else:
            logger.error("Failed to query routing rules from state")
            return []
    
    async def get_expired_rules(self) -> List[str]:
        """Get IDs of expired routing rules."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Query for expired rules
        result = await self.router.emit("state:entity:query", {
            "type": self.ENTITY_TYPE,
            "where": {
                "properties.expires_at": {"$lt": now, "$ne": None}
            },
            "include": ["id"]
        })
        
        response = extract_single_response(result)
        if response and response.get("status") == "success":
            entities = response.get("entities", [])  # Changed from 'data' to 'entities'
            return [entity["entity_id"] for entity in entities]  # Changed 'id' to 'entity_id'
        return []
    
    def _entity_to_rule(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert state entity to routing rule format."""
        if not entity or "properties" not in entity:
            return None
        
        props = entity["properties"]
        
        # Check if expired
        if props.get("expires_at"):
            expires_at = datetime.fromisoformat(props["expires_at"].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                return None  # Rule has expired
        
        return {
            "rule_id": entity["entity_id"],  # Changed from 'id' to 'entity_id'
            "source_pattern": props.get("source_pattern"),
            "target": props.get("target"),
            "condition": props.get("condition"),
            "mapping": props.get("mapping"),
            "priority": props.get("priority", 100),
            "ttl": props.get("ttl"),
            "parent_scope": props.get("parent_scope"),  # Include parent_scope
            "created_by": props.get("created_by"),
            "created_at": props.get("created_at"),
            "metadata": props.get("metadata")
        }
    
    def _calculate_expiry(self, ttl_seconds: Optional[int]) -> Optional[str]:
        """Calculate expiry timestamp from TTL seconds."""
        if not ttl_seconds:
            return None
        
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        return expiry.isoformat()