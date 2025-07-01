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
from ksi_daemon.core_plugin import get_ksi_context_variable

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
CAPABILITIES_BASE = config.capabilities_dir

# Capability schema cache
_capability_schema_cache = None


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
    task_description: NotRequired[str]
    preferred_style: NotRequired[str]
    context_variables: NotRequired[Dict[str, Any]]
    max_suggestions: NotRequired[int]
    requirements: NotRequired[Dict[str, Any]]


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
        
        # Merge variables and required_context for capability detection
        variables = data.get('variables', {}).copy()
        required_context = data.get('required_context', {})
        
        # Convert required_context entries to variable definitions
        for var_name, var_spec in required_context.items():
            if var_name not in variables:
                if isinstance(var_spec, str):
                    # Simple string specification like "string - description"
                    variables[var_name] = {'description': var_spec}
                elif isinstance(var_spec, dict):
                    # Complex specification with nested structure
                    variables[var_name] = {'default': var_spec}
                else:
                    # Direct value
                    variables[var_name] = {'default': var_spec}
        
        return cls(
            name=data['name'],
            type=data['type'],
            version=data['version'],
            description=data['description'],
            author=data.get('author'),
            extends=data.get('extends'),
            mixins=data.get('mixins', []),
            components=components,
            variables=variables,
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


def _load_capability_schema() -> Dict[str, Any]:
    """Load capability schema from declarative YAML file."""
    global _capability_schema_cache
    
    if _capability_schema_cache is not None:
        return _capability_schema_cache
    
    schema_file = CAPABILITIES_BASE / "ksi_capabilities.yaml"
    
    try:
        if not schema_file.exists():
            logger.error(f"Capability schema file not found: {schema_file}")
            return {"capability_groups": {}}
        
        with open(schema_file, 'r') as f:
            schema = yaml.safe_load(f)
        
        _capability_schema_cache = schema
        logger.debug(f"Loaded capability schema from {schema_file}")
        return schema
        
    except Exception as e:
        logger.error(f"Failed to load capability schema: {e}")
        return {"capability_groups": {}}


def _resolve_ksi_capabilities_from_requirements(required_capabilities) -> Set[str]:
    """Map plugin-based capability requirements to KSI context using discovery-driven schema with [all]/[exclude] patterns."""
    schema = _load_capability_schema()
    plugin_capabilities = schema.get("plugin_capabilities", {})
    capability_groups = schema.get("capability_groups", {})
    ksi_context_vars = set()
    
    # Handle simple string capability groups (minimal, standard, orchestrator, full_ksi)
    if isinstance(required_capabilities, str):
        group_def = capability_groups.get(required_capabilities, {})
        if group_def:
            ksi_context_vars.update(group_def.get("context_required", []))
            logger.debug(f"Capability group '{required_capabilities}' requires context: {group_def.get('context_required', [])}")
            return ksi_context_vars
    
    # Handle [all] at top level - grant all plugins
    if required_capabilities == "all" or (isinstance(required_capabilities, list) and "all" in required_capabilities):
        for plugin_def in plugin_capabilities.values():
            ksi_context_vars.update(plugin_def.get("context_required", []))
        logger.debug(f"[all] pattern requires context from all plugins: {ksi_context_vars}")
        return ksi_context_vars
    
    # Handle full_ksi special case (backwards compatibility)
    if required_capabilities == 'full_ksi' or (isinstance(required_capabilities, list) and 'full_ksi' in required_capabilities):
        full_ksi_def = capability_groups.get("full_ksi", {})
        ksi_context_vars.update(full_ksi_def.get("context_required", []))
        return ksi_context_vars
    
    # Handle complex capability requirements with [all]/[exclude] patterns
    if isinstance(required_capabilities, dict):
        # Handle top-level [all] with exclusions
        if "plugins" in required_capabilities:
            requested_plugins = required_capabilities["plugins"]
            excluded_plugins = set(required_capabilities.get("exclude", []))
            excluded_events = set(required_capabilities.get("exclude_events", []))
            
            # Handle [all] plugins pattern
            if "all" in requested_plugins:
                # Start with all plugins
                for plugin_name, plugin_def in plugin_capabilities.items():
                    if plugin_name not in excluded_plugins:
                        context_needed = plugin_def.get("context_required", [])
                        ksi_context_vars.update(context_needed)
                        logger.debug(f"[all] plugin '{plugin_name}' requires context: {context_needed}")
            else:
                # Specific plugin list
                for plugin_name in requested_plugins:
                    if plugin_name != "all" and plugin_name not in excluded_plugins:
                        plugin_def = plugin_capabilities.get(plugin_name, {})
                        context_needed = plugin_def.get("context_required", [])
                        ksi_context_vars.update(context_needed)
                        logger.debug(f"Plugin '{plugin_name}' requires context: {context_needed}")
        else:
            # Per-plugin event specifications with [all]/[exclude] support
            for plugin_name, plugin_spec in required_capabilities.items():
                plugin_def = plugin_capabilities.get(plugin_name, {})
                if not plugin_def:
                    logger.warning(f"Unknown plugin capability: {plugin_name}")
                    continue
                
                available_events = plugin_def.get("events", [])
                context_needed = plugin_def.get("context_required", [])
                
                # Handle different plugin specification formats
                if isinstance(plugin_spec, dict):
                    # Complex plugin specification with events and exclusions
                    requested_events = plugin_spec.get("events", [])
                    excluded_events = set(plugin_spec.get("exclude", []))
                    
                    if "all" in requested_events:
                        # All events from this plugin except excluded
                        granted_events = [e for e in available_events if e not in excluded_events]
                        if granted_events:
                            ksi_context_vars.update(context_needed)
                            logger.debug(f"Plugin '{plugin_name}' [all] events (excluding {excluded_events}) requires context: {context_needed}")
                    else:
                        # Specific events only
                        granted_events = [e for e in requested_events if e in available_events and e not in excluded_events]
                        if granted_events:
                            ksi_context_vars.update(context_needed)
                            logger.debug(f"Plugin '{plugin_name}' events {granted_events} requires context: {context_needed}")
                            
                elif isinstance(plugin_spec, list):
                    # Simple event list or [all]
                    if "all" in plugin_spec:
                        # All events from this plugin
                        ksi_context_vars.update(context_needed)
                        logger.debug(f"Plugin '{plugin_name}' [all] events requires context: {context_needed}")
                    else:
                        # Specific events
                        granted_events = [e for e in plugin_spec if e in available_events]
                        if granted_events:
                            ksi_context_vars.update(context_needed)
                            logger.debug(f"Plugin '{plugin_name}' events {granted_events} requires context: {context_needed}")
                else:
                    # Simple plugin access (backward compatibility)
                    ksi_context_vars.update(context_needed)
                    logger.debug(f"Plugin '{plugin_name}' (full access) requires context: {context_needed}")
    
    # Handle simple plugin list (with [all] support)
    elif isinstance(required_capabilities, list):
        excluded_items = set()
        
        # Extract exclusions if present
        if any(isinstance(item, dict) and "exclude" in item for item in required_capabilities):
            for item in required_capabilities:
                if isinstance(item, dict) and "exclude" in item:
                    excluded_items.update(item["exclude"])
        
        for capability in required_capabilities:
            if isinstance(capability, dict):
                continue  # Skip exclude specs, already processed
                
            if capability == "all":
                # Grant all plugins except excluded
                for plugin_name, plugin_def in plugin_capabilities.items():
                    if plugin_name not in excluded_items:
                        ksi_context_vars.update(plugin_def.get("context_required", []))
                        logger.debug(f"[all] capability granted plugin '{plugin_name}'")
            elif capability in capability_groups and capability not in excluded_items:
                # It's a capability group
                group_def = capability_groups[capability]
                ksi_context_vars.update(group_def.get("context_required", []))
            elif capability in plugin_capabilities and capability not in excluded_items:
                # It's a plugin name
                plugin_def = plugin_capabilities[capability]
                ksi_context_vars.update(plugin_def.get("context_required", []))
            elif capability not in excluded_items:
                logger.warning(f"Unknown capability: {capability}")
    
    return ksi_context_vars


def _should_resolve_ksi_context(composition: Composition) -> bool:
    """Infer KSI context needs from declared capability requirements."""
    # Check if composition declares capabilities in required_context
    required_capabilities = None
    
    # Look for capabilities in the composition's variable definitions
    for var_name, var_def in composition.variables.items():
        if var_name == 'capabilities':
            required_capabilities = var_def.get('default') if isinstance(var_def, dict) else var_def
            break
    
    if not required_capabilities:
        return False
    
    # Resolve what KSI context is needed for these capabilities
    needed_context = _resolve_ksi_capabilities_from_requirements(required_capabilities)
    return len(needed_context) > 0


def _resolve_ksi_context_variables(variables: Dict[str, Any], composition: Composition) -> None:
    """Resolve special KSI context variables from daemon cache based on required context."""
    
    # Get the specific KSI context variables needed for this composition's capabilities
    required_capabilities = None
    for var_name, var_def in composition.variables.items():
        if var_name == 'capabilities':
            required_capabilities = var_def.get('default') if isinstance(var_def, dict) else var_def
            break
    
    if not required_capabilities:
        logger.debug(f"Skipping KSI resolution for composition without capability requirements: {composition.name}")
        return
    
    # Determine which KSI context variables are needed
    needed_context_vars = _resolve_ksi_capabilities_from_requirements(required_capabilities)
    
    if not needed_context_vars:
        logger.debug(f"No KSI context needed for composition capabilities: {composition.name}")
        return
    
    logger.debug(f"Resolving KSI context for {composition.name}: {needed_context_vars}")
    
    # Resolve only the needed KSI context variables
    for var_name in needed_context_vars:
        # Resolve if variable is not set or is a template placeholder
        should_resolve = (
            var_name not in variables or  # Not set at all
            variables[var_name] == f"{{{{{var_name}}}}}" or  # Template placeholder  
            isinstance(variables[var_name], str) and variables[var_name].startswith("{{") and variables[var_name].endswith("}}")  # Any template
        )
        
        if should_resolve:
            try:
                cached_value = get_ksi_context_variable(var_name)
                if cached_value is not None:
                    variables[var_name] = cached_value
                    logger.debug(f"Resolved KSI context variable: {var_name} for capability-driven composition")
                else:
                    logger.warning(f"KSI context variable not available: {var_name}")
                    variables[var_name] = f"KSI context not available: {var_name}"
            except Exception as e:
                logger.error(f"Error resolving KSI context variable {var_name}: {e}")
                variables[var_name] = f"Error loading {var_name}"


async def _score_composition_for_context(composition: Composition, context: SelectionContext) -> tuple[float, List[str]]:
    """Score a composition against selection context using multi-factor algorithm."""
    score = 0.0
    reasons = []
    
    # 1. Role matching (weight: 30%)
    if context.role and composition.metadata.get('role'):
        if context.role.lower() == composition.metadata['role'].lower():
            score += 30
            reasons.append(f"Exact role match: {context.role}")
        elif context.role.lower() in composition.metadata.get('compatible_roles', []):
            score += 20
            reasons.append(f"Compatible role: {context.role}")
    
    # Check suitable_for field
    if context.role and composition.metadata.get('suitable_for'):
        suitable_for = composition.metadata['suitable_for']
        if isinstance(suitable_for, list) and context.role.lower() in [s.lower() for s in suitable_for]:
            score += 25
            reasons.append(f"Listed as suitable for: {context.role}")
    
    # 2. Capability requirements (weight: 25%)
    if context.capabilities:
        comp_caps_required = composition.metadata.get('required_capabilities', [])
        comp_caps_provided = composition.metadata.get('provides_capabilities', [])
        
        # Check if composition requires capabilities the agent has
        if comp_caps_required:
            matching_caps = set(context.capabilities) & set(comp_caps_required)
            if matching_caps:
                cap_score = (len(matching_caps) / len(comp_caps_required)) * 25
                score += cap_score
                reasons.append(f"Capability match: {', '.join(matching_caps)}")
        
        # Check if composition provides capabilities the agent needs  
        if comp_caps_provided:
            useful_caps = set(comp_caps_provided) & set(context.capabilities)
            if useful_caps:
                score += 10
                reasons.append(f"Provides useful capabilities: {', '.join(useful_caps)}")
    
    # 3. Task relevance (weight: 25%)
    if context.task_description:
        task_keywords = context.task_description.lower().split()
        
        # Check description
        desc_matches = sum(1 for kw in task_keywords if kw in composition.description.lower())
        if desc_matches:
            score += min(desc_matches * 5, 15)
            reasons.append(f"Description matches task ({desc_matches} keywords)")
        
        # Check tags
        comp_tags = [tag.lower() for tag in composition.metadata.get('tags', [])]
        tag_matches = sum(1 for kw in task_keywords if any(kw in tag for tag in comp_tags))
        if tag_matches:
            score += min(tag_matches * 3, 10)
            reasons.append(f"Tags match task ({tag_matches} matches)")
    
    # 4. Style preference (weight: 10%)
    if context.preferred_style:
        comp_style = composition.metadata.get('style', '').lower()
        if context.preferred_style.lower() in comp_style:
            score += 10
            reasons.append(f"Style match: {context.preferred_style}")
    
    # 5. Quality indicators (weight: 10%)
    # Prefer newer versions
    try:
        version = float(composition.version)
        if version >= 2.0:
            score += 5
            reasons.append("Recent version")
    except (ValueError, TypeError):
        pass
    
    # Prefer well-documented compositions
    if len(composition.metadata.get('use_cases', [])) >= 2:
        score += 3
        reasons.append("Well-documented use cases")
    
    if composition.metadata.get('tested', False):
        score += 2
        reasons.append("Tested composition")
    
    # KSI context requirement check
    if context.requirements and 'ksi_context' in context.requirements:
        required_ksi = context.requirements['ksi_context']
        comp_has_ksi = _should_resolve_ksi_context(composition)
        if required_ksi == comp_has_ksi:
            score += 15
            reasons.append(f"KSI context requirement met: {comp_has_ksi}")
        elif required_ksi and not comp_has_ksi:
            score -= 20
            reasons.append("KSI context required but composition has no KSI dependencies")
    
    return score, reasons


def _get_fallback_selection() -> SelectionResult:
    """Get fallback selection when no composition can be found."""
    return SelectionResult(
        composition_name='claude_agent_default',
        score=0.0,
        reasons=['Fallback: No suitable composition found'],
        fallback_used=True
    )


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
    
    # Resolve special KSI context variables 
    _resolve_ksi_context_variables(variables, composition)
    
    # Process components
    for component in composition.components:
        # Check conditions
        if component.condition and not evaluate_condition(component.condition, variables):
            continue
        
        if component.conditions and not evaluate_conditions(component.conditions, variables):
            continue
        
        # Merge component vars with global vars
        comp_vars = {**variables, **component.vars}
        
        # Resolve KSI context variables in comp_vars (handles component-level overrides)
        _resolve_ksi_context_variables(comp_vars, composition)
        
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
    category=EventCategory.CORE,
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
    """Discover available compositions using index with optional metadata filtering."""
    if not composition_index:
        return {'error': 'Composition index not available'}
    
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
    category=EventCategory.CONTROL,
    typical_duration_ms=800,
    has_cost=True,
    best_practices=["Provide clear task description for better selection", "Include relevant capabilities"]
)
async def handle_select_composition(data: CompositionSelectData) -> Dict[str, Any]:
    """Handle intelligent composition selection using sophisticated scoring algorithm."""
    try:
        # Build selection context
        context = SelectionContext(
            agent_id=data.get('agent_id', 'unknown'),
            role=data.get('role'),
            capabilities=data.get('capabilities', []),
            task_description=data.get('task_description'),
            preferred_style=data.get('preferred_style'),
            context_variables=data.get('context_variables', {}),
            requirements=data.get('requirements', {})
        )
        
        # Get all available compositions
        if not composition_index:
            logger.error("Composition index not available")
            fallback = _get_fallback_selection()
            return {
                'status': 'error',
                'selected': fallback.composition_name,
                'score': fallback.score,
                'reasons': fallback.reasons,
                'fallback_used': True,
                'error': 'Composition index not available'
            }
        
        # Discover all compositions  
        discovered = composition_index.discover({})
        if not discovered:
            logger.warning("No compositions found for selection")
            fallback = _get_fallback_selection()
            return {
                'status': 'success',
                'selected': fallback.composition_name,
                'score': fallback.score,
                'reasons': fallback.reasons,
                'fallback_used': True
            }
        
        # Score each composition
        scored_compositions = []
        for comp_info in discovered:
            try:
                # Load full composition for metadata
                composition = await load_composition(comp_info['name'])
                score, reasons = await _score_composition_for_context(composition, context)
                
                if score > 0:
                    scored_compositions.append((comp_info['name'], score, reasons, composition))
            except Exception as e:
                logger.warning(f"Failed to score composition {comp_info['name']}: {e}")
                continue
        
        # Select best composition
        if scored_compositions:
            # Sort by score (highest first)
            scored_compositions.sort(key=lambda x: x[1], reverse=True)
            best_name, best_score, best_reasons, best_composition = scored_compositions[0]
            
            result = SelectionResult(
                composition_name=best_name,
                score=best_score,
                reasons=best_reasons,
                fallback_used=False
            )
            
            logger.info(f"Selected composition '{best_name}' for {context.agent_id} (score: {best_score:.2f})")
        else:
            logger.warning(f"No suitable composition found for {context.agent_id}, using fallback")
            result = _get_fallback_selection()
        
        # Prepare response
        response = {
            'status': 'success',
            'selected': result.composition_name,
            'score': result.score,
            'reasons': result.reasons,
            'fallback_used': result.fallback_used
        }
        
        # Add suggestions if requested
        max_suggestions = data.get('max_suggestions', 1)
        if max_suggestions > 1 and scored_compositions:
            suggestions = [
                {
                    'name': name,
                    'score': score,
                    'reasons': reasons
                }
                for name, score, reasons, _ in scored_compositions[:max_suggestions]
            ]
            response['suggestions'] = suggestions
        
        return response
        
    except Exception as e:
        logger.error(f"Composition selection failed: {e}")
        fallback = _get_fallback_selection()
        return {
            'status': 'error',
            'selected': fallback.composition_name,
            'score': fallback.score,
            'reasons': fallback.reasons + [f"Error: {str(e)}"],
            'fallback_used': True,
            'error': str(e)
        }


