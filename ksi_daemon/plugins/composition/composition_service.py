#!/usr/bin/env python3
"""
Composition Service Plugin

Provides unified declarative composition system for profiles, prompts, and system configs.
All configurations in KSI are treated as YAML-based compositions.
"""

import asyncio
import json
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict
from typing_extensions import NotRequired
from dataclasses import dataclass, field
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata, event_handler, create_ksi_describe_events_hook
from ksi_daemon.enhanced_decorators import enhanced_event_handler, EventCategory
from ksi_common.timestamps import timestamp_utc, format_for_logging
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

# Plugin metadata
plugin_metadata("composition_service", version="1.0.0",
                description="Unified declarative composition system")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_bound_logger("composition_service", version="2.0.0")
composition_index = None  # Will be set from context
state_manager = None  # For shared state operations only

# Define path constants from config
FRAGMENTS_BASE = config.fragments_dir
COMPOSITIONS_BASE = config.compositions_dir
SCHEMAS_BASE = config.schemas_dir


# Per-plugin TypedDict definitions (optional type safety)
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

class CompositionSelectData(TypedDict):
    """Type-safe data for composition:select."""
    agent_id: NotRequired[str]
    role: NotRequired[str]
    capabilities: NotRequired[List[str]]
    task: NotRequired[str]
    style: NotRequired[str]
    context: NotRequired[Dict[str, Any]]
    max_suggestions: NotRequired[int]


@dataclass
class CompositionComponent:
    """A single component in a composition."""
    name: str
    source: Optional[str] = None
    composition: Optional[str] = None
    inline: Optional[Dict[str, Any]] = None
    template: Optional[str] = None
    vars: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    conditions: Optional[Dict[str, List[str]]] = None


@dataclass
class Composition:
    """A complete composition definition."""
    name: str
    type: str
    version: str
    description: str
    author: Optional[str] = None
    extends: Optional[str] = None
    mixins: List[str] = field(default_factory=list)
    components: List[CompositionComponent] = field(default_factory=list)
    variables: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> 'Composition':
        """Create composition from YAML data."""
        components = []
        for comp_data in data.get('components', []):
            components.append(CompositionComponent(**comp_data))
        
        return cls(
            name=data['name'],
            type=data['type'],
            version=data['version'],
            description=data['description'],
            author=data.get('author'),
            extends=data.get('extends'),
            mixins=data.get('mixins', []),
            components=components,
            variables=data.get('variables', {}),
            metadata=data.get('metadata', {})
        )


def load_fragment(path: str) -> str:
    """Load a text fragment from disk (no caching)."""
    fragment_path = FRAGMENTS_BASE / path
    if not fragment_path.exists():
        raise FileNotFoundError(f"Fragment not found: {path}")
    
    return fragment_path.read_text()


def substitute_variables(text: str, variables: Dict[str, Any]) -> str:
    """Substitute {{variable}} placeholders in text."""
    def replace_var(match):
        var_name = match.group(1).strip()
        if var_name in variables:
            value = variables[var_name]
            # Handle different value types
            if isinstance(value, (dict, list)):
                return json.dumps(value, indent=2)
            return str(value)
        return match.group(0)  # Keep original if not found
    
    return re.sub(r'\{\{([^}]+)\}\}', replace_var, text)


def evaluate_condition(condition: str, variables: Dict[str, Any]) -> bool:
    """Evaluate a simple condition expression."""
    # Substitute variables in condition
    condition = substitute_variables(condition, variables)
    
    # Remove {{ }} if still present (means variable was undefined)
    if '{{' in condition:
        return False
    
    # Simple evaluation - just check for truthiness
    # In a real implementation, could use ast.literal_eval or similar
    condition = condition.strip()
    if condition.lower() in ('true', '1', 'yes'):
        return True
    elif condition.lower() in ('false', '0', 'no', ''):
        return False
    else:
        # If it's any other non-empty string, consider it true
        return bool(condition)


def evaluate_conditions(conditions: Dict[str, List[str]], variables: Dict[str, Any]) -> bool:
    """Evaluate complex condition expressions."""
    if 'all_of' in conditions:
        for cond in conditions['all_of']:
            if not evaluate_condition(cond, variables):
                return False
    
    if 'any_of' in conditions:
        any_true = False
        for cond in conditions['any_of']:
            if evaluate_condition(cond, variables):
                any_true = True
                break
        if not any_true:
            return False
    
    if 'none_of' in conditions:
        for cond in conditions['none_of']:
            if evaluate_condition(cond, variables):
                return False
    
    return True


