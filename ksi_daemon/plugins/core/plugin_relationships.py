#!/usr/bin/env python3
"""
Plugin Relationships Discovery Service

Provides runtime discovery of plugin relationships through enhanced introspection:
- Which events each plugin provides and consumes
- State namespace dependencies
- Plugin dependency validation
"""

import json
from typing import Dict, Any, Optional
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata, event_handler
from ksi_daemon.enhanced_introspection import (
    discover_plugin_relationships,
    validate_plugin_dependencies,
    collect_enhanced_metadata
)
from ksi_common.logging import get_bound_logger

# Plugin metadata
plugin_metadata("plugin_relationships", version="1.0.0",
                description="Discover and validate plugin relationships through introspection")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_bound_logger("plugin_relationships", version="1.0.0")
cached_relationships: Optional[Dict[str, Any]] = None
plugin_manager = None


@hookimpl
def ksi_startup(config):
    """Initialize relationships discovery on startup."""
    logger.info("Plugin relationships service initializing...")
    return {"status": "relationships_service_ready"}


@hookimpl  
def ksi_plugin_context(context):
    """Store plugin manager reference."""
    global plugin_manager
    plugin_manager = context.get("plugin_manager")
    logger.info(f"Plugin context received, plugin_manager: {plugin_manager}")


@hookimpl
def ksi_ready():
    """Called when all plugins are loaded and daemon is ready.
    
    This is the perfect time to do initial plugin discovery since all
    plugins are guaranteed to be loaded at this point.
    """
    logger.info("Plugin relationships service ready - performing initial discovery")
    
    # Force initial discovery now that all plugins are loaded
    if plugin_manager:
        relationships = get_relationships(force_refresh=True)
        plugin_count = len(relationships.get('plugins', {}))
        event_count = len(relationships.get('event_providers', {}))
        logger.info(f"Initial discovery complete: {plugin_count} plugins, {event_count} events")
    else:
        logger.error("Plugin manager not available in ksi_ready")
    
    # No async tasks needed for this plugin
    return None


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle plugin relationship events using decorated handlers."""
    
    # Look for decorated handlers
    import sys
    import inspect
    module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    return None


def get_relationships(force_refresh: bool = False) -> Dict[str, Any]:
    """Get cached relationships or discover them."""
    global cached_relationships
    
    if force_refresh or cached_relationships is None:
        logger.debug(f"Plugin manager status: {plugin_manager}")
        if not plugin_manager:
            logger.error("Plugin manager not available")
            return {
                'plugins': {},
                'event_providers': {},
                'event_consumers': {},
                'state_namespaces': {},
                'validation': {'valid': True, 'errors': ['Plugin manager not initialized'], 'warnings': [], 'orphaned_events': [], 'unused_events': []}
            }
        
        logger.info("Discovering plugin relationships...")
        cached_relationships = discover_plugin_relationships(plugin_manager)
        
        # Validate relationships
        validation = validate_plugin_dependencies(cached_relationships)
        cached_relationships['validation'] = validation
        
        # Log summary
        plugin_count = len(cached_relationships['plugins'])
        event_count = len(cached_relationships['event_providers'])
        logger.info(f"Discovered {plugin_count} plugins with {event_count} unique events")
        
        if validation['errors']:
            logger.warning(f"Validation errors: {validation['errors']}")
        if validation['warnings']:
            logger.debug(f"Validation warnings: {validation['warnings']}")
    
    return cached_relationships


@event_handler("plugin:relationships")
def handle_plugin_relationships(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get comprehensive plugin relationship information."""
    force_refresh = data.get('refresh', False)
    relationships = get_relationships(force_refresh)
    
    return {
        'plugin_count': len(relationships.get('plugins', {})),
        'event_count': len(relationships.get('event_providers', {})),
        'relationships': relationships
    }


@event_handler("plugin:dependencies") 
def handle_plugin_dependencies(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get dependencies for a specific plugin."""
    plugin_name = data.get('plugin')
    
    if not plugin_name:
        return {'error': 'plugin parameter required'}
    
    relationships = get_relationships()
    
    if plugin_name not in relationships.get('plugins', {}):
        # Try to find by partial match
        matches = [p for p in relationships['plugins'] if plugin_name in p]
        if not matches:
            return {'error': f'Plugin {plugin_name} not found'}
        plugin_name = matches[0]
    
    plugin_info = relationships['plugins'][plugin_name]
    
    # Build dependency info
    dependencies = {
        'plugin': plugin_name,
        'provides': plugin_info.get('provides', {}).get('events', []),
        'consumes': [],
        'state_dependencies': plugin_info.get('state_dependencies', {})
    }
    
    # For each consumed event, find the provider
    for consumed in plugin_info.get('consumes', []):
        event = consumed['event']
        provider = relationships['event_providers'].get(event, ['unknown'])
        dependencies['consumes'].append({
            'event': event,
            'provider': provider[0] if provider else 'unknown',
            'functions': consumed.get('functions', [])
        })
    
    # Find who consumes this plugin's events
    consumed_by = {}
    for event in dependencies['provides']:
        consumers = relationships['event_consumers'].get(event, [])
        if consumers:
            consumed_by[event] = [c['plugin'] for c in consumers]
    
    dependencies['consumed_by'] = consumed_by
    
    return dependencies


@event_handler("plugin:validate")
def handle_plugin_validate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate plugin dependencies."""
    relationships = get_relationships(force_refresh=True)
    return relationships.get('validation', {})


@event_handler("plugin:graph")
def handle_plugin_graph(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a simplified dependency graph."""
    relationships = get_relationships()
    
    # Build simplified graph
    graph = {
        'nodes': [],
        'edges': []
    }
    
    # Add nodes (plugins)
    for plugin_name in relationships.get('plugins', {}):
        # Simplify plugin name for display
        short_name = plugin_name.split('.')[-1] if '.' in plugin_name else plugin_name
        graph['nodes'].append({
            'id': plugin_name,
            'label': short_name,
            'type': 'plugin'
        })
    
    # Add edges (event relationships)
    edge_id = 0
    for event, providers in relationships.get('event_providers', {}).items():
        consumers = relationships.get('event_consumers', {}).get(event, [])
        
        for provider in providers:
            for consumer_info in consumers:
                consumer = consumer_info['plugin']
                if provider != consumer:  # Skip self-loops
                    graph['edges'].append({
                        'id': edge_id,
                        'source': provider,
                        'target': consumer,
                        'label': event.split(':')[-1],  # Short event name
                        'event': event
                    })
                    edge_id += 1
    
    return graph


@event_handler("plugin:orphaned_events")
def handle_orphaned_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """Find events that have consumers but no providers."""
    relationships = get_relationships()
    validation = relationships.get('validation', {})
    
    return {
        'orphaned_events': validation.get('orphaned_events', []),
        'unused_events': validation.get('unused_events', [])
    }


@event_handler("plugin:refresh_relationships")
def handle_refresh_relationships(data: Dict[str, Any]) -> Dict[str, Any]:
    """Force refresh of cached relationships."""
    global cached_relationships
    cached_relationships = None
    
    relationships = get_relationships(force_refresh=True)
    
    return {
        'status': 'refreshed',
        'plugin_count': len(relationships.get('plugins', {})),
        'event_count': len(relationships.get('event_providers', {}))
    }


# Module marker
ksi_plugin = True

# Enable event discovery
from ksi_daemon.plugin_utils import create_ksi_describe_events_hook
ksi_describe_events = create_ksi_describe_events_hook(__name__)