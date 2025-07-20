"""
Shared utilities for composition path resolution and loading.

Provides consistent path resolution across all composition handlers to avoid
duplication and ensure uniform behavior.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from ksi_common.config import config
from ksi_common.component_loader import find_component_file, load_component_file
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("composition_utils")

# Base directories from config
COMPOSITIONS_BASE = config.compositions_dir
COMPONENTS_BASE = config.components_dir


def get_composition_base_path(comp_type: str) -> Path:
    """
    Get the base path for a composition type.
    
    Args:
        comp_type: The composition type (orchestration, evaluation, component, etc.)
        
    Returns:
        The base path for the composition type
    """
    # Components live under components/
    if comp_type == 'component':
        return COMPONENTS_BASE
    
    # Everything else (orchestrations, evaluations, workflows) lives under compositions/
    return COMPOSITIONS_BASE


def resolve_composition_path(name: str, comp_type: str = 'component') -> Optional[Path]:
    """
    Resolve the full path to a composition file.
    
    This handles the different directory structures:
    - components/* -> var/lib/compositions/components/*
    - orchestrations/* -> var/lib/compositions/orchestrations/*
    - evaluations/* -> var/lib/compositions/evaluations/*
    
    Args:
        name: The composition name (can include subdirectories)
        comp_type: The composition type
        
    Returns:
        The resolved path if found, None otherwise
    """
    base_path = get_composition_base_path(comp_type)
    
    # Use the shared component finder which handles extensions
    return find_component_file(base_path, name)


def load_composition_with_metadata(name: str, comp_type: str = 'component') -> Tuple[Dict[str, Any], str, Path]:
    """
    Load a composition file with its metadata.
    
    Args:
        name: The composition name
        comp_type: The composition type
        
    Returns:
        Tuple of (metadata, content, file_path)
        
    Raises:
        FileNotFoundError: If composition not found
        ValueError: If composition cannot be parsed
    """
    # Resolve the path
    file_path = resolve_composition_path(name, comp_type)
    if not file_path:
        raise FileNotFoundError(f"Composition '{name}' of type '{comp_type}' not found")
    
    # Load using shared loader
    metadata, content = load_component_file(file_path)
    
    return metadata, content, file_path


def normalize_composition_name(name: str) -> str:
    """
    Normalize a composition name for consistent handling.
    
    - Removes 'components/' prefix if present
    - Strips .md/.yaml extensions
    - Converts backslashes to forward slashes
    
    Args:
        name: The raw composition name
        
    Returns:
        The normalized name
    """
    # Convert backslashes to forward slashes
    name = name.replace('\\', '/')
    
    # Remove components/ prefix if present
    if name.startswith('components/'):
        name = name[11:]
    
    # Strip common extensions
    for ext in ['.md', '.yaml', '.yml']:
        if name.endswith(ext):
            name = name[:-len(ext)]
    
    return name