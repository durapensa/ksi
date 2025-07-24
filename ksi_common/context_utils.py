#!/usr/bin/env python3
"""
Context Standardization Utilities for KSI

Provides utilities to standardize context passing between event handlers
and transformers, ensuring consistent access patterns for template substitution.

Key Problems Solved:
1. Templates expect {{_ksi_context.event}} but system provides {{event}}
2. Context structure varies between different parts of the system
3. Template substitution needs unified access to both data and context

Solution: Provide a context wrapper that supports both access patterns
and utilities to standardize context before template processing.
"""

from typing import Dict, Any, Optional, Union
import copy


class ContextWrapper:
    """
    Wraps context and data to provide unified access patterns for templates.
    
    Supports both direct access ({{event}}) and nested access ({{_ksi_context.event}}).
    This allows templates to work regardless of which pattern they use.
    """
    
    def __init__(self, data: Dict[str, Any], context: Dict[str, Any]):
        self.data = data or {}
        self.context = context or {}
        self._merged = None
        
    def get_merged_context(self) -> Dict[str, Any]:
        """
        Get a merged context suitable for template substitution.
        
        Returns a dictionary that supports both access patterns:
        - Direct: {{event}}, {{_agent_id}}
        - Nested: {{_ksi_context.event}}, {{_ksi_context._agent_id}}
        """
        if self._merged is None:
            # Start with a copy of the data
            self._merged = copy.deepcopy(self.data)
            
            # Add context fields at root level for direct access
            for key, value in self.context.items():
                if key not in self._merged and not key.startswith('_'):
                    self._merged[key] = value
            
            # Create _ksi_context structure for nested access
            ksi_context = {}
            
            # Add event name if present in context
            if 'event' in self.context:
                ksi_context['event'] = self.context['event']
            
            # Add standard context fields
            context_fields = [
                '_event_id', '_correlation_id', '_parent_event_id',
                '_root_event_id', '_event_depth', '_agent_id',
                '_client_id', '_request_id', 'event'
            ]
            
            for field in context_fields:
                if field in self.context:
                    ksi_context[field] = self.context[field]
            
            # If data already has _ksi_context, merge it
            if '_ksi_context' in self.data:
                existing = self.data['_ksi_context']
                if isinstance(existing, dict):
                    ksi_context.update(existing)
            
            # Store the complete _ksi_context
            if ksi_context:
                self._merged['_ksi_context'] = ksi_context
            
            # Also ensure direct access to common fields
            for field in ['_agent_id', '_event_id', '_correlation_id']:
                if field in self.context and field not in self._merged:
                    self._merged[field] = self.context[field]
                    
        return self._merged


def standardize_context_for_transformer(
    data: Dict[str, Any], 
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Standardize context for transformer template substitution.
    
    This function ensures that templates can access context variables
    using either pattern:
    - {{event}} - direct access
    - {{_ksi_context.event}} - nested access
    
    Args:
        data: The event data
        context: The event context (containing event name, router, etc.)
        
    Returns:
        A merged context suitable for template substitution
    """
    wrapper = ContextWrapper(data, context or {})
    return wrapper.get_merged_context()


def prepare_transformer_context(
    event: str,
    data: Dict[str, Any],
    router_context: Optional[Dict[str, Any]] = None
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Prepare data and context for transformer processing.
    
    Args:
        event: The event name
        data: The event data
        router_context: The router's context dictionary
        
    Returns:
        Tuple of (prepared_data, ksi_context) suitable for apply_mapping
    """
    # Ensure we have a context
    context = router_context or {}
    
    # Always include the event name in context
    if 'event' not in context:
        context['event'] = event
    
    # Create the ksi_context structure for template access
    ksi_context = {
        'event': event,
        '_event_id': context.get('_event_id'),
        '_correlation_id': context.get('_correlation_id'),
        '_parent_event_id': context.get('_parent_event_id'),
        '_root_event_id': context.get('_root_event_id'),
        '_event_depth': context.get('_event_depth', 0),
        '_agent_id': context.get('_agent_id', 'system'),
        '_client_id': context.get('_client_id'),
    }
    
    # Remove None values
    ksi_context = {k: v for k, v in ksi_context.items() if v is not None}
    
    return data, ksi_context


def extract_ksi_context_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract KSI context from event data.
    
    Handles both embedded context and context references.
    
    Args:
        data: Event data that may contain _ksi_context
        
    Returns:
        The extracted context dictionary
    """
    ksi_context = data.get('_ksi_context', {})
    
    # If it's a string reference, return empty dict
    # (would need context manager to resolve)
    if isinstance(ksi_context, str):
        return {}
    
    # If it's a dict, return it
    if isinstance(ksi_context, dict):
        return ksi_context
    
    return {}


def merge_contexts(
    base_context: Dict[str, Any],
    override_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge two context dictionaries, with override taking precedence.
    
    Args:
        base_context: The base context
        override_context: Context values to override
        
    Returns:
        Merged context dictionary
    """
    merged = copy.deepcopy(base_context)
    merged.update(override_context)
    return merged


# Compatibility function for existing code
def get_template_context(
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get a context suitable for template substitution.
    
    This is a compatibility wrapper around standardize_context_for_transformer.
    
    Args:
        data: Event data
        context: Event context
        
    Returns:
        Merged context for templates
    """
    return standardize_context_for_transformer(data, context)


# Export public API
__all__ = [
    'ContextWrapper',
    'standardize_context_for_transformer',
    'prepare_transformer_context',
    'extract_ksi_context_from_data',
    'merge_contexts',
    'get_template_context',
]