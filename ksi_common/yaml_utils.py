#!/usr/bin/env python3

"""
Modern YAML utilities using ruamel.yaml
Provides type-safe, robust YAML parsing with better error handling
"""

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from pathlib import Path
from typing import Dict, Any, Union, Optional, List, TextIO
import structlog
from .timestamps import sanitize_for_json

logger = structlog.get_logger("yaml_utils")


class YAMLProcessor:
    """Modern YAML processor with ruamel.yaml backend."""
    
    def __init__(self, preserve_quotes: bool = True, indent: int = 2):
        """Initialize YAML processor with safe defaults."""
        self.yaml = YAML(typ='safe')
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = preserve_quotes
        self.yaml.indent(mapping=indent, sequence=indent, offset=indent)
        self.yaml.width = 4096  # Avoid line wrapping
        
    def loads(self, content: str) -> Any:
        """Parse YAML string with robust error handling."""
        if not content or not content.strip():
            return {}
            
        try:
            result = self.yaml.load(content)
            return result if result is not None else {}
        except YAMLError as e:
            logger.error(f"YAML parsing failed: {e}")
            raise YAMLParseError(f"Failed to parse YAML: {e}") from e
    
    def dumps(self, data: Any, sanitize_dates: bool = True) -> str:
        """Convert data to YAML string with consistent formatting."""
        if sanitize_dates:
            data = sanitize_for_json(data)
            
        try:
            from io import StringIO
            stream = StringIO()
            self.yaml.dump(data, stream)
            return stream.getvalue()
        except Exception as e:
            logger.error(f"YAML serialization failed: {e}")
            raise YAMLSerializationError(f"Failed to serialize to YAML: {e}") from e
    
    def load_file(self, file_path: Union[str, Path]) -> Any:
        """Load YAML from file with comprehensive error handling."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {path}")
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return self.loads(content)
        except UnicodeDecodeError as e:
            logger.error(f"UTF-8 decode error in {path}: {e}")
            raise YAMLParseError(f"File encoding error in {path}: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load YAML file {path}: {e}")
            raise YAMLParseError(f"Failed to load YAML file {path}: {e}") from e
    
    def save_file(self, file_path: Union[str, Path], data: Any, 
                  create_dirs: bool = True, atomic: bool = True) -> None:
        """Save data to YAML file with atomic writes."""
        path = Path(file_path)
        
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
            
        content = self.dumps(data)
        
        if atomic:
            # Atomic write using temporary file
            temp_path = path.with_suffix(path.suffix + '.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                temp_path.replace(path)  # Atomic on most filesystems
            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise YAMLSerializationError(f"Failed to write YAML file {path}: {e}") from e
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)


class YAMLParseError(ValueError):
    """YAML parsing error with context."""
    pass


class YAMLSerializationError(ValueError):
    """YAML serialization error with context."""
    pass


# Global processor instance for convenience
_default_processor = YAMLProcessor()

# Convenience functions that match old PyYAML API
def safe_load(content: str) -> Any:
    """Parse YAML string - replacement for yaml.safe_load()."""
    return _default_processor.loads(content)

def safe_dump(data: Any, sanitize_dates: bool = True) -> str:
    """Convert data to YAML string - replacement for yaml.safe_dump()."""
    return _default_processor.dumps(data, sanitize_dates=sanitize_dates)

def load_yaml_file(file_path: Union[str, Path]) -> Any:
    """Load YAML from file - enhanced version of file_utils function."""
    return _default_processor.load_file(file_path)

def save_yaml_file(file_path: Union[str, Path], data: Any, 
                   create_dirs: bool = True, atomic: bool = True) -> None:
    """Save data to YAML file - enhanced version of file_utils function."""
    _default_processor.save_file(file_path, data, create_dirs=create_dirs, atomic=atomic)

def validate_yaml_structure(data: Any, required_keys: List[str], 
                           optional_keys: List[str] = None) -> bool:
    """Validate YAML structure has required keys."""
    if not isinstance(data, dict):
        return False
        
    optional_keys = optional_keys or []
    all_allowed_keys = set(required_keys + optional_keys)
    data_keys = set(data.keys())
    
    # Check required keys exist
    if not all(key in data_keys for key in required_keys):
        return False
        
    # Check no unexpected keys
    if not data_keys.issubset(all_allowed_keys):
        return False
        
    return True

def merge_yaml_configs(base_config: Dict[str, Any], 
                      override_config: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge YAML configurations."""
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    return _deep_merge(base_config, override_config)


# Specialized processors for different use cases
class ComponentYAMLProcessor(YAMLProcessor):
    """YAML processor optimized for component metadata."""
    
    def __init__(self):
        super().__init__(preserve_quotes=True, indent=2)
        
    def validate_component_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Validate component metadata structure."""
        required_keys = []  # No strictly required keys
        optional_keys = [
            'extends', 'mixins', 'variables', 'metadata', 'conditions',
            'version', 'author', 'description', 'tags'
        ]
        return validate_yaml_structure(metadata, required_keys, optional_keys)


class ProfileYAMLProcessor(YAMLProcessor):
    """YAML processor optimized for profile configurations."""
    
    def __init__(self):
        super().__init__(preserve_quotes=True, indent=2)
        
    def validate_profile_structure(self, profile: Dict[str, Any]) -> bool:
        """Validate profile structure."""
        required_keys = ['name', 'type']
        optional_keys = [
            'version', 'description', 'author', 'extends', 'mixins',
            'components', 'variables', 'metadata', 'capabilities'
        ]
        return validate_yaml_structure(profile, required_keys, optional_keys)


# Export specialized processors
component_yaml = ComponentYAMLProcessor()
profile_yaml = ProfileYAMLProcessor()