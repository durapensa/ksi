#!/usr/bin/env python3
"""
Composition Service Module - Event handlers for composition system
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict
from typing_extensions import NotRequired
from dataclasses import dataclass

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.timestamps import timestamp_utc, format_for_logging
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

# Import composition modules
from . import composition_index
from .composition_core import (
    Composition, CompositionComponent,
    load_fragment, substitute_variables, evaluate_condition, evaluate_conditions,
    load_composition as load_composition_file,
    FRAGMENTS_BASE, COMPOSITIONS_BASE, SCHEMAS_BASE, CAPABILITIES_BASE
)

# Module state
logger = get_bound_logger("composition_service", version="2.0.0")
state_manager = None  # For shared state operations only

# Capability schema cache
_capability_schema_cache = None


# TypedDict definitions
class CompositionComposeData(TypedDict):
    """Type-safe data for composition:compose."""
    name: str
    type: NotRequired[str]
    variables: NotRequired[Dict[str, Any]]

class CompositionProfileData(TypedDict):
    """Type-safe data for composition:profile."""
    name: str
    variables: NotRequired[Dict[str, Any]]

class CompositionPromptData(TypedDict):
    """Type-safe data for composition:prompt."""
    name: str
    variables: NotRequired[Dict[str, Any]]

class CompositionValidateData(TypedDict):
    """Type-safe data for composition:validate."""
    name: str
    type: NotRequired[str]

class CompositionListData(TypedDict):
    """Type-safe data for composition:list."""
    type: NotRequired[str]

class CompositionGetData(TypedDict):
    """Type-safe data for composition:get."""
    name: str
    type: NotRequired[str]


@dataclass
class SelectionContext:
    """Context for intelligent composition selection."""
    agent_id: str
    role: Optional[str] = None
    capabilities: Optional[List[str]] = None
    task_description: Optional[str] = None
    preferred_style: Optional[str] = None
    context_variables: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None


@dataclass 
class SelectionResult:
    """Result of intelligent composition selection."""
    composition_name: str
    score: float
    reasons: List[str]
    fallback_used: bool = False


# Event Handlers

@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive infrastructure from daemon context."""
    global state_manager
    
    state_manager = context.get("state_manager")
    
    if state_manager:
        logger.info("Composition service connected to state manager")


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize composition service on startup."""
    logger.info("Composition service starting up...")
    
    # Ensure directories exist
    COMPOSITIONS_BASE.mkdir(parents=True, exist_ok=True)
    FRAGMENTS_BASE.mkdir(parents=True, exist_ok=True)
    
    # Initialize and rebuild composition index
    composition_index.initialize()
    indexed_count = composition_index.rebuild()
    
    logger.info(f"Composition service started - indexed {indexed_count} compositions")
    return {"status": "composition_service_ready", "indexed": indexed_count}


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Composition service shutting down")


@event_handler("composition:compose")
async def handle_compose(data: CompositionComposeData) -> Dict[str, Any]:
    """Compose a complete configuration from components."""
    name = data.get('name')
    comp_type = data.get('type', 'profile')
    variables = data.get('variables', {})
    
    try:
        composition = await resolve_composition(name, comp_type, variables)
        return {
            'status': 'success',
            'composition': composition
        }
    except Exception as e:
        logger.error(f"Composition failed: {e}")
        return {'error': str(e)}


@event_handler("composition:profile")
async def handle_compose_profile(data: CompositionProfileData) -> Dict[str, Any]:
    """Compose a profile (returns full configuration)."""
    name = data.get('name')
    variables = data.get('variables', {})
    
    try:
        result = await compose_profile(name, variables)
        return {
            'status': 'success',
            'profile': result
        }
    except Exception as e:
        logger.error(f"Profile composition failed: {e}")
        return {'error': str(e)}


@event_handler("composition:prompt")
async def handle_compose_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compose a prompt (returns text)."""
    name = data.get('name')
    variables = data.get('variables', {})
    
    try:
        result = await compose_prompt(name, variables)
        return {
            'status': 'success',
            'prompt': result
        }
    except Exception as e:
        logger.error(f"Prompt composition failed: {e}")
        return {'error': str(e)}


