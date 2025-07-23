#!/usr/bin/env python3
"""
Composition Service Module - Event handlers for composition system
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict, Tuple, Union, Literal
from typing_extensions import NotRequired, Required
from dataclasses import dataclass

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.timestamps import timestamp_utc, format_for_logging, sanitize_for_json
from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.file_utils import ensure_directory
from ksi_common.event_utils import extract_single_response
from ksi_common.git_utils import git_manager
from ksi_common.yaml_utils import safe_load, safe_dump, load_yaml_file, save_yaml_file
from ksi_common.json_utils import loads as json_loads, dumps as json_dumps
from ksi_common.frontmatter_utils import parse_frontmatter, validate_frontmatter
from ksi_common.component_renderer import get_renderer, ComponentResolutionError, CircularDependencyError
from ksi_common.component_loader import find_component_file, load_component_file
from ksi_common.composition_utils import (
    resolve_composition_path, load_composition_with_metadata, 
    normalize_composition_name, get_composition_base_path
)

# Import composition modules
from . import composition_index
from .composition_core import (
    Composition, CompositionComponent,
    load_component, substitute_variables, evaluate_condition, evaluate_conditions,
    load_composition as load_composition_file,
    COMPONENTS_BASE, COMPOSITIONS_BASE, SCHEMAS_BASE, CAPABILITIES_BASE
)
from .evaluation_utils import (
    create_evaluation_record, calculate_overall_score, 
    find_best_evaluation, summarize_evaluation_status,
    merge_evaluation_record
)
# TypedDict imports are now defined locally in this file

# Module state
logger = get_bound_logger("composition_service", version="2.0.0")
state_manager = None  # For shared state operations only
event_emitter = None  # For event emission to other services

# Capability schema cache
_capability_schema_cache = None


def _normalize_component_name(name: str) -> str:
    """Normalize component name by stripping 'components/' prefix if present."""
    if name.startswith('components/'):
        return name[11:]  # len('components/') = 11
    return name


# Date sanitization function moved to ksi_common.timestamps.sanitize_for_json


# We'll define TypedDict types close to their handlers below


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
async def handle_context(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive infrastructure from daemon context."""
    # PYTHONIC CONTEXT REFACTOR: Use system registry for components
    global state_manager, event_emitter
    
    if data.get("registry_available"):
        from ksi_daemon.core.system_registry import SystemRegistry
        state_manager = SystemRegistry.get("state_manager")
        event_emitter = SystemRegistry.get("event_emitter")
    else:
        # Fallback to router
        router = get_router()
        event_emitter = router.emit if router else None
    
    if state_manager:
        logger.info("Composition service connected to state manager")
    if event_emitter:
        logger.info("Composition service connected to event emitter")


@event_handler("system:startup")
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize composition service on startup."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    logger.info("Composition service starting up...")
    
    # Ensure directories exist
    ensure_directory(COMPOSITIONS_BASE)
    ensure_directory(COMPONENTS_BASE)
    
    # Initialize and rebuild composition index with dedicated database
    await composition_index.initialize(config.composition_index_db_path)
    indexed_count = await composition_index.rebuild()
    
    logger.info(f"Composition service started - indexed {indexed_count} compositions")
    return event_response_builder(
        {"status": "composition_service_ready", "indexed": indexed_count},
        context=context
    )


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    logger.info("Composition service shutting down")


