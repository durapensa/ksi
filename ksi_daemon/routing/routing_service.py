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
from ksi_daemon.event_system import event_handler, get_router

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
        
        # Routing rule storage (will move to state system)
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
        
        logger.info("RoutingService initialized")
    
    async def initialize(self):
        """Initialize the routing service."""
        # Load any persisted routing rules
        await self._load_persisted_rules()
        
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
        # TODO: In Stage 1.4, load from state system
        # For now, start with empty rules
        logger.info("Loading persisted routing rules", count=0)
    
    async def _persist_rules(self):
        """Persist routing rules to storage."""
        # TODO: In Stage 1.4, save to state system
        logger.info("Persisting routing rules", count=len(self.routing_rules))
    
    async def _manage_ttl(self):
        """Background task to manage rule TTLs."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.utcnow()
                expired_rules = []
                
                for rule_id, rule in self.routing_rules.items():
                    if rule.get("ttl") and rule.get("expires_at"):
                        expires_at = datetime.fromisoformat(rule["expires_at"])
                        if now > expires_at:
                            expired_rules.append(rule_id)
                
                # Remove expired rules
                for rule_id in expired_rules:
                    await self._remove_rule(rule_id, reason="TTL expired")
                    self.metrics["rules_expired"] += 1
                
                if expired_rules:
                    logger.info("Expired routing rules", count=len(expired_rules))
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in TTL management", error=str(e))
    
    async def add_routing_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new routing rule to the system.
        
        This method will be called by the event handlers and will
        integrate with the transformer system in Stage 1.2.
        """
        rule_id = rule["rule_id"]
        
        # Calculate expiration if TTL is set
        if rule.get("ttl"):
            expires_at = datetime.utcnow() + timedelta(seconds=rule["ttl"])
            rule["expires_at"] = expires_at.isoformat()
        
        # Store rule
        self.routing_rules[rule_id] = rule
        self.metrics["rules_created"] += 1
        
        # TODO: In Stage 1.2, register with transformer system
        # For now, just log
        logger.info("Routing rule added",
                   rule_id=rule_id,
                   source_pattern=rule["source_pattern"],
                   target=rule["target"])
        
        return {"status": "success", "rule_id": rule_id}
    
    async def modify_routing_rule(self, rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Modify an existing routing rule."""
        if rule_id not in self.routing_rules:
            return {"status": "error", "error": "Rule not found"}
        
        rule = self.routing_rules[rule_id]
        
        # Apply updates
        for key, value in updates.items():
            if key not in ["rule_id", "created_by", "created_at"]:
                rule[key] = value
        
        # Update TTL if changed
        if "ttl" in updates:
            if updates["ttl"]:
                expires_at = datetime.utcnow() + timedelta(seconds=updates["ttl"])
                rule["expires_at"] = expires_at.isoformat()
            else:
                rule.pop("expires_at", None)
        
        self.metrics["rules_modified"] += 1
        
        # TODO: In Stage 1.2, update transformer system
        
        logger.info("Routing rule modified", rule_id=rule_id)
        
        return {"status": "success", "rule_id": rule_id}
    
    async def _remove_rule(self, rule_id: str, reason: str = "deleted") -> Dict[str, Any]:
        """Remove a routing rule."""
        if rule_id not in self.routing_rules:
            return {"status": "error", "error": "Rule not found"}
        
        # Remove rule
        rule = self.routing_rules.pop(rule_id)
        self.metrics["rules_deleted"] += 1
        
        # TODO: In Stage 1.2, remove from transformer system
        
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

# Service initialization function
def create_service(event_emitter=None) -> RoutingService:
    """Create and return a RoutingService instance."""
    return RoutingService(event_emitter)