async def load_composition(name: str, comp_type: Optional[str] = None) -> Composition:
    """Load a composition by name using index."""
    if not composition_index:
        raise RuntimeError("Composition index not available")
        
    # Determine full name
    full_name = f"local:{name}" if ':' not in name else name
    
    # Get file path from index
    file_path = composition_index.get_path(full_name)
    if not file_path or not file_path.exists():
        raise FileNotFoundError(f"Composition not found: {name}")
    
    # Load directly from file (no cache)
    logger.debug(f"Loading composition from {file_path}")
    data = yaml.safe_load(file_path.read_text())
    
    # Validate type if specified
    if comp_type and data.get('type') != comp_type:
        raise ValueError(f"Composition {name} is type {data.get('type')}, expected {comp_type}")
    
    return Composition.from_yaml(data)


async def resolve_composition(
    composition: Composition,
    variables: Dict[str, Any],
    visited: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """Resolve a composition into its final form."""
    if visited is None:
        visited = set()
    
    if composition.name in visited:
        raise ValueError(f"Circular reference detected: {composition.name}")
    
    visited.add(composition.name)
    result = {}
    
    # Handle inheritance
    if composition.extends:
        base = await load_composition(composition.extends, composition.type)
        base_result = await resolve_composition(base, variables, visited.copy())
        result.update(base_result)
    
    # Handle mixins
    for mixin_name in composition.mixins:
        mixin = await load_composition(mixin_name, composition.type)
        mixin_result = await resolve_composition(mixin, variables, visited.copy())
        # Merge mixin results
        for key, value in mixin_result.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key].update(value)
            else:
                result[key] = value
    
    # Apply variable defaults
    for var_name, var_def in composition.variables.items():
        if var_name not in variables and 'default' in var_def:
            variables[var_name] = var_def['default']
    
    # Process components
    for component in composition.components:
        # Check conditions
        if component.condition and not evaluate_condition(component.condition, variables):
            continue
        
        if component.conditions and not evaluate_conditions(component.conditions, variables):
            continue
        
        # Merge component vars with global vars
        comp_vars = {**variables, **component.vars}
        
        # Process component based on type
        if component.source:
            # Load fragment
            content = load_fragment(component.source)
            content = substitute_variables(content, comp_vars)
            result[component.name] = content
            
        elif component.composition:
            # Nested composition
            nested = await load_composition(component.composition)
            nested_result = await resolve_composition(nested, comp_vars, visited.copy())
            result[component.name] = nested_result
            
        elif component.inline:
            # Inline content
            result[component.name] = component.inline
            
        elif component.template:
            # Template string
            content = substitute_variables(component.template, comp_vars)
            result[component.name] = content
    
    # Add metadata
    result['_metadata'] = {
        'composition': composition.name,
        'type': composition.type,
        'version': composition.version,
        'resolved_at': format_for_logging()
    }
    
    return result


