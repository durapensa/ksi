#!/usr/bin/env python3
"""
Routing State Adapter

Provides state system integration for routing rules, replacing in-memory storage
with persistent state entities. Part of Stage 1.4 implementation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_daemon.event_system import get_router
from ksi_common.event_utils import extract_single_response
from ksi_common.yaml_utils import save_yaml_file, load_yaml_file
from ksi_common.file_utils import ensure_directory
from ksi_common.timestamps import filename_timestamp
from ksi_common.json_utils import JSONProcessor

logger = get_bound_logger("routing_state_adapter", version="1.0.0")


class RoutingStateAdapter:
    """Adapts routing rules to use the state entity system."""
    
    ENTITY_TYPE = "routing_rule"
    
    def __init__(self):
        self.router = get_router()
        self.json_processor = JSONProcessor()
        logger.info("RoutingStateAdapter initialized")
    
    async def create_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Create a routing rule in state system with hybrid persistence."""
        # Determine persistence class
        persistence_class = rule.get("persistence_class", "ephemeral")
        
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
                "parent_scope": rule.get("parent_scope"),
                "created_by": rule["created_by"],
                "created_at": rule["created_at"],
                "metadata": rule.get("metadata"),
                "persistence_class": persistence_class,
                # Store expiry time if TTL is set
                "expires_at": self._calculate_expiry(rule.get("ttl")) if rule.get("ttl") else None,
                # Store full rule config for restoration
                "rule_config": rule
            }
        }
        
        # Create in state system
        result_list = await self.router.emit("state:entity:create", entity_data)
        result = extract_single_response(result_list)
        
        if result and result.get("status") == "success":
            logger.info(f"Created routing rule entity: {rule['rule_id']} (persistence: {persistence_class})")
            
            # Persist to YAML if marked persistent
            if persistence_class == "persistent":
                await self._persist_to_yaml(rule)
            # Optional: Log ephemeral rules for debugging
            elif rule.get("debug_log", False):
                await self._log_ephemeral_rule(rule)
            
            return {"status": "success", "rule": rule, "persistence": persistence_class}
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
    
    async def _persist_to_yaml(self, rule: Dict[str, Any]) -> None:
        """Persist a rule to YAML for recovery using ksi_common utilities."""
        try:
            rule_id = rule["rule_id"]
            source_pattern = rule.get("source_pattern", "unknown").replace(":", "_").replace("*", "wildcard")
            
            # Ensure directory exists using file_utils
            ensure_directory(config.routes_dir)
            
            # Prepare YAML content
            # Handle metadata which might be a string or dict
            metadata = rule.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = self.json_processor.loads(metadata)
                except Exception as e:
                    logger.debug(f"Failed to parse metadata as JSON: {e}")
                    metadata = {"raw": metadata}
            
            yaml_content = {
                "rule": rule,
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": rule.get("created_by", "system"),
                    "description": metadata.get("description", "") if isinstance(metadata, dict) else "",
                    "persistence_class": "persistent"
                }
            }
            
            # Use taxonomy: source_pattern_ruleid.yaml
            yaml_path = config.routes_dir / f"{source_pattern}_{rule_id}.yaml"
            # Use atomic write for safety
            save_yaml_file(yaml_path, yaml_content, create_dirs=False, atomic=True)
            
            logger.info(f"Persisted routing rule to YAML: {yaml_path}")
        except Exception as e:
            logger.error(f"Failed to persist rule to YAML: {e}")
    
    async def _log_ephemeral_rule(self, rule: Dict[str, Any]) -> None:
        """Log ephemeral rule for debugging (optional)."""
        try:
            # Create routes directory if needed for debug logs
            debug_dir = ensure_directory(config.routes_dir / "debug")
            
            # Add .gitignore if not exists
            gitignore_path = debug_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text("# Debug routing rules - not tracked\n*\n!.gitignore\n")
            
            # Write debug log using timestamp utility
            timestamp = filename_timestamp(utc=True, include_seconds=True)
            debug_path = debug_dir / f"{rule['rule_id']}_{timestamp}.yaml"
            
            debug_content = {
                "rule": rule,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "debug": True
            }
            save_yaml_file(debug_path, debug_content, create_dirs=False, atomic=False)
            
            logger.debug(f"Logged ephemeral rule for debugging: {debug_path}")
        except Exception as e:
            logger.debug(f"Failed to log ephemeral rule: {e}")
    
    async def restore_rules_from_yaml(self) -> List[Dict[str, Any]]:
        """Restore persistent rules from YAML files using ksi_common utilities."""
        restored_rules = []
        
        if not config.routes_dir.exists():
            logger.info("No routes directory found")
            return restored_rules
        
        # Walk through YAML files in routes directory (skip debug subdirectory)
        for yaml_file in config.routes_dir.glob("*.yaml"):
            try:
                content = load_yaml_file(yaml_file)
                if content and "rule" in content:
                    rule = content["rule"]
                    rule["persistence_class"] = "persistent"
                    rule["restored_from"] = str(yaml_file)
                    restored_rules.append(rule)
                    logger.info(f"Restored rule from YAML: {rule['rule_id']}")
            except Exception as e:
                logger.error(f"Failed to restore rule from {yaml_file}: {e}")
        
        return restored_rules
    
    async def restore_ephemeral_rules(self) -> List[Dict[str, Any]]:
        """Restore non-expired ephemeral rules from state."""
        # Query non-expired ephemeral rules
        current_time = datetime.now(timezone.utc).isoformat()
        
        result = await self.router.emit("state:entity:query", {
            "type": self.ENTITY_TYPE,
            "where": {
                "persistence_class": "ephemeral",
                "$or": [
                    {"expires_at": None},  # No expiry
                    {"expires_at": {">=": current_time}}  # Not expired
                ]
            }
        })
        
        response = extract_single_response(result)
        if response and response.get("status") == "success":
            entities = response.get("entities", [])
            rules = []
            for entity in entities:
                if "properties" in entity and "rule_config" in entity["properties"]:
                    rule = entity["properties"]["rule_config"]
                    rule["restored_from"] = "state"
                    rules.append(rule)
                    logger.info(f"Restored ephemeral rule from state: {rule['rule_id']}")
            return rules
        return []