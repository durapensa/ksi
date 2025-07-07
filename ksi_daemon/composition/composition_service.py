#!/usr/bin/env python3
"""
Composition Service Module - Event handlers for composition system
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict, Tuple
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
from .evaluation_utils import (
    create_evaluation_record, calculate_overall_score, 
    find_best_evaluation, summarize_evaluation_status,
    merge_evaluation_record
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

class CompositionEvaluateData(TypedDict):
    """Type-safe data for composition:evaluate."""
    name: str
    type: NotRequired[str]
    test_suite: str
    model: NotRequired[str]
    update_metadata: NotRequired[bool]
    test_options: NotRequired[Dict[str, Any]]

class CompositionListData(TypedDict):
    """Type-safe data for composition:list."""
    type: NotRequired[str]
    include_validation: NotRequired[bool]

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


@event_handler("composition:evaluate")
async def handle_evaluate(data: CompositionEvaluateData) -> Dict[str, Any]:
    """Evaluate a composition's effectiveness with test results.
    
    This handler records test results for a composition. Full integration
    with automated prompt testing framework is future work.
    
    Expected data:
        name: Composition name
        type: Optional composition type
        test_suite: Name of test suite used
        model: Model used for testing (default from config)
        update_metadata: Whether to save results to composition (default: False)
        test_options: Dict containing test results:
            - test_results: List of test result dicts
            - performance_metrics: Performance metrics dict
            - notes: Optional notes about the evaluation
    """
    name = data['name']
    comp_type = data.get('type')
    test_suite = data['test_suite']
    model = data.get('model', config.completion_default_model)
    update_metadata = data.get('update_metadata', False)
    test_options = data.get('test_options', {})
    
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
        
        # Update composition metadata if requested
        if update_metadata:
            # Get current evaluated_for list or create new one
            evaluated_for = composition.metadata.get('evaluated_for', [])
            
            # Merge new evaluation record
            evaluated_for = merge_evaluation_record(evaluated_for, evaluation_record)
            
            # Update composition metadata
            composition.metadata['evaluated_for'] = evaluated_for
            
            # Save updated composition
            comp_path = COMPOSITIONS_BASE / composition.type / f"{composition.name}.yaml"
            import yaml
            with open(comp_path, 'w') as f:
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
                yaml.dump(comp_dict, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Updated composition {name} with evaluation metadata")
        
        # Return evaluation results
        return {
            'status': 'success',
            'composition': {
                'name': composition.name,
                'type': composition.type,
                'version': composition.version
            },
            'evaluation': evaluation_record,
            'metadata_updated': update_metadata
        }
        
    except Exception as e:
        logger.error(f"Error evaluating composition: {e}")
        return {
            'status': 'error',
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


@event_handler("composition:create")
async def handle_create_composition(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a dynamic composition at runtime."""
    try:
        name = data.get('name')
        if not name:
            # Generate unique name
            import uuid
            name = f"dynamic_{uuid.uuid4().hex[:8]}"
        
        comp_type = data.get('type', 'profile')
        base_composition = data.get('extends', 'base_agent')
        
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
        
        # Save to state manager as dynamic composition
        if state_manager:
            dynamic_cache_key = f"dynamic_composition:{name}"
            state_manager.set_shared_state(dynamic_cache_key, composition)
            logger.info(f"Created dynamic composition: {name}")
        
        return {
            'status': 'success',
            'name': name,
            'composition': composition,
            'message': f'Created dynamic composition: {name}'
        }
        
    except Exception as e:
        logger.error(f"Dynamic composition creation failed: {e}")
        return {'error': str(e)}


# Core Composition Functions

async def _select_composition_for_context(context: SelectionContext) -> SelectionResult:
    """Select the best composition for the given context using scoring algorithm."""
    # Get all available compositions with metadata
    discovered = composition_index.discover({
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
    discovered = composition_index.discover({
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
    # TODO: Update to use new relational state API
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