async def compose_profile(name: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compose an agent profile."""
    if variables is None:
        variables = {}
    
    composition = await load_composition(name, "profile")
    result = await resolve_composition(composition, variables)
    
    # Extract and structure profile data
    profile = {
        'name': name,
        'composition': composition.name,
        **result.get('agent_config', {}),
        '_metadata': result['_metadata']
    }
    
    # Add composed prompt if present
    if 'prompt' in result:
        profile['composed_prompt'] = result['prompt']
    
    return profile


async def compose_prompt(name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Compose a prompt template."""
    if variables is None:
        variables = {}
    
    composition = await load_composition(name, "prompt")
    result = await resolve_composition(composition, variables)
    
    # Concatenate all text components
    prompt_parts = []
    for key, value in result.items():
        if key.startswith('_'):
            continue
        if isinstance(value, str):
            prompt_parts.append(value)
        elif isinstance(value, dict) and 'content' in value:
            prompt_parts.append(value['content'])
    
    return '\n\n'.join(prompt_parts)


# Event handlers
@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle composition-related events using decorated handlers."""
    
    # Look for decorated handlers
    import sys
    import inspect
    module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    return None


@event_handler("composition:compose")
async def handle_compose(data: CompositionComposeData) -> Dict[str, Any]:
    """Handle generic composition request."""
    name = data.get('name')
    comp_type = data.get('type')
    variables = data.get('variables', {})
    
    if not name:
        return {'error': 'Composition name required'}
    
    try:
        composition = await load_composition(name, comp_type)
        result = await resolve_composition(composition, variables)
        return {
            'status': 'success',
            'result': result
        }
    except Exception as e:
        logger.error(f"Composition failed: {e}")
        return {'error': str(e)}


@event_handler("composition:profile")
async def handle_compose_profile(data: CompositionProfileData) -> Dict[str, Any]:
    """Handle profile composition request."""
    name = data.get('name')
    variables = data.get('variables', {})
    
    if not name:
        return {'error': 'Profile name required'}
    
    try:
        profile = await compose_profile(name, variables)
        return {
            'status': 'success',
            'profile': profile
        }
    except Exception as e:
        logger.error(f"Profile composition failed: {e}")
        return {'error': str(e)}


@event_handler("composition:prompt")
async def handle_compose_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle prompt composition request."""
    name = data.get('name')
    variables = data.get('variables', {})
    
    if not name:
        return {'error': 'Prompt name required'}
    
    try:
        prompt = await compose_prompt(name, variables)
        return {
            'status': 'success',
            'prompt': prompt
        }
    except Exception as e:
        logger.error(f"Prompt composition failed: {e}")
        return {'error': str(e)}


@enhanced_event_handler(
    "composition:validate",
    category=EventCategory.VALIDATION,
    typical_duration_ms=200,
    has_side_effects=False,
    best_practices=["Validate compositions before using in production", "Check for circular dependencies"]
)
async def handle_validate(data: CompositionValidateData) -> Dict[str, Any]:
    """Validate a composition."""
    name = data.get('name')
    comp_type = data.get('type')
    
    if not name:
        return {'error': 'Composition name required'}
    
    try:
        composition = await load_composition(name, comp_type)
        
        # Basic validation
        errors = []
        warnings = []
        
        # Check required fields
        if not composition.version:
            errors.append("Missing version field")
        
        # Check variable definitions
        for var_name, var_def in composition.variables.items():
            if 'type' not in var_def:
                warnings.append(f"Variable '{var_name}' missing type definition")
        
        # Try to resolve with empty variables to check for issues
        try:
            await resolve_composition(composition, {})
        except Exception as e:
            errors.append(f"Resolution error: {str(e)}")
        
        return {
            'status': 'valid' if not errors else 'invalid',
            'errors': errors,
            'warnings': warnings
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


@event_handler("composition:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """Discover available compositions using index."""
    if not composition_index:
        return {'error': 'Composition index not available'}
    
    # Use index for fast discovery
    discovered = composition_index.discover(data)
    
    return {
        'status': 'success',
        'compositions': discovered,
        'count': len(discovered)
    }


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
                'variables': composition.variables,
                'metadata': composition.metadata
            }
        }
        
    except Exception as e:
        return {'error': str(e)}


@event_handler("composition:reload")
async def handle_reload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Reload compositions by rebuilding index."""
    if not composition_index:
        return {'error': 'Composition index not available'}
    
    # Rebuild index from filesystem
    indexed_count = composition_index.rebuild_index()
    
    logger.info(f"Rebuilt composition index - {indexed_count} compositions")
    
    return {
        'status': 'success',
        'indexed_count': indexed_count,
        'message': f'Reindexed {indexed_count} compositions'
    }


@event_handler("composition:load_tree")
async def handle_load_tree(data: Dict[str, Any]) -> Dict[str, Any]:
    """Universal tree loading based on composition's declared strategy."""
    if not composition_index:
        return {'error': 'Composition index not available'}
    
    name = data.get('name')
    max_depth = data.get('max_depth', 5)
    
    if not name:
        return {'error': 'Composition name required'}
    
    try:
        # Get composition metadata to check loading strategy
        metadata = composition_index.get_metadata(f"local:{name}")
        if not metadata:
            return {'error': f'Composition not found: {name}'}
        
        loading_strategy = metadata.get('loading_strategy', 'single')
        
        if loading_strategy == 'single':
            # Just load the one composition
            composition = await load_composition(name)
            return {
                'status': 'success',
                'strategy': 'single',
                'compositions': {name: composition}
            }
        
        elif loading_strategy == 'tree':
            # Load composition + dependencies recursively
            tree = {}
            to_load = [(name, 0)]
            
            while to_load:
                comp_name, depth = to_load.pop(0)
                if depth > max_depth or comp_name in tree:
                    continue
                
                comp = await load_composition(comp_name)
                tree[comp_name] = comp
                
                # Add dependencies to load queue
                for dep in comp.dependencies or []:
                    to_load.append((dep, depth + 1))
                    
                # Add extends parent
                if comp.extends:
                    to_load.append((comp.extends, depth + 1))
            
            return {
                'status': 'success', 
                'strategy': 'tree',
                'compositions': tree,
                'loaded_count': len(tree)
            }
        
        else:
            return {'error': f'Unknown loading strategy: {loading_strategy}'}
            
    except Exception as e:
        return {'error': str(e)}


@event_handler("composition:load_bulk")
async def handle_load_bulk(data: Dict[str, Any]) -> Dict[str, Any]:
    """Universal bulk loading for agent efficiency."""
    if not composition_index:
        return {'error': 'Composition index not available'}
    
    names = data.get('names', [])
    if not names:
        return {'error': 'Composition names list required'}
    
    try:
        # Load all compositions in parallel
        compositions = {}
        failed = {}
        
        for name in names:
            try:
                comp = await load_composition(name)
                compositions[name] = comp
            except Exception as e:
                failed[name] = str(e)
        
        return {
            'status': 'success',
            'compositions': compositions,
            'failed': failed,
            'loaded_count': len(compositions),
            'failed_count': len(failed)
        }
        
    except Exception as e:
        return {'error': str(e)}


@enhanced_event_handler(
    "composition:select",
    category=EventCategory.AI_COORDINATION,
    typical_duration_ms=800,
    has_cost=True,
    best_practices=["Provide clear task description for better selection", "Include relevant capabilities"]
)
async def handle_select_composition(data: CompositionSelectData) -> Dict[str, Any]:
    """Handle dynamic composition selection based on context."""
    try:
        # Import selector dynamically to avoid circular imports
        from prompts.composition_selector import CompositionSelector, SelectionContext
        
        # Build selection context
        context = SelectionContext(
            agent_id=data.get('agent_id', 'unknown'),
            role=data.get('role'),
            capabilities=data.get('capabilities', []),
            task_description=data.get('task'),
            preferred_style=data.get('style'),
            context_variables=data.get('context', {})
        )
        
        # Use selector to find best composition
        selector = CompositionSelector()
        result = await selector.select_composition(context)
        
        # Get additional suggestions if requested
        max_suggestions = data.get('max_suggestions', 1)
        suggestions = []
        
        if max_suggestions > 1:
            # Get all scored compositions from selector
            all_compositions = await selector.get_scored_compositions(context)
            suggestions = [
                {
                    'name': name,
                    'score': score,
                    'reasons': reasons
                }
                for name, score, reasons in all_compositions[:max_suggestions]
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
    """Handle runtime composition creation."""
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
        
        # Save to temporary location (in-memory cache)
        # In production, could save to disk or state service
        dynamic_cache_key = f"dynamic_composition:{name}"
        if state_manager:
            state_manager.set_state(dynamic_cache_key, composition)
        
        return {
            'status': 'success',
            'name': name,
            'composition': composition,
            'message': f'Created dynamic composition: {name}'
        }
        
    except Exception as e:
        logger.error(f"Dynamic composition creation failed: {e}")
        return {'error': str(e)}


# Plugin lifecycle
@hookimpl
def ksi_plugin_context(context):
    """Receive infrastructure from daemon context."""
    global composition_index, state_manager
    
    composition_index = context.get("composition_index")
    state_manager = context.get("state_manager")
    
    if composition_index:
        logger.info("Composition service connected to composition index")
    else:
        logger.error("Composition index not available in context")


@hookimpl
def ksi_startup(config):
    """Initialize composition service on startup."""
    logger.info("Composition service starting up...")
    
    # Ensure directories exist
    COMPOSITIONS_BASE.mkdir(parents=True, exist_ok=True)
    FRAGMENTS_BASE.mkdir(parents=True, exist_ok=True)
    SCHEMAS_BASE.mkdir(parents=True, exist_ok=True)
    
    return {"status": "composition_service_ready"}


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info("Composition service stopped")
    return {"status": "composition_service_stopped"}


# Module-level marker for plugin discovery
ksi_plugin = True

# Enable event discovery
ksi_describe_events = create_ksi_describe_events_hook(__name__)