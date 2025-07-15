#!/usr/bin/env python3
"""
Composition Service Module - Event handlers for composition system
"""

import asyncio
import json
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict, Tuple, Union, Literal
from typing_extensions import NotRequired, Required
from dataclasses import dataclass

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.timestamps import timestamp_utc, format_for_logging
from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.file_utils import save_yaml_file, ensure_directory, load_yaml_file
from ksi_common.event_utils import extract_single_response
from ksi_common.git_utils import git_manager

# Import composition modules
from . import composition_index
from .composition_core import (
    Composition, CompositionComponent,
    load_fragment, substitute_variables, evaluate_condition, evaluate_conditions,
    load_composition as load_composition_file,
    FRAGMENTS_BASE, COMPOSITIONS_BASE, SCHEMAS_BASE, CAPABILITIES_BASE
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

# Capability schema cache
_capability_schema_cache = None


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
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive infrastructure from daemon context."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, dict)  # Simple dict for context handler
    global state_manager
    
    state_manager = data.get("state_manager")
    
    if state_manager:
        logger.info("Composition service connected to state manager")


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize composition service on startup."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, dict)  # Simple dict for startup
    logger.info("Composition service starting up...")
    
    # Ensure directories exist
    ensure_directory(COMPOSITIONS_BASE)
    ensure_directory(FRAGMENTS_BASE)
    
    # Initialize and rebuild composition index
    await composition_index.initialize()
    indexed_count = await composition_index.rebuild()
    
    logger.info(f"Composition service started - indexed {indexed_count} compositions")
    return event_response_builder(
        {"status": "composition_service_ready", "indexed": indexed_count},
        context=context
    )


@event_handler("system:shutdown")
async def handle_shutdown(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    logger.info("Composition service shutting down")


class CompositionComposeData(TypedDict):
    """Compose a complete configuration from components."""
    name: str  # Composition name to compose
    type: NotRequired[str]  # Composition type (default: profile)
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


@event_handler("composition:compose")
async def handle_compose(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose a complete configuration from components."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionComposeData)
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


class CompositionProfileData(TypedDict):
    """Compose a profile (returns full configuration)."""
    name: str  # Profile name to compose
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


@event_handler("composition:profile")
async def handle_compose_profile(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose a profile (returns full configuration)."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionProfileData)
    name = data.get('name')
    variables = data.get('variables', {})
    
    try:
        result = await compose_profile(name, variables)
        return event_response_builder(
            {
                'status': 'success',
                'profile': result
            },
            context=context
        )
    except Exception as e:
        logger.error(f"Profile composition failed: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionPromptData(TypedDict):
    """Compose a prompt (returns text)."""
    name: str  # Prompt name to compose
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


@event_handler("composition:prompt")
async def handle_compose_prompt(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose a prompt (returns text)."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionPromptData)
    name = data.get('name')
    variables = data.get('variables', {})
    
    try:
        result = await compose_prompt(name, variables)
        return event_response_builder(
            {
                'status': 'success',
                'prompt': result
            },
            context=context
        )
    except Exception as e:
        logger.error(f"Prompt composition failed: {e}")
        return error_response(
            str(e),
            context=context
        )


class CompositionValidateData(TypedDict):
    """Validate a composition structure and syntax."""
    name: str  # Composition name to validate
    type: NotRequired[str]  # Composition type


@event_handler("composition:validate")
async def handle_validate(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a composition structure and syntax (like a linter)."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionValidateData)
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


@event_handler("composition:evaluate")
async def handle_evaluate(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process evaluation results for a composition (in-memory only)."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionEvaluateData)
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


@event_handler("composition:save")
async def handle_save_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Save a composition to disk."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Using dict for flexible save operations
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


@event_handler("composition:update")
async def handle_update_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update an existing composition's properties or metadata."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Using dict for flexible update operations
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


@event_handler("composition:discover")
async def handle_discover(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Discover available compositions using index."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Simple dict for discovery operations
    try:
        # Use index for fast discovery
        discovered = await composition_index.discover(data)
        
        # Check if evaluation info requested
        evaluation_detail = data.get('evaluation_detail', 'none')  # none, minimal, summary, detailed
        
        if evaluation_detail != 'none':
            # Import here to avoid circular dependencies
            from ksi_daemon.evaluation.evaluation_index import evaluation_index
            
            # Add evaluation info to each composition
            for comp_info in discovered:
                comp_type = comp_info.get('type', 'profile')
                comp_name = comp_info.get('name', '')
                
                eval_info = evaluation_index.get_evaluation_info(
                    comp_type, comp_name, evaluation_detail
                )
                
                # Add evaluation info to composition
                if eval_info.get('has_evaluations', False):
                    comp_info['evaluation_info'] = eval_info
        
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
        
        return event_response_builder(
            {
                'status': 'success',
                'compositions': discovered,
                'count': len(discovered),
                'filtered': metadata_filter is not None
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
    type: NotRequired[Literal['all', 'profile', 'prompt', 'orchestration', 'evaluation']]  # Filter by type
    include_validation: NotRequired[bool]  # Include validation status
    metadata_filter: NotRequired[Dict[str, Any]]  # Filter by metadata
    evaluation_detail: NotRequired[Literal['none', 'minimal', 'summary', 'detailed']]  # Evaluation detail level


@event_handler("composition:list")
async def handle_list(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all compositions of a given type."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, CompositionListData)
    comp_type = data.get('type', 'all')
    include_validation = data.get('include_validation', False)
    
    compositions = []
    
    if comp_type == 'all':
        types = ['profile', 'prompt', 'system']
    else:
        types = [comp_type]
    
    for t in types:
        discovered = await handle_discover({
            'type': t,
            'include_validation': include_validation
        }, context)
        compositions.extend(discovered.get('compositions', []))
    
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
    # Try to find composition file
    composition_path = None
    
    if comp_type:
        # Try specific type directory first
        type_dirs = {
            'profile': 'profiles',
            'prompt': 'prompts',
            'system': 'system',
            'orchestration': 'orchestrations',
            'evaluation': 'evaluations'
        }
        if comp_type in type_dirs:
            potential_path = COMPOSITIONS_BASE / type_dirs[comp_type] / f"{name}.yaml"
            if potential_path.exists():
                composition_path = potential_path
    
    # Search all composition directories
    if not composition_path:
        for yaml_file in COMPOSITIONS_BASE.rglob(f"{name}.yaml"):
            composition_path = yaml_file
            break
    
    if not composition_path or not composition_path.exists():
        raise FileNotFoundError(f"Composition not found: {name}")
    
    # Load and return raw YAML data
    return load_yaml_file(composition_path)


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


@event_handler("composition:get")
async def handle_get(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a composition definition with all sections preserved."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CompositionGetData)
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
                'Invalid composition structure',
                context=context
            )
        
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




@event_handler("composition:sync")
async def handle_sync_compositions(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Synchronize composition submodules with remote repositories."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, dict)
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
async def handle_git_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about git repositories for composition submodules."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, dict)
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


@event_handler("composition:rebuild_index")
@event_handler("composition:reload")  # Alias for backward compatibility
async def handle_rebuild_index(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Simple dict for rebuild operations
    try:
        indexed_count = await composition_index.rebuild()
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
async def handle_index_file(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Index a specific composition file."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Simple dict for file operations
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


@event_handler("composition:select")
async def handle_select_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Select the best composition for given context using intelligent scoring."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, dict)  # Simple dict for selection operations
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


class CompositionCreateWithContent(CompositionCreateBase):
    """Create composition from full content."""
    content: Required[Dict[str, Any]]  # Full composition structure


class CompositionCreateProfile(CompositionCreateBase):
    """Create profile composition with components."""
    type: Required[Literal['profile']]
    model: NotRequired[str]
    capabilities: NotRequired[List[str]]
    tools: NotRequired[List[str]]
    role: NotRequired[str]
    prompt: NotRequired[str]  # Optional prompt component


class CompositionCreatePrompt(CompositionCreateBase):
    """Create prompt composition."""
    type: Required[Literal['prompt']]
    content: Required[str]  # The prompt text
    category: NotRequired[str]  # Categorization for prompts


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
async def handle_create_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create and save a composition."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    try:
        data = event_format_linter(raw_data, CompositionCreateData)
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
    """Load a composition with caching support."""
    # Check dynamic cache first
    # TODO: Update to use new graph database API
    # if state_manager:
    #     cache_key = f"dynamic_composition:{name}"
    #     cached = state_manager.get_shared_state(cache_key)
    #     if cached and isinstance(cached, dict):
    #         return Composition.from_yaml(cached)
    
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
        context = {
            'agent_id': agent_id,
            'agent_profile': await load_composition_raw(profile_name, 'profile')
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
        import yaml
        composition_yaml = yaml.dump(redacted_context, default_flow_style=False, sort_keys=False)
        
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


# Pattern Evolution Event Handlers

class CompositionForkData(TypedDict):
    """Fork a composition to create a variant."""
    parent: Required[str]  # Name of parent composition
    name: Required[str]  # Name for forked composition
    reason: Required[str]  # Reason for forking
    modifications: NotRequired[Dict[str, Any]]  # Initial modifications
    author: NotRequired[str]  # Defaults to agent_id


@event_handler("composition:fork")
async def handle_fork_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fork a composition to create a variant with git-based lineage tracking."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionForkData)
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


@event_handler("composition:merge")
async def handle_merge_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge improvements from a forked composition back to parent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionMergeData)
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


@event_handler("composition:agent_context")
async def handle_compose_agent_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose agent context for self-configuring agents."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionAgentContextData)
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


@event_handler("composition:diff")
async def handle_diff_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Show differences between two compositions."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionDiffData)
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


class CompositionTrackDecisionData(TypedDict):
    """Track orchestrator decisions for learning."""
    pattern: Required[str]  # Pattern name
    decision: Required[str]  # Decision made
    context: Required[Dict[str, Any]]  # Decision context
    outcome: Required[str]  # Decision outcome
    confidence: NotRequired[float]  # Confidence 0-1


@event_handler("composition:initial_message")
async def handle_compose_initial_message(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose initial message for agent spawning using composition system."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionInitialMessageData)
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
async def handle_track_decision(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Track orchestrator decisions for pattern learning."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, CompositionTrackDecisionData)
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
                decisions = yaml.safe_load(f) or []
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