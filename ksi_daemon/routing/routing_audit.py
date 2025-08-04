#!/usr/bin/env python3
"""
Routing Audit Trail

Tracks all routing decisions, rule changes, and system events for debugging
and analysis of the dynamic routing system.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from collections import deque
import json

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import get_router

logger = get_bound_logger("routing_audit")


class RoutingAuditTrail:
    """
    Maintains an audit trail of all routing system activities.
    
    Tracks:
    - Rule lifecycle (create/modify/delete)
    - Routing decisions
    - Performance metrics
    - Validation results
    - Permission checks
    - System events
    """
    
    def __init__(self, max_entries: int = 10000, persist_interval: int = 300):
        """
        Initialize the audit trail.
        
        Args:
            max_entries: Maximum number of entries to keep in memory
            persist_interval: Seconds between persistence to state
        """
        self.max_entries = max_entries
        self.persist_interval = persist_interval
        
        # In-memory audit log (circular buffer)
        self.audit_log = deque(maxlen=max_entries)
        
        # Performance metrics
        self.metrics = {
            "total_events": 0,
            "rule_changes": 0,
            "routing_decisions": 0,
            "validation_failures": 0,
            "permission_denials": 0,
            "conflicts_detected": 0,
            "ttl_expirations": 0
        }
        
        # Persistence task
        self._persist_task = None
        
        self.logger = logger
    
    async def initialize(self):
        """Initialize the audit trail and start persistence task."""
        # Start persistence task
        self._persist_task = asyncio.create_task(self._persist_periodically())
        logger.info("Routing audit trail initialized")
    
    async def shutdown(self):
        """Shutdown the audit trail and persist final state."""
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
        
        # Final persistence
        await self._persist_to_state()
        logger.info("Routing audit trail shutdown complete")
    
    def log_rule_change(self, action: str, rule_id: str, rule: Dict[str, Any],
                       actor: str, result: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
        """Log a rule lifecycle event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "rule_change",
            "action": action,  # create, modify, delete
            "rule_id": rule_id,
            "rule": rule,
            "actor": actor,
            "result": result,
            "success": result.get("status") == "success",
            "context": self._extract_context(context)
        }
        
        self._add_entry(entry)
        self.metrics["rule_changes"] += 1
    
    def log_routing_decision(self, event_name: str, matched_rules: List[Dict[str, Any]],
                           selected_rule: Optional[Dict[str, Any]], context: Optional[Dict[str, Any]] = None):
        """Log a routing decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "routing_decision",
            "event_name": event_name,
            "matched_rules_count": len(matched_rules),
            "matched_rules": [{"rule_id": r["rule_id"], "priority": r["priority"]} for r in matched_rules],
            "selected_rule": {"rule_id": selected_rule["rule_id"], "priority": selected_rule["priority"]} if selected_rule else None,
            "context": self._extract_context(context)
        }
        
        self._add_entry(entry)
        self.metrics["routing_decisions"] += 1
    
    def log_validation_result(self, rule: Dict[str, Any], valid: bool, 
                            errors: Optional[str], conflicts: List[Dict[str, Any]],
                            actor: str, context: Optional[Dict[str, Any]] = None):
        """Log a validation result."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "validation",
            "rule": rule,
            "valid": valid,
            "errors": errors,
            "conflicts": conflicts,
            "high_severity_conflicts": len([c for c in conflicts if c.get("severity") == "high"]),
            "actor": actor,
            "context": self._extract_context(context)
        }
        
        self._add_entry(entry)
        if not valid:
            self.metrics["validation_failures"] += 1
        if conflicts:
            self.metrics["conflicts_detected"] += 1
    
    def log_permission_check(self, actor: str, action: str, allowed: bool,
                           reason: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Log a permission check."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "permission_check",
            "actor": actor,
            "action": action,
            "allowed": allowed,
            "reason": reason,
            "context": self._extract_context(context)
        }
        
        self._add_entry(entry)
        if not allowed:
            self.metrics["permission_denials"] += 1
    
    def log_ttl_expiration(self, rule_id: str, rule: Dict[str, Any]):
        """Log a TTL expiration event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "ttl_expiration",
            "rule_id": rule_id,
            "rule": rule,
            "ttl_seconds": rule.get("ttl"),
            "created_at": rule.get("created_at"),
            "expired_after_seconds": self._calculate_lifetime(rule)
        }
        
        self._add_entry(entry)
        self.metrics["ttl_expirations"] += 1
    
    def log_system_event(self, event_type: str, details: Dict[str, Any]):
        """Log a system event (startup, shutdown, errors, etc)."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "system_event",
            "event_type": event_type,
            "details": details
        }
        
        self._add_entry(entry)
    
    async def query_audit_log(self, filter_params: Optional[Dict[str, Any]] = None,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query the audit log with optional filters.
        
        Filter parameters:
        - type: Entry type (rule_change, routing_decision, etc)
        - actor: Actor who performed action
        - rule_id: Specific rule ID
        - since: ISO timestamp for time range
        - success: Boolean for filtering by success/failure
        """
        entries = list(self.audit_log)
        
        # Apply filters
        if filter_params:
            if "type" in filter_params:
                entries = [e for e in entries if e["type"] == filter_params["type"]]
            
            if "actor" in filter_params:
                entries = [e for e in entries if e.get("actor") == filter_params["actor"]]
            
            if "rule_id" in filter_params:
                entries = [e for e in entries if e.get("rule_id") == filter_params["rule_id"]]
            
            if "since" in filter_params:
                since_time = datetime.fromisoformat(filter_params["since"].replace('Z', '+00:00'))
                entries = [e for e in entries 
                          if datetime.fromisoformat(e["timestamp"].replace('Z', '+00:00')) >= since_time]
            
            if "success" in filter_params:
                entries = [e for e in entries if e.get("success") == filter_params["success"]]
        
        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda e: e["timestamp"], reverse=True)
        
        # Apply limit
        if isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                limit = 100
        
        return entries[:limit]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current audit metrics."""
        return {
            "metrics": self.metrics.copy(),
            "audit_log_size": len(self.audit_log),
            "oldest_entry": self.audit_log[0]["timestamp"] if self.audit_log else None,
            "newest_entry": self.audit_log[-1]["timestamp"] if self.audit_log else None
        }
    
    def _add_entry(self, entry: Dict[str, Any]):
        """Add entry to audit log."""
        self.audit_log.append(entry)
        self.metrics["total_events"] += 1
    
    def _extract_context(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract relevant context information."""
        if not context:
            return {}
        
        return {
            "request_id": context.get("_request_id"),
            "correlation_id": context.get("_correlation_id"),
            "client_id": context.get("_client_id"),
            "agent_id": context.get("_agent_id")
        }
    
    def _calculate_lifetime(self, rule: Dict[str, Any]) -> Optional[float]:
        """Calculate how long a rule lived before expiration."""
        if not rule.get("created_at"):
            return None
        
        try:
            created = datetime.fromisoformat(rule["created_at"].replace('Z', '+00:00'))
            expired = datetime.now(timezone.utc)
            return (expired - created).total_seconds()
        except:
            return None
    
    async def _persist_periodically(self):
        """Periodically persist audit data to state system."""
        while True:
            try:
                await asyncio.sleep(self.persist_interval)
                await self._persist_to_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error persisting audit data: {e}")
    
    async def _persist_to_state(self):
        """Persist audit data to state system."""
        # Get router for state operations
        router = get_router()
        if not router:
            return
        
        # Create audit summary
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": self.metrics.copy(),
            "recent_entries": list(self.audit_log)[-100:],  # Last 100 entries
            "audit_log_size": len(self.audit_log)
        }
        
        # Store in state system
        try:
            await router.emit("state:entity:update", {
                "type": "routing_audit",
                "id": "current",
                "properties": {
                    "summary": json.dumps(summary),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            })
            
            logger.debug("Persisted audit data to state")
        except Exception as e:
            logger.error(f"Failed to persist audit data: {e}")


# Global audit trail instance
_audit_trail: Optional[RoutingAuditTrail] = None


def get_audit_trail() -> Optional[RoutingAuditTrail]:
    """Get the global audit trail instance."""
    return _audit_trail


async def initialize_audit_trail():
    """Initialize the global audit trail."""
    global _audit_trail
    _audit_trail = RoutingAuditTrail()
    await _audit_trail.initialize()
    return _audit_trail