class CompositionComposeData(TypedDict):
    """Compose a complete configuration from components."""
    name: str  # Component name (e.g., "components/agents/hello_agent", "base_single_agent")
    type: NotRequired[str]  # Optional type hint (inferred from component if not specified)
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:compose")
async def handle_compose(data: CompositionComposeData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Universal composition endpoint - composes any component type.
    
    The component's type field is used as a hint for composition behavior,
    but intelligent agents can determine appropriate usage from context
    (e.g., components/agents/* are agent profiles, prompts/* are prompts).
    
    This replaces the deprecated type-specific endpoints:
    - composition:profile (removed)
    - composition:prompt (removed)
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    name = data.get('name')
    comp_type = data.get('type', 'profile')
    variables = data.get('variables', {})
    
    try:
        composition = await resolve_composition(name, comp_type, variables)
        return event_response_builder(
            {
                'status': 'success',
                'composition': composition
            },
            context=context
        )
    except Exception as e:
        logger.error(f"Composition failed: {e}")
        return error_response(
            str(e),
            context=context
        )


# Type-specific composition endpoints removed - use composition:compose


class CompositionValidateData(TypedDict):
    """Validate a composition structure and syntax."""
    name: str  # Composition name to validate
    type: NotRequired[str]  # Composition type
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:validate")
async def handle_validate(data: CompositionValidateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a composition structure and syntax (like a linter)."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
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
        
        return event_response_builder(
            {
                'status': 'success',
                'valid': len(issues) == 0,
                'issues': issues,
                'composition': {
                    'name': composition.name,
                    'type': composition.type,
                    'version': composition.version
                }
            },
            context=context
        )
        
    except Exception as e:
        return error_response(
            str(e),
            context=context
        )


class CompositionEvaluateData(TypedDict):
    """Process evaluation results for a composition."""
    name: str  # Composition to evaluate
    type: NotRequired[str]  # Composition type
    test_suite: str  # Test suite that was run
    model: NotRequired[str]  # Model used for testing
    test_options: NotRequired[Dict[str, Any]]  # Test results and metrics
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:evaluate")
async def handle_evaluate(data: CompositionEvaluateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process evaluation results for a composition (in-memory only)."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    name = data['name']  # Composition to evaluate
    comp_type = data.get('type')  # Composition type
    test_suite = data['test_suite']  # Test suite that was run
    model = data.get('model', config.completion_default_model)  # Model used for testing
    test_options = data.get('test_options', {})  # Test results and metrics
    
    try:
        # Load the composition
        composition = await load_composition(name, comp_type)
        
        # Extract test results from options
        test_results = test_options.get('test_results', [])
        performance_metrics = test_options.get('performance_metrics', {})
        notes = test_options.get('notes', '')
        
        # Calculate overall score
        overall_score = calculate_overall_score(test_results)
        
        # Create evaluation record
        evaluation_record = create_evaluation_record(
            model=model,
            test_suite=test_suite,
            test_results=test_results,
            overall_score=overall_score,
            performance_metrics=performance_metrics,
            notes=notes
        )
        
        # Return evaluation results (without saving)
        return event_response_builder(
            {
                'status': 'success',
                'composition': {
                    'name': composition.name,
                    'type': composition.type,
                    'version': composition.version
                },
                'evaluation': evaluation_record,
                'metadata': composition.metadata
            },
            context=context
        )
        
    except Exception as e:
        logger.error(f"Error evaluating composition: {e}")
        return error_response(
            str(e),
            context=context
        )


async def _save_composition_to_disk(composition: Composition, overwrite: bool = False) -> Dict[str, Any]:
    """Internal helper to save composition to disk with git commit."""
    try:
        # Build composition dict
        comp_dict = {
            'name': composition.name,
            'type': composition.type,
            'version': composition.version,
            'description': composition.description,
            'author': composition.author,
            'extends': composition.extends,
            'mixins': composition.mixins,
            'components': [vars(c) for c in composition.components],
            'variables': composition.variables,
            'metadata': composition.metadata
        }
        # Remove None values
        comp_dict = {k: v for k, v in comp_dict.items() if v is not None}
        
        # Use git manager to save and commit
        git_result = await git_manager.save_component(
            component_type="compositions",
            name=composition.name,
            content=comp_dict,
            message=f"Save composition {composition.name} v{composition.version}"
        )
        
        if not git_result.success:
            return {
                'status': 'error',
                'error': f'Failed to save composition: {git_result.error}'
            }
        
        # Update index
        comp_path = git_manager.get_component_repo_path("compositions")
        subdir = git_manager._determine_composition_subdir(comp_dict)
        file_path = comp_path / subdir / f"{composition.name}.yaml"
        await composition_index.index_file(file_path)
        
        logger.info(f"Saved and committed composition {composition.name} (commit: {git_result.commit_hash})")
        
        return {
            'status': 'success',
            'path': str(file_path),
            'commit_hash': git_result.commit_hash,
            'git_message': git_result.message
        }
        
    except Exception as e:
        logger.error(f"Failed to save composition: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


class CompositionSaveData(TypedDict):
    """Save a composition to disk with git commit."""
    composition: Required[Dict[str, Any]]  # Complete composition object or dict
    overwrite: NotRequired[bool]  # Replace existing file if True
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:save")
async def handle_save_composition(data: CompositionSaveData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Save a composition to disk."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    try:
        comp_data = data.get('composition')  # Complete composition object or dict
        if not comp_data:
            return error_response(
                'No composition data provided',
                context=context
            )
            
        overwrite = data.get('overwrite', False)  # Replace existing file if True
        
        # Create Composition object if needed
        if isinstance(comp_data, dict):
            composition = Composition.from_yaml(comp_data)
        else:
            composition = comp_data
            
        # Use helper to save
        save_result = await _save_composition_to_disk(composition, overwrite)
        
        if save_result['status'] == 'success':
            # Emit event for profile system integration
            if event_emitter:
                try:
                    await event_emitter("composition:saved", {
                        'name': composition.name,
                        'type': composition.type,
                        'path': save_result['path']
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit composition:saved event: {e}")
            
            return event_response_builder(
                {
                    'status': 'success',
                    'name': composition.name,
                    'type': composition.type,
                    'path': save_result['path'],
                    'message': f'Composition saved to {save_result["path"]}'
                },
                context=context
            )
        else:
            return error_response(
                save_result.get('error', 'Save failed'),
                context=context
            )
        
    except Exception as e:
        logger.error(f"Failed to save composition: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionUpdateData(TypedDict):
    """Update an existing composition's properties or metadata."""
    name: Required[str]  # Composition name to update
    type: NotRequired[str]  # Composition type (defaults to 'profile')
    updates: NotRequired[Dict[str, Any]]  # Properties to update (metadata, version, etc)
    merge_metadata: NotRequired[bool]  # Merge vs replace metadata (defaults to True)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:update")
async def handle_update_composition(data: CompositionUpdateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update an existing composition's properties or metadata."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    try:
        name = data.get('name')  # Composition name to update
        if not name:
            return error_response(
                'Composition name required',
                context=context
            )
            
        comp_type = data.get('type', 'profile')  # Composition type
        updates = data.get('updates', {})  # Properties to update (metadata, version, etc)
        merge_metadata = data.get('merge_metadata', True)  # Merge vs replace metadata
        
        # Load existing composition
        composition = await load_composition(name, comp_type)
        
        # Apply updates
        if 'description' in updates:
            composition.description = updates['description']
        if 'version' in updates:
            composition.version = updates['version']
        if 'components' in updates:
            composition.components = [
                CompositionComponent(**comp) if isinstance(comp, dict) else comp
                for comp in updates['components']
            ]
        if 'variables' in updates:
            composition.variables = updates['variables']
            
        # Handle metadata updates
        if 'metadata' in updates:
            if merge_metadata:
                # Merge with existing metadata
                composition.metadata.update(updates['metadata'])
            else:
                # Replace metadata
                composition.metadata = updates['metadata']
        
        # Save updated composition
        save_result = await _save_composition_to_disk(composition, overwrite=True)
        
        if save_result['status'] != 'success':
            return error_response(
                save_result.get('error', 'Update failed'),
                context=context
            )
        
        # Emit event for profile system integration
        if event_emitter:
            try:
                await event_emitter("composition:updated", {
                    'name': composition.name,
                    'type': composition.type,
                    'path': save_result['path'],
                    'updates_applied': list(updates.keys())
                })
            except Exception as e:
                logger.warning(f"Failed to emit composition:updated event: {e}")
            
        return event_response_builder(
            {
                'status': 'success',
                'name': composition.name,
                'type': composition.type,
                'version': composition.version,
                'updates_applied': list(updates.keys()),
                'message': f'Updated composition {name}'
            },
            context=context
        )
        
    except Exception as e:
        logger.error(f"Failed to update composition: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionDiscoverData(TypedDict):
    """Discover compositions with filters and limits."""
    type: NotRequired[Literal['all', 'profile', 'prompt', 'orchestration', 'evaluation', 'component']]  # Filter by type
    name: NotRequired[str]  # Filter by name (supports partial matching)
    capabilities: NotRequired[List[str]]  # Filter by capabilities
    tags: NotRequired[List[str]]  # Filter by tags
    loading_strategy: NotRequired[str]  # Filter by loading strategy
    metadata_filter: NotRequired[Dict[str, Any]]  # Filter by metadata
    include_metadata: NotRequired[bool]  # Include full metadata in response
    limit: NotRequired[int]  # Limit number of results (default: no limit)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:discover")
async def handle_discover(data: CompositionDiscoverData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Discover available compositions using index."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    try:
        logger.debug(f"composition:discover received data: {data}")
        logger.debug(f"composition:discover type parameter: {data.get('type', 'NOT SET')}")
        
        # Use index for fast discovery with SQL-based filtering
        # Include metadata filter in the query
        query = dict(data)  # Copy to avoid modifying original
        
        # Apply default limit if none specified to prevent timeouts
        if 'limit' not in query:
            query['limit'] = 50  # Sensible default to prevent timeouts
        
        # Don't include full metadata by default - it makes responses too large
        
        logger.debug(f"composition:discover sending to index: {query}")
        discovered = await composition_index.discover(query)
        
        # TODO: Re-enable evaluation detail when performance is optimized
        # Currently disabled to prevent timeouts
        
        # Metadata filtering is now handled in the SQL query
        # The index already filtered by metadata if requested
        
        return event_response_builder(
            {
                'status': 'success',
                'compositions': discovered,
                'count': len(discovered),
                'filtered': data.get('metadata_filter') is not None
            },
            context=context
        )
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionListData(TypedDict):
    """List compositions with filters."""
    type: NotRequired[Literal['all', 'profile', 'prompt', 'orchestration', 'evaluation', 'component']]  # Filter by type
    include_validation: NotRequired[bool]  # Include validation status
    metadata_filter: NotRequired[Dict[str, Any]]  # Filter by metadata
    evaluation_detail: NotRequired[Literal['none', 'minimal', 'summary', 'detailed']]  # Evaluation detail level
    filter: NotRequired[Union[str, Dict[str, Any]]]  # JSON string filter from CLI or dict
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:list")
async def handle_list(data: CompositionListData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all compositions of a given type."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    from ksi_common.json_utils import parse_json_parameter
    
    # Debug data first
    logger.info(f"composition:list TESTING INFO LOG LEVEL")
    logger.debug(f"composition:list DATA: {data}")
    
    # Handle filter parameter if it's a JSON string
    parse_json_parameter(data, 'filter')
    
    # Handle filter parameter if it's already a dict (from agent JSON emission)
    if 'filter' in data and isinstance(data['filter'], dict):
        filter_data = data.pop('filter')
        data.update(filter_data)
        logger.debug(f"composition:list merged filter dict: {filter_data}")
    
    # Debug logging to trace the issue
    logger.debug(f"composition:list after parse_json_parameter, data: {data}")
    logger.debug(f"composition:list type from data: {data.get('type', 'NOT SET')}")
    
    include_validation = data.get('include_validation', False)
    
    # Pass through all query parameters directly to discover
    query_params = dict(data)
    query_params.pop('filter', None)  # Remove filter string parameter
    query_params.pop('include_validation', None)  # Remove non-query parameter
    
    # Debug logging
    logger.debug(f"composition:list query_params: {query_params}")
    
    # Let discover handle the query - it will filter by type if specified
    discovered = await handle_discover(query_params, context)
    compositions = discovered.get('compositions', [])
    
    logger.debug(f"composition:list discovered {len(compositions)} compositions")
    
    return event_response_builder(
        {
            'status': 'success',
            'compositions': compositions,
            'count': len(compositions)
        },
        context=context
    )


async def load_composition_raw(name: str, comp_type: Optional[str] = None) -> Dict[str, Any]:
    """Load raw composition YAML data preserving all sections."""
    # Use shared utility to resolve path based on type
    composition_path = resolve_composition_path(name, comp_type or 'orchestration')
    
    if not composition_path:
        raise FileNotFoundError(f"Composition not found: {name}")
    
    # Load using shared component loader
    metadata, content = load_component_file(composition_path)
    
    # For orchestrations and other YAML-content types that have content, parse content as YAML
    if content and comp_type in ['orchestration', 'evaluation', 'workflow']:
        try:
            # Parse the content as YAML
            content_data = safe_load(content) if content.strip() else {}
            # Merge metadata and content, with metadata taking precedence
            return {**content_data, **metadata}
        except Exception as e:
            logger.error(f"Failed to parse YAML content in {name}: {e}")
            raise ValueError(f"Invalid YAML content in file: {e}")
    
    # For YAML files or other types, just return metadata
    return metadata or {}


def validate_core_composition(data: Dict[str, Any]) -> List[str]:
    """Validate only core composition fields."""
    errors = []
    
    # Required fields
    if not isinstance(data.get('name'), str):
        errors.append("'name' must be a string")
    
    if not isinstance(data.get('type'), str):
        errors.append("'type' must be a string")
    
    # Optional fields with type checking
    if 'version' in data and not isinstance(data['version'], str):
        errors.append("'version' must be a string")
    if 'description' in data and not isinstance(data['description'], str):
        errors.append("'description' must be a string")
    if 'author' in data and not isinstance(data['author'], str):
        errors.append("'author' must be a string")
    
    # Name format validation
    name = data.get('name', '')
    if name and not re.match(r'^[a-zA-Z0-9_-]+$', name):
        errors.append("'name' must contain only alphanumeric, underscore, and hyphen characters")
    
    return errors


class CompositionGetData(TypedDict):
    """Get a composition definition."""
    name: str  # Composition name to get
    type: NotRequired[str]  # Composition type
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:get")
async def handle_get(data: CompositionGetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a composition definition with all sections preserved."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    name = data.get('name')
    comp_type = data.get('type')
    
    if not name:
        return error_response(
            'Composition name required',
            context=context
        )
    
    try:
        # Load raw YAML data to preserve all sections
        composition_data = await load_composition_raw(name, comp_type)
        
        # Validate core fields
        validation_errors = validate_core_composition(composition_data)
        if validation_errors:
            return error_response(
                f'Invalid composition structure: {"; ".join(validation_errors)}',
                context=context
            )
        
        # Sanitize datetime objects for JSON serialization
        composition_data = sanitize_for_json(composition_data)
        
        return event_response_builder(
            {
                'status': 'success',
                'composition': composition_data  # Return ALL sections, not just core fields
            },
            context=context
        )
        
    except Exception as e:
        logger.error(f"Failed to get composition: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionSyncData(TypedDict):
    """Synchronize composition submodules with remote repositories."""
    component_type: NotRequired[str]  # Optional: sync specific component
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionGitInfoData(TypedDict):
    """Get information about git repositories for composition submodules."""
    component_type: NotRequired[str]  # Optional: get info for specific component
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:sync")
async def handle_sync_compositions(data: CompositionSyncData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Synchronize composition submodules with remote repositories."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    component_type = data.get('component_type')  # Optional: sync specific component
    
    try:
        # Use git manager to sync submodules
        sync_result = await git_manager.sync_submodules(component_type)
        
        if not sync_result.success:
            return error_response(f'Sync failed: {sync_result.error}', context)
        
        # Rebuild index after sync
        indexed_count = await composition_index.rebuild()
        
        logger.info(f"Synchronized compositions and rebuilt index ({indexed_count} compositions)")
        
        return event_response_builder({
            'status': 'success',
            'sync_message': sync_result.message,
            'indexed_count': indexed_count,
            'message': f'Synchronized compositions and indexed {indexed_count} compositions'
        }, context)
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return error_response(str(e), context)


@event_handler("composition:git_info")
async def handle_git_info(data: CompositionGitInfoData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about git repositories for composition submodules."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    component_type = data.get('component_type')  # Optional: get info for specific component
    
    try:
        if component_type:
            # Get info for specific component
            repo_info = await git_manager.get_repository_info(component_type)
            return event_response_builder({
                'status': 'success',
                'repository_info': {
                    'path': str(repo_info.path),
                    'url': repo_info.url,
                    'branch': repo_info.branch,
                    'last_commit': repo_info.last_commit,
                    'has_changes': repo_info.has_changes,
                    'status': repo_info.status
                }
            }, context)
        else:
            # Get info for all components
            all_info = {}
            for comp_type in ['compositions', 'evaluations', 'capabilities']:
                try:
                    repo_info = await git_manager.get_repository_info(comp_type)
                    all_info[comp_type] = {
                        'path': str(repo_info.path),
                        'url': repo_info.url,
                        'branch': repo_info.branch,
                        'last_commit': repo_info.last_commit,
                        'has_changes': repo_info.has_changes,
                        'status': repo_info.status
                    }
                except Exception as e:
                    all_info[comp_type] = {'error': str(e)}
            
            return event_response_builder({
                'status': 'success',
                'repositories': all_info
            }, context)
            
    except Exception as e:
        logger.error(f"Git info failed: {e}")
        return error_response(str(e), context)


class CompositionReloadData(TypedDict):
    """Rebuild the composition index by scanning all composition files."""
    # No specific fields - rebuilds entire index
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionIndexFileData(TypedDict):
    """Index a specific composition file."""
    file_path: Required[str]  # Path to the composition file to index
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:rebuild_index")
@event_handler("composition:reload")  # Alias for backward compatibility
async def handle_rebuild_index(data: CompositionReloadData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Rebuild the composition index by scanning all composition files.
    
    This performs a full rebuild:
    1. Clears the existing index
    2. Scans all .yaml files in the compositions directory
    3. Re-indexes each valid composition file
    
    Note: Individual file saves are automatically indexed via composition:save.
    This is only needed for:
    - Initial setup or after manual file changes
    - Recovering from index corruption
    - Bulk imports of composition files
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    try:
        indexed_count = await composition_index.rebuild()
        
        # Clear component renderer cache to ensure fresh components are loaded
        renderer = get_renderer()
        renderer.clear_cache()
        logger.debug("Cleared component renderer cache after index rebuild")
        
        return event_response_builder(
            {
                'status': 'success',
                'indexed_count': indexed_count,
                'message': f'Indexed {indexed_count} compositions'
            },
            context=context
        )
    except Exception as e:
        logger.error(f"Index rebuild failed: {e}")
        return error_response(
            str(e),
            context=context
        )


@event_handler("composition:index_file")
async def handle_index_file(data: CompositionIndexFileData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Index a specific composition file."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    file_path = data.get('file_path')
    if not file_path:
        return error_response(
            'file_path required',
            context=context
        )
    
    try:
        success = await composition_index.index_file(Path(file_path))
        return event_response_builder(
            {
                'status': 'success' if success else 'failed',
                'file_path': file_path,
                'indexed': success
            },
            context=context
        )
    except Exception as e:
        logger.error(f"File indexing failed: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionSelectData(TypedDict):
    """Select the best composition for given context using intelligent scoring."""
    agent_id: NotRequired[str]  # Agent ID (defaults to 'unknown')
    role: NotRequired[str]  # Agent role
    capabilities: NotRequired[List[str]]  # Agent capabilities
    task: NotRequired[str]  # Task description
    style: NotRequired[str]  # Preferred style
    context: NotRequired[Dict[str, Any]]  # Context variables
    requirements: NotRequired[Dict[str, Any]]  # Requirements
    max_suggestions: NotRequired[int]  # Maximum number of suggestions (default: 1)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:select")
async def handle_select_composition(data: CompositionSelectData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Select the best composition for given context using intelligent scoring."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    try:
        # Build selection context from request data
        selection_context = SelectionContext(
            agent_id=data.get('agent_id', 'unknown'),
            role=data.get('role'),
            capabilities=data.get('capabilities', []),
            task_description=data.get('task'),
            preferred_style=data.get('style'),
            context_variables=data.get('context', {}),
            requirements=data.get('requirements', {})
        )
        
        # Get best composition
        result = await _select_composition_for_context(selection_context)
        
        # Get additional suggestions if requested
        max_suggestions = data.get('max_suggestions', 1)
        suggestions = []
        
        if max_suggestions > 1:
            # Get all scored compositions
            all_scored = await _get_scored_compositions(selection_context)
            suggestions = [
                {
                    'name': name,
                    'score': score,
                    'reasons': reasons
                }
                for name, score, reasons in all_scored[:max_suggestions]
            ]
        
        return event_response_builder(
            {
                'status': 'success',
                'selected': result.composition_name,
                'score': result.score,
                'reasons': result.reasons,
                'suggestions': suggestions,
                'fallback_used': result.fallback_used
            },
            context=context
        )
        
    except Exception as e:
        logger.error(f"Composition selection failed: {e}")
        return error_response(
            str(e),
            context=context
        )


# TypedDict definitions for composition:create
class CompositionCreateBase(TypedDict):
    """Base parameters for composition creation."""
    name: NotRequired[str]  # Auto-generated if not provided
    type: NotRequired[Literal['profile', 'prompt', 'orchestration', 'evaluation']]
    description: NotRequired[str]
    author: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]
    overwrite: NotRequired[bool]  # For save operations
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionCreateWithContent(CompositionCreateBase):
    """Create composition from full content."""
    content: Required[Dict[str, Any]]  # Full composition structure
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionCreateProfile(CompositionCreateBase):
    """Create profile composition with components."""
    type: Required[Literal['profile']]
    model: NotRequired[str]
    capabilities: NotRequired[List[str]]
    tools: NotRequired[List[str]]
    role: NotRequired[str]
    prompt: NotRequired[str]  # Optional prompt component
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionCreatePrompt(CompositionCreateBase):
    """Create prompt composition."""
    type: Required[Literal['prompt']]
    content: Required[str]  # The prompt text
    category: NotRequired[str]  # Categorization for prompts
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


# Union type for all composition creation variants
CompositionCreateData = Union[
    CompositionCreateWithContent,
    CompositionCreateProfile,
    CompositionCreatePrompt,
    CompositionCreateBase
]


class CompositionResult(TypedDict):
    """Standard result for composition operations."""
    status: str
    name: NotRequired[str]
    composition: NotRequired[Dict[str, Any]]
    path: NotRequired[str]
    message: NotRequired[str]
    error: NotRequired[str]


@event_handler("composition:create")
async def handle_create_composition(data: CompositionCreateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create and save a composition."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        # Handle metadata parameter if it's a JSON string
        from ksi_common.json_utils import parse_json_parameter
        parse_json_parameter(data, 'metadata')
        
        # TypedDict is still a dict at runtime
        name = data.get('name')  # Optional composition name (auto-generated if not provided)
        if not name:
            # Generate unique name
            import uuid
            name = f"dynamic_{uuid.uuid4().hex[:8]}"
        
        comp_type = data.get('type', 'profile')  # Composition type (profile, orchestration, etc)
        base_composition = data.get('extends', 'base_agent')  # Base composition to extend
        
        # Build composition structure
        composition = {
            'name': name,
            'type': comp_type,
            'version': '1.0.0',
            'description': data.get('description', f'Dynamically created {comp_type}'),
            'author': data.get('author', 'dynamic_agent'),
            'extends': base_composition,
            'components': [],
            'metadata': data.get('metadata', {})
        }
        
        # Add components
        if 'components' in data:
            composition['components'] = data['components']
        else:
            # Default components based on type
            if comp_type == 'profile':
                composition['components'] = [
                    {
                        'name': 'agent_config',
                        'inline': data.get('config', {
                            'role': data.get('role', 'assistant'),
                            'model': data.get('model', 'sonnet'),
                            'capabilities': data.get('capabilities', []),
                            'tools': data.get('tools', [])
                        })
                    }
                ]
                if 'prompt' in data:
                    composition['components'].append({
                        'name': 'prompt',
                        'template': data['prompt']
                    })
        
        # Add metadata for dynamic composition
        composition['metadata'].update({
            'dynamic': True,
            'created_at': format_for_logging(),
            'parent_agent': data.get('agent_id')
        })
        
        # Handle content based on composition type
        if 'content' in data:
            if comp_type == 'prompt':
                # For prompts, content is the prompt text
                composition['content'] = data['content']
                # Remove extends for prompt compositions
                composition.pop('extends', None)
            elif isinstance(data['content'], dict):
                # For other types, content might be a full composition structure
                composition = data['content']
            else:
                # If content is a string for non-prompt types, error
                return error_response(f"Invalid content type for {comp_type} composition", context)
            
        # Always save to disk (no more in-memory only compositions)
        # Create Composition object
        comp_obj = Composition.from_yaml(composition)
        save_result = await _save_composition_to_disk(comp_obj, overwrite=data.get('overwrite', False))
        
        if save_result['status'] != 'success':
            return save_result
            
        logger.info(f"Created and saved composition: {name}")
        
        return event_response_builder({
            'status': 'success',
            'name': name,
            'composition': composition,
            'path': save_result['path'],
            'message': f'Created and saved composition: {name}'
        }, context)
        
    except Exception as e:
        logger.error(f"Dynamic composition creation failed: {e}")
        return error_response(e, context)


# Core Composition Functions

async def _select_composition_for_context(context: SelectionContext) -> SelectionResult:
    """Select the best composition for the given context using scoring algorithm."""
    # Get all available compositions with metadata
    discovered = await composition_index.discover({
        'type': 'profile',  # Focus on profiles for agent compositions
        'include_metadata': True
    })
    
    if not discovered:
        return _get_fallback_selection()
    
    # Score each composition
    scored = []
    for comp_info in discovered:
        score, reasons = _score_composition_for_context(comp_info, context)
        if score > 0:
            scored.append((comp_info['name'], score, reasons))
    
    # Sort by score
    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        best_name, best_score, best_reasons = scored[0]
        
        logger.info(f"Selected composition '{best_name}' for {context.agent_id} (score: {best_score:.2f})")
        
        return SelectionResult(
            composition_name=best_name,
            score=best_score,
            reasons=best_reasons,
            fallback_used=False
        )
    else:
        logger.warning(f"No suitable composition found for {context.agent_id}, using fallback")
        return _get_fallback_selection()


async def _get_scored_compositions(context: SelectionContext) -> List[Tuple[str, float, List[str]]]:
    """Get all compositions scored for the context."""
    discovered = await composition_index.discover({
        'type': 'profile',
        'include_metadata': True
    })
    
    scored = []
    for comp_info in discovered:
        score, reasons = _score_composition_for_context(comp_info, context)
        if score > 0:
            scored.append((comp_info['name'], score, reasons))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _score_composition_for_context(comp_info: Dict[str, Any], context: SelectionContext) -> Tuple[float, List[str]]:
    """Score a composition against the selection context."""
    score = 0.0
    reasons = []
    
    metadata = comp_info.get('metadata', {})
    
    # 1. Role matching (weight: 30%)
    if context.role and metadata.get('role'):
        if context.role.lower() == metadata['role'].lower():
            score += 30
            reasons.append(f"Exact role match: {context.role}")
        elif context.role.lower() in metadata.get('compatible_roles', []):
            score += 20
            reasons.append(f"Compatible role: {context.role}")
    
    # 2. Capability requirements (weight: 25%)
    if context.capabilities:
        comp_caps = metadata.get('capabilities_required', [])
        comp_provides = metadata.get('capabilities_provided', [])
        
        # Check if composition requires capabilities the agent has
        if comp_caps:
            matching_caps = set(context.capabilities) & set(comp_caps)
            if matching_caps:
                cap_score = (len(matching_caps) / len(comp_caps)) * 25
                score += cap_score
                reasons.append(f"Capability match: {', '.join(matching_caps)}")
        
        # Check if composition provides capabilities the agent needs
        if comp_provides:
            useful_caps = set(comp_provides) & set(context.capabilities)
            if useful_caps:
                score += 10
                reasons.append(f"Provides useful capabilities: {', '.join(useful_caps)}")
    
    # 3. Task relevance (weight: 25%)
    if context.task_description:
        task_keywords = context.task_description.lower().split()
        
        # Check description
        desc_matches = sum(1 for kw in task_keywords if kw in comp_info.get('description', '').lower())
        if desc_matches:
            score += min(desc_matches * 5, 15)
            reasons.append(f"Description matches task ({desc_matches} keywords)")
        
        # Check tags
        comp_tags = [tag.lower() for tag in metadata.get('tags', [])]
        tag_matches = sum(1 for kw in task_keywords if any(kw in tag for tag in comp_tags))
        if tag_matches:
            score += min(tag_matches * 3, 10)
            reasons.append(f"Tags match task ({tag_matches} matches)")
    
    # 4. Style preference (weight: 10%)
    if context.preferred_style:
        comp_style = metadata.get('style', '').lower()
        if context.preferred_style.lower() in comp_style:
            score += 10
            reasons.append(f"Style match: {context.preferred_style}")
    
    # 5. General quality indicators (weight: 10%)
    # Prefer newer versions
    try:
        version = float(comp_info.get('version', '1.0'))
        if version >= 2.0:
            score += 5
            reasons.append("Recent version")
    except (ValueError, TypeError):
        # Invalid version format, skip scoring
        pass
    
    # Prefer well-documented compositions
    if len(metadata.get('use_cases', [])) >= 2:
        score += 3
        reasons.append("Well-documented use cases")
    
    if metadata.get('tested', False):
        score += 2
        reasons.append("Tested composition")
    
    return score, reasons


def _get_fallback_selection() -> SelectionResult:
    """Get fallback composition when no suitable match found."""
    return SelectionResult(
        composition_name='base_agent',
        score=0.0,
        reasons=['Fallback: no suitable composition found'],
        fallback_used=True
    )


async def load_composition(name: str, comp_type: Optional[str] = None) -> Composition:
    """Load a composition."""
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
    composition = await load_composition(name)
    
    # For markdown components without a components list, return the content itself
    if not composition.components and name.endswith('.md') or name.startswith('components/'):
        # This is a leaf component, return its content
        try:
            # Get the actual file path
            composition_path = await composition_index.get_path(name)
            if composition_path and composition_path.exists() and composition_path.suffix == '.md':
                content = composition_path.read_text()
                # Extract content after frontmatter
                from ksi_common.frontmatter_utils import parse_frontmatter
                post = parse_frontmatter(content)
                if post.has_frontmatter():
                    # Return the content after frontmatter as the prompt
                    return {
                        'prompt': post.content,
                        'metadata': composition.metadata if hasattr(composition, 'metadata') else {}
                    }
        except Exception as e:
            logger.warning(f"Failed to load component content for {name}: {e}")
    
    # Process inheritance
    if composition.extends:
        parent = await resolve_composition(composition.extends, 'profile', variables)
        # Merge parent configuration
        # (simplified - in production would do deep merge)
        if isinstance(parent, dict):
            result = parent.copy()
        else:
            logger.warning(f"Parent composition {composition.extends} returned non-dict: {type(parent)}")
            result = {}
    else:
        result = {}
    
    # Process mixins
    for mixin_name in composition.mixins:
        # Check if mixin is a component (markdown file)
        if mixin_name.endswith('.md') or mixin_name.startswith('components/'):
            # Load as component content
            try:
                component_content = load_component(mixin_name)
                # Add component content to appropriate field
                if 'system_prompt_base' not in result:
                    result['system_prompt_base'] = component_content
                else:
                    result['system_prompt_base'] += '\n\n' + component_content
            except FileNotFoundError:
                logger.error(f"Mixin component not found: {mixin_name}")
        else:
            # Load as composition
            mixin = await resolve_composition(mixin_name, 'profile', variables)
            # Merge mixin configuration
            if isinstance(mixin, dict):
                for key, value in mixin.items():
                    if key not in result:
                        result[key] = value
            else:
                logger.warning(f"Mixin composition {mixin_name} returned non-dict: {type(mixin)}")
    
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
            # Load from component file
            content = load_component(component.source)
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
    
    # Extract generated_content.system_prompt to prompt field for agent spawning compatibility
    if isinstance(result, dict) and 'generated_content' in result:
        generated_content = result.get('generated_content', {})
        if isinstance(generated_content, dict) and 'system_prompt' in generated_content:
            # Extract the system_prompt to the prompt field that agent spawning expects
            result['prompt'] = generated_content['system_prompt']
            logger.info(f"Extracted system_prompt from generated_content for composition {name}")
    
    # Resolve any remaining variables in the result
    if isinstance(result, dict):
        result_str = json_dumps(result)
        result_str = substitute_variables(result_str, variables)
        result = json_loads(result_str)
    
    return result


# Type-specific compose functions removed - composition:compose handles all types


def apply_minimal_redaction(composition_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Apply minimal redaction - only truly sensitive information.
    
    Philosophy: Give agents full context awareness, only remove genuine secrets.
    
    Args:
        composition_dict: The composition data to redact
    
    Returns:
        Tuple of (redacted_dict, list_of_redactions_applied)
    """
    import copy
    redacted = copy.deepcopy(composition_dict)
    redactions_applied = []
    
    # Only genuinely sensitive data
    sensitive_keys = [
        'password', 'secret', 'token', 'api_key', 'private_key',
        'auth_token', 'session_token', 'bearer_token'
    ]
    
    def redact_recursive(obj: Any, path: str = '') -> Any:
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Only redact truly sensitive keys
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    redactions_applied.append(f"Redacted sensitive key: {current_path}")
                    result[key] = "[REDACTED]"
                else:
                    result[key] = redact_recursive(value, current_path)
            return result
            
        elif isinstance(obj, list):
            return [redact_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
            
        elif isinstance(obj, str):
            # Only redact obvious secrets in string values
            for sensitive in sensitive_keys:
                if sensitive in obj.lower() and '=' in obj:
                    # Looks like key=value pair with sensitive data
                    parts = obj.split('=')
                    if len(parts) == 2:
                        redactions_applied.append(f"Redacted sensitive value in: {path}")
                        return f"{parts[0]}=[REDACTED]"
            return obj
            
        else:
            return obj
    
    redacted_composition = redact_recursive(redacted)
    return redacted_composition, redactions_applied


async def compose_agent_context(
    profile_name: str,
    agent_id: str,
    interaction_prompt: str = '',
    orchestration_name: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Compose complete agent context for self-configuring agents.
    
    Philosophy: Full context awareness - give agents complete view with minimal redaction.
    Let smart agents parse and understand their context rather than complex pre-processing.
    
    Args:
        profile_name: Agent profile name
        agent_id: Unique agent identifier
        interaction_prompt: Initial task/prompt for the agent
        orchestration_name: Name of orchestration if agent is part of one
        variables: Variables for composition substitution
    
    Returns:
        Dict with 'message', 'composition_context', 'redaction_applied'
    """
    if variables is None:
        variables = {}
    
    try:
        # Build complete agent context
        profile_data = await load_composition_raw(profile_name, 'profile')
        
        # Apply agent spawn-time variable substitution
        spawn_vars = {
            'agent_id': agent_id,
            **variables  # Include any passed variables
        }
        
        # Substitute variables in the system_prompt if present
        if isinstance(profile_data, dict):
            # Look for system_prompt in components
            if 'components' in profile_data:
                for component in profile_data['components']:
                    if isinstance(component, dict) and 'inline' in component:
                        inline_data = component['inline']
                        if isinstance(inline_data, dict) and 'system_prompt' in inline_data:
                            # Substitute variables in system_prompt
                            inline_data['system_prompt'] = substitute_variables(
                                inline_data['system_prompt'], 
                                spawn_vars
                            )
        
        context = {
            'agent_id': agent_id,
            'agent_profile': profile_data
        }
        
        # Add full orchestration context if available
        if orchestration_name:
            try:
                context['orchestration'] = await load_composition_raw(orchestration_name, 'orchestration')
            except FileNotFoundError:
                logger.warning(f"Orchestration {orchestration_name} not found, proceeding without it")
        
        # Add variables if provided
        if variables:
            context['variables'] = variables
        
        # Add interaction prompt
        if interaction_prompt:
            context['interaction_prompt'] = interaction_prompt
        
        # Apply minimal redaction - only remove genuine secrets
        redacted_context, redactions_applied = apply_minimal_redaction(context)
        
        # Create simple boilerplate
        boilerplate = f"""You are agent {agent_id} in the KSI (Knowledge System Infrastructure) system.

Your complete configuration context is provided below in YAML format.

Please read and understand your configuration, then self-configure and begin operating:

1. Parse your agent profile to understand your capabilities and role
2. If part of an orchestration, understand the full workflow and your relationships with other agents
3. Extract any initial tasks or prompts directed at you
4. Begin autonomous operation according to your configuration

"""
        
        if interaction_prompt:
            boilerplate += f"Your initial task: {interaction_prompt}\n\n"
        
        # Format as YAML for agent consumption
        composition_yaml = safe_dump(redacted_context)
        
        # Combine boilerplate with full context
        full_message = boilerplate + "=== YOUR COMPLETE CONTEXT ===\n```yaml\n" + composition_yaml + "\n```\n\nPlease proceed according to your configuration."
        
        return {
            'message': full_message,
            'composition_context': redacted_context,
            'redaction_applied': redactions_applied,
            'boilerplate': boilerplate,
            'composition_yaml': composition_yaml
        }
        
    except Exception as e:
        logger.error(f"Failed to compose agent context for {profile_name}: {e}")
        # Return minimal fallback
        fallback_message = f"""You are agent {agent_id} in the KSI system.

Error loading your configuration: {str(e)}

{f"Your initial task: {interaction_prompt}" if interaction_prompt else "Please await further instructions."}

Please proceed as a basic autonomous agent with full autonomy to execute tasks and emit JSON events."""
        
        return {
            'message': fallback_message,
            'composition_context': {},
            'redaction_applied': [],
            'error': str(e)
        }


# Component Management Event Handlers
class ComponentCreateData(TypedDict):
    """Create a component (fragment, template, etc.) with content."""
    name: Required[str]  # Component name (can include path like "instructions/persona_bypass")
    content: Required[str]  # The actual content (markdown, text, etc.)
    type: NotRequired[Literal['component', 'template', 'instruction']]  # Default: component
    description: NotRequired[str]  # Component description
    metadata: NotRequired[Dict[str, Any]]  # Additional metadata
    overwrite: NotRequired[bool]  # Replace if exists
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class ComponentGetData(TypedDict):
    """Get a component with its content."""
    name: Required[str]  # Component name/path
    type: NotRequired[Literal['component', 'template', 'instruction']]  # Default: component
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class ComponentForkData(TypedDict):
    """Fork a component to create a variant."""
    parent: Required[str]  # Parent component name/path
    name: Required[str]  # New component name/path
    modifications: NotRequired[str]  # Modified content (if not provided, copies parent)
    reason: NotRequired[str]  # Reason for forking
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class ComponentUpdateData(TypedDict):
    """Update an existing component."""
    name: Required[str]  # Component name/path
    content: Required[str]  # New content
    type: NotRequired[Literal['component', 'template', 'instruction']]  # Default: component
    message: NotRequired[str]  # Git commit message
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:create_component")
async def handle_create_component(data: ComponentCreateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a component (fragment/template) with content preserved."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        name = _normalize_component_name(data['name'])
        content = data['content']
        comp_type = data.get('type', 'component')
        
        # Determine base path based on type using shared utility
        base_path = get_composition_base_path(comp_type)
        
        # Create file path - handle subdirectories in name
        if '/' in name:
            file_path = base_path / f"{name}.md"
        else:
            # For components without subdirectory, put in type subdirectory
            file_path = base_path / comp_type / f"{name}.md"
        ensure_directory(file_path.parent)
        
        # Check if exists
        if file_path.exists() and not data.get('overwrite', False):
            return error_response(f"Component {name} already exists", context)
        
        # Write content directly
        file_path.write_text(content)
        
        # Write metadata if provided
        if data.get('metadata'):
            metadata_path = file_path.with_suffix('.yaml')
            save_yaml_file(metadata_path, data['metadata'])
        
        # Git commit - use direct git operations for markdown files
        import subprocess
        repo_path = COMPOSITIONS_BASE
        relative_path = file_path.relative_to(repo_path)
        
        try:
            # Add file to git
            subprocess.run(['git', 'add', str(relative_path)], 
                         cwd=repo_path, check=True, capture_output=True)
            
            # Commit
            commit_msg = f"Create {comp_type} component: {name}"
            subprocess.run(['git', 'commit', '-m', commit_msg], 
                         cwd=repo_path, check=True, capture_output=True)
            
            git_result = type('GitResult', (), {
                'success': True,
                'message': f'Committed {relative_path}'
            })()
        except subprocess.CalledProcessError as e:
            # If nothing to commit, that's ok
            if b"nothing to commit" in e.stderr:
                git_result = type('GitResult', (), {
                    'success': True,
                    'message': 'No changes to commit'
                })()
            else:
                git_result = type('GitResult', (), {
                    'success': False,
                    'error': e.stderr.decode()
                })()
        except Exception as e:
            git_result = type('GitResult', (), {
                'success': False,
                'error': str(e)
            })()
        
        if not git_result.success:
            return error_response(f"Git operation failed: {git_result.error}", context)
        
        # Update index - all compositions should be indexed (unified architecture)
        await composition_index.index_file(file_path.relative_to(config.compositions_dir))
        
        # Clear component renderer cache to ensure fresh component is loaded
        renderer = get_renderer()
        renderer.clear_cache()
        logger.debug(f"Cleared component renderer cache after creating/updating component: {name}")
        
        logger.info(f"Created component: {name} ({comp_type})")
        
        return event_response_builder({
            'status': 'success',
            'name': name,
            'type': comp_type,
            'path': str(file_path.relative_to(config.lib_dir)),
            'message': f'Created {comp_type} component: {name}'
        }, context)
        
    except Exception as e:
        logger.error(f"Component creation failed: {e}")
        return error_response(str(e), context)


@event_handler("composition:get_component")
async def handle_get_component(data: ComponentGetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a component with its content."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        name = normalize_composition_name(data['name'])
        comp_type = data.get('type', 'component')
        
        # Use shared utility to load composition with proper path resolution
        try:
            metadata, content, file_path = load_composition_with_metadata(name, comp_type)
        except FileNotFoundError:
            return error_response(f"Composition '{name}' not found", context)
        
        # Parse frontmatter using modern frontmatter utilities
        try:
            post = parse_frontmatter(content, sanitize_dates=True)
            frontmatter = post.metadata if post.has_frontmatter() else None
            body_content = post.content
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter in {name}: {e}")
            # Fallback to simple component
            frontmatter = None
            body_content = content
        
        # Get external metadata if stored (legacy support)
        external_metadata = {}
        metadata_path = file_path.with_suffix('.yaml')
        if metadata_path.exists():
            external_metadata = load_yaml_file(metadata_path)
            # Sanitize external metadata too
            external_metadata = sanitize_for_json(external_metadata)
        
        # Merge metadata sources (frontmatter takes precedence)
        metadata = external_metadata.copy()
        if frontmatter:
            metadata.update(frontmatter)
        
        # Determine component classification
        component_classification = 'enhanced' if frontmatter else 'simple'
        
        return event_response_builder({
            'status': 'success',
            'name': name,
            'type': comp_type,
            'component_type': component_classification,  # 'simple' or 'enhanced'
            'content': body_content,  # Content without frontmatter
            'frontmatter': frontmatter,  # Parsed frontmatter (if any)
            'metadata': metadata,  # Combined metadata
            'path': str(file_path.relative_to(config.lib_dir))
        }, context)
        
    except Exception as e:
        logger.error(f"Component retrieval failed: {e}")
        return error_response(str(e), context)


class ComponentRenderData(TypedDict):
    """Render a component with variable substitution and mixin resolution."""
    name: str  # Component name to render
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution
    include_metadata: NotRequired[bool]  # Include metadata in response
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionInspectData(TypedDict):
    """Inspect a component and return its dependency tree."""
    component: Required[str]  # Component name to inspect (e.g., "orchestrations/optimization/hybrid_marketplace")
    variables: NotRequired[Dict[str, Any]]  # Variables for conditional dependency resolution
    output_format: NotRequired[Literal['tree', 'json', 'summary']]  # Output format (default: tree)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:render_component")
async def handle_render_component(data: ComponentRenderData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Render a component with full mixin resolution and variable substitution."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        name = _normalize_component_name(data['name'])
        variables = data.get('variables', {})
        include_metadata = data.get('include_metadata', False)
        
        # Ensure variables is a dictionary
        if isinstance(variables, str):
            try:
                variables = json_loads(variables)
            except Exception:
                variables = {}
        elif not isinstance(variables, dict):
            variables = {}
        
        # Get renderer and render component
        renderer = get_renderer()
        rendered_content = renderer.render(name, variables)
        
        response_data = {
            'status': 'success',
            'name': name,
            'type': 'component',
            'rendered_content': rendered_content,
            'variables': variables
        }
        
        # Include metadata if requested
        if include_metadata:
            cache_stats = renderer.get_cache_stats()
            response_data['cache_stats'] = cache_stats
            
        return event_response_builder(response_data, context)
        
    except CircularDependencyError as e:
        logger.error(f"Circular dependency in component {name}: {e}")
        return error_response(f"Circular dependency detected: {e}", context)
    except ComponentResolutionError as e:
        logger.error(f"Component resolution failed for {name}: {e}")
        return error_response(f"Component resolution failed: {e}", context)
    except Exception as e:
        logger.error(f"Component rendering failed: {e}")
        return error_response(f"Component rendering failed: {e}", context)


@event_handler("composition:inspect")
async def handle_inspect(data: CompositionInspectData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Inspect a component and return its dependency tree."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        component_name = data['component']
        variables = data.get('variables', {})
        output_format = data.get('output_format', 'tree')
        
        # Ensure variables is a dictionary
        if isinstance(variables, str):
            try:
                variables = json_loads(variables)
            except Exception:
                variables = {}
        elif not isinstance(variables, dict):
            variables = {}
        
        # Get renderer and inspect component
        renderer = get_renderer()
        inspection_result = renderer.inspect(component_name, variables)
        
        # Format output based on requested format
        if output_format == 'tree':
            # Format as tree string
            tree_output = _format_dependency_tree(inspection_result['dependency_tree'])
            response_data = {
                'status': 'success',
                'component': component_name,
                'tree': tree_output,
                'summary': {
                    'type': inspection_result['type'],
                    'version': inspection_result['version'],
                    'description': inspection_result['description'],
                    'direct_dependencies': len(inspection_result['dependencies']),
                    'total_dependencies': len(inspection_result['transitive_dependencies']) + 1,
                    'capabilities': inspection_result['capabilities']
                }
            }
        elif output_format == 'summary':
            # Just the summary info
            response_data = {
                'status': 'success',
                'component': component_name,
                'type': inspection_result['type'],
                'version': inspection_result['version'],
                'description': inspection_result['description'],
                'dependencies': inspection_result['dependencies'],
                'transitive_dependencies': inspection_result['transitive_dependencies'],
                'capabilities': inspection_result['capabilities']
            }
        else:  # json format
            # Full JSON structure
            response_data = {
                'status': 'success',
                'component': component_name,
                'inspection': inspection_result
            }
        
        return event_response_builder(response_data, context)
        
    except CircularDependencyError as e:
        logger.error(f"Circular dependency in component: {e}")
        return error_response(f"Circular dependency detected: {e}", context)
    except ComponentResolutionError as e:
        logger.error(f"Component inspection failed: {e}")
        return error_response(f"Component inspection failed: {e}", context)
    except Exception as e:
        logger.error(f"Component inspection failed: {e}")
        return error_response(f"Component inspection failed: {e}", context)


def _format_dependency_tree(tree: Dict[str, Any], indent: int = 0) -> str:
    """Format dependency tree as readable string."""
    lines = []
    prefix = "  " * indent
    
    # Handle error or circular reference
    if tree.get('error'):
        lines.append(f"{prefix}├── {tree['name']} (ERROR: {tree['error']})")
        return "\n".join(lines)
    if tree.get('circular_reference'):
        lines.append(f"{prefix}├── {tree['name']} (circular reference)")
        return "\n".join(lines)
    if tree.get('max_depth_reached'):
        lines.append(f"{prefix}├── {tree['name']} (max depth)")
        return "\n".join(lines)
    
    # Format current node
    node_info = f"{tree['name']} [{tree.get('type', 'unknown')} v{tree.get('version', '0.0.0')}]"
    if indent == 0:
        lines.append(node_info)
    else:
        lines.append(f"{prefix}├── {node_info}")
    
    # Add capabilities if present
    if tree.get('capabilities'):
        cap_prefix = "  " * (indent + 1)
        lines.append(f"{cap_prefix}capabilities: {', '.join(tree['capabilities'])}")
    
    # Format dependencies
    if tree.get('dependencies'):
        dep_prefix = "  " * (indent + 1)
        lines.append(f"{dep_prefix}dependencies:")
        for dep in tree['dependencies']:
            if isinstance(dep, dict):
                lines.extend(_format_dependency_tree(dep, indent + 2).split('\n'))
            else:
                lines.append(f"{dep_prefix}  ├── {dep}")
    
    # Format mixins
    if tree.get('mixins'):
        mixin_prefix = "  " * (indent + 1)
        lines.append(f"{mixin_prefix}mixins:")
        for mixin in tree['mixins']:
            if isinstance(mixin, dict):
                lines.extend(_format_dependency_tree(mixin, indent + 2).split('\n'))
            else:
                lines.append(f"{mixin_prefix}  ├── {mixin}")
    
    return "\n".join(lines)


@event_handler("composition:fork_component")
async def handle_fork_component(data: ComponentForkData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fork a component to create a variant."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        # Get parent component
        parent_result = await handle_get_component({
            'name': data['parent']
        }, context)
        
        if parent_result['status'] != 'success':
            return error_response(f"Parent component not found: {data['parent']}", context)
        
        # Create forked component
        content = data.get('modifications', parent_result['content'])
        
        create_result = await handle_create_component({
            'name': data['name'],
            'content': content,
            'type': parent_result.get('type', 'component'),
            'description': data.get('reason', f"Forked from {data['parent']}"),
            'metadata': {
                'parent': data['parent'],
                'fork_reason': data.get('reason', 'variant'),
                'forked_at': format_for_logging()
            },
            'overwrite': False
        }, context)
        
        return create_result
        
    except Exception as e:
        logger.error(f"Component fork failed: {e}")
        return error_response(str(e), context)


@event_handler("composition:update_component") 
async def handle_update_component(data: ComponentUpdateData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update an existing component."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        # Check if exists
        get_result = await handle_get_component({
            'name': data['name'],
            'type': data.get('type', 'component')
        }, context)
        
        if get_result['status'] != 'success':
            return error_response(f"Component {data['name']} not found", context)
        
        # Update with overwrite
        update_result = await handle_create_component({
            'name': data['name'],
            'content': data['content'],
            'type': data.get('type', 'component'),
            'overwrite': True
        }, context)
        
        return update_result
        
    except Exception as e:
        logger.error(f"Component update failed: {e}")
        return error_response(str(e), context)


# Pattern Evolution Event Handlers

class CompositionForkData(TypedDict):
    """Fork a composition to create a variant."""
    parent: Required[str]  # Name of parent composition
    name: Required[str]  # Name for forked composition
    reason: Required[str]  # Reason for forking
    modifications: NotRequired[Dict[str, Any]]  # Initial modifications
    author: NotRequired[str]  # Defaults to agent_id
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:fork")
async def handle_fork_composition(data: CompositionForkData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fork a composition to create a variant with git-based lineage tracking."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    parent_name = data.get('parent')
    new_name = data.get('name')
    fork_reason = data.get('reason', 'Experimental variant')
    modifications = data.get('modifications', {})
    author = data.get('author', data.get('agent_id', 'unknown'))
    
    if not parent_name or not new_name:
        return error_response('Both parent and name required for fork', context)
    
    try:
        # Use git manager to fork the composition
        git_result = await git_manager.fork_component(
            component_type="compositions",
            source_name=parent_name,
            target_name=new_name
        )
        
        if not git_result.success:
            return error_response(f'Fork failed: {git_result.error}', context)
        
        # Load the forked composition to apply modifications
        if modifications:
            forked_comp = await load_composition(new_name)
            
            # Apply modifications
            for key, value in modifications.items():
                if hasattr(forked_comp, key):
                    setattr(forked_comp, key, value)
            
            # Update metadata with fork info
            forked_comp.metadata.update({
                'fork_reason': fork_reason,
                'fork_author': author,
                'modifications_applied': list(modifications.keys())
            })
            
            # Save the modified fork
            save_result = await _save_composition_to_disk(forked_comp, overwrite=True)
            if save_result['status'] != 'success':
                return error_response(f'Failed to save modified fork: {save_result["error"]}', context)
        
        logger.info(f"Forked composition {parent_name} -> {new_name} (commit: {git_result.commit_hash})")
        
        return event_response_builder({
            'status': 'success',
            'parent': parent_name,
            'fork': new_name,
            'commit_hash': git_result.commit_hash,
            'files_changed': git_result.files_changed,
            'message': f'Forked composition {parent_name} -> {new_name}'
        }, context)
        
    except Exception as e:
        logger.error(f"Fork failed: {e}")
        return error_response(e, context)


class CompositionMergeData(TypedDict):
    """Merge improvements from fork back to parent."""
    source: Required[str]  # Name of source (fork)
    target: Required[str]  # Name of target (parent)
    strategy: Required[Literal['selective', 'full', 'metadata_only']]
    improvements: NotRequired[List[str]]  # List of improvements
    validation_results: NotRequired[Dict[str, Any]]  # Evaluation results
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:merge")
async def handle_merge_composition(data: CompositionMergeData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge improvements from a forked composition back to parent."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    source_name = data.get('source')
    target_name = data.get('target')
    strategy = data.get('strategy', 'selective')
    improvements = data.get('improvements', [])
    validation_results = data.get('validation_results', {})
    
    if not source_name or not target_name:
        return error_response('Both source and target required for merge', context)
    
    try:
        # Load both compositions
        source = await load_composition(source_name)
        target = await load_composition(target_name)
        
        # Verify lineage - source should be fork of target
        lineage = source.metadata.get('lineage', {})
        if not lineage.get('parent', '').startswith(target_name):
            return error_response(f'{source_name} is not a fork of {target_name}', context)
        
        # Prepare merge based on strategy
        updates = {}
        
        if strategy == 'full':
            # Full merge - take all changes from source
            updates = {
                'components': source.components,
                'variables': source.variables,
                'metadata': {**target.metadata, **source.metadata}
            }
        
        elif strategy == 'selective':
            # Selective merge - only specific improvements
            # This would require more sophisticated diffing
            updates['metadata'] = target.metadata.copy()
            
            # Track merge in metadata
            updates['metadata']['merges'] = updates['metadata'].get('merges', [])
            updates['metadata']['merges'].append({
                'from': source_name,
                'date': timestamp_utc(),
                'improvements': improvements,
                'validation': validation_results
            })
            
            # Copy performance metrics if better
            if 'performance' in source.metadata:
                source_perf = source.metadata['performance']
                target_perf = target.metadata.get('performance', {})
                
                if source_perf.get('avg_score', 0) > target_perf.get('avg_score', 0):
                    updates['metadata']['performance'] = source_perf
        
        elif strategy == 'metadata_only':
            # Only merge metadata (learnings, performance)
            updates['metadata'] = {
                **target.metadata,
                'learnings': source.metadata.get('learnings', []),
                'performance': source.metadata.get('performance', {})
            }
        
        # Apply updates
        result = await handle_update_composition({
            'name': target_name,
            'updates': updates
        })
        
        if result.get('status') == 'success':
            logger.info(f"Merged {source_name} -> {target_name} using {strategy} strategy")
        
        return result
        
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        return error_response(e, context)


class CompositionAgentContextData(TypedDict):
    """Compose agent context for self-configuring agents."""
    profile: Required[str]  # Agent profile name
    agent_id: Required[str]  # Agent ID for context
    interaction_prompt: NotRequired[str]  # Initial interaction prompt
    orchestration: NotRequired[str]  # Orchestration name if part of one
    variables: NotRequired[Dict[str, Any]]  # Variables for composition
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:agent_context")
async def handle_compose_agent_context(data: CompositionAgentContextData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose agent context for self-configuring agents."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    profile_name = data.get('profile')
    agent_id = data.get('agent_id')
    interaction_prompt = data.get('interaction_prompt', '')
    orchestration_name = data.get('orchestration')
    variables = data.get('variables', {})
    
    if not profile_name or not agent_id:
        return error_response('Profile name and agent_id required', context)
    
    try:
        result = await compose_agent_context(
            profile_name, agent_id, interaction_prompt, 
            orchestration_name, variables
        )
        return event_response_builder({
            'status': 'success',
            'agent_context_message': result['message'],
            'composition_context': result['composition_context'],
            'redaction_applied': result['redaction_applied'],
            'composition_yaml': result['composition_yaml']
        }, context)
    except Exception as e:
        logger.error(f"Agent context composition failed: {e}")
        return error_response(e, context)


class CompositionDiffData(TypedDict):
    """Show differences between compositions."""
    left: Required[str]  # First composition
    right: Required[str]  # Second composition
    detail_level: NotRequired[Literal['summary', 'detailed', 'full']]
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:diff")
async def handle_diff_composition(data: CompositionDiffData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Show differences between two compositions."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    left_name = data.get('left')
    right_name = data.get('right')
    detail_level = data.get('detail_level', 'summary')
    
    if not left_name or not right_name:
        return error_response('Both left and right compositions required', context)
    
    try:
        # Load both compositions
        left = await load_composition(left_name)
        right = await load_composition(right_name)
        
        differences = {
            'left': {'name': left_name, 'version': left.version},
            'right': {'name': right_name, 'version': right.version},
            'changes': {}
        }
        
        # Compare basic fields
        for field in ['type', 'description', 'author', 'extends']:
            left_val = getattr(left, field, None)
            right_val = getattr(right, field, None)
            if left_val != right_val:
                differences['changes'][field] = {
                    'left': left_val,
                    'right': right_val
                }
        
        # Compare components
        left_comps = {c.name: c for c in left.components}
        right_comps = {c.name: c for c in right.components}
        
        comp_changes = {}
        for name in set(left_comps.keys()) | set(right_comps.keys()):
            if name not in left_comps:
                comp_changes[name] = {'status': 'added'}
            elif name not in right_comps:
                comp_changes[name] = {'status': 'removed'}
            elif left_comps[name] != right_comps[name]:
                comp_changes[name] = {'status': 'modified'}
                if detail_level in ['detailed', 'full']:
                    # Add more details about what changed
                    comp_changes[name]['changes'] = {
                        'left': left_comps[name],
                        'right': right_comps[name]
                    }
        
        if comp_changes:
            differences['changes']['components'] = comp_changes
        
        # Compare metadata
        if detail_level in ['detailed', 'full']:
            meta_diff = {}
            all_keys = set(left.metadata.keys()) | set(right.metadata.keys())
            for key in all_keys:
                left_val = left.metadata.get(key)
                right_val = right.metadata.get(key)
                if left_val != right_val:
                    meta_diff[key] = {
                        'left': left_val,
                        'right': right_val
                    }
            if meta_diff:
                differences['changes']['metadata'] = meta_diff
        
        # Check lineage relationship
        left_lineage = left.metadata.get('lineage', {})
        right_lineage = right.metadata.get('lineage', {})
        
        if left_lineage.get('parent', '').startswith(right_name):
            differences['relationship'] = f"{left_name} is a fork of {right_name}"
        elif right_lineage.get('parent', '').startswith(left_name):
            differences['relationship'] = f"{right_name} is a fork of {left_name}"
        else:
            differences['relationship'] = "No direct lineage relationship"
        
        return event_response_builder({
            'status': 'success',
            'differences': differences
        }, context)
        
    except Exception as e:
        logger.error(f"Diff failed: {e}")
        return error_response(e, context)


class CompositionInitialMessageData(TypedDict):
    """Compose initial message for agent spawning."""
    profile: Required[str]  # Agent profile name
    interaction_prompt: NotRequired[str]  # Initial interaction prompt
    variables: NotRequired[Dict[str, Any]]  # Variables for composition
    format_style: NotRequired[Literal['concatenated', 'structured', 'custom']]  # Message format style
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CompositionTrackDecisionData(TypedDict):
    """Track orchestrator decisions for learning."""
    pattern: Required[str]  # Pattern name
    decision: Required[str]  # Decision made
    context: Required[Dict[str, Any]]  # Decision context
    outcome: Required[str]  # Decision outcome
    confidence: NotRequired[float]  # Confidence 0-1
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:initial_message")
async def handle_compose_initial_message(data: CompositionInitialMessageData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose initial message for agent spawning using composition system."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    profile_name = data.get('profile')
    interaction_prompt = data.get('interaction_prompt', '')
    variables = data.get('variables', {})
    format_style = data.get('format_style', 'concatenated')
    
    if not profile_name:
        return error_response('Profile name required', context)
    
    try:
        result = await compose_initial_message(profile_name, interaction_prompt, variables, format_style)
        return event_response_builder({
            'status': 'success',
            'initial_message': result['message'],
            'agent_prompt': result['agent_prompt'],
            'interaction_prompt': result['interaction_prompt'],
            'format_style': result['format_style']
        }, context)
    except Exception as e:
        logger.error(f"Initial message composition failed: {e}")
        return error_response(e, context)


@event_handler("composition:track_decision")
async def handle_track_decision(data: CompositionTrackDecisionData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Track orchestrator decisions for pattern learning."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    pattern_name = data.get('pattern')
    decision = data.get('decision')
    context = data.get('context', {})
    outcome = data.get('outcome')
    confidence = data.get('confidence', 0.5)
    agent_id = data.get('agent_id', 'unknown')
    
    if not pattern_name or not decision:
        return error_response('Pattern name and decision required', context)
    
    try:
        # Store decision in pattern-specific decision log
        decision_record = {
            'pattern': pattern_name,
            'decision': decision,
            'context': context,
            'outcome': outcome,
            'confidence': confidence,
            'agent_id': agent_id,
            'timestamp': timestamp_utc()
        }
        
        # Save to decisions file alongside pattern
        decisions_path = config.compositions_dir / 'orchestrations' / f"{pattern_name}_decisions.yaml"
        
        # Load existing decisions or create new list
        if decisions_path.exists():
            with open(decisions_path, 'r') as f:
                decisions = safe_load(f.read()) or []
        else:
            decisions = []
        
        # Append new decision
        decisions.append(decision_record)
        
        # Save updated decisions
        save_yaml_file(decisions_path, decisions)
        
        # Also update pattern metadata with high-level insights
        try:
            pattern = await load_composition(pattern_name, 'orchestration')
            
            # Update decision statistics in metadata
            if 'decision_stats' not in pattern.metadata:
                pattern.metadata['decision_stats'] = {
                    'total_decisions': 0,
                    'common_adaptations': {}
                }
            
            pattern.metadata['decision_stats']['total_decisions'] += 1
            
            # Track common adaptations
            adaptations = pattern.metadata['decision_stats']['common_adaptations']
            if decision not in adaptations:
                adaptations[decision] = 0
            adaptations[decision] += 1
            
            # Save updated pattern metadata
            await handle_update_composition({
                'name': pattern_name,
                'updates': {'metadata': pattern.metadata}
            })
            
        except Exception as meta_error:
            logger.warning(f"Could not update pattern metadata: {meta_error}")
        
        logger.debug(f"Tracked decision for pattern {pattern_name}: {decision} -> {outcome}")
        
        return event_response_builder({
            'status': 'success',
            'tracked': decision_record,
            'decisions_file': str(decisions_path)
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to track decision: {e}")
        return error_response(e, context)


# KSI System Integration Event Handlers (Phase 4)

class ComponentToProfileData(TypedDict):
    """Convert component to agent profile."""
    component: Required[str]  # Component name to convert
    profile_name: NotRequired[str]  # Optional profile name (default: temp_profile_{hash})
    variables: NotRequired[Dict[str, Any]]  # Variables for component rendering
    save_to_disk: NotRequired[bool]  # Whether to save profile to disk (default: False)
    overwrite: NotRequired[bool]  # Whether to overwrite existing profile (default: False)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:component_to_profile")
async def handle_component_to_profile(data: ComponentToProfileData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert a component to an agent profile for spawning."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        component_name = data['component']
        variables = data.get('variables', {})
        save_to_disk = data.get('save_to_disk', False)
        overwrite = data.get('overwrite', False)
        
        # Generate profile name if not provided
        profile_name = data.get('profile_name')
        if not profile_name:
            # Create a temporary profile name based on component name and hash
            import hashlib
            var_hash = hashlib.sha256(json_dumps(variables).encode()).hexdigest()[:8]
            profile_name = f"temp_profile_{component_name.replace('/', '_')}_{var_hash}"
        
        # Render the component with variables
        render_result = await handle_render_component({
            'name': component_name,
            'variables': variables,
            'include_metadata': True
        }, context)
        
        if render_result['status'] != 'success':
            return error_response(f"Failed to render component {component_name}: {render_result.get('error')}", context)
        
        rendered_content = render_result['rendered_content']
        component_metadata = render_result.get('cache_stats', {})
        
        # Create profile structure in proper composition format
        profile_data = {
            'name': profile_name,
            'type': 'profile',
            'version': '1.0.0',
            'description': f'Profile generated from component {component_name}',
            'author': 'composition:component_to_profile',
            'components': [
                {
                    'name': 'agent_config',
                    'inline': {
                        'model': 'sonnet',
                        'capabilities': ['conversation', 'analysis', 'task_execution'],
                        'message_queue_size': 100,
                        'priority': 'normal'
                    }
                },
                {
                    'name': 'generated_content',
                    'inline': {
                        'system_prompt': rendered_content
                    }
                }
            ],
            'variables': variables if isinstance(variables, dict) else {},
            'metadata': {
                'source_component': component_name,
                'component_metadata': component_metadata,
                'render_timestamp': format_for_logging(),
                'generated_by': 'composition:component_to_profile'
            }
        }
        
        # Save to disk if requested
        if save_to_disk:
            # Check if profile already exists
            profiles_dir = config.compositions_dir / 'profiles'
            profile_path = profiles_dir / f"{profile_name}.yaml"
            
            if profile_path.exists() and not overwrite:
                return error_response(f"Profile {profile_name} already exists. Use overwrite=true to replace.", context)
            
            # Ensure directory exists
            ensure_directory(profiles_dir)
            
            # Save profile to disk
            save_yaml_file(profile_path, profile_data)
            
            # Profile saved locally for runtime use (no git commit needed for temp artifacts)
            logger.info(f"Generated profile {profile_name} from component {component_name}")
        
        return event_response_builder({
            'status': 'success',
            'profile_name': profile_name,
            'profile_data': profile_data,
            'source_component': component_name,
            'variables_used': variables,
            'saved_to_disk': save_to_disk,
            'render_metadata': render_result.get('cache_stats', {})
        }, context)
        
    except Exception as e:
        logger.error(f"Component to profile conversion failed: {e}")
        return error_response(f"Component to profile conversion failed: {e}", context)


class ComponentGenerateOrchestrationData(TypedDict):
    """Generate orchestration pattern from component."""
    component: Required[str]  # Component name to use as orchestration template
    pattern_name: NotRequired[str]  # Generated pattern name (default: orchestration_{component})
    variables: NotRequired[Dict[str, Any]]  # Variables for component rendering
    save_to_disk: NotRequired[bool]  # Whether to save orchestration to disk (default: False)
    overwrite: NotRequired[bool]  # Whether to overwrite existing orchestration (default: False)
    agent_profile: NotRequired[str]  # Default agent profile to use (default: base_single_agent)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:generate_orchestration")
async def handle_generate_orchestration(data: ComponentGenerateOrchestrationData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate an orchestration pattern from a component."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        component_name = data['component']
        variables = data.get('variables', {})
        save_to_disk = data.get('save_to_disk', False)
        overwrite = data.get('overwrite', False)
        agent_profile = data.get('agent_profile', 'base_single_agent')
        
        # Generate pattern name if not provided
        pattern_name = data.get('pattern_name')
        if not pattern_name:
            pattern_name = f"orchestration_{component_name.replace('/', '_')}"
        
        # Render the component with variables
        render_result = await handle_render_component({
            'name': component_name,
            'variables': variables,
            'include_metadata': True
        }, context)
        
        if render_result['status'] != 'success':
            return error_response(f"Failed to render component {component_name}: {render_result.get('error')}", context)
        
        rendered_content = render_result['rendered_content']
        
        # Generate orchestration pattern structure
        orchestration_data = {
            'name': pattern_name,
            'type': 'orchestration',
            'description': f"Generated orchestration pattern from component {component_name}",
            'agents': {
                'main_agent': {
                    'profile': agent_profile,
                    'vars': {
                        'initial_prompt': rendered_content
                    }
                }
            },
            'orchestration_logic': {
                'strategy': f"""
                    # Generated orchestration from component: {component_name}
                    
                    SPAWN main_agent WITH initial_prompt=\"{rendered_content[:100]}...\"
                    AWAIT main_agent COMPLETION
                    TRACK results
                    CLEANUP all agents
                """.strip()
            },
            'variables': variables,
            'metadata': {
                'source_component': component_name,
                'component_metadata': render_result.get('cache_stats', {}),
                'generation_timestamp': format_for_logging(),
                'generated_by': 'composition:generate_orchestration'
            }
        }
        
        # Save to disk if requested
        if save_to_disk:
            # Check if orchestration already exists
            orchestrations_dir = config.compositions_dir / 'orchestrations'
            orchestration_path = orchestrations_dir / f"{pattern_name}.yaml"
            
            if orchestration_path.exists() and not overwrite:
                return error_response(f"Orchestration {pattern_name} already exists. Use overwrite=true to replace.", context)
            
            # Ensure directory exists
            ensure_directory(orchestrations_dir)
            
            # Save orchestration to disk
            save_yaml_file(orchestration_path, orchestration_data)
            
            # Orchestration saved locally for runtime use (no git commit needed for temp artifacts)
            logger.info(f"Generated orchestration {pattern_name} from component {component_name}")
        
        return event_response_builder({
            'status': 'success',
            'pattern_name': pattern_name,
            'orchestration_data': orchestration_data,
            'source_component': component_name,
            'variables_used': variables,
            'saved_to_disk': save_to_disk,
            'render_metadata': render_result.get('cache_stats', {})
        }, context)
        
    except Exception as e:
        logger.error(f"Orchestration generation failed: {e}")
        return error_response(f"Orchestration generation failed: {e}", context)


class ComponentTrackUsageData(TypedDict):
    """Track component usage for analytics."""
    component: Required[str]  # Component name that was used
    usage_context: Required[str]  # Context of usage (agent_spawn, orchestration, profile_creation, etc.)
    metadata: NotRequired[Dict[str, Any]]  # Additional metadata about the usage
    timestamp: NotRequired[str]  # Timestamp of usage (auto-generated if not provided)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("composition:track_usage")
async def handle_track_usage(data: ComponentTrackUsageData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Track component usage for analytics."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        
        component_name = data['component']
        usage_context = data['usage_context']
        metadata = data.get('metadata', {})
        timestamp = data.get('timestamp', format_for_logging())
        
        # Create usage record
        usage_record = {
            'component': component_name,
            'usage_context': usage_context,
            'metadata': metadata,
            'timestamp': timestamp,
            'agent_id': context.get('agent_id') if context else None,
            'request_id': context.get('request_id') if context else None
        }
        
        # Store usage record in the monitoring system via event emission
        if event_emitter:
            try:
                await event_emitter("monitor:record_component_usage", usage_record, context)
            except Exception as monitor_error:
                logger.warning(f"Failed to record usage in monitoring system: {monitor_error}")
        
        # Store usage record in component usage file
        usage_dir = config.compositions_dir / 'usage_analytics'
        ensure_directory(usage_dir)
        
        # Create daily usage log file
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        usage_file = usage_dir / f"component_usage_{date_str}.jsonl"
        
        # Append usage record to daily log
        try:
            with open(usage_file, 'a') as f:
                f.write(json_dumps(usage_record) + '\n')
        except Exception as file_error:
            logger.warning(f"Failed to write usage record to file: {file_error}")
        
        logger.debug(f"Tracked component usage: {component_name} in {usage_context}")
        
        return event_response_builder({
            'status': 'success',
            'tracked_component': component_name,
            'usage_context': usage_context,
            'timestamp': timestamp,
            'usage_file': str(usage_file)
        }, context)
        
    except Exception as e:
        logger.error(f"Component usage tracking failed: {e}")
        return error_response(f"Component usage tracking failed: {e}", context)


# Removed GetComponentTypesData and handle_get_component_types - no longer needed with unified 'type' field