#!/usr/bin/env python3

"""
Component Renderer - Progressive Component System Phase 3
Handles recursive mixin resolution, variable substitution, and conditional logic
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union, Tuple
from dataclasses import dataclass, field
import structlog

from .frontmatter_utils import parse_frontmatter, load_component_with_frontmatter
from .yaml_utils import safe_load
from .json_utils import loads as json_loads, dumps as json_dumps
from .timestamps import sanitize_for_json
import hashlib
import json

logger = structlog.get_logger("component_renderer")


@dataclass
class ComponentContext:
    """Context for component rendering with dependency tracking."""
    name: str
    content: str
    frontmatter: Dict[str, Any]
    variables: Dict[str, Any] = field(default_factory=dict)
    mixins: List[str] = field(default_factory=list)
    extends: Optional[str] = None
    conditions: List[Dict[str, Any]] = field(default_factory=list)


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in component resolution."""
    pass


class ComponentResolutionError(Exception):
    """Raised when component resolution fails."""
    pass


class ComponentRenderer:
    """
    Advanced component renderer with recursive mixin resolution and variable substitution.
    
    Features:
    - Recursive mixin loading and merging
    - Variable substitution with default values
    - Circular dependency detection
    - Conditional mixin application
    - Component caching for performance
    """
    
    def __init__(self, components_base_path: Union[str, Path]):
        """Initialize renderer with components base path."""
        self.components_base = Path(components_base_path)
        self.cache: Dict[str, ComponentContext] = {}
        self.render_stack: List[str] = []
        
    def _hash_variables(self, variables: Dict[str, Any]) -> str:
        """Create a stable hash for complex variable structures."""
        # Convert to JSON string for stable hashing
        json_str = json.dumps(variables, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
        
    def render(self, component_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Render a component with full mixin resolution and variable substitution.
        
        Args:
            component_name: Name of component to render
            variables: Variables for substitution
            
        Returns:
            Fully rendered component content
            
        Raises:
            CircularDependencyError: If circular dependencies detected
            ComponentResolutionError: If component resolution fails
        """
        if variables is None:
            variables = {}
            
        try:
            # Clear render stack for new rendering session
            self.render_stack = []
            
            # Load and resolve component
            context = self._load_component_with_resolution(component_name, variables)
            
            # Render final content
            return self._render_final_content(context, variables)
            
        except Exception as e:
            logger.error(f"Component rendering failed for {component_name}: {e}")
            raise ComponentResolutionError(f"Failed to render component {component_name}: {e}") from e
    
    def _load_component_with_resolution(self, component_name: str, variables: Dict[str, Any]) -> ComponentContext:
        """Load component and resolve all mixins recursively."""
        # Check for circular dependencies
        if component_name in self.render_stack:
            cycle = " -> ".join(self.render_stack + [component_name])
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")
        
        # Check cache first
        cache_key = f"{component_name}#{self._hash_variables(variables)}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Add to render stack
        self.render_stack.append(component_name)
        
        try:
            # Load base component
            context = self._load_component(component_name)
            
            # Merge component variables with provided variables
            merged_variables = self._merge_variables(context.frontmatter.get('variables', {}), variables)
            context.variables = merged_variables
            
            # Resolve extends chain first
            if context.extends:
                parent_context = self._load_component_with_resolution(context.extends, merged_variables)
                context = self._merge_contexts(parent_context, context)
            
            # Resolve mixins
            resolved_mixins = self._resolve_mixins(context.frontmatter.get('mixins', []), merged_variables)
            
            # Apply conditional mixins
            conditional_mixins = self._evaluate_conditional_mixins(
                context.frontmatter.get('conditions', []), 
                merged_variables
            )
            
            # Merge all mixin content
            all_mixins = resolved_mixins + conditional_mixins
            for mixin_name in all_mixins:
                mixin_context = self._load_component_with_resolution(mixin_name, merged_variables)
                context = self._merge_contexts(context, mixin_context)
            
            # Cache resolved context
            self.cache[cache_key] = context
            return context
            
        finally:
            # Remove from render stack
            self.render_stack.pop()
    
    def _load_component(self, component_name: str) -> ComponentContext:
        """Load component from disk."""
        component_path = self.components_base / f"{component_name}.md"
        
        if not component_path.exists():
            raise ComponentResolutionError(f"Component not found: {component_name}")
        
        try:
            component_data = load_component_with_frontmatter(component_path)
            
            frontmatter = component_data.get('frontmatter') or {}
            
            return ComponentContext(
                name=component_name,
                content=component_data['content'],
                frontmatter=frontmatter,
                extends=frontmatter.get('extends'),
                mixins=frontmatter.get('mixins', []),
                conditions=frontmatter.get('conditions', [])
            )
            
        except Exception as e:
            raise ComponentResolutionError(f"Failed to load component {component_name}: {e}") from e
    
    def _merge_variables(self, component_vars: Dict[str, Any], provided_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Merge component variable definitions with provided values."""
        merged = {}
        
        # Process component variable definitions
        for var_name, var_def in component_vars.items():
            if isinstance(var_def, dict):
                # Full variable definition with type, default, etc.
                default_value = var_def.get('default')
                if var_name in provided_vars:
                    merged[var_name] = provided_vars[var_name]
                elif default_value is not None:
                    merged[var_name] = default_value
                else:
                    merged[var_name] = ""  # Fallback for undefined variables
            else:
                # Simple variable definition
                merged[var_name] = var_def
        
        # Add any provided variables not defined in component
        for var_name, var_value in provided_vars.items():
            if var_name not in merged:
                merged[var_name] = var_value
        
        return merged
    
    def _resolve_mixins(self, mixins: List[str], variables: Dict[str, Any]) -> List[str]:
        """Resolve mixin names, applying variable substitution."""
        resolved = []
        
        for mixin in mixins:
            # Apply variable substitution to mixin name
            resolved_mixin = self._substitute_variables(mixin, variables)
            resolved.append(resolved_mixin)
            
        return resolved
    
    def _evaluate_conditional_mixins(self, conditions: List[Dict[str, Any]], variables: Dict[str, Any]) -> List[str]:
        """Evaluate conditional mixins based on variables."""
        conditional_mixins = []
        
        for condition in conditions:
            condition_expr = condition.get('condition', '')
            mixins = condition.get('mixins', [])
            
            if self._evaluate_condition(condition_expr, variables):
                conditional_mixins.extend(mixins)
        
        return conditional_mixins
    
    def _evaluate_condition(self, condition_expr: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a condition expression safely."""
        if not condition_expr:
            return False
        
        try:
            # Simple condition evaluation for common patterns
            # Support: var == 'value', var != 'value', var in ['a', 'b']
            
            # Replace variables in condition
            for var_name, var_value in variables.items():
                if isinstance(var_value, str):
                    condition_expr = condition_expr.replace(var_name, f"'{var_value}'")
                else:
                    condition_expr = condition_expr.replace(var_name, str(var_value))
            
            # Evaluate safely (limited subset of Python expressions)
            allowed_names = {"True": True, "False": False, "None": None}
            return eval(condition_expr, {"__builtins__": {}}, allowed_names)
            
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition_expr}': {e}")
            return False
    
    def _merge_contexts(self, base: ComponentContext, override: ComponentContext) -> ComponentContext:
        """Merge two component contexts, with override taking precedence."""
        # Merge content (override content takes precedence)
        merged_content = override.content if override.content.strip() else base.content
        
        # Merge frontmatter
        merged_frontmatter = base.frontmatter.copy()
        merged_frontmatter.update(override.frontmatter)
        
        # Merge variables
        merged_variables = base.variables.copy()
        merged_variables.update(override.variables)
        
        # Combine mixins
        merged_mixins = base.mixins + override.mixins
        
        # Combine conditions
        merged_conditions = base.conditions + override.conditions
        
        return ComponentContext(
            name=override.name,
            content=merged_content,
            frontmatter=merged_frontmatter,
            variables=merged_variables,
            mixins=merged_mixins,
            extends=override.extends or base.extends,
            conditions=merged_conditions
        )
    
    def _render_final_content(self, context: ComponentContext, variables: Dict[str, Any]) -> str:
        """Render final content with variable substitution."""
        content = context.content
        
        # Apply variable substitution
        content = self._substitute_variables(content, context.variables)
        
        # Handle special placeholders
        content = self._handle_special_placeholders(content, context)
        
        return content
    
    def _substitute_variables(self, content: str, variables: Dict[str, Any]) -> str:
        """
        Apply variable substitution with support for:
        - {{variable}} - basic substitution
        - {{variable|default}} - with default value
        - {{variable.key}} - nested access
        """
        def replace_var(match):
            var_expr = match.group(1)
            
            # Handle default values
            if '|' in var_expr:
                var_name, default_value = var_expr.split('|', 1)
                var_name = var_name.strip()
                default_value = default_value.strip()
            else:
                var_name = var_expr.strip()
                default_value = ""
            
            # Handle nested variables (e.g., user.name)
            if '.' in var_name:
                value = self._get_nested_value(variables, var_name)
            else:
                value = variables.get(var_name, default_value)
            
            # Convert complex types to appropriate string representation
            if isinstance(value, (dict, list)):
                return json_dumps(value)
            elif value is None:
                return default_value
            else:
                return str(value)
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, content)
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _handle_special_placeholders(self, content: str, context: ComponentContext) -> str:
        """Handle special placeholders like {{base_content}}."""
        # Replace {{base_content}} with content from parent component
        if '{{base_content}}' in content:
            # This would be populated during mixin resolution
            # For now, remove the placeholder
            content = content.replace('{{base_content}}', '')
        
        return content
    
    def clear_cache(self):
        """Clear the component cache."""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cached_components': len(self.cache),
            'cache_keys': list(self.cache.keys())
        }


# Global renderer instance
_default_renderer = None

def get_renderer(components_base_path: Union[str, Path] = None) -> ComponentRenderer:
    """Get default component renderer instance."""
    global _default_renderer
    
    if _default_renderer is None or components_base_path is not None:
        if components_base_path is None:
            from .config import config
            components_base_path = config.components_dir
        _default_renderer = ComponentRenderer(components_base_path)
    
    return _default_renderer

def render_component(component_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to render a component."""
    renderer = get_renderer()
    return renderer.render(component_name, variables)