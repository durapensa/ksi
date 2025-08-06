#!/usr/bin/env python3
"""
Transformer Integration for Dynamic Routing

Bridges the routing service with the transformer system, converting
routing rules into transformer configurations that control event flow.
"""

from typing import Dict, Any, List, Optional
import asyncio
import json

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import get_router

logger = get_bound_logger("routing_transformer", version="1.0.0")

class RoutingTransformerBridge:
    """
    Bridges routing rules with the transformer system.
    
    This class manages the conversion of routing rules to transformer
    configurations and ensures they are applied to the event system.
    """
    
    def __init__(self, routing_service):
        self.routing_service = routing_service
        self._router = None
        self._applied_rules: Dict[str, str] = {}  # rule_id -> transformer name
        
    def _get_router(self):
        """Get cached router instance."""
        if self._router is None:
            self._router = get_router()
        return self._router
    
    def routing_rule_to_transformer(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a routing rule to transformer configuration.
        
        Args:
            rule: Routing rule dictionary with fields:
                - rule_id: Unique identifier
                - source_pattern: Event pattern to match
                - target: Target event to route to
                - condition: Optional condition expression
                - mapping: Optional data transformation
                - priority: Rule priority (higher = more important)
                
        Returns:
            Transformer configuration dictionary
        """
        # Default mapping if none provided - pass all data through
        mapping = rule.get("mapping", {"{{$}}": "{{$}}"})
        
        # Build transformer config
        transformer = {
            "name": f"dynamic_route_{rule['rule_id']}",
            "source": rule["source_pattern"],
            "target": rule["target"],
            "description": f"Dynamic routing rule: {rule['source_pattern']} -> {rule['target']}",
            "dynamic": True,  # Mark as dynamically created
            "routing_rule_id": rule["rule_id"]  # Track source rule
        }
        
        # Add optional fields
        if rule.get("condition"):
            transformer["condition"] = rule["condition"]
            
        if mapping:
            transformer["mapping"] = mapping
            
        # Add priority as metadata (transformer system doesn't use priority yet)
        transformer["_priority"] = rule.get("priority", 100)
        
        return transformer
    
    async def apply_routing_rule(self, rule: Dict[str, Any]) -> bool:
        """
        Apply a routing rule by registering it as a transformer.
        
        Args:
            rule: Routing rule to apply
            
        Returns:
            True if successfully applied, False otherwise
        """
        try:
            # Convert to transformer
            transformer = self.routing_rule_to_transformer(rule)
            
            # Add introspection metadata to transformer
            transformer["_routing_rule"] = rule  # Attach original rule for introspection
            transformer["_routing_introspection"] = True  # Flag for introspection tracking
            
            # Register with router
            router = self._get_router()
            router.register_transformer_from_yaml(transformer)
            
            # Track applied transformer by name
            self._applied_rules[rule["rule_id"]] = transformer["name"]
            
            logger.info(f"Applied routing rule {rule['rule_id']}: {rule['source_pattern']} -> {rule['target']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply routing rule {rule.get('rule_id')}: {e}")
            return False
    
    async def remove_routing_rule(self, rule_id: str) -> bool:
        """
        Remove a routing rule's transformer.
        
        Args:
            rule_id: ID of rule to remove
            
        Returns:
            True if successfully removed, False otherwise
        """
        try:
            # Check if we have this rule applied
            if rule_id not in self._applied_rules:
                logger.warning(f"Routing rule {rule_id} not found in applied rules")
                return False
            
            # Get transformer name
            transformer_name = self._applied_rules[rule_id]
            
            # Unregister specific transformer by name (not source pattern)
            # This allows multiple rules to share the same source pattern
            router = self._get_router()
            success = router.unregister_transformer_by_name(transformer_name)
            
            if not success:
                logger.error(f"Failed to unregister transformer by name: {transformer_name}")
                return False
            
            # Remove from tracking
            del self._applied_rules[rule_id]
            
            logger.info(f"Removed routing rule {rule_id} (transformer: {transformer_name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove routing rule {rule_id}: {e}")
            return False
    
    async def sync_all_rules(self):
        """
        Synchronize all routing rules with the transformer system.
        
        This is called on startup and can be used to refresh all rules.
        """
        logger.info("Syncing all routing rules with transformer system")
        
        # Get all current rules
        rules = self.routing_service.routing_rules
        
        # Clear existing applied rules
        # NOTE: In production, we'd want to be more careful about this
        self._applied_rules.clear()
        
        # Apply each rule
        success_count = 0
        for rule_id, rule in rules.items():
            if await self.apply_routing_rule(rule):
                success_count += 1
        
        logger.info(f"Synced {success_count}/{len(rules)} routing rules")
    
    async def update_routing_rule(self, rule_id: str, rule: Dict[str, Any]) -> bool:
        """
        Update an existing routing rule's transformer.
        
        Args:
            rule_id: ID of rule to update
            rule: Updated rule data
            
        Returns:
            True if successfully updated, False otherwise
        """
        # For now, we remove and re-add
        # In the future, we could be smarter about this
        await self.remove_routing_rule(rule_id)
        return await self.apply_routing_rule(rule)
    
    def get_applied_rules(self) -> Dict[str, str]:
        """Get currently applied routing rules (rule_id -> transformer_name)."""
        return self._applied_rules.copy()