@event_handler("composition:validate")
async def handle_validate(data: CompositionValidateData) -> Dict[str, Any]:
    """Validate a composition."""
    name = data.get('name')
    comp_type = data.get('type')
    
    try:
        # Try to load the composition
        composition = await load_composition(name, comp_type)
        
        # Validate structure
        issues = []
        
        # Check required fields
        if not composition.name:
            issues.append("Missing composition name")
        if not composition.type:
            issues.append("Missing composition type")
        if not composition.version:
            issues.append("Missing composition version")
        
        # Validate components
        for i, component in enumerate(composition.components):
            if not component.name:
                issues.append(f"Component {i} missing name")
            
            # Check that component has a source
            sources = [component.source, component.composition, 
                      component.inline, component.template]
            if not any(sources):
                issues.append(f"Component '{component.name}' has no content source")
        
        return {
            'status': 'success',
            'valid': len(issues) == 0,
            'issues': issues,
            'composition': {
                'name': composition.name,
                'type': composition.type,
                'version': composition.version
            }
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'valid': False,
            'error': str(e)
        }


@event_handler("composition:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """Discover available compositions using index."""
    try:
        # Use index for fast discovery
        discovered = composition_index.discover(data)
        
        # Apply metadata filtering if specified
        metadata_filter = data.get('metadata_filter')
        if metadata_filter:
            filtered_compositions = []
            for comp_info in discovered:
                try:
                    # Load composition to get full metadata
                    composition = await load_composition(comp_info['name'])
                    metadata = composition.metadata
                    
                    # Check if all filter criteria match
                    matches = True
                    for key, expected_value in metadata_filter.items():
                        actual_value = metadata.get(key)
                        
                        if isinstance(expected_value, list):
                            # For list filters, check if there's any overlap
                            if not isinstance(actual_value, list):
                                actual_value = [actual_value] if actual_value else []
                            if not set(expected_value) & set(actual_value):
                                matches = False
                                break
                        else:
                            # For scalar filters, check exact match
                            if actual_value != expected_value:
                                matches = False
                                break
                    
                    if matches:
                        # Add metadata to composition info
                        comp_info_with_metadata = {**comp_info, 'metadata': metadata}
                        filtered_compositions.append(comp_info_with_metadata)
                        
                except Exception as e:
                    logger.warning(f"Failed to load composition {comp_info['name']} for filtering: {e}")
                    continue
            
            discovered = filtered_compositions
            logger.debug(f"Filtered compositions by metadata: {len(discovered)} matches")
        
        return {
            'status': 'success',
            'compositions': discovered,
            'count': len(discovered),
            'filtered': metadata_filter is not None
        }
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return {'error': str(e)}


@event_handler("composition:list")
async def handle_list(data: CompositionListData) -> Dict[str, Any]:
    """List all compositions of a given type."""
    comp_type = data.get('type', 'all')
    
    compositions = []
    
    if comp_type == 'all':
        types = ['profile', 'prompt', 'system']
    else:
        types = [comp_type]
    
    for t in types:
        discovered = await handle_discover({'type': t})
        compositions.extend(discovered.get('compositions', []))
    
    return {
        'status': 'success',
        'compositions': compositions,
        'count': len(compositions)
    }


@event_handler("composition:get")
async def handle_get(data: CompositionGetData) -> Dict[str, Any]:
    """Get a composition definition."""
    name = data.get('name')
    comp_type = data.get('type')
    
    if not name:
        return {'error': 'Composition name required'}
    
    try:
        composition = await load_composition(name, comp_type)
        
        return {
            'status': 'success',
            'composition': {
                'name': composition.name,
                'type': composition.type,
                'version': composition.version,
                'description': composition.description,
                'author': composition.author,
                'extends': composition.extends,
                'mixins': composition.mixins,
                'components': [
                    {
                        'name': c.name,
                        'source': c.source,
                        'composition': c.composition,
                        'has_inline': c.inline is not None,
                        'has_template': c.template is not None,
                        'condition': c.condition,
                        'vars': list(c.vars.keys())
                    }
                    for c in composition.components
                ],
                'variables': list(composition.variables.keys()),
                'metadata': composition.metadata
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get composition: {e}")
        return {'error': str(e)}


@event_handler("composition:reload")
async def handle_reload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Reload composition index."""
    try:
        indexed_count = composition_index.rebuild()
        
        return {
            'status': 'success',
            'indexed': indexed_count,
            'message': f'Reloaded {indexed_count} compositions'
        }
    except Exception as e:
        logger.error(f"Failed to reload compositions: {e}")
        return {'error': str(e)}


@event_handler("composition:rebuild_index")
async def handle_rebuild_index(data: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild the composition index."""
    try:
        indexed_count = composition_index.rebuild()
        return {
            'status': 'success',
            'indexed_count': indexed_count,
            'message': f'Indexed {indexed_count} compositions'
        }
    except Exception as e:
        logger.error(f"Index rebuild failed: {e}")
        return {'error': str(e)}


@event_handler("composition:index_file")
async def handle_index_file(data: Dict[str, Any]) -> Dict[str, Any]:
    """Index a specific composition file."""
    file_path = data.get('file_path')
    if not file_path:
        return {'error': 'file_path required'}
    
    try:
        success = composition_index.index_file(Path(file_path))
        return {
            'status': 'success' if success else 'failed',
            'file_path': file_path,
            'indexed': success
        }
    except Exception as e:
        logger.error(f"File indexing failed: {e}")
        return {'error': str(e)}


# Core Composition Functions

async def load_composition(name: str, comp_type: Optional[str] = None) -> Composition:
    """Load a composition with caching support."""
    # Check dynamic cache first
    if state_manager:
        cache_key = f"dynamic_composition:{name}"
        cached = state_manager.get_shared_state(cache_key)
        if cached and isinstance(cached, dict):
            return Composition.from_yaml(cached)
    
    # Load from file
    return await load_composition_file(name, comp_type)


async def resolve_composition(
    name: str, 
    comp_type: str = 'profile',
    variables: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Resolve a composition into final configuration."""
    if variables is None:
        variables = {}
    
    # Load the composition
    composition = await load_composition(name, comp_type)
    
    # Process inheritance
    if composition.extends:
        parent = await resolve_composition(composition.extends, comp_type, variables)
        # Merge parent configuration
        # (simplified - in production would do deep merge)
        result = parent.copy()
    else:
        result = {}
    
    # Process mixins
    for mixin_name in composition.mixins:
        mixin = await resolve_composition(mixin_name, comp_type, variables)
        # Merge mixin configuration
        for key, value in mixin.items():
            if key not in result:
                result[key] = value
    
    # Process components
    for component in composition.components:
        # Check conditions
        if component.condition and not evaluate_condition(component.condition, variables):
            continue
        
        if component.conditions and not evaluate_conditions(component.conditions, variables):
            continue
        
        # Merge component variables with composition variables
        comp_vars = {**variables, **component.vars}
        
        # Load component content
        content = None
        
        if component.source:
            # Load from fragment file
            content = load_fragment(component.source)
            content = substitute_variables(content, comp_vars)
            
        elif component.composition:
            # Load from another composition
            content = await resolve_composition(component.composition, 'component', comp_vars)
            
        elif component.inline:
            # Use inline content
            content = component.inline
            
        elif component.template:
            # Use template string
            content = substitute_variables(component.template, comp_vars)
        
        # Add to result
        if content is not None:
            result[component.name] = content
    
    # Resolve any remaining variables in the result
    if isinstance(result, dict):
        result_str = json.dumps(result)
        result_str = substitute_variables(result_str, variables)
        result = json.loads(result_str)
    
    return result


async def compose_profile(name: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose a profile configuration."""
    if variables is None:
        variables = {}
    
    # Resolve the profile composition
    profile_config = await resolve_composition(name, 'profile', variables)
    
    # Ensure required profile fields
    if 'name' not in profile_config:
        profile_config['name'] = name
    
    if 'type' not in profile_config:
        profile_config['type'] = 'profile'
    
    return profile_config


async def compose_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Compose a prompt into final text."""
    if variables is None:
        variables = {}
    
    # Resolve the prompt composition
    prompt_parts = await resolve_composition(name, 'prompt', variables)
    
    # Combine parts into final prompt
    if isinstance(prompt_parts, dict):
        # If it's a dict, concatenate the values
        parts = []
        for key in sorted(prompt_parts.keys()):
            value = prompt_parts[key]
            if isinstance(value, str):
                parts.append(value)
            else:
                parts.append(json.dumps(value, indent=2))
        return '\n\n'.join(parts)
    else:
        # Otherwise return as string
        return str(prompt_parts)