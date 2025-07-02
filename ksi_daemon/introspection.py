#!/usr/bin/env python3
"""
Enhanced Plugin Introspection

Extends the basic introspection to discover:
- Event emissions (event_emitter calls)
- State dependencies (state namespace usage)
- Plugin inter-dependencies
"""

import ast
import inspect
from typing import Dict, Any, List, Optional, Callable, Set, Tuple
from pathlib import Path
import sys

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("introspection", version="1.0.0")


class EventEmissionExtractor:
    """Extract event emissions from AST analysis."""
    
    @staticmethod
    def extract_from_function(func: Callable) -> List[Dict[str, Any]]:
        """Extract event_emitter calls from a function."""
        try:
            source = inspect.getsource(func)
            tree = ast.parse(source)
            return EventEmissionExtractor._extract_from_ast(tree)
        except Exception as e:
            logger.debug(f"Could not extract emissions from function {func.__name__}: {e}")
            return []
    
    @staticmethod
    def extract_from_module(module) -> List[Dict[str, Any]]:
        """Extract all event_emitter calls from a module."""
        try:
            source = inspect.getsource(module)
            tree = ast.parse(source)
            return EventEmissionExtractor._extract_from_ast(tree)
        except Exception as e:
            logger.debug(f"Could not extract emissions from module: {e}")
            return []
    
    @staticmethod
    def _extract_from_ast(tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract event emissions from AST."""
        emissions = []
        
        class EmissionVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.is_async = False
            
            def visit_FunctionDef(self, node):
                old_func = self.current_function
                old_async = self.is_async
                self.current_function = node.name
                self.is_async = False
                self.generic_visit(node)
                self.current_function = old_func
                self.is_async = old_async
            
            def visit_AsyncFunctionDef(self, node):
                old_func = self.current_function
                old_async = self.is_async
                self.current_function = node.name
                self.is_async = True
                self.generic_visit(node)
                self.current_function = old_func
                self.is_async = old_async
            
            def visit_Call(self, node):
                # Look for event_emitter() calls
                event_name = None
                is_await = False
                
                # Check if it's await event_emitter(...)
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == 'event_emitter' and
                    isinstance(node.func.value, ast.Name)):
                    is_await = self.is_async
                elif (isinstance(node.func, ast.Name) and 
                      node.func.id == 'event_emitter'):
                    is_await = self.is_async
                else:
                    self.generic_visit(node)
                    return
                
                # Extract event name from first argument
                if node.args and isinstance(node.args[0], ast.Constant):
                    event_name = node.args[0].value
                elif node.args and isinstance(node.args[0], ast.Str):  # Python < 3.8
                    event_name = node.args[0].s
                
                if event_name:
                    emission = {
                        'event': event_name,
                        'function': self.current_function or '<module>',
                        'is_async': is_await
                    }
                    
                    # Try to extract purpose from second arg if it's a dict
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
                        # Could analyze the dict for common patterns
                        pass
                    
                    emissions.append(emission)
                
                self.generic_visit(node)
        
        visitor = EmissionVisitor()
        visitor.visit(tree)
        return emissions


class StateUsageExtractor:
    """Extract state namespace usage from AST analysis."""
    
    @staticmethod
    def extract_from_module(module) -> Dict[str, Set[str]]:
        """Extract state namespace usage from a module.
        
        Returns:
            Dict mapping namespace to set of operations (read/write)
        """
        try:
            source = inspect.getsource(module)
            tree = ast.parse(source)
            return StateUsageExtractor._extract_from_ast(tree)
        except Exception as e:
            logger.debug(f"Could not extract state usage from module: {e}")
            return {}
    
    @staticmethod
    def _extract_from_ast(tree: ast.AST) -> Dict[str, Set[str]]:
        """Extract state usage from AST."""
        state_usage = {}
        
        class StateVisitor(ast.NodeVisitor):
            def visit_Call(self, node):
                # Look for state-related event emissions
                event_name = None
                namespace = None
                
                # Check if it's an event_emitter call
                if ((isinstance(node.func, ast.Attribute) and node.func.attr == 'event_emitter') or
                    (isinstance(node.func, ast.Name) and node.func.id == 'event_emitter')):
                    
                    # Get event name
                    if node.args and isinstance(node.args[0], (ast.Constant, ast.Str)):
                        event_name = node.args[0].value if isinstance(node.args[0], ast.Constant) else node.args[0].s
                    
                    # Check if it's a state event
                    if event_name and event_name.startswith(('state:', 'async_state:')):
                        operation = event_name.split(':')[1]  # get, set, push, pop, etc.
                        
                        # Try to extract namespace from data dict
                        if len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
                            for key, value in zip(node.args[1].keys, node.args[1].values):
                                if (isinstance(key, (ast.Constant, ast.Str)) and 
                                    (key.value if isinstance(key, ast.Constant) else key.s) == 'namespace'):
                                    if isinstance(value, (ast.Constant, ast.Str)):
                                        namespace = value.value if isinstance(value, ast.Constant) else value.s
                                        break
                        
                        if namespace:
                            if namespace not in state_usage:
                                state_usage[namespace] = set()
                            
                            # Map operations to access types
                            if operation in ['get', 'pop', 'get_keys', 'queue_length']:
                                state_usage[namespace].add('read')
                            elif operation in ['set', 'push', 'delete']:
                                state_usage[namespace].add('write')
                
                self.generic_visit(node)
        
        visitor = StateVisitor()
        visitor.visit(tree)
        return state_usage


def _extract_direct_event_handlers(module) -> List[str]:
    """Extract events handled directly in ksi_handle_event hook.
    
    Looks for patterns like:
    - if event_name == "completion:async":
    - elif event_name == "some:event":
    """
    try:
        # Find ksi_handle_event function in module
        if not hasattr(module, 'ksi_handle_event'):
            return []
            
        func = module.ksi_handle_event
        source = inspect.getsource(func)
        tree = ast.parse(source)
        
        events = []
        
        class EventNameVisitor(ast.NodeVisitor):
            def visit_Compare(self, node):
                # Look for: event_name == "some:event"
                if (isinstance(node.left, ast.Name) and 
                    node.left.id == 'event_name' and
                    len(node.ops) == 1 and
                    isinstance(node.ops[0], ast.Eq) and
                    len(node.comparators) == 1):
                    
                    comparator = node.comparators[0]
                    if isinstance(comparator, ast.Constant):
                        event = comparator.value
                        if isinstance(event, str) and ':' in event:
                            events.append(event)
                    elif isinstance(comparator, ast.Str):  # Python < 3.8
                        event = comparator.s
                        if ':' in event:
                            events.append(event)
                
                self.generic_visit(node)
        
        visitor = EventNameVisitor()
        visitor.visit(tree)
        
        return list(set(events))  # Remove duplicates
        
    except Exception as e:
        logger.debug(f"Could not extract direct event handlers: {e}")
        return []


def collect_enhanced_metadata(module) -> Dict[str, Any]:
    """Collect comprehensive metadata about a plugin module.
    
    Combines:
    - Basic event handler discovery
    - Event emission discovery
    - State usage discovery
    """
    metadata = {
        'provides': {},
        'consumes': [],
        'state_dependencies': {}
    }
    
    # Get provided events (from decorators)
    import ksi_daemon.plugin_utils as plugin_utils
    provided_events = plugin_utils.collect_event_metadata(module)
    
    # Also check for events handled directly in ksi_handle_event
    additional_events = _extract_direct_event_handlers(module)
    for event in additional_events:
        if event not in provided_events:
            provided_events[event] = [{
                'event': event,
                'summary': 'Handled directly in ksi_handle_event',
                'parameters': {},
                'discovered_by': 'ksi_handle_event'
            }]
    
    metadata['provides']['events'] = list(provided_events.keys())
    metadata['provides']['handlers'] = provided_events
    
    # Get consumed events (from emissions)
    emissions = EventEmissionExtractor.extract_from_module(module)
    
    # Group by event and deduplicate
    consumed_events = {}
    for emission in emissions:
        event = emission['event']
        if event not in consumed_events:
            consumed_events[event] = {
                'event': event,
                'functions': [],
                'is_async': emission['is_async']
            }
        if emission['function'] not in consumed_events[event]['functions']:
            consumed_events[event]['functions'].append(emission['function'])
    
    metadata['consumes'] = list(consumed_events.values())
    
    # Get state dependencies
    state_usage = StateUsageExtractor.extract_from_module(module)
    for namespace, operations in state_usage.items():
        access = 'read_write' if len(operations) > 1 else list(operations)[0]
        metadata['state_dependencies'][namespace] = {
            'namespace': namespace,
            'access': access,
            'operations': list(operations)
        }
    
    return metadata


def discover_plugin_relationships(plugin_manager) -> Dict[str, Any]:
    """Discover relationships between all loaded plugins.
    
    Returns a graph of plugin dependencies based on event consumption.
    """
    relationships = {
        'plugins': {},
        'event_providers': {},
        'event_consumers': {},
        'state_namespaces': {}
    }
    
    # Get all plugins
    plugins = plugin_manager.get_plugins()
    logger.debug(f"Found {len(plugins)} plugins to analyze")
    
    # Iterate through all loaded plugins
    for plugin in plugins:
        logger.debug(f"Analyzing plugin: {plugin}")
        
        # Plugins can be modules or instances
        if hasattr(plugin, '__module__'):
            # It's an instance - get its module
            module_name = plugin.__module__
            module = sys.modules.get(module_name)
        elif hasattr(plugin, '__name__'):
            # It's already a module
            module_name = plugin.__name__
            module = plugin
        else:
            logger.debug(f"Plugin {plugin} has neither __module__ nor __name__ attribute")
            continue
            
        logger.debug(f"Plugin module name: {module_name}")
        
        if not module:
            logger.debug(f"Module {module_name} not found")
            continue
        
        # Collect enhanced metadata
        metadata = collect_enhanced_metadata(module)
        relationships['plugins'][module_name] = metadata
        
        # Index event providers
        for event_type in metadata['provides']['events']:
            for event in metadata['provides']['handlers'].get(event_type, []):
                event_name = event['event']
                if event_name not in relationships['event_providers']:
                    relationships['event_providers'][event_name] = []
                relationships['event_providers'][event_name].append(module_name)
        
        # Index event consumers
        for consumed in metadata['consumes']:
            event_name = consumed['event']
            if event_name not in relationships['event_consumers']:
                relationships['event_consumers'][event_name] = []
            relationships['event_consumers'][event_name].append({
                'plugin': module_name,
                'functions': consumed['functions']
            })
        
        # Index state namespace usage
        for namespace, info in metadata['state_dependencies'].items():
            if namespace not in relationships['state_namespaces']:
                relationships['state_namespaces'][namespace] = []
            relationships['state_namespaces'][namespace].append({
                'plugin': module_name,
                'access': info['access'],
                'operations': info['operations']
            })
    
    return relationships


def validate_plugin_dependencies(relationships: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that all consumed events have providers."""
    validation = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'orphaned_events': [],
        'unused_events': []
    }
    
    # Check for orphaned consumers (events with no provider)
    for event, consumers in relationships['event_consumers'].items():
        if event not in relationships['event_providers']:
            validation['orphaned_events'].append({
                'event': event,
                'consumers': [c['plugin'] for c in consumers]
            })
            validation['errors'].append(f"Event {event} has consumers but no provider")
            validation['valid'] = False
    
    # Check for unused events (events with no consumers)
    for event, providers in relationships['event_providers'].items():
        if event not in relationships['event_consumers']:
            # Some events are intentionally not consumed (like monitoring events)
            if not any(skip in event for skip in ['result', 'error', 'progress', 'status']):
                validation['unused_events'].append({
                    'event': event,
                    'providers': providers
                })
                validation['warnings'].append(f"Event {event} has no consumers")
    
    return validation