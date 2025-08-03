"""
Shared utilities for composition path resolution and loading.

Provides consistent path resolution across all composition handlers to avoid
duplication and ensure uniform behavior.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from ksi_common.config import config
from ksi_common.component_loader import find_component_file, load_component_file
from ksi_common.component_renderer import render_component, get_renderer
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import format_for_logging

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


def create_agent_manifest_from_component(
    component_name: str,
    frontmatter: Dict[str, Any],
    rendered_content: str,
    variables: Dict[str, Any],
    agent_id: str
) -> Dict[str, Any]:
    """
    Create an in-memory agent manifest from component data.
    
    This is a shared utility that creates the same manifest structure as
    composition:component_to_profile but returns it in-memory instead of
    saving to disk.
    
    Args:
        component_name: The source component name
        frontmatter: The component's frontmatter metadata
        rendered_content: The rendered component content
        variables: Variables used for rendering
        agent_id: The target agent ID
        
    Returns:
        Complete agent manifest data structure
    """
    # Extract agent config fields from frontmatter
    agent_config_fields = {
        'model': frontmatter.get('model', config.completion_default_model),
        'role': frontmatter.get('role', 'assistant'),
        'enable_tools': frontmatter.get('enable_tools', False),
        'capabilities': frontmatter.get('capabilities', ['conversation', 'analysis', 'task_execution']),
        'message_queue_size': frontmatter.get('message_queue_size', 100),
        'priority': frontmatter.get('priority', 'normal'),
        'allowed_claude_tools': frontmatter.get('allowed_claude_tools', [])
    }
    
    # Add any additional fields from frontmatter that start with 'agent_'
    for key, value in frontmatter.items():
        if key.startswith('agent_') and key not in agent_config_fields:
            agent_config_fields[key] = value
    
    # Create manifest structure
    manifest_data = {
        'name': f"in_memory_manifest_{agent_id}",
        'type': 'profile',  # Keep as 'profile' for compatibility with existing systems
        'version': '1.0.0',
        'description': f'In-memory agent manifest generated from component {component_name}',
        'author': 'composition_utils:create_agent_manifest_from_component',
        'components': [
            {
                'name': 'agent_config',
                'inline': agent_config_fields
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
            'render_timestamp': format_for_logging(),
            'generated_by': 'composition_utils:create_agent_manifest_from_component'
        }
    }
    
    # Known top-level fields to preserve
    top_level_preserve = [
        'security_profile',
        'permission_profile', 
        'sandbox',
        'dependencies',
        'extends',
        'loading_strategy'
    ]
    
    # Add known top-level fields if present
    for field in top_level_preserve:
        if field in frontmatter:
            manifest_data[field] = frontmatter[field]
            logger.debug(f"Preserved {field} from component frontmatter: {frontmatter[field]}")
    
    # Also add agent config fields to top level for backward compatibility
    # The agent spawn handler expects these at the top level
    manifest_data.update(agent_config_fields)
    
    # Pass through any other unknown fields from frontmatter
    # This ensures forward compatibility
    for key, value in frontmatter.items():
        if (key not in manifest_data and 
            key not in agent_config_fields and
            key not in ['name', 'type', 'version', 'description', 'author', 'component_type'] and
            not key.startswith('_')):  # Skip internal fields
            manifest_data[key] = value
            logger.debug(f"Preserved unknown field {key} from frontmatter")
    
    return manifest_data


def render_component_to_agent_manifest(
    component_name: str,
    variables: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-level utility to render a component and create an agent manifest.
    
    This combines component loading, rendering, and manifest creation into
    a single convenient function for in-memory agent manifests.
    
    Args:
        component_name: The component to render
        variables: Variables for rendering
        agent_id: Agent ID (generated if not provided)
        
    Returns:
        Complete agent manifest data structure
        
    Raises:
        FileNotFoundError: If component not found
        ValueError: If component cannot be parsed or rendered
    """
    if variables is None:
        variables = {}
    
    if agent_id is None:
        import uuid
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    
    # Ensure agent_id is in variables for template substitution
    variables = {**variables, 'agent_id': agent_id}
    
    try:
        # Use the component renderer to get both rendered content AND merged frontmatter
        # This ensures behavioral overrides are properly applied
        renderer = get_renderer()
        rendered_content, merged_frontmatter = renderer.render_with_frontmatter(component_name, variables)
        
        # Create the agent manifest using the merged frontmatter that includes behavioral overrides
        manifest_data = create_agent_manifest_from_component(
            component_name=component_name,
            frontmatter=merged_frontmatter,  # Use merged frontmatter instead of raw
            rendered_content=rendered_content,
            variables=variables,
            agent_id=agent_id
        )
        
        logger.info(f"Created in-memory agent manifest for {agent_id} from component {component_name}")
        return manifest_data
        
    except Exception as e:
        logger.error(f"Failed to render component {component_name} to agent manifest: {e}")
        raise ValueError(f"Failed to render component {component_name} to agent manifest: {e}") from e