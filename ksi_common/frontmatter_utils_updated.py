#!/usr/bin/env python3

"""
Modern frontmatter parsing utilities using python-frontmatter
Provides robust parsing of YAML frontmatter in markdown and other text files
"""

import frontmatter
from pathlib import Path
from typing import Dict, Any, Union, Optional, Tuple, List
import structlog
from pydantic import BaseModel, ValidationError
from .timestamps import sanitize_for_json
from .yaml_utils import safe_load, YAMLParseError

logger = structlog.get_logger("frontmatter_utils")


class FrontmatterPost:
    """Enhanced frontmatter post with validation and type safety."""
    
    def __init__(self, content: str, metadata: Dict[str, Any], original_content: str = None):
        self.content = content
        self.metadata = metadata
        self.original_content = original_content or (metadata.get('---', '') + content)
        
    def __str__(self) -> str:
        return self.content
        
    def __repr__(self) -> str:
        return f"FrontmatterPost(metadata_keys={list(self.metadata.keys())}, content_length={len(self.content)})"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get metadata value with default."""
        return self.metadata.get(key, default)
        
    def has_frontmatter(self) -> bool:
        """Check if post has frontmatter."""
        return bool(self.metadata)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'content': self.content,
            'metadata': self.metadata,
            'has_frontmatter': self.has_frontmatter()
        }


class FrontmatterParseError(ValueError):
    """Frontmatter parsing error with context."""
    pass


class FrontmatterValidator:
    """Validates frontmatter against schemas."""
    
    @staticmethod
    def validate_component_frontmatter(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate component frontmatter structure."""
        errors = []
        
        # Check extends field
        if 'extends' in metadata:
            extends = metadata['extends']
            if not isinstance(extends, str):
                errors.append("'extends' must be a string")
            elif not extends.endswith('.md') and not extends.endswith('.yaml'):
                errors.append("'extends' must reference a .md or .yaml file")
                
        # Check mixins field
        if 'mixins' in metadata:
            mixins = metadata['mixins']
            if not isinstance(mixins, list):
                errors.append("'mixins' must be a list")
            else:
                for i, mixin in enumerate(mixins):
                    if not isinstance(mixin, str):
                        errors.append(f"mixin[{i}] must be a string")
                        
        # Check variables field
        if 'variables' in metadata:
            variables = metadata['variables']
            if not isinstance(variables, dict):
                errors.append("'variables' must be a dictionary")
            else:
                for var_name, var_def in variables.items():
                    if not isinstance(var_def, dict):
                        errors.append(f"variable '{var_name}' must be a dictionary")
                    else:
                        # Check variable definition structure
                        if 'type' in var_def:
                            valid_types = ['string', 'integer', 'boolean', 'list', 'dict']
                            if var_def['type'] not in valid_types:
                                errors.append(f"variable '{var_name}' has invalid type: {var_def['type']}")
                                
        # Check metadata field
        if 'metadata' in metadata:
            meta_field = metadata['metadata']
            if not isinstance(meta_field, dict):
                errors.append("'metadata' must be a dictionary")
                
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_profile_frontmatter(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate profile frontmatter structure."""
        errors = []
        
        # Check required fields
        if 'name' not in metadata:
            errors.append("'name' is required")
        elif not isinstance(metadata['name'], str):
            errors.append("'name' must be a string")
            
        if 'type' not in metadata:
            errors.append("'type' is required")
        elif metadata['type'] not in ['profile', 'component', 'template']:
            errors.append("'type' must be 'profile', 'component', or 'template'")
            
        return len(errors) == 0, errors


def parse_frontmatter(content: str, sanitize_dates: bool = True) -> FrontmatterPost:
    """Parse frontmatter from content with robust error handling."""
    try:
        post = frontmatter.loads(content)
        metadata = dict(post.metadata)
        
        if sanitize_dates:
            metadata = sanitize_for_json(metadata)
            
        return FrontmatterPost(
            content=post.content,
            metadata=metadata,
            original_content=content
        )
    except Exception as e:
        logger.warning(f"Frontmatter parsing failed, falling back to manual parsing: {e}")
        return _manual_frontmatter_parse(content, sanitize_dates)


def _manual_frontmatter_parse(content: str, sanitize_dates: bool = True) -> FrontmatterPost:
    """Manual frontmatter parsing fallback for malformed content."""
    if not content.startswith('---\n'):
        return FrontmatterPost(content=content, metadata={})
    
    try:
        # Find closing ---
        end_marker = content.find('\n---\n', 4)
        if end_marker == -1:
            logger.warning("No closing --- found in frontmatter")
            return FrontmatterPost(content=content, metadata={})
        
        frontmatter_text = content[4:end_marker]
        body_content = content[end_marker + 5:]
        
        # Try to parse YAML
        try:
            metadata = safe_load(frontmatter_text)
            if not isinstance(metadata, dict):
                metadata = {}
        except YAMLParseError as e:
            logger.warning(f"YAML parsing failed in frontmatter: {e}")
            metadata = {}
            
        if sanitize_dates:
            metadata = sanitize_for_json(metadata)
            
        return FrontmatterPost(
            content=body_content,
            metadata=metadata,
            original_content=content
        )
    except Exception as e:
        logger.error(f"Manual frontmatter parsing failed: {e}")
        return FrontmatterPost(content=content, metadata={})


def parse_frontmatter_file(file_path: Union[str, Path], sanitize_dates: bool = True) -> FrontmatterPost:
    """Parse frontmatter from file."""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return parse_frontmatter(content, sanitize_dates=sanitize_dates)
    except UnicodeDecodeError as e:
        raise FrontmatterParseError(f"File encoding error in {path}: {e}") from e
    except Exception as e:
        raise FrontmatterParseError(f"Failed to read file {path}: {e}") from e


def create_frontmatter_content(metadata: Dict[str, Any], content: str, 
                              sanitize_dates: bool = True) -> str:
    """Create content with frontmatter from metadata and body."""
    if sanitize_dates:
        metadata = sanitize_for_json(metadata)
        
    try:
        post = frontmatter.Post(content, **metadata)
        return frontmatter.dumps(post)
    except Exception as e:
        logger.error(f"Failed to create frontmatter content: {e}")
        raise FrontmatterParseError(f"Failed to create frontmatter: {e}") from e


def update_frontmatter_file(file_path: Union[str, Path], 
                           metadata: Dict[str, Any], 
                           content: str = None,
                           sanitize_dates: bool = True) -> None:
    """Update frontmatter in file, preserving content if not provided."""
    path = Path(file_path)
    
    if content is None:
        # Read existing content
        existing_post = parse_frontmatter_file(path, sanitize_dates=False)
        content = existing_post.content
    
    # Create new content with updated frontmatter
    new_content = create_frontmatter_content(metadata, content, sanitize_dates)
    
    # Write atomically
    temp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            f.flush()
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise FrontmatterParseError(f"Failed to update file {path}: {e}") from e


def extract_frontmatter_metadata(content: str) -> Dict[str, Any]:
    """Extract only the frontmatter metadata without parsing the full content."""
    post = parse_frontmatter(content)
    return post.metadata


def has_frontmatter(content: str) -> bool:
    """Check if content has frontmatter."""
    return content.strip().startswith('---\n')


def validate_frontmatter(content: str, 
                        validator_type: str = 'component') -> Tuple[bool, List[str]]:
    """Validate frontmatter against schema."""
    post = parse_frontmatter(content)
    
    if not post.has_frontmatter():
        return True, []  # No frontmatter is valid
    
    if validator_type == 'component':
        return FrontmatterValidator.validate_component_frontmatter(post.metadata)
    elif validator_type == 'profile':
        return FrontmatterValidator.validate_profile_frontmatter(post.metadata)
    else:
        return True, []  # Unknown validator type, assume valid


def strip_frontmatter(content: str) -> str:
    """Remove frontmatter from content, returning only body."""
    post = parse_frontmatter(content)
    return post.content


def get_component_type(content: str) -> str:
    """Determine component type from frontmatter."""
    post = parse_frontmatter(content)
    if post.has_frontmatter():
        # Return actual component_type from frontmatter
        return post.metadata.get('component_type', 'component')
    return 'component'  # Default type


# Convenience functions for common operations
def load_component_with_frontmatter(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load component file and return structured data."""
    post = parse_frontmatter_file(file_path)
    
    return {
        'component_type': 'enhanced' if post.has_frontmatter() else 'simple',
        'content': post.content,
        'frontmatter': post.metadata if post.has_frontmatter() else None,
        'metadata': post.metadata,
        'path': str(file_path)
    }