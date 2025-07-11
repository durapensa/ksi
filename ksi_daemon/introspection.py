#!/usr/bin/env python3
"""
Enhanced Module Introspection

Extends the basic introspection to discover:
- Event emissions (event_emitter calls)
- State dependencies (state namespace usage)
- Module inter-dependencies
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
    """Extract events handled directly in event handler functions.
    
    Looks for patterns like:
    - if event_name == "completion:async":
    - elif event_name == "some:event":
    """
    try:
        # Find event handler functions in module
        events = []
        
        # Look for functions with @event_handler decorator
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, '_event_handler_metadata'):
                metadata = obj._event_handler_metadata
                if 'event' in metadata:
                    events.append(metadata['event'])
        
        return list(set(events))  # Remove duplicates
        
    except Exception as e:
        logger.debug(f"Could not extract direct event handlers: {e}")
        return []


def collect_event_metadata(module) -> Dict[str, List[Dict[str, Any]]]:
    """Collect event handler metadata from a module."""
    event_metadata = {}
    
    for name, obj in inspect.getmembers(module):
        if hasattr(obj, '_event_handler_metadata'):
            metadata = obj._event_handler_metadata
            event = metadata.get('event', 'unknown')
            
            if event not in event_metadata:
                event_metadata[event] = []
            
            event_metadata[event].append({
                'event': event,
                'function': name,
                'summary': f"Event handler for {event}",
                'parameters': {},
                'discovered_by': 'decorator'
            })
    
    return event_metadata


def collect_enhanced_metadata(module) -> Dict[str, Any]:
    """Collect comprehensive metadata about a module.
    
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
    provided_events = collect_event_metadata(module)
    
    # Also check for events handled directly
    additional_events = _extract_direct_event_handlers(module)
    for event in additional_events:
        if event not in provided_events:
            provided_events[event] = [{
                'event': event,
                'summary': 'Event handler',
                'parameters': {},
                'discovered_by': 'direct'
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


def discover_module_relationships(modules: List[Any]) -> Dict[str, Any]:
    """Discover relationships between loaded modules.
    
    Returns a graph of module dependencies based on event consumption.
    """
    relationships = {
        'modules': {},
        'event_providers': {},
        'event_consumers': {},
        'state_namespaces': {}
    }
    
    logger.debug(f"Found {len(modules)} modules to analyze")
    
    # Iterate through all loaded modules
    for module in modules:
        logger.debug(f"Analyzing module: {module}")
        
        # Modules can be modules or instances
        if hasattr(module, '__module__'):
            # It's an instance - get its module
            module_name = module.__module__
            module = sys.modules.get(module_name)
        elif hasattr(module, '__name__'):
            # It's already a module
            module_name = module.__name__
        else:
            logger.debug(f"Module {module} has neither __module__ nor __name__ attribute")
            continue
            
        logger.debug(f"Module name: {module_name}")
        
        if not module:
            logger.debug(f"Module {module_name} not found")
            continue
        
        # Collect enhanced metadata
        metadata = collect_enhanced_metadata(module)
        relationships['modules'][module_name] = metadata
        
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
                'module': module_name,
                'functions': consumed['functions']
            })
        
        # Index state namespace usage
        for namespace, info in metadata['state_dependencies'].items():
            if namespace not in relationships['state_namespaces']:
                relationships['state_namespaces'][namespace] = []
            relationships['state_namespaces'][namespace].append({
                'module': module_name,
                'access': info['access'],
                'operations': info['operations']
            })
    
    return relationships


def validate_module_dependencies(relationships: Dict[str, Any]) -> Dict[str, Any]:
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
                'consumers': [c['module'] for c in consumers]
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