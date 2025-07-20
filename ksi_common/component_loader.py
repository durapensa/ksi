#!/usr/bin/env python3
"""
Unified component/composition loader that handles multiple file formats.
Provides consistent loading interface for the entire system.

## Core Functions:
- find_component_file() - Locate files with multiple extension fallbacks
- load_component_file() - Load YAML/Markdown/JSON with unified interface
- resolve_component_path() - Smart path resolution with type-based defaults
- extract_metadata() - Consistent metadata extraction across formats

## Usage Examples:
    # Find and load any component
    metadata, content, path = load_component(base_dir, "my_component")
    
    # Load specific file
    metadata, content = load_component_file(Path("component.yaml"))
    
    # Smart path resolution
    path = resolve_component_path("data_analyst", component_type="persona")
"""

from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List
import json
import hashlib
import datetime

from .frontmatter_utils import parse_frontmatter
from .file_utils import load_yaml_file, load_json_file
from .yaml_utils import safe_load


# File type constants
MARKDOWN_EXTENSIONS = ['.md', '.markdown']
YAML_EXTENSIONS = ['.yaml', '.yml']
JSON_EXTENSIONS = ['.json']
ALL_EXTENSIONS = MARKDOWN_EXTENSIONS + YAML_EXTENSIONS + JSON_EXTENSIONS

# Component type to directory mapping
COMPONENT_TYPE_DIRS = {
    'core': 'core',
    'persona': 'personas',
    'behavior': 'behaviors',
    'behaviour': 'behaviors',  # Alias
    'orchestration': 'orchestrations',
    'evaluation': 'evaluations',
    'evaluation_suite': 'evaluations/suites',
    'tool': 'tools',
    'example': 'examples',
    'component': 'components',  # Generic
}


def find_component_file(base_path: Path, component_name: str, extensions: Optional[List[str]] = None) -> Optional[Path]:
    """
    Find a component file by trying different extensions.
    
    Args:
        base_path: Base directory to search in
        component_name: Name/path of component (without extension)
        extensions: List of extensions to try (defaults to ALL_EXTENSIONS)
        
    Returns:
        Path to found file or None if not found
    """
    if extensions is None:
        extensions = ALL_EXTENSIONS
    
    # Clean component name (remove any existing extension)
    name_path = Path(component_name)
    if name_path.suffix in ALL_EXTENSIONS:
        component_name = str(name_path.with_suffix(''))
    
    # Try exact path with different extensions
    for ext in extensions:
        component_path = base_path / f"{component_name}{ext}"
        if component_path.exists():
            return component_path
    
    # Try recursive search if no exact match
    for ext in extensions:
        pattern = f"{component_name}{ext}"
        matches = list(base_path.rglob(pattern))
        if matches:
            # Sort by path depth (prefer shallower matches)
            matches.sort(key=lambda p: len(p.parts))
            return matches[0]
    
    return None


def resolve_component_path(component_name: str, component_type: Optional[str] = None, base_path: Optional[Path] = None) -> str:
    """
    Resolve component path with smart type-based directory mapping.
    
    Args:
        component_name: Component name or path
        component_type: Optional component type for directory resolution
        base_path: Optional base path (defaults to current directory)
        
    Returns:
        Resolved component path (without extension)
        
    Examples:
        resolve_component_path("data_analyst", "persona") -> "personas/data_analyst"
        resolve_component_path("behaviors/claude_override") -> "behaviors/claude_override"
    """
    # If already contains directory separator, return as-is
    if '/' in component_name:
        return component_name
    
    # If component type provided, use type-based directory
    if component_type and component_type.lower() in COMPONENT_TYPE_DIRS:
        type_dir = COMPONENT_TYPE_DIRS[component_type.lower()]
        return f"{type_dir}/{component_name}"
    
    # Default: return as-is
    return component_name


def extract_file_type(file_path: Path) -> str:
    """
    Determine file type from extension.
    
    Returns: 'markdown', 'yaml', 'json', or 'unknown'
    """
    suffix = file_path.suffix.lower()
    
    if suffix in MARKDOWN_EXTENSIONS:
        return 'markdown'
    elif suffix in YAML_EXTENSIONS:
        return 'yaml'
    elif suffix in JSON_EXTENSIONS:
        return 'json'
    else:
        return 'unknown'


