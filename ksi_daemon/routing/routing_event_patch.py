#!/usr/bin/env python3
"""
Routing Event System Patch

Enhances the event system with routing introspection capabilities by patching
the emit method to track routing decisions.
"""

import asyncio
from typing import Dict, Any, List, Optional
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("routing_event_patch", version="1.0.0")


def patch_event_router_for_introspection():
    """
    Patch the EventRouter class to add routing introspection.
    
    This should be called during routing service initialization.
    """
    from ksi_daemon.event_system import EventRouter
    from .routing_introspection import track_routing_decision, enhance_event_with_routing_metadata
    
    # Store original emit method
    original_emit = EventRouter.emit
    
    async def emit_with_routing_introspection(self, event: str, data: Optional[Dict[str, Any]] = None, 
                                             context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Enhanced emit that tracks routing decisions."""
        # Store current event for condition evaluation
        self._current_event = event
        
        # Track routing decisions if we have transformers
        routing_rules_evaluated = []
        routing_rules_matched = []
        routing_rule_applied = None
        transformation_applied = None
        routing_decision_id = None
        
        # Check for dynamic transformers first
        transformers = []
        if event in self._transformers:
            transformers.extend(self._transformers[event])
            logger.debug(f"Found {len(self._transformers[event])} direct transformers for {event}")
        
        # Also check pattern transformers
        for pattern, transformer_def in self._pattern_transformers:
            if self._matches_pattern(event, pattern):
                transformers.append(transformer_def)
                logger.debug(f"Pattern {pattern} matched event {event}")
        
        # Track routing introspection if we have routing transformers
        has_routing_transformers = any(t.get("_routing_introspection") for t in transformers)
        
        if has_routing_transformers and transformers:
            # Extract event ID from context if available
            event_id = context.get("_event_id") if context else None
            if not event_id and isinstance(data, dict):
                # Try to get from _ksi_context in data
                ksi_context = data.get("_ksi_context", {})
                if isinstance(ksi_context, dict):
                    event_id = ksi_context.get("_event_id")
            
            # Evaluate all routing rules
            for transformer in transformers:
                if transformer.get("_routing_introspection"):
                    rule = transformer.get("_routing_rule", {})
                    rule_info = {
                        "rule_id": rule.get("rule_id"),
                        "source_pattern": rule.get("source_pattern"),
                        "target": rule.get("target"),
                        "priority": rule.get("priority", 100),
                        "condition": rule.get("condition")
                    }
                    routing_rules_evaluated.append(rule_info)
                    
                    # Check if this transformer will match
                    should_transform = True
                    if 'condition' in transformer:
                        # Evaluate condition
                        if not self._evaluate_condition(transformer['condition'], data):
                            should_transform = False
                    
                    if should_transform:
                        routing_rules_matched.append(rule_info)
                        # Track the highest priority rule that will be applied
                        rule_priority = int(rule_info["priority"]) if isinstance(rule_info["priority"], (int, str)) else 100
                        current_priority = int(routing_rule_applied["priority"]) if routing_rule_applied and isinstance(routing_rule_applied.get("priority"), (int, str)) else 0
                        if not routing_rule_applied or rule_priority > current_priority:
                            routing_rule_applied = rule_info
                            transformation_applied = transformer.get("mapping")
            
            # Track the routing decision
            if routing_rules_evaluated:
                routing_decision_id = track_routing_decision(
                    event_id=event_id or f"unknown_{event}",
                    event_name=event,
                    rules_evaluated=routing_rules_evaluated,
                    rules_matched=routing_rules_matched,
                    rule_applied=routing_rule_applied,
                    transformation_applied=transformation_applied,
                    context=context
                )
        
        # Call original emit method
        result = await original_emit(self, event, data, context)
        
        # If we tracked a routing decision, enhance routed events with metadata
        if routing_decision_id and routing_rule_applied:
            # This is a bit tricky - we need to enhance the data that will be passed
            # to the target event. Since the original emit already happened, we'll
            # need a different approach. For now, log that we would enhance it.
            logger.debug(f"Routing decision {routing_decision_id} tracked for {event}")
        
        return result
    
    # Replace the emit method
    EventRouter.emit = emit_with_routing_introspection
    logger.info("EventRouter patched for routing introspection")


def patch_transformer_context_for_routing():
    """
    Patch transformer context preparation to include routing metadata.
    
    This enhances events with routing decision information.
    """
    try:
        from ksi_daemon.event_system import prepare_transformer_context
        from .routing_introspection import enhance_event_with_routing_metadata
        
        # We can't directly patch this since it's a module-level function
        # Instead, we'll need to modify the transformer processing
        logger.info("Transformer context patching would require event_system.py modification")
        
    except ImportError as e:
        logger.error(f"Failed to import for patching: {e}")


# Simpler approach: Add routing metadata in the transformer itself
def create_routing_aware_transformer(transformer_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a transformer that adds routing metadata to events.
    
    This wraps the mapping to include routing information.
    """
    original_mapping = transformer_def.get("mapping", {})
    
    # Create enhanced mapping that includes routing metadata
    enhanced_mapping = {
        **original_mapping,
        "_ksi_routing.rule_id": f"{{{{routing_rule_id or '{transformer_def.get('routing_rule_id', 'unknown')}'}}}}",
        "_ksi_routing.source_pattern": f"{{{{source_pattern or '{transformer_def.get('source', '')}'}}}}",
        "_ksi_routing.transformation_type": "dynamic"
    }
    
    transformer_def["mapping"] = enhanced_mapping
    return transformer_def