#!/usr/bin/env python3
"""
Dynamic Routing Service

Manages runtime routing rules and integrates with the transformer system
to enable dynamic event routing controlled by agents.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

from ksi_common.logging import get_bound_logger
from ksi_common.checkpoint_participation import checkpoint_participant
from ksi_common.service_lifecycle import service_startup
from ksi_daemon.event_system import event_handler, get_router
from .transformer_integration import RoutingTransformerBridge
from .routing_state_adapter import RoutingStateAdapter

logger = get_bound_logger("routing_service", version="1.0.0")

@checkpoint_participant("routing_service")
class RoutingService:
    """
    Service for managing dynamic routing rules.
    
    This service enables agents to modify event routing at runtime,
    replacing static orchestration patterns with dynamic, adaptive routing.
    """
    
    def __init__(self, event_emitter=None):
        self.event_emitter = event_emitter
        self.service_name = "routing_service"
        
        # State adapter for persistence (Stage 1.4 implementation)
        self.state_adapter = RoutingStateAdapter()
        
        # Routing rule storage (cache - state is source of truth)
        self.routing_rules: Dict[str, Dict[str, Any]] = {}
        self.rule_timers: Dict[str, asyncio.Task] = {}  # For TTL management
        
        # Subscription tracking
        self.agent_subscriptions: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.metrics = {
            "rules_created": 0,
            "rules_modified": 0,
            "rules_deleted": 0,
            "rules_expired": 0,
            "routing_decisions": 0
        }
        
        # Create transformer bridge for routing integration
        self.transformer_bridge = RoutingTransformerBridge(self)
        
        logger.info("RoutingService initialized")
    
    async def initialize(self):
        """Initialize the routing service."""
        # Load any persisted routing rules
        await self._load_persisted_rules()
        
        # Sync all rules with transformer system
        await self.transformer_bridge.sync_all_rules()
        
        # Start TTL management task
        self._ttl_task = asyncio.create_task(self._manage_ttl())
        
        logger.info("RoutingService initialization complete")
    
    async def shutdown(self):
        """Shutdown the routing service."""
        logger.info("RoutingService shutting down")
        
        # Cancel TTL task
        if hasattr(self, '_ttl_task'):
            self._ttl_task.cancel()
            try:
                await self._ttl_task
            except asyncio.CancelledError:
                pass
        
        # Persist current rules
        await self._persist_rules()
        
        logger.info("RoutingService shutdown complete")
    
    async def _load_persisted_rules(self):
        """Load routing rules from persistent storage."""
        # Stage 1.4 implementation: Load from state system
        try:
            rules = await self.state_adapter.list_rules()
            
            # Populate cache and re-apply transformers
            for rule in rules:
                self.routing_rules[rule["rule_id"]] = rule
                
                # Apply transformer for this rule
                if await self.transformer_bridge.apply_routing_rule(rule):
                    logger.debug(f"Re-applied transformer for rule {rule['rule_id']}")
            
            logger.info("Loaded persisted routing rules", count=len(rules))
        except Exception as e:
            logger.error(f"Failed to load routing rules: {e}")
            # Continue with empty rules on error
    
    async def _persist_rules(self):
        """Persist routing rules to storage."""
        # Stage 1.4: Rules are already persisted in state system
        # This method is now a no-op but kept for compatibility
        logger.info("Rules already persisted in state system", count=len(self.routing_rules))
    
    async def _manage_ttl(self):
        """Background task to manage rule TTLs."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check for expired rules using state adapter
                expired_rule_ids = await self.state_adapter.get_expired_rules()
                
                # Remove expired rules
                for rule_id in expired_rule_ids:
                    await self._remove_rule(rule_id, reason="TTL expired")
                    self.metrics["rules_expired"] += 1
                
                if expired_rule_ids:
                    logger.info("Expired routing rules", count=len(expired_rule_ids))
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in TTL management", error=str(e))
    
    async def add_routing_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new routing rule to the system.
        
        Stage 1.4: Rules are now persisted in state system.
        """
        rule_id = rule["rule_id"]
        
        # Store in state system first (source of truth)
        result = await self.state_adapter.create_rule(rule)
        
        if result.get("status") != "success":
            return result
        
        # Update cache
        self.routing_rules[rule_id] = rule
        self.metrics["rules_created"] += 1
        
        # Register with transformer system
        success = await self.transformer_bridge.apply_routing_rule(rule)
        
        if not success:
            # Roll back if transformer registration failed
            del self.routing_rules[rule_id]
            self.metrics["rules_created"] -= 1
            return {"status": "error", "error": "Failed to register transformer"}
        
        logger.info("Routing rule added",
                   rule_id=rule_id,
                   source_pattern=rule["source_pattern"],
                   target=rule["target"])
        
        return {"status": "success", "rule_id": rule_id}
    
    async def modify_routing_rule(self, rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Modify an existing routing rule."""
        # Check cache first for quick validation
        if rule_id not in self.routing_rules:
            # Try to load from state in case cache is out of sync
            rule = await self.state_adapter.get_rule(rule_id)
            if not rule:
                return {"status": "error", "error": "Rule not found"}
            self.routing_rules[rule_id] = rule
        
        # Update in state system (source of truth)
        result = await self.state_adapter.update_rule(rule_id, updates)
        
        if result.get("status") != "success":
            return result
        
        # Update cache
        rule = self.routing_rules[rule_id]
        for key, value in updates.items():
            if key not in ["rule_id", "created_by", "created_at"]:
                rule[key] = value
        
        self.metrics["rules_modified"] += 1
        
        # Update transformer system
        success = await self.transformer_bridge.update_routing_rule(rule_id, rule)
        
        if not success:
            logger.error(f"Failed to update transformer for rule {rule_id}")
            # We still keep the rule updated in our storage
            # This is a design choice - we could also roll back
        
        logger.info("Routing rule modified", rule_id=rule_id)
        
        return {"status": "success", "rule_id": rule_id}
    
    async def _remove_rule(self, rule_id: str, reason: str = "deleted") -> Dict[str, Any]:
        """Remove a routing rule."""
        # Check cache first
        if rule_id not in self.routing_rules:
            # Check state in case cache is out of sync
            rule = await self.state_adapter.get_rule(rule_id)
            if not rule:
                return {"status": "error", "error": "Rule not found"}
        
        # Remove from state system (source of truth)
        result = await self.state_adapter.delete_rule(rule_id)
        
        if result.get("status") != "success":
            return result
        
        # Remove from cache
        if rule_id in self.routing_rules:
            self.routing_rules.pop(rule_id)
        
        self.metrics["rules_deleted"] += 1
        
        # Remove from transformer system
        success = await self.transformer_bridge.remove_routing_rule(rule_id)
        
        if not success:
            logger.error(f"Failed to remove transformer for rule {rule_id}")
        
        logger.info("Routing rule removed", rule_id=rule_id, reason=reason)
        
        return {"status": "success", "rule_id": rule_id}
    
    async def get_applicable_rules(self, event_name: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get all routing rules that apply to a given event.
        
        This will be used by the transformer system to determine routing.
        """
        applicable_rules = []
        
        for rule_id, rule in self.routing_rules.items():
            # Check if pattern matches
            pattern = rule["source_pattern"]
            
            # Simple pattern matching (enhance in Stage 1.5)
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if event_name.startswith(prefix):
                    applicable_rules.append(rule)
            elif pattern == event_name:
                applicable_rules.append(rule)
        
        # Sort by priority (descending)
        applicable_rules.sort(key=lambda r: r.get("priority", 100), reverse=True)
        
        self.metrics["routing_decisions"] += 1
        
        return applicable_rules
    
    async def update_agent_subscription(self, agent_id: str, subscription_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update an agent's subscription configuration."""
        self.agent_subscriptions[agent_id] = {
            "subscription_level": subscription_config.get("subscription_level", 0),
            "error_subscription_level": subscription_config.get("error_subscription_level"),
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": subscription_config.get("updated_by", "system")
        }
        
        logger.info("Agent subscription updated",
                   agent_id=agent_id,
                   subscription_level=subscription_config.get("subscription_level"))
        
        # TODO: In Stage 1.2, update hierarchical routing transformers
        
        return {"status": "success", "agent_id": agent_id}
    
    def collect_checkpoint_data(self) -> Dict[str, Any]:
        """Collect routing state for checkpointing."""
        return {
            "routing_rules": self.routing_rules,
            "agent_subscriptions": self.agent_subscriptions,
            "metrics": self.metrics
        }
    
    def restore_from_checkpoint(self, checkpoint_data: Dict[str, Any]):
        """Restore routing state from checkpoint."""
        self.routing_rules = checkpoint_data.get("routing_rules", {})
        self.agent_subscriptions = checkpoint_data.get("agent_subscriptions", {})
        self.metrics = checkpoint_data.get("metrics", self.metrics)
        
        logger.info("Restored from checkpoint",
                   rules_count=len(self.routing_rules),
                   subscriptions_count=len(self.agent_subscriptions))
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "status": "running",
            "rules_count": len(self.routing_rules),
            "subscriptions_count": len(self.agent_subscriptions),
            "metrics": self.metrics
        }

# Global service instance
_routing_service_instance = None

# Service initialization function
def create_service(event_emitter=None) -> RoutingService:
    """Create and return a RoutingService instance."""
    return RoutingService(event_emitter)

def get_routing_service() -> RoutingService:
    """Get the global routing service instance."""
    return _routing_service_instance

@service_startup("routing_service", load_transformers=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize routing service on startup."""
    global _routing_service_instance
    
    logger.info("Starting routing service...")
    
    # Create service instance
    _routing_service_instance = create_service()
    
    # Initialize the service
    await _routing_service_instance.initialize()
    
    logger.info("Routing service started successfully")
    
    return {
        "status": "started",
        "features": [
            "dynamic_routing",
            "routing_rules", 
            "ttl_management",
            "transformer_integration",
            "audit_trail"
        ]
    }