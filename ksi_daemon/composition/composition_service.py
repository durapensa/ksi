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
    ensure_directory(COMPOSITIONS_BASE)
    ensure_directory(FRAGMENTS_BASE)
    
    # Initialize and rebuild composition index
    await composition_index.initialize()
    indexed_count = await composition_index.rebuild()
    
    logger.info(f"Composition service started - indexed {indexed_count} compositions")
    return {"status": "composition_service_ready", "indexed": indexed_count}


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Composition service shutting down")


class CompositionComposeData(TypedDict):
    """Compose a complete configuration from components."""
    name: str  # Composition name to compose
    type: NotRequired[str]  # Composition type (default: profile)
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


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


class CompositionProfileData(TypedDict):
    """Compose a profile (returns full configuration)."""
    name: str  # Profile name to compose
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


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


class CompositionPromptData(TypedDict):
    """Compose a prompt (returns text)."""
    name: str  # Prompt name to compose
    variables: NotRequired[Dict[str, Any]]  # Variables for substitution


@event_handler("composition:prompt")
async def handle_compose_prompt(data: CompositionPromptData) -> Dict[str, Any]:
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


class CompositionValidateData(TypedDict):
    """Validate a composition structure and syntax."""
    name: str  # Composition name to validate
    type: NotRequired[str]  # Composition type


@event_handler("composition:validate")
async def handle_validate(data: CompositionValidateData) -> Dict[str, Any]:
    """Validate a composition structure and syntax (like a linter)."""
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


class CompositionEvaluateData(TypedDict):
    """Process evaluation results for a composition."""
    name: str  # Composition to evaluate
    type: NotRequired[str]  # Composition type
    test_suite: str  # Test suite that was run
    model: NotRequired[str]  # Model used for testing
    test_options: NotRequired[Dict[str, Any]]  # Test results and metrics


