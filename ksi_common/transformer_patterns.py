#!/usr/bin/env python3
"""
Transformer Patterns - Shared utilities for common transformer configurations.

Provides reusable patterns to eliminate duplication in transformer YAML files:
- Common mapping patterns
- Standard condition expressions  
- Event broadcasting templates
- State update patterns
- Error handling templates
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json

@dataclass
class TransformerPattern:
    """Base class for reusable transformer patterns."""
    name: str
    description: str
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        """Convert pattern to YAML-serializable dictionary."""
        raise NotImplementedError

@dataclass 
class BroadcastPattern(TransformerPattern):
    """Pattern for broadcasting events to monitor system."""
    source_event: str
    event_data_mapping: Dict[str, Any]
    originator_agent: str = "system"
    subscription_required: bool = False
    category: Optional[str] = None
    severity: Optional[str] = None
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        broadcast_metadata = {
            "originator_agent": self.originator_agent,
            "timestamp": "{{timestamp_utc()}}",
            "subscription_required": self.subscription_required
        }
        if self.category:
            broadcast_metadata["category"] = self.category
        if self.severity:
            broadcast_metadata["severity"] = self.severity
            
        return {
            "name": f"{self.source_event}_broadcast",
            "source": self.source_event,
            "target": "monitor:broadcast_event",
            "mapping": {
                "event_name": self.source_event,
                "event_data": self.event_data_mapping,
                "broadcast_metadata": broadcast_metadata
            },
            "description": f"Broadcast {self.source_event} events for monitoring"
        }

@dataclass
class StateUpdatePattern(TransformerPattern):
    """Pattern for updating entity state."""
    source_event: str
    entity_type: str
    entity_id_field: str
    updates: Dict[str, Any]
    operation: str = "update"
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        return {
            "name": f"{self.source_event}_state_update",
            "source": self.source_event,
            "target": "state:entity:update",
            "mapping": {
                "entity_type": self.entity_type,
                "entity_id": f"{{{{{self.entity_id_field}}}}}",
                "updates": self.updates,
                "operation": self.operation,
                "context": "{{_ksi_context}}"
            },
            "description": f"Update {self.entity_type} state on {self.source_event}"
        }

@dataclass
class ErrorRoutingPattern(TransformerPattern):
    """Pattern for routing errors to centralized error handling."""
    source_event: str
    error_type: str
    target_event: str = "event:error"
    critical_condition: Optional[str] = None
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        mapping = {
            "source_event": self.source_event,
            "error": "{{error}}",
            "error_type": self.error_type,
            "timestamp": "{{timestamp_utc()}}",
            "context": "{{_ksi_context}}"
        }
        
        transformer = {
            "name": f"{self.source_event}_error_routing",
            "source": self.source_event,
            "target": self.target_event,
            "mapping": mapping,
            "description": f"Route {self.source_event} errors to centralized error handling"
        }
        
        if self.critical_condition:
            transformer["condition"] = self.critical_condition
            
        return transformer

@dataclass
class CleanupPattern(TransformerPattern):
    """Pattern for resource cleanup after completion."""
    source_event: str
    cleanup_type: str
    resources_to_clean: List[str]
    cleanup_delay: int = 300
    force_cleanup: bool = False
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        return {
            "name": f"{self.source_event}_cleanup",
            "source": self.source_event,
            "target": "system:cleanup",
            "async": True,
            "mapping": {
                "cleanup_type": self.cleanup_type,
                "resources_to_clean": self.resources_to_clean,
                "cleanup_delay": self.cleanup_delay,
                "force_cleanup": self.force_cleanup,
                "source_event": self.source_event,
                "timestamp": "{{timestamp_utc()}}"
            },
            "description": f"Schedule resource cleanup after {self.source_event}"
        }

@dataclass
class ConditionalRoutingPattern(TransformerPattern):
    """Pattern for conditional event routing based on status."""
    source_event: str
    routes: List[Dict[str, Any]]  # List of {condition, target, mapping}
    
    def to_yaml_dict(self) -> List[Dict[str, Any]]:
        """Returns list of transformers for each route."""
        transformers = []
        for i, route in enumerate(self.routes):
            transformer = {
                "name": f"{self.source_event}_route_{i}",
                "source": self.source_event,
                "target": route["target"],
                "condition": route["condition"],
                "mapping": route["mapping"],
                "description": f"Route {self.source_event} to {route['target']} when {route['condition']}"
            }
            transformers.append(transformer)
        return transformers

class CommonConditions:
    """Library of common condition expressions."""
    
    # Status-based conditions
    SUCCESS = "status == 'success'"
    ERROR = "status == 'error'"
    COMPLETED = "status == 'completed'"
    FAILED = "status == 'failed'"
    CANCELLED = "status == 'cancelled'"
    
    # Agent-related conditions
    HAS_AGENT_ID = "_ksi_context.agent_id exists"
    HAS_ORCHESTRATION_ID = "_ksi_context.orchestration_id exists"
    IS_AGENT_EVENT = "_ksi_context.agent_id exists and _ksi_context.agent_id != 'system'"
    
    # Error severity conditions
    CRITICAL_ERROR = "severity == 'critical' or error_type in ['system_failure', 'data_corruption', 'security_breach']"
    RECOVERABLE_ERROR = "error_type in ['timeout', 'rate_limit', 'temporary_failure'] and retry_count < 3"
    
    # Retry conditions
    RETRY_ELIGIBLE = "retry_count < 3 and error_type in ['timeout', 'rate_limit', 'connection_error']"
    MAX_RETRIES_REACHED = "retry_count >= 3"
    
    # Orchestration conditions
    IS_COORDINATOR = "is_coordinator(agent_id)"
    IS_SUBORDINATE = "is_subordinate(agent_id)"
    SAME_ORCHESTRATION = "source_orchestration_id == target_orchestration_id"

class CommonMappings:
    """Library of common mapping patterns."""
    
    @staticmethod
    def pass_through() -> str:
        """Pass all data through unchanged."""
        return "{{$}}"
    
    @staticmethod
    def with_timestamp() -> Dict[str, Any]:
        """Add timestamp to existing data."""
        return {
            "{{$}}": "{{$}}",
            "timestamp": "{{timestamp_utc()}}"
        }
    
    @staticmethod
    def agent_context() -> Dict[str, Any]:
        """Standard agent context fields."""
        return {
            "agent_id": "{{agent_id}}",
            "orchestration_id": "{{_ksi_context.orchestration_id}}",
            "timestamp": "{{timestamp_utc()}}",
            "context": "{{_ksi_context}}"
        }
    
    @staticmethod
    def error_mapping(error_type: str) -> Dict[str, Any]:
        """Standard error mapping."""
        return {
            "error": "{{error}}",
            "error_type": error_type,
            "timestamp": "{{timestamp_utc()}}",
            "context": "{{_ksi_context}}",
            "stack_trace": "{{stack_trace}}"
        }
    
    @staticmethod
    def completion_mapping() -> Dict[str, Any]:
        """Standard completion event mapping."""
        return {
            "request_id": "{{request_id}}",
            "agent_id": "{{agent_id}}",
            "status": "{{status}}",
            "completion_time": "{{timestamp_utc()}}",
            "context": "{{_ksi_context}}"
        }

class TransformerTemplateBuilder:
    """Builder for creating transformer configurations from patterns."""
    
    def __init__(self):
        self.transformers: List[Dict[str, Any]] = []
    
    def add_broadcast(self, source_event: str, event_data_mapping: Dict[str, Any], **kwargs) -> 'TransformerTemplateBuilder':
        """Add a broadcast pattern."""
        pattern = BroadcastPattern(
            name=f"{source_event}_broadcast",
            description=f"Broadcast {source_event} events",
            source_event=source_event,
            event_data_mapping=event_data_mapping,
            **kwargs
        )
        self.transformers.append(pattern.to_yaml_dict())
        return self
    
    def add_state_update(self, source_event: str, entity_type: str, entity_id_field: str, updates: Dict[str, Any], **kwargs) -> 'TransformerTemplateBuilder':
        """Add a state update pattern."""
        pattern = StateUpdatePattern(
            name=f"{source_event}_state_update",
            description=f"Update {entity_type} state",
            source_event=source_event,
            entity_type=entity_type,
            entity_id_field=entity_id_field,
            updates=updates,
            **kwargs
        )
        self.transformers.append(pattern.to_yaml_dict())
        return self
    
    def add_error_routing(self, source_event: str, error_type: str, **kwargs) -> 'TransformerTemplateBuilder':
        """Add an error routing pattern."""
        pattern = ErrorRoutingPattern(
            name=f"{source_event}_error_routing",
            description=f"Route {source_event} errors",
            source_event=source_event,
            error_type=error_type,
            **kwargs
        )
        self.transformers.append(pattern.to_yaml_dict())
        return self
    
    def add_cleanup(self, source_event: str, cleanup_type: str, resources: List[str], **kwargs) -> 'TransformerTemplateBuilder':
        """Add a cleanup pattern."""
        pattern = CleanupPattern(
            name=f"{source_event}_cleanup",
            description=f"Cleanup after {source_event}",
            source_event=source_event,
            cleanup_type=cleanup_type,
            resources_to_clean=resources,
            **kwargs
        )
        self.transformers.append(pattern.to_yaml_dict())
        return self
    
    def add_conditional_routing(self, source_event: str, routes: List[Dict[str, Any]]) -> 'TransformerTemplateBuilder':
        """Add conditional routing patterns."""
        pattern = ConditionalRoutingPattern(
            name=f"{source_event}_conditional_routing",
            description=f"Conditional routing for {source_event}",
            source_event=source_event,
            routes=routes
        )
        transformers = pattern.to_yaml_dict()
        if isinstance(transformers, list):
            self.transformers.extend(transformers)
        else:
            self.transformers.append(transformers)
        return self
    
    def build(self) -> List[Dict[str, Any]]:
        """Build the transformer list."""
        return self.transformers
    
    def to_yaml_config(self) -> Dict[str, Any]:
        """Build as YAML configuration."""
        return {
            "transformers": self.transformers
        }

# Convenience functions for common patterns
def create_service_transformers(service_name: str) -> TransformerTemplateBuilder:
    """Create a builder pre-configured for a service."""
    return TransformerTemplateBuilder()

def create_agent_lifecycle_transformers() -> List[Dict[str, Any]]:
    """Create standard agent lifecycle transformers."""
    return (TransformerTemplateBuilder()
        .add_broadcast("agent:spawned", CommonMappings.agent_context(), category="agent_lifecycle")
        .add_broadcast("agent:terminated", CommonMappings.agent_context(), category="agent_lifecycle")
        .add_state_update("agent:spawned", "agent", "agent_id", {"status": "active", "spawned_at": "{{timestamp_utc()}}"})
        .add_state_update("agent:terminated", "agent", "agent_id", {"status": "terminated", "terminated_at": "{{timestamp_utc()}}"})
        .add_cleanup("agent:terminated", "agent_resources", ["sandbox", "sessions", "temp_files"])
        .build())

def create_completion_transformers() -> List[Dict[str, Any]]:
    """Create standard completion transformers."""
    routes = [
        {"condition": CommonConditions.SUCCESS, "target": "completion:result", "mapping": CommonMappings.pass_through()},
        {"condition": CommonConditions.ERROR, "target": "completion:error", "mapping": CommonMappings.error_mapping("completion_error")},
        {"condition": CommonConditions.CANCELLED, "target": "completion:cancelled", "mapping": CommonMappings.completion_mapping()}
    ]
    
    return (TransformerTemplateBuilder()
        .add_conditional_routing("completion:internal_result", routes)
        .add_broadcast("completion:result", CommonMappings.completion_mapping(), category="completion")
        .add_broadcast("completion:error", CommonMappings.error_mapping("completion_error"), category="completion", severity="error")
        .build())