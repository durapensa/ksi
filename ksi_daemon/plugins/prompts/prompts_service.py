#!/usr/bin/env python3
"""
Prompts Service Plugin

Provides prompt composition functionality as a plugin service.
Handles composition, validation, and component management through events.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from ...plugin_base import BasePlugin, hookimpl
from ...plugin_types import PluginInfo

logger = logging.getLogger(__name__)


class PromptsServicePlugin(BasePlugin):
    """Service plugin for handling prompt composition and management."""
    
    def __init__(self):
        super().__init__(
            name="prompts_service",
            version="1.0.0",
            description="Prompt composition and management service",
            author="KSI Team",
            namespaces=["prompts"]
        )
        
        # Plugin context references
        self._event_bus = None
        self._composer = None
        
    def _get_composer(self):
        """Lazy load the prompt composer."""
        if self._composer is None:
            # Add parent directories to path if needed
            project_root = Path(__file__).parent.parent.parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from prompts.composer import PromptComposer
            self._composer = PromptComposer()
        
        return self._composer
    
    @hookimpl
    def ksi_startup(self):
        """Initialize prompts service on startup."""
        logger.info("Prompts service plugin starting")
        
        # Verify prompts directory exists
        project_root = Path(__file__).parent.parent.parent.parent.parent
        prompts_dir = project_root / "prompts"
        
        if not prompts_dir.exists():
            logger.warning(f"Prompts directory not found at {prompts_dir}")
            return {"status": "prompts_service_warning", "message": "Prompts directory not found"}
        
        return {"status": "prompts_service_ready"}
    
    @hookimpl
    def ksi_plugin_context(self, context):
        """Receive plugin context with event bus access."""
        self._event_bus = context.get("event_bus")
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle prompts-related events."""
        
        if event_name == "prompts:compose":
            return self._handle_compose(data)
        
        elif event_name == "prompts:list_compositions":
            return self._handle_list_compositions(data)
        
        elif event_name == "prompts:get_composition":
            return self._handle_get_composition(data)
        
        elif event_name == "prompts:validate":
            return self._handle_validate_composition(data)
        
        elif event_name == "prompts:list_components":
            return self._handle_list_components(data)
        
        return None
    
    def _handle_compose(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle prompt composition request.
        
        Args:
            data: Request data containing composition and context
            
        Returns:
            Composed prompt or error
        """
        composition = data.get("composition")
        context = data.get("context", {})
        
        if not composition:
            return {
                "error": {
                    "code": "INVALID_PARAMETERS",
                    "message": "Missing required parameter: composition"
                }
            }
        
        try:
            composer = self._get_composer()
            
            # Compose the prompt
            prompt = composer.compose(composition, context)
            
            # Load composition metadata
            composition_metadata = {}
            try:
                composition_obj = composer.load_composition(composition)
                composition_metadata = {
                    'name': composition_obj.name,
                    'version': composition_obj.version,
                    'description': composition_obj.description,
                    'author': composition_obj.author,
                    'component_count': len(composition_obj.components),
                    'metadata': composition_obj.metadata
                }
            except Exception as e:
                logger.warning(f"Could not load composition metadata: {e}")
                composition_metadata = {
                    'name': composition,
                    'metadata_error': str(e)
                }
            
            # Analyze the composed prompt
            prompt_lines = prompt.split('\n')
            non_empty_lines = [line for line in prompt_lines if line.strip()]
            
            prompt_analysis = {
                'length_chars': len(prompt),
                'length_words': len(prompt.split()),
                'length_lines': len(prompt_lines),
                'non_empty_lines': len(non_empty_lines),
                'estimated_tokens': len(prompt.split()) * 1.3,  # Rough estimate
                'has_variables': '{{' in prompt and '}}' in prompt
            }
            
            # Check for potential issues
            warnings = []
            if prompt_analysis['has_variables']:
                warnings.append("Prompt contains unresolved variables ({{variable_name}})")
            if prompt_analysis['length_chars'] == 0:
                warnings.append("Composed prompt is empty")
            elif prompt_analysis['length_chars'] < 50:
                warnings.append("Composed prompt is very short")
            elif prompt_analysis['length_chars'] > 100000:
                warnings.append("Composed prompt is very long (>100KB)")
            
            # Build response
            return {
                'prompt': prompt,
                'composition_used': composition,
                'context_provided': context,
                'composition_metadata': composition_metadata,
                'prompt_analysis': prompt_analysis,
                'warnings': warnings,
                'composed_successfully': True
            }
            
        except FileNotFoundError:
            # Handle composition not found
            try:
                composer = self._get_composer()
                available_compositions = composer.list_compositions()
                
                error_msg = f"Composition not found: {composition}. "
                if available_compositions:
                    similar = [name for name in available_compositions 
                             if composition.lower() in name.lower() or name.lower() in composition.lower()]
                    
                    if similar:
                        error_msg += f"Similar compositions: {', '.join(similar[:3])}. "
                    else:
                        error_msg += f"Available compositions: {', '.join(available_compositions[:5])}"
                        if len(available_compositions) > 5:
                            error_msg += f" (and {len(available_compositions) - 5} more)"
                        error_msg += ". "
                else:
                    error_msg += "No compositions are available. "
                
                error_msg += "Use prompts:list_compositions to see all available compositions."
                
            except Exception:
                error_msg = f"Composition not found: {composition}"
            
            return {
                "error": {
                    "code": "COMPOSITION_NOT_FOUND",
                    "message": error_msg
                }
            }
            
        except ValueError as e:
            # Handle context validation errors
            error_msg = str(e)
            
            try:
                composer = self._get_composer()
                composition_obj = composer.load_composition(composition)
                required_context = list(composition_obj.required_context.keys())
                provided_context = list(context.keys())
                
                missing = [key for key in required_context if key not in provided_context]
                if missing:
                    error_msg += f" Missing required context: {', '.join(missing)}."
                
                error_msg += f" Required context: {', '.join(required_context)}."
                error_msg += " Use prompts:validate to check context requirements."
                
            except Exception:
                pass
            
            return {
                "error": {
                    "code": "CONTEXT_VALIDATION_ERROR",
                    "message": error_msg
                }
            }
            
        except Exception as e:
            logger.error(f"Error composing prompt: {e}")
            return {
                "error": {
                    "code": "COMPOSITION_FAILED",
                    "message": f"Failed to compose prompt: {str(e)}"
                }
            }
    
    def _handle_list_compositions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list compositions request.
        
        Args:
            data: Request data with optional filters
            
        Returns:
            List of available compositions
        """
        include_metadata = data.get("include_metadata", True)
        category = data.get("category")
        
        try:
            composer = self._get_composer()
            composition_names = composer.list_compositions()
            
            items = []
            failed_compositions = []
            
            for comp_name in composition_names:
                try:
                    if include_metadata:
                        composition = composer.load_composition(comp_name)
                        
                        # Apply category filter if specified
                        if category and composition.metadata.get('category') != category:
                            continue
                        
                        # Build complete composition info
                        comp_info = {
                            'name': composition.name,
                            'version': composition.version,
                            'description': composition.description,
                            'author': composition.author,
                            'required_context': composition.required_context,
                            'metadata': composition.metadata,
                            'component_count': len(composition.components)
                        }
                    else:
                        comp_info = {
                            'name': comp_name,
                            'version': 'unknown',
                            'description': 'Metadata not loaded',
                            'author': 'unknown'
                        }
                    
                    items.append(comp_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to load composition {comp_name}: {e}")
                    failed_compositions.append({
                        'name': comp_name,
                        'error': str(e)
                    })
            
            # Build metadata about the results
            metadata = {
                'include_metadata': include_metadata,
                'category_filter': category,
                'total_found': len(composition_names),
                'filtered_count': len(items),
                'failed_to_load': len(failed_compositions)
            }
            
            if failed_compositions:
                metadata['failed_compositions'] = failed_compositions
            
            return {
                'items': items,
                'total': len(items),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error listing compositions: {e}")
            return {
                "error": {
                    "code": "LIST_FAILED",
                    "message": f"Failed to list compositions: {str(e)}"
                }
            }
    
    def _handle_get_composition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get specific composition request.
        
        Args:
            data: Request data with composition name
            
        Returns:
            Composition details or error
        """
        name = data.get("name")
        
        if not name:
            return {
                "error": {
                    "code": "INVALID_PARAMETERS",
                    "message": "Missing required parameter: name"
                }
            }
        
        try:
            composer = self._get_composer()
            composition = composer.load_composition(name)
            
            # Build detailed composition info
            comp_info = {
                'name': composition.name,
                'version': composition.version,
                'description': composition.description,
                'author': composition.author,
                'required_context': composition.required_context,
                'optional_context': composition.optional_context,
                'components': composition.components,
                'metadata': composition.metadata,
                'instructions': composition.instructions
            }
            
            # Add analysis
            comp_info['analysis'] = {
                'component_count': len(composition.components),
                'required_context_count': len(composition.required_context),
                'optional_context_count': len(composition.optional_context),
                'has_instructions': bool(composition.instructions)
            }
            
            return comp_info
            
        except FileNotFoundError:
            return {
                "error": {
                    "code": "COMPOSITION_NOT_FOUND",
                    "message": f"Composition not found: {name}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting composition: {e}")
            return {
                "error": {
                    "code": "GET_FAILED",
                    "message": f"Failed to get composition: {str(e)}"
                }
            }
    
    def _handle_validate_composition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle validate composition request.
        
        Args:
            data: Request data with name and context
            
        Returns:
            Validation result
        """
        name = data.get("name")
        context = data.get("context", {})
        
        if not name:
            return {
                "error": {
                    "code": "INVALID_PARAMETERS",
                    "message": "Missing required parameter: name"
                }
            }
        
        try:
            composer = self._get_composer()
            composition = composer.load_composition(name)
            
            # Check required context
            required_keys = set(composition.required_context.keys())
            provided_keys = set(context.keys())
            missing_keys = required_keys - provided_keys
            
            # Check optional context
            optional_keys = set(composition.optional_context.keys())
            optional_provided = optional_keys & provided_keys
            optional_missing = optional_keys - provided_keys
            
            # Extra keys not in schema
            all_expected_keys = required_keys | optional_keys
            extra_keys = provided_keys - all_expected_keys
            
            # Validate types if all required keys are present
            type_errors = []
            if not missing_keys:
                for key, value in context.items():
                    if key in composition.required_context:
                        expected_type = composition.required_context[key].get('type', 'any')
                        if not self._validate_type(value, expected_type):
                            type_errors.append({
                                'key': key,
                                'expected': expected_type,
                                'actual': type(value).__name__
                            })
            
            # Build validation result
            is_valid = len(missing_keys) == 0 and len(type_errors) == 0
            
            result = {
                'composition_name': name,
                'is_valid': is_valid,
                'required_context': dict(composition.required_context),
                'optional_context': dict(composition.optional_context),
                'validation_details': {
                    'required_keys': list(required_keys),
                    'provided_keys': list(provided_keys),
                    'missing_required': list(missing_keys),
                    'optional_provided': list(optional_provided),
                    'optional_missing': list(optional_missing),
                    'extra_keys': list(extra_keys)
                }
            }
            
            if type_errors:
                result['validation_details']['type_errors'] = type_errors
            
            # Add helpful message
            if is_valid:
                result['message'] = "Context is valid for this composition"
            else:
                messages = []
                if missing_keys:
                    messages.append(f"Missing required context: {', '.join(missing_keys)}")
                if type_errors:
                    messages.append(f"Type errors in {len(type_errors)} field(s)")
                result['message'] = ". ".join(messages)
            
            return result
            
        except FileNotFoundError:
            return {
                "error": {
                    "code": "COMPOSITION_NOT_FOUND",
                    "message": f"Composition not found: {name}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating composition: {e}")
            return {
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": f"Failed to validate composition: {str(e)}"
                }
            }
    
    def _handle_list_components(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list components request.
        
        Args:
            data: Request data with optional directory filter
            
        Returns:
            List of available components
        """
        directory = data.get("directory")
        
        try:
            composer = self._get_composer()
            
            # Get components directory
            project_root = Path(__file__).parent.parent.parent.parent.parent
            components_dir = project_root / "prompts" / "components"
            
            if directory:
                # List specific subdirectory
                target_dir = components_dir / directory
                if not target_dir.exists():
                    return {
                        "error": {
                            "code": "DIRECTORY_NOT_FOUND",
                            "message": f"Component directory not found: {directory}"
                        }
                    }
            else:
                target_dir = components_dir
            
            # Collect all markdown files
            items = []
            for path in target_dir.rglob("*.md"):
                rel_path = path.relative_to(components_dir)
                
                # Read component content
                content = path.read_text()
                lines = content.strip().split('\n')
                
                # Extract first heading as description
                description = "No description"
                for line in lines:
                    if line.startswith('#') and not line.startswith('##'):
                        description = line.strip('#').strip()
                        break
                
                # Analyze component
                has_variables = '{{' in content and '}}' in content
                
                comp_info = {
                    'name': path.stem,
                    'path': str(rel_path),
                    'directory': str(rel_path.parent) if rel_path.parent != Path('.') else '',
                    'description': description,
                    'size_bytes': path.stat().st_size,
                    'line_count': len(lines),
                    'has_variables': has_variables
                }
                
                items.append(comp_info)
            
            # Sort by path
            items.sort(key=lambda x: x['path'])
            
            # Build directory tree for metadata
            directories = set()
            for item in items:
                if item['directory']:
                    parts = Path(item['directory']).parts
                    for i in range(len(parts)):
                        directories.add('/'.join(parts[:i+1]))
            
            metadata = {
                'total_components': len(items),
                'directories': sorted(list(directories)),
                'search_directory': directory or 'components'
            }
            
            return {
                'items': items,
                'total': len(items),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error listing components: {e}")
            return {
                "error": {
                    "code": "LIST_FAILED",
                    "message": f"Failed to list components: {str(e)}"
                }
            }
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value matches expected type."""
        if expected_type == 'any':
            return True
        elif expected_type == 'string':
            return isinstance(value, str)
        elif expected_type == 'number':
            return isinstance(value, (int, float))
        elif expected_type == 'boolean':
            return isinstance(value, bool)
        elif expected_type == 'object':
            return isinstance(value, dict)
        elif expected_type == 'array':
            return isinstance(value, list)
        else:
            return True  # Unknown type, allow it
    
    @hookimpl
    def ksi_shutdown(self):
        """Clean up on shutdown."""
        return {"status": "prompts_service_stopped"}


# Plugin instance
plugin = PromptsServicePlugin()

# Module-level hooks that delegate to plugin instance
@hookimpl
def ksi_startup(config):
    """Initialize prompts service on startup."""
    return plugin.ksi_startup()

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle prompts-related events."""
    return plugin.ksi_handle_event(event_name, data, context)

@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    return plugin.ksi_shutdown()

# Module-level marker for plugin discovery
ksi_plugin = True