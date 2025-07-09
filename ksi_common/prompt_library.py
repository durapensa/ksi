#!/usr/bin/env python3
"""
Prompt Library - Centralized management for reusable prompts

This module provides:
- Standardized prompt storage and retrieval
- Prompt composition and variable substitution
- Metadata tracking for prompt effectiveness
- Integration with the evaluation system
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import re

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.file_utils import save_yaml_file, load_yaml_file, ensure_directory
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("prompt_library")


class PromptEntry:
    """A single prompt in the library."""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data['name']
        self.type = data.get('type', 'prompt')
        self.version = data.get('version', '1.0.0')
        self.description = data.get('description', '')
        self.author = data.get('author', 'unknown')
        self.parameters = data.get('parameters', {})
        self.content = data.get('content', '')
        self.metadata = data.get('metadata', {})
        self.category = data.get('category', 'general')
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            'name': self.name,
            'type': self.type,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'parameters': self.parameters,
            'content': self.content,
            'metadata': self.metadata,
            'category': self.category
        }
    
    def render(self, variables: Dict[str, Any]) -> str:
        """Render the prompt with variable substitution."""
        content = self.content
        
        # Check required parameters
        for param_name, param_spec in self.parameters.items():
            if param_spec.get('required', False) and param_name not in variables:
                # Use default if available
                if 'default' in param_spec:
                    variables[param_name] = param_spec['default']
                else:
                    raise ValueError(f"Required parameter '{param_name}' not provided")
        
        # Substitute variables
        def replace_var(match):
            var_name = match.group(1).strip()
            if var_name in variables:
                value = variables[var_name]
                # Handle different value types
                if isinstance(value, (dict, list)):
                    import json
                    return json.dumps(value, indent=2)
                return str(value)
            # Check for default
            if var_name in self.parameters and 'default' in self.parameters[var_name]:
                return str(self.parameters[var_name]['default'])
            return match.group(0)  # Keep original if not found
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, content)


class PromptLibrary:
    """Manages the prompt library."""
    
    def __init__(self):
        self.prompts_dir = config.compositions_dir / "prompts"
        self._cache: Dict[str, PromptEntry] = {}
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure prompt library directories exist."""
        ensure_directory(self.prompts_dir)
        for subdir in ['core', 'templates', 'conversations', 'specialized']:
            ensure_directory(self.prompts_dir / subdir)
    
    def save_prompt(
        self,
        name: str,
        content: str,
        category: str = "templates",
        subcategory: Optional[str] = None,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        author: str = "ksi-system"
    ) -> str:
        """Save a prompt to the library."""
        # Determine file path
        if subcategory:
            prompt_path = self.prompts_dir / category / subcategory / f"{name}.yaml"
        else:
            prompt_path = self.prompts_dir / category / f"{name}.yaml"
        
        ensure_directory(prompt_path.parent)
        
        # Build prompt data
        prompt_data = {
            'name': name,
            'type': 'prompt',
            'version': '1.0.0',
            'description': description,
            'author': author,
            'category': f"{category}/{subcategory}" if subcategory else category,
            'parameters': parameters or {},
            'content': content,
            'metadata': {
                **(metadata or {}),
                'created': timestamp_utc()
            }
        }
        
        # Save to file
        save_yaml_file(prompt_path, prompt_data)
        
        # Update cache
        self._cache[name] = PromptEntry(prompt_data)
        
        logger.info(f"Saved prompt '{name}' to {prompt_path}")
        return str(prompt_path)
    
    def load_prompt(self, name: str, category: Optional[str] = None) -> Optional[PromptEntry]:
        """Load a prompt from the library."""
        # Check cache first
        if name in self._cache:
            return self._cache[name]
        
        # Search for prompt file
        if category:
            # Try specific category first
            pattern = f"{category}/**/{name}.yaml"
        else:
            # Search all categories
            pattern = f"**/{name}.yaml"
        
        for prompt_file in self.prompts_dir.glob(pattern):
            try:
                data = load_yaml_file(prompt_file)
                prompt = PromptEntry(data)
                self._cache[name] = prompt
                return prompt
            except Exception as e:
                logger.error(f"Failed to load prompt from {prompt_file}: {e}")
        
        return None
    
    def list_prompts(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all prompts, optionally filtered by category."""
        prompts = []
        
        if category:
            search_path = self.prompts_dir / category
        else:
            search_path = self.prompts_dir
        
        for prompt_file in search_path.rglob("*.yaml"):
            try:
                data = load_yaml_file(prompt_file)
                # Extract key info
                prompts.append({
                    'name': data.get('name'),
                    'category': data.get('category', 'unknown'),
                    'description': data.get('description', ''),
                    'version': data.get('version', '1.0.0'),
                    'author': data.get('author', 'unknown'),
                    'tags': data.get('metadata', {}).get('tags', []),
                    'path': str(prompt_file.relative_to(self.prompts_dir))
                })
            except Exception as e:
                logger.warning(f"Failed to read prompt file {prompt_file}: {e}")
        
        return sorted(prompts, key=lambda p: (p['category'], p['name']))
    
    def compose_prompts(
        self,
        prompts: List[str],
        separator: str = "\n\n",
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """Compose multiple prompts together."""
        composed = []
        
        for prompt_name in prompts:
            prompt = self.load_prompt(prompt_name)
            if prompt:
                rendered = prompt.render(variables or {})
                composed.append(rendered)
            else:
                logger.warning(f"Prompt '{prompt_name}' not found")
        
        return separator.join(composed)


# Global instance
prompt_library = PromptLibrary()