def load_component_file(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """
    Load a component from YAML, Markdown, or JSON file.
    
    Args:
        file_path: Path to component file
        
    Returns:
        Tuple of (metadata dict, content string)
        - For YAML/JSON files: (data, '')
        - For MD files: (frontmatter, content)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type is not supported or has invalid format
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Component file not found: {file_path}")
    
    file_type = extract_file_type(file_path)
    
    if file_type == 'markdown':
        # Handle markdown files with frontmatter
        content = file_path.read_text(encoding='utf-8')
        post = parse_frontmatter(content, sanitize_dates=True)
        
        if post.has_frontmatter():
            return post.metadata, post.content
        else:
            # No frontmatter, treat as pure content
            return {}, content
            
    elif file_type == 'yaml':
        # Handle YAML files
        yaml_data = load_yaml_file(file_path)
        return yaml_data or {}, ''  # YAML files have no separate content
        
    elif file_type == 'json':
        # Handle JSON files
        json_data = load_json_file(file_path)
        return json_data or {}, ''  # JSON files have no separate content
        
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")


def load_component(base_path: Path, component_name: str, component_type: Optional[str] = None) -> Tuple[Dict[str, Any], str, Path]:
    """
    Find and load a component by name, with smart path resolution.
    
    Args:
        base_path: Base directory to search in
        component_name: Name/path of component (without extension)
        component_type: Optional type for path resolution
        
    Returns:
        Tuple of (metadata dict, content string, file path)
        
    Raises:
        FileNotFoundError: If component not found
        ValueError: If file type is not supported
    """
    # Resolve component path based on type
    resolved_name = resolve_component_path(component_name, component_type)
    
    # Find the file
    file_path = find_component_file(base_path, resolved_name)
    
    if not file_path:
        tried_extensions = ', '.join(ALL_EXTENSIONS)
        raise FileNotFoundError(f"Component not found: {resolved_name} (tried {tried_extensions})")
    
    # Load the file
    metadata, content = load_component_file(file_path)
    return metadata, content, file_path


def extract_metadata(metadata: Dict[str, Any], content: str = '') -> Dict[str, Any]:
    """
    Extract and normalize metadata from various sources.
    
    Ensures consistent metadata structure with common fields:
    - name, type, version, description, author
    - component_type (normalized from type)
    - dependencies, capabilities, tags
    
    Args:
        metadata: Raw metadata dictionary
        content: Optional content string for analysis
        
    Returns:
        Normalized metadata dictionary
    """
    normalized = metadata.copy()
    
    # Ensure component_type field exists
    if 'component_type' not in normalized and 'type' in normalized:
        normalized['component_type'] = normalized['type']
    
    # Ensure lists are lists
    list_fields = ['dependencies', 'capabilities', 'tags', 'mixins']
    for field in list_fields:
        if field in normalized and not isinstance(normalized[field], list):
            # Convert single value to list
            normalized[field] = [normalized[field]] if normalized[field] else []
    
    # Set defaults for common fields
    defaults = {
        'version': '0.0.0',
        'description': '',
        'dependencies': [],
        'capabilities': [],
        'tags': []
    }
    
    for key, default in defaults.items():
        if key not in normalized:
            normalized[key] = default
    
    return normalized


def component_exists(base_path: Path, component_name: str, component_type: Optional[str] = None) -> bool:
    """
    Check if a component exists without loading it.
    
    Args:
        base_path: Base directory to search in
        component_name: Name/path of component
        component_type: Optional type for path resolution
        
    Returns:
        True if component exists, False otherwise
    """
    resolved_name = resolve_component_path(component_name, component_type)
    file_path = find_component_file(base_path, resolved_name)
    return file_path is not None


def calculate_file_hash(file_path: Path, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file's contents.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        Hex digest of file hash
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    content = file_path.read_text(encoding='utf-8')
    
    if algorithm == 'sha256':
        return hashlib.sha256(content.encode()).hexdigest()
    elif algorithm == 'md5':
        return hashlib.md5(content.encode()).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(content.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def get_file_stats(file_path: Path) -> Dict[str, Any]:
    """
    Get file statistics including size, modification time, and hash.
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file stats:
        - size: File size in bytes
        - modified: ISO format modification time
        - created: ISO format creation time (if available)
        - hash: SHA256 hash of contents
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    stats = file_path.stat()
    
    return {
        'size': stats.st_size,
        'modified': datetime.datetime.fromtimestamp(stats.st_mtime).isoformat(),
        'created': datetime.datetime.fromtimestamp(stats.st_ctime).isoformat() if hasattr(stats, 'st_ctime') else None,
        'hash': calculate_file_hash(file_path)
    }