@event_handler("composition:evaluate")
async def handle_evaluate(data: CompositionEvaluateData) -> Dict[str, Any]:
    """Process evaluation results for a composition (in-memory only)."""
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
        return {
            'status': 'success',
            'composition': {
                'name': composition.name,
                'type': composition.type,
                'version': composition.version
            },
            'evaluation': evaluation_record,
            'metadata': composition.metadata
        }
        
    except Exception as e:
        logger.error(f"Error evaluating composition: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


async def _save_composition_to_disk(composition: Composition, overwrite: bool = False) -> Dict[str, Any]:
    """Internal helper to save composition to disk."""
    try:
        # Determine file path
        type_dir = config.get_composition_type_dir(composition.type)
        comp_path = type_dir / f"{composition.name}.yaml"
        
        # Check if file exists
        if comp_path.exists() and not overwrite:
            return {
                'status': 'error',
                'error': f'Composition {composition.name} already exists. Set overwrite=true to replace.'
            }
        
        # Ensure directory exists
        ensure_directory(type_dir)
        
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
        
        # Save composition
        save_yaml_file(comp_path, comp_dict)
        
        # Update index
        await composition_index.index_file(comp_path)
        
        logger.info(f"Saved composition {composition.name} to {comp_path}")
        
        return {
            'status': 'success',
            'path': str(comp_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to save composition: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@event_handler("composition:save")
async def handle_save_composition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save a composition to disk."""
    try:
        comp_data = data.get('composition')  # Complete composition object or dict
        if not comp_data:
            return {'status': 'error', 'error': 'No composition data provided'}
            
        overwrite = data.get('overwrite', False)  # Replace existing file if True
        
        # Create Composition object if needed
        if isinstance(comp_data, dict):
            composition = Composition.from_yaml(comp_data)
        else:
            composition = comp_data
            
        # Use helper to save
        save_result = await _save_composition_to_disk(composition, overwrite)
        
        if save_result['status'] == 'success':
            return {
                'status': 'success',
                'name': composition.name,
                'type': composition.type,
                'path': save_result['path'],
                'message': f'Composition saved to {save_result["path"]}'
            }
        else:
            return save_result
        
    except Exception as e:
        logger.error(f"Failed to save composition: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@event_handler("composition:update")
async def handle_update_composition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing composition's properties or metadata."""
    try:
        name = data.get('name')  # Composition name to update
        if not name:
            return {'status': 'error', 'error': 'Composition name required'}
            
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
            return save_result
            
        return {
            'status': 'success',
            'name': composition.name,
            'type': composition.type,
            'version': composition.version,
            'updates_applied': list(updates.keys()),
            'message': f'Updated composition {name}'
        }
        
    except Exception as e:
        logger.error(f"Failed to update composition: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@event_handler("composition:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """Discover available compositions using index."""
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
        
        return {
            'status': 'success',
            'compositions': discovered,
            'count': len(discovered),
            'filtered': metadata_filter is not None
        }
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return {'error': str(e)}


class CompositionListData(TypedDict):
    """List compositions with filters."""
    type: NotRequired[Literal['all', 'profile', 'prompt', 'orchestration', 'evaluation']]  # Filter by type
    include_validation: NotRequired[bool]  # Include validation status
    metadata_filter: NotRequired[Dict[str, Any]]  # Filter by metadata
    evaluation_detail: NotRequired[Literal['none', 'minimal', 'summary', 'detailed']]  # Evaluation detail level


@event_handler("composition:list")
async def handle_list(data: CompositionListData) -> Dict[str, Any]:
    """List all compositions of a given type."""
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
        })
        compositions.extend(discovered.get('compositions', []))
    
    return {
        'status': 'success',
        'compositions': compositions,
        'count': len(compositions)
    }


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
async def handle_get(data: CompositionGetData) -> Dict[str, Any]:
    """Get a composition definition with all sections preserved."""
    name = data.get('name')
    comp_type = data.get('type')
    
    if not name:
        return {'error': 'Composition name required'}
    
    try:
        # Load raw YAML data to preserve all sections
        composition_data = await load_composition_raw(name, comp_type)
        
        # Validate core fields
        validation_errors = validate_core_composition(composition_data)
        if validation_errors:
            return {
                'status': 'error',
                'error': 'Invalid composition structure',
                'validation_errors': validation_errors
            }
        
        return {
            'status': 'success',
            'composition': composition_data  # Return ALL sections, not just core fields
        }
        
    except Exception as e:
        logger.error(f"Failed to get composition: {e}")
        return {'error': str(e)}




@event_handler("composition:rebuild_index")
@event_handler("composition:reload")  # Alias for backward compatibility
async def handle_rebuild_index(data: Dict[str, Any]) -> Dict[str, Any]:
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
    try:
        indexed_count = await composition_index.rebuild()
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
        success = await composition_index.index_file(Path(file_path))
        return {
            'status': 'success' if success else 'failed',
            'file_path': file_path,
            'indexed': success
        }
    except Exception as e:
        logger.error(f"File indexing failed: {e}")
        return {'error': str(e)}


@event_handler("composition:select")
async def handle_select_composition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Select the best composition for given context using intelligent scoring."""
    try:
        # Build selection context from request data
        context = SelectionContext(
            agent_id=data.get('agent_id', 'unknown'),
            role=data.get('role'),
            capabilities=data.get('capabilities', []),
            task_description=data.get('task'),
            preferred_style=data.get('style'),
            context_variables=data.get('context', {}),
            requirements=data.get('requirements', {})
        )
        
        # Get best composition
        result = await _select_composition_for_context(context)
        
        # Get additional suggestions if requested
        max_suggestions = data.get('max_suggestions', 1)
        suggestions = []
        
        if max_suggestions > 1:
            # Get all scored compositions
            all_scored = await _get_scored_compositions(context)
            suggestions = [
                {
                    'name': name,
                    'score': score,
                    'reasons': reasons
                }
                for name, score, reasons in all_scored[:max_suggestions]
            ]
        
        return {
            'status': 'success',
            'selected': result.composition_name,
            'score': result.score,
            'reasons': result.reasons,
            'suggestions': suggestions,
            'fallback_used': result.fallback_used
        }
        
    except Exception as e:
        logger.error(f"Composition selection failed: {e}")
        return {'error': str(e)}


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
async def handle_create_composition(data: CompositionCreateData) -> CompositionResult:
    """Create and save a composition."""
    try:
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
                return {
                    'status': 'error',
                    'error': f"Invalid content type for {comp_type} composition"
                }
            
        # Always save to disk (no more in-memory only compositions)
        # Create Composition object
        comp_obj = Composition.from_yaml(composition)
        save_result = await _save_composition_to_disk(comp_obj, overwrite=data.get('overwrite', False))
        
        if save_result['status'] != 'success':
            return save_result
            
        logger.info(f"Created and saved composition: {name}")
        
        return {
            'status': 'success',
            'name': name,
            'composition': composition,
            'path': save_result['path'],
            'message': f'Created and saved composition: {name}'
        }
        
    except Exception as e:
        logger.error(f"Dynamic composition creation failed: {e}")
        return {'error': str(e)}


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


# Pattern Evolution Event Handlers

class CompositionForkData(TypedDict):
    """Fork a composition to create a variant."""
    parent: Required[str]  # Name of parent composition
    name: Required[str]  # Name for forked composition
    reason: Required[str]  # Reason for forking
    modifications: NotRequired[Dict[str, Any]]  # Initial modifications
    author: NotRequired[str]  # Defaults to agent_id


@event_handler("composition:fork")
async def handle_fork_composition(data: CompositionForkData) -> CompositionResult:
    """Fork a composition to create a variant with lineage tracking."""
    parent_name = data.get('parent')
    new_name = data.get('name')
    fork_reason = data.get('reason', 'Experimental variant')
    modifications = data.get('modifications', {})
    author = data.get('author', data.get('agent_id', 'unknown'))
    
    if not parent_name or not new_name:
        return {'error': 'Both parent and name required for fork'}
    
    try:
        # Load parent composition
        parent = await load_composition(parent_name)
        
        # Create forked composition with lineage
        forked_data = {
            'name': new_name,
            'type': parent.type,
            'version': '0.1.0',  # Start fork at 0.1.0
            'description': f"Fork of {parent_name}: {fork_reason}",
            'author': author,
            'extends': parent_name,  # Inherit from parent
            'components': [vars(c) for c in parent.components],  # Serialize components
            'variables': parent.variables,
            'metadata': {
                **parent.metadata,
                'lineage': {
                    'parent': f"{parent_name}@{parent.version}",
                    'fork_date': timestamp_utc(),
                    'fork_reason': fork_reason,
                    'fork_author': author
                }
            }
        }
        
        # Apply modifications
        if modifications:
            for key, value in modifications.items():
                if key in forked_data:
                    forked_data[key] = value
        
        # Create the forked composition
        result = await handle_create_composition({
            'name': new_name,
            'type': parent.type,
            'content': forked_data,
            'save': data.get('save', True)  # Save by default
        })
        
        if result.get('status') == 'success':
            # Update parent's metadata to track forks
            parent.metadata['forks'] = parent.metadata.get('forks', [])
            parent.metadata['forks'].append({
                'name': new_name,
                'date': timestamp_utc(),
                'reason': fork_reason,
                'author': author
            })
            
            # Save updated parent
            parent_update = await handle_update_composition({
                'name': parent_name,
                'updates': {'metadata': parent.metadata}
            })
            
            logger.info(f"Forked composition {parent_name} -> {new_name}")
        
        return result
        
    except Exception as e:
        logger.error(f"Fork failed: {e}")
        return {'error': str(e)}


class CompositionMergeData(TypedDict):
    """Merge improvements from fork back to parent."""
    source: Required[str]  # Name of source (fork)
    target: Required[str]  # Name of target (parent)
    strategy: Required[Literal['selective', 'full', 'metadata_only']]
    improvements: NotRequired[List[str]]  # List of improvements
    validation_results: NotRequired[Dict[str, Any]]  # Evaluation results


@event_handler("composition:merge")
async def handle_merge_composition(data: CompositionMergeData) -> CompositionResult:
    """Merge improvements from a forked composition back to parent."""
    source_name = data.get('source')
    target_name = data.get('target')
    strategy = data.get('strategy', 'selective')
    improvements = data.get('improvements', [])
    validation_results = data.get('validation_results', {})
    
    if not source_name or not target_name:
        return {'error': 'Both source and target required for merge'}
    
    try:
        # Load both compositions
        source = await load_composition(source_name)
        target = await load_composition(target_name)
        
        # Verify lineage - source should be fork of target
        lineage = source.metadata.get('lineage', {})
        if not lineage.get('parent', '').startswith(target_name):
            return {'error': f'{source_name} is not a fork of {target_name}'}
        
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
        return {'error': str(e)}


class CompositionDiffData(TypedDict):
    """Show differences between compositions."""
    left: Required[str]  # First composition
    right: Required[str]  # Second composition
    detail_level: NotRequired[Literal['summary', 'detailed', 'full']]


@event_handler("composition:diff")
async def handle_diff_composition(data: CompositionDiffData) -> Dict[str, Any]:
    """Show differences between two compositions."""
    left_name = data.get('left')
    right_name = data.get('right')
    detail_level = data.get('detail_level', 'summary')
    
    if not left_name or not right_name:
        return {'error': 'Both left and right compositions required'}
    
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
        
        return {
            'status': 'success',
            'differences': differences
        }
        
    except Exception as e:
        logger.error(f"Diff failed: {e}")
        return {'error': str(e)}


class CompositionTrackDecisionData(TypedDict):
    """Track orchestrator decisions for learning."""
    pattern: Required[str]  # Pattern name
    decision: Required[str]  # Decision made
    context: Required[Dict[str, Any]]  # Decision context
    outcome: Required[str]  # Decision outcome
    confidence: NotRequired[float]  # Confidence 0-1


@event_handler("composition:track_decision")
async def handle_track_decision(data: CompositionTrackDecisionData) -> Dict[str, Any]:
    """Track orchestrator decisions for pattern learning."""
    pattern_name = data.get('pattern')
    decision = data.get('decision')
    context = data.get('context', {})
    outcome = data.get('outcome')
    confidence = data.get('confidence', 0.5)
    agent_id = data.get('agent_id', 'unknown')
    
    if not pattern_name or not decision:
        return {'error': 'Pattern name and decision required'}
    
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
        
        return {
            'status': 'success',
            'tracked': decision_record,
            'decisions_file': str(decisions_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to track decision: {e}")
        return {'error': str(e)}