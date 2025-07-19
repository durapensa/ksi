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
    
    # Use composition index to find the file path
    composition_path = await composition_index.get_path(name)
    logger.info(f"Index returned path: {composition_path}")
    
    if not composition_path or not composition_path.exists():
        # Fallback: search for the file by name pattern
        composition_path = None
        
        # Try exact name match for both .yaml and .md files
        for pattern in [f"{name}.yaml", f"{name}.md"]:
            matches = list(COMPOSITIONS_BASE.rglob(pattern))
            if matches:
                composition_path = matches[0]
                break
        
        if not composition_path or not composition_path.exists():
            raise FileNotFoundError(f"Composition not found: {name}")
    
    # Load and parse based on file type
    if composition_path.suffix == '.md':
        # Handle markdown files with frontmatter
        from ksi_common.frontmatter_utils import parse_frontmatter
        content = composition_path.read_text()
        post = parse_frontmatter(content, sanitize_dates=True)
        if post.has_frontmatter():
            comp_data = post.metadata
        else:
            raise ValueError(f"Markdown file {name} has no frontmatter")
    else:
        # Handle YAML files
        comp_data = load_yaml_file(composition_path)
    
    return Composition.from_yaml(comp_data)