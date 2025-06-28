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
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
import logging
import pluggy

from ...plugin_utils import get_logger, plugin_metadata
from ksi_common import TimestampManager
from ...config import config

# Plugin metadata
plugin_metadata("composition_service", version="1.0.0",
                description="Unified declarative composition system")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("composition_service")

# Base path for compositions
VAR_DIR = Path("var")  # Relative to project root
COMPOSITIONS_BASE = VAR_DIR / "lib/compositions"
FRAGMENTS_BASE = VAR_DIR / "lib/fragments"
SCHEMAS_BASE = VAR_DIR / "lib/schemas"

# Cache for loaded compositions
composition_cache: Dict[str, 'Composition'] = {}
fragment_cache: Dict[str, str] = {}


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
    """Load a text fragment from disk with caching."""
    if path in fragment_cache:
        return fragment_cache[path]
    
    fragment_path = FRAGMENTS_BASE / path
    if not fragment_path.exists():
        # Try legacy location
        legacy_path = VAR_DIR / "prompts" / path
        if legacy_path.exists():
            fragment_path = legacy_path
        else:
            raise FileNotFoundError(f"Fragment not found: {path}")
    
    content = fragment_path.read_text()
    fragment_cache[path] = content
    return content


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
    """Load a composition by name and optional type."""
    cache_key = f"{comp_type or 'any'}:{name}"
    
    if cache_key in composition_cache:
        return composition_cache[cache_key]
    
    # Search for composition file
    search_paths = []
    if comp_type:
        if comp_type == "profile":
            search_paths.extend([
                COMPOSITIONS_BASE / "profiles" / "agents" / f"{name}.yaml",
                COMPOSITIONS_BASE / "profiles" / "base" / f"{name}.yaml"
            ])
        elif comp_type == "prompt":
            search_paths.extend([
                COMPOSITIONS_BASE / "prompts" / "templates" / f"{name}.yaml",
                COMPOSITIONS_BASE / "prompts" / "components" / f"{name}.yaml"
            ])
        else:
            search_paths.append(COMPOSITIONS_BASE / comp_type / f"{name}.yaml")
    else:
        # Search all types
        for type_dir in ["profiles/agents", "profiles/base", "prompts/templates", 
                        "prompts/components", "system"]:
            search_paths.append(COMPOSITIONS_BASE / type_dir / f"{name}.yaml")
    
    # Also check legacy locations
    search_paths.extend([
        VAR_DIR / "prompts/compositions" / f"{name}.yaml",
        VAR_DIR / "agent_profiles" / f"{name}.yaml"
    ])
    
    for path in search_paths:
        if path.exists():
            logger.debug(f"Loading composition from {path}")
            data = yaml.safe_load(path.read_text())
            
            # Add type if not specified
            if 'type' not in data:
                if 'profiles' in str(path):
                    data['type'] = 'profile'
                elif 'prompts' in str(path):
                    data['type'] = 'prompt'
                else:
                    data['type'] = 'system'
            
            composition = Composition.from_yaml(data)
            composition_cache[cache_key] = composition
            return composition
    
    raise FileNotFoundError(f"Composition not found: {name}")


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
        'resolved_at': TimestampManager.format_for_logging()
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
    """Handle composition events."""
    
    if event_name == "composition:compose":
        # Generic composition
        return handle_compose(data)
    
    elif event_name == "composition:profile":
        # Profile-specific composition
        return handle_compose_profile(data)
    
    elif event_name == "composition:prompt":
        # Prompt-specific composition
        return handle_compose_prompt(data)
    
    elif event_name == "composition:validate":
        # Validate composition
        return handle_validate(data)
    
    elif event_name == "composition:discover":
        # Discover available compositions
        return handle_discover(data)
    
    elif event_name == "composition:list":
        # List compositions by type
        return handle_list(data)
    
    elif event_name == "composition:get":
        # Get composition definition
        return handle_get(data)
    
    elif event_name == "composition:reload":
        # Reload compositions from disk
        return handle_reload(data)
    
    return None


async def handle_compose(data: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_compose_profile(data: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_validate(data: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """Discover available compositions matching criteria."""
    comp_type = data.get('type')
    tags = data.get('tags', [])
    capabilities = data.get('capabilities', [])
    
    discovered = []
    
    # Search all composition directories
    search_dirs = []
    if comp_type == 'profile':
        search_dirs = [
            COMPOSITIONS_BASE / "profiles" / "agents",
            COMPOSITIONS_BASE / "profiles" / "base"
        ]
    elif comp_type == 'prompt':
        search_dirs = [
            COMPOSITIONS_BASE / "prompts" / "templates",
            COMPOSITIONS_BASE / "prompts" / "components"
        ]
    else:
        search_dirs = [COMPOSITIONS_BASE]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        for yaml_file in search_dir.rglob("*.yaml"):
            try:
                comp = await load_composition(yaml_file.stem, comp_type)
                
                # Check filters
                if tags:
                    comp_tags = comp.metadata.get('tags', [])
                    if not any(tag in comp_tags for tag in tags):
                        continue
                
                if capabilities:
                    comp_caps = comp.metadata.get('capabilities_required', [])
                    if not all(cap in capabilities for cap in comp_caps):
                        continue
                
                discovered.append({
                    'name': comp.name,
                    'type': comp.type,
                    'description': comp.description,
                    'version': comp.version,
                    'metadata': comp.metadata
                })
                
            except Exception as e:
                logger.warning(f"Failed to load {yaml_file}: {e}")
    
    return {
        'status': 'success',
        'compositions': discovered,
        'count': len(discovered)
    }


async def handle_list(data: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_get(data: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_reload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Reload compositions from disk."""
    # Clear caches
    composition_cache.clear()
    fragment_cache.clear()
    
    logger.info("Cleared composition and fragment caches")
    
    return {
        'status': 'success',
        'message': 'Caches cleared, compositions will be reloaded on next access'
    }


# Plugin lifecycle
@hookimpl
def ksi_startup(config):
    """Initialize composition service on startup."""
    logger.info("Composition service started")
    
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