@event_handler("composition:suggest")
async def handle_suggest_compositions(data: CompositionSelectData) -> Dict[str, Any]:
    """Get top N composition suggestions for the given context."""
    try:
        # Build selection context
        context = SelectionContext(
            agent_id=data.get('agent_id', 'unknown'),
            role=data.get('role'),
            capabilities=data.get('capabilities', []),
            task_description=data.get('task_description'),
            preferred_style=data.get('preferred_style'),
            context_variables=data.get('context_variables', {}),
            requirements=data.get('requirements', {})
        )
        
        max_suggestions = data.get('max_suggestions', 3)
        
        # Get all available compositions
        if not composition_index:
            return {'error': 'Composition index not available'}
        
        discovered = composition_index.discover({})
        if not discovered:
            return {
                'status': 'success',
                'suggestions': [],
                'count': 0
            }
        
        # Score all compositions
        scored_results = []
        for comp_info in discovered:
            try:
                composition = await load_composition(comp_info['name'])
                score, reasons = await _score_composition_for_context(composition, context)
                
                if score > 0:
                    scored_results.append({
                        'name': comp_info['name'],
                        'score': score,
                        'reasons': reasons,
                        'description': composition.description,
                        'metadata': composition.metadata
                    })
            except Exception as e:
                logger.warning(f"Failed to score composition {comp_info['name']}: {e}")
                continue
        
        # Sort by score and return top N
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        suggestions = scored_results[:max_suggestions]
        
        return {
            'status': 'success',
            'suggestions': suggestions,
            'count': len(suggestions),
            'total_evaluated': len(discovered)
        }
        
    except Exception as e:
        logger.error(f"Composition suggestion failed: {e}")
        return {'error': str(e)}


