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

from .component_loader import load_component_file, find_component_file, extract_metadata
from .json_utils import loads as json_loads, dumps as json_dumps
from .template_utils import substitute_variables
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
    dependencies: List[str] = field(default_factory=list)
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
            
            # Resolve mixins and dependencies
            resolved_mixins = self._resolve_mixins(context.frontmatter.get('mixins', []), merged_variables)
            resolved_dependencies = self._resolve_mixins(context.frontmatter.get('dependencies', []), merged_variables)
            
            # Apply conditional mixins
            conditional_mixins = self._evaluate_conditional_mixins(
                context.frontmatter.get('conditions', []), 
                merged_variables
            )
            
            # Merge all mixin and dependency content
            all_mixins = resolved_mixins + resolved_dependencies + conditional_mixins
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
        """Load component from disk using shared loader."""
        # Find the component file
        component_path = find_component_file(self.components_base, component_name)
        
        if not component_path:
            raise ComponentResolutionError(f"Component not found: {component_name}")
        
        try:
            # Load using shared loader
            metadata, content = load_component_file(component_path)
            
            # Normalize metadata
            frontmatter = extract_metadata(metadata, content)
            
            return ComponentContext(
                name=component_name,
                content=content,
                frontmatter=frontmatter,
                extends=frontmatter.get('extends'),
                mixins=frontmatter.get('mixins', []),
                dependencies=frontmatter.get('dependencies', []),
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
        # Merge content - combine both contents with proper separation
        # This ensures dependencies and mixins are properly combined, not replaced
        base_content = base.content.strip()
        override_content = override.content.strip()
        
        if base_content and override_content:
            # Both have content - combine them
            merged_content = f"{base_content}\n\n{override_content}"
        elif override_content:
            # Only override has content
            merged_content = override_content
        else:
            # Only base has content (or neither)
            merged_content = base_content
        
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
        # CRITICAL FIX: Use passed variables (which include runtime vars like agent_id)
        # not context.variables (which only has component-defined vars)
        # This ensures {{agent_id}} and other runtime variables are properly substituted
        final_variables = context.variables.copy()
        final_variables.update(variables)  # Runtime variables override component defaults
        content = self._substitute_variables(content, final_variables)
        
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
        return substitute_variables(content, variables)
    
    
    def _handle_special_placeholders(self, content: str, context: ComponentContext) -> str:
        """Handle special placeholders like {{base_content}}."""
        # Replace {{base_content}} with content from parent component
        if '{{base_content}}' in content:
            # This would be populated during mixin resolution
            # For now, remove the placeholder
            content = content.replace('{{base_content}}', '')
        
        return content
    
    def inspect(self, component_name: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Inspect a component and return its dependency tree.
        
        Args:
            component_name: Name of component to inspect
            variables: Variables for conditional dependency resolution
            
        Returns:
            Dictionary with component tree structure including:
            - name: Component name
            - type: Component type from frontmatter
            - version: Component version
            - description: Component description
            - capabilities: List of capabilities provided
            - dependencies: Direct dependencies
            - transitive_dependencies: All transitive dependencies
            - dependency_tree: Full tree structure
        """
        if variables is None:
            variables = {}
            
        try:
            # Clear tracking for new inspection
            self.render_stack = []
            self._inspection_seen = set()
            self._inspection_tree = {}
            
            # Build dependency tree
            tree = self._inspect_component(component_name, variables)
            
            # Collect all dependencies
            all_deps = self._collect_all_dependencies(tree)
            direct_deps = tree.get('dependencies', []) + tree.get('mixins', [])
            transitive_deps = [d for d in all_deps if d not in direct_deps and d != component_name]
            
            return {
                'name': component_name,
                'type': tree.get('type', 'unknown'),
                'version': tree.get('version', '0.0.0'),
                'description': tree.get('description', ''),
                'capabilities': tree.get('capabilities', []),
                'dependencies': direct_deps,
                'transitive_dependencies': sorted(transitive_deps),
                'dependency_tree': tree
            }
            
        except Exception as e:
            logger.error(f"Component inspection failed for {component_name}: {e}")
            raise ComponentResolutionError(f"Failed to inspect component {component_name}: {e}") from e
    
    def _inspect_component(self, component_name: str, variables: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """Recursively inspect component and build dependency tree."""
        # Avoid infinite recursion
        if component_name in self._inspection_seen:
            return {
                'name': component_name,
                'circular_reference': True
            }
        
        self._inspection_seen.add(component_name)
        
        try:
            # Load component
            context = self._load_component(component_name)
            
            # Build tree node
            node = {
                'name': component_name,
                'type': context.frontmatter.get('component_type', context.frontmatter.get('type', 'unknown')),
                'version': context.frontmatter.get('version', '0.0.0'),
                'description': context.frontmatter.get('description', ''),
                'capabilities': context.frontmatter.get('capabilities', []),
                'dependencies': [],
                'mixins': []
            }
            
            # Process dependencies
            dependencies = context.frontmatter.get('dependencies', [])
            for dep in dependencies:
                dep_name = self._substitute_variables(dep, variables)
                if depth < 10:  # Prevent excessive depth
                    dep_tree = self._inspect_component(dep_name, variables, depth + 1)
                    node['dependencies'].append(dep_tree)
                else:
                    node['dependencies'].append({'name': dep_name, 'max_depth_reached': True})
            
            # Process mixins
            mixins = context.frontmatter.get('mixins', [])
            for mixin in mixins:
                mixin_name = self._substitute_variables(mixin, variables)
                if depth < 10:
                    mixin_tree = self._inspect_component(mixin_name, variables, depth + 1)
                    node['mixins'].append(mixin_tree)
                else:
                    node['mixins'].append({'name': mixin_name, 'max_depth_reached': True})
            
            return node
            
        except Exception as e:
            return {
                'name': component_name,
                'error': str(e)
            }
    
    def _collect_all_dependencies(self, tree: Dict[str, Any], collected: Optional[Set[str]] = None) -> List[str]:
        """Collect all unique dependencies from tree."""
        if collected is None:
            collected = set()
        
        # Add current component
        if not tree.get('circular_reference') and not tree.get('error'):
            collected.add(tree['name'])
        
        # Recursively collect from dependencies
        for dep in tree.get('dependencies', []):
            if isinstance(dep, dict):
                self._collect_all_dependencies(dep, collected)
            else:
                collected.add(dep)
        
        # Recursively collect from mixins
        for mixin in tree.get('mixins', []):
            if isinstance(mixin, dict):
                self._collect_all_dependencies(mixin, collected)
            else:
                collected.add(mixin)
        
        return list(collected)
    
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
            components_base_path = config.compositions_dir
        _default_renderer = ComponentRenderer(components_base_path)
    
    return _default_renderer

def render_component(component_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to render a component."""
    renderer = get_renderer()
    return renderer.render(component_name, variables)