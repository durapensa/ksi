#!/usr/bin/env python3
"""
Composition Core - Data structures and loading logic
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.yaml_utils import load_yaml_file, safe_load
from ksi_common.json_utils import loads as json_loads, dumps as json_dumps
from ksi_common.template_utils import substitute_variables as template_substitute_variables
from ksi_common.component_loader import find_component_file, load_component_file
from ksi_common.composition_utils import resolve_composition_path, get_composition_base_path
from . import composition_index

logger = get_bound_logger("composition_core")

# Path constants
COMPONENTS_BASE = config.components_dir
COMPOSITIONS_BASE = config.compositions_dir
SCHEMAS_BASE = config.schemas_dir
CAPABILITIES_BASE = config.capabilities_dir


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
                    # Simple string specification
                    variables[var_name] = {'description': var_spec}
                elif isinstance(var_spec, dict):
                    # Complex specification
                    variables[var_name] = {'default': var_spec}
                else:
                    # Direct value
                    variables[var_name] = {'default': var_spec}
        
        # Preserve all fields that aren't explicitly handled
        known_fields = {
            'name', 'type', 'version', 'description', 'author',
            'extends', 'mixins', 'components', 'variables', 
            'metadata', 'required_context'
        }
        
        # Create metadata dict that includes existing metadata plus any unknown fields
        combined_metadata = data.get('metadata', {}).copy()
        for key, value in data.items():
            if key not in known_fields:
                combined_metadata[key] = value
        
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
            metadata=combined_metadata
        )


def load_component(path: str) -> str:
    """Load a text component from disk."""
    # Strip leading 'components/' if present to avoid double-prefixing
    if path.startswith('components/'):
        path = path[11:]  # len('components/') = 11
    
    component_path = COMPONENTS_BASE / path
    if not component_path.exists():
        raise FileNotFoundError(f"Component not found: {path}")
    
    return component_path.read_text()


def substitute_variables(text: str, variables: Dict[str, Any]) -> str:
    """Substitute {{variable}} placeholders in text."""
    return template_substitute_variables(text, variables)


def evaluate_condition(condition: str, variables: Dict[str, Any]) -> bool:
    """Evaluate a simple condition expression."""
    # Substitute variables in condition
    condition = substitute_variables(condition, variables)
    
    # Remove {{ }} if still present (means variable was undefined)
    if '{{' in condition:
        return False
    
    # Security: only allow simple comparisons
    allowed_names = {
        'True': True, 'False': False, 'None': None,
        'len': len, 'str': str, 'int': int, 'bool': bool
    }
    
    try:
        # Use eval with restricted globals
        return bool(eval(condition, {"__builtins__": {}}, allowed_names))
    except Exception:
        logger.warning(f"Failed to evaluate condition: {condition}")
        return False


def evaluate_conditions(conditions: Dict[str, List[str]], variables: Dict[str, Any]) -> bool:
    """Evaluate multiple condition groups (all_of, any_of, none_of)."""
    # all_of: all conditions must be true
    if 'all_of' in conditions:
        for cond in conditions['all_of']:
            if not evaluate_condition(cond, variables):
                return False
    
    # any_of: at least one condition must be true
    if 'any_of' in conditions:
        any_true = False
        for cond in conditions['any_of']:
            if evaluate_condition(cond, variables):
                any_true = True
                break
        if not any_true:
            return False
    
    # none_of: no condition must be true
    if 'none_of' in conditions:
        for cond in conditions['none_of']:
            if evaluate_condition(cond, variables):
                return False
    
    return True


async def load_composition(name: str, comp_type: Optional[str] = None) -> Composition:
    """Load a composition by name and optional type."""
    logger.info(f"Loading composition: name={name}, comp_type={comp_type}")
    
    # Use shared utility to resolve path based on type
    composition_path = resolve_composition_path(name, comp_type or 'orchestration')
    
    if not composition_path:
        raise FileNotFoundError(f"Composition not found: {name}")
    
    # Load using shared component loader
    metadata, content = load_component_file(composition_path)
    
    # For compositions, we only need the metadata
    comp_data = metadata
    
    # If it was a markdown file with no frontmatter, content might be all we have
    if not comp_data and content and composition_path.suffix == '.md':
        raise ValueError(f"Markdown file {name} has no frontmatter")
    
    return Composition.from_yaml(comp_data)