@event_handler("composition:validate_context")
async def handle_validate_context(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that a composition will work with the given context."""
    composition_name = data.get('composition_name')
    context_vars = data.get('context', {})
    
    if not composition_name:
        return {'error': 'composition_name is required'}
    
    try:
        # Load the composition
        composition = await load_composition(composition_name)
        
        # Check required context variables
        missing_context = []
        invalid_types = []
        
        for var_name, var_def in composition.variables.items():
            if var_name not in context_vars:
                # Check if there's a default
                if 'default' not in var_def:
                    missing_context.append(var_name)
            else:
                # Type validation (basic)
                expected_type = var_def.get('type')
                if expected_type:
                    actual_value = context_vars[var_name]
                    # Simple type checking
                    type_valid = True
                    if expected_type == 'string' and not isinstance(actual_value, str):
                        type_valid = False
                    elif expected_type == 'number' and not isinstance(actual_value, (int, float)):
                        type_valid = False
                    elif expected_type == 'boolean' and not isinstance(actual_value, bool):
                        type_valid = False
                    elif expected_type == 'array' and not isinstance(actual_value, list):
                        type_valid = False
                    elif expected_type == 'object' and not isinstance(actual_value, dict):
                        type_valid = False
                    
                    if not type_valid:
                        invalid_types.append({
                            'variable': var_name,
                            'expected': expected_type,
                            'actual': type(actual_value).__name__
                        })
        
        # Check if composition has required capabilities
        required_caps = composition.metadata.get('required_capabilities', [])
        provided_caps = context_vars.get('capabilities', [])
        missing_capabilities = []
        
        if required_caps:
            missing_capabilities = [cap for cap in required_caps if cap not in provided_caps]
        
        # Determine if valid
        is_valid = not missing_context and not invalid_types and not missing_capabilities
        
        result = {
            'status': 'success',
            'valid': is_valid,
            'composition_name': composition_name
        }
        
        if missing_context:
            result['missing_context'] = missing_context
        
        if invalid_types:
            result['invalid_types'] = invalid_types
        
        if missing_capabilities:
            result['missing_capabilities'] = missing_capabilities
        
        if is_valid:
            result['message'] = 'Context validation passed'
        else:
            issues = []
            if missing_context:
                issues.append(f"{len(missing_context)} missing variables")
            if invalid_types:
                issues.append(f"{len(invalid_types)} type mismatches")
            if missing_capabilities:
                issues.append(f"{len(missing_capabilities)} missing capabilities")
            result['message'] = f"Validation failed: {', '.join(issues)}"
        
        return result
        
    except Exception as e:
        logger.error(f"Context validation failed: {e}")
        return {'error': str(e)}


@event_handler("composition:capabilities")
async def handle_get_capabilities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get available KSI capabilities from declarative schema."""
    try:
        schema = _load_capability_schema()
        capability_groups = schema.get("capability_groups", {})
        
        # Optional filtering by group
        group_filter = data.get("group")
        if group_filter:
            if group_filter in capability_groups:
                filtered_groups = {group_filter: capability_groups[group_filter]}
            else:
                return {
                    'status': 'error',
                    'error': f'Capability group not found: {group_filter}'
                }
        else:
            filtered_groups = capability_groups
        
        # Transform for response
        capabilities = {}
        for group_name, group_caps in filtered_groups.items():
            capabilities[group_name] = {}
            for cap_name, cap_def in group_caps.items():
                capabilities[group_name][cap_name] = {
                    'description': cap_def.get('description', ''),
                    'context_required': cap_def.get('context', []),
                    'future_proof': cap_def.get('future_proof', False)
                }
        
        return {
            'status': 'success',
            'capabilities': capabilities,
            'schema_version': schema.get('schema_version', 'unknown'),
            'total_groups': len(capabilities),
            'total_capabilities': sum(len(group) for group in capabilities.values())
        }
        
    except Exception as e:
        logger.error(f"Failed to get capabilities: {e}")
        return {'error': str(e)}


@event_handler("composition:get_path") 
async def handle_get_path(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get the file path for a composition."""
    full_name = data.get("full_name")
    
    if not full_name:
        return {"error": "full_name is required"}
    
    if not composition_index:
        return {"error": "Composition index not available"}
    
    try:
        path = composition_index.get_path(full_name)
        
        if path:
            return {
                "status": "success",
                "full_name": full_name,
                "path": str(path),
                "found": True
            }
        else:
            return {
                "status": "not_found",
                "full_name": full_name,
                "found": False
            }
    except Exception as e:
        logger.error(f"Failed to get composition path: {e}")
        return {"error": str(e)}


@event_handler("composition:get_metadata")
async def handle_get_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get metadata for a composition."""
    full_name = data.get("full_name")
    
    if not full_name:
        return {"error": "full_name is required"}
    
    if not composition_index:
        return {"error": "Composition index not available"}
    
    try:
        metadata = composition_index.get_metadata(full_name)
        
        if metadata:
            return {
                "status": "success",
                "full_name": full_name,
                "metadata": metadata,
                "found": True
            }
        else:
            return {
                "status": "not_found",
                "full_name": full_name,
                "found": False
            }
    except Exception as e:
        logger.error(f"Failed to get composition metadata: {e}")
        return {"error": str(e)}


@event_handler("composition:rebuild_index")
async def handle_rebuild_index(data: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild the composition index."""
    repository_id = data.get("repository_id", "local")
    
    if not composition_index:
        return {"error": "Composition index not available"}
    
    try:
        indexed_count = composition_index.rebuild_index(repository_id)
        
        return {
            "status": "success",
            "repository_id": repository_id,
            "indexed_count": indexed_count
        }
    except Exception as e:
        logger.error(f"Failed to rebuild composition index: {e}")
        return {"error": str(e)}


@event_handler("composition:index_file")
async def handle_index_file(data: Dict[str, Any]) -> Dict[str, Any]:
    """Index a single composition file."""
    file_path = data.get("file_path")
    
    if not file_path:
        return {"error": "file_path is required"}
    
    if not composition_index:
        return {"error": "Composition index not available"}
    
    try:
        from pathlib import Path
        path = Path(file_path)
        
        success = composition_index.index_composition_file(path)
        
        return {
            "status": "success" if success else "failed",
            "file_path": file_path,
            "indexed": success
        }
    except Exception as e:
        logger.error(f"Failed to index composition file: {e}")
        return {"error": str(e)}


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