#!/usr/bin/env python3
"""
Simplified Plugin Loader for KSI Daemon

A minimal wrapper around pluggy that follows community best practices.
Handles plugin discovery and loading without complex tracking or hot reload.
"""

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
import pluggy

# Import hookspecs to ensure it's available
from . import hookspecs

logger = logging.getLogger(__name__)



class SimplePluginLoader:
    """
    Minimal plugin loader using pure pluggy patterns.
    """
    
    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        """
        Initialize plugin loader.
        
        Args:
            plugin_dirs: List of directories to search for plugins
        """
        # Create plugin manager
        self.pm = pluggy.PluginManager("ksi")
        
        # Register hook specifications
        self.pm.add_hookspecs(sys.modules["ksi_daemon.hookspecs"])
        
        # Plugin directories
        self.plugin_dirs = plugin_dirs or []
        self._add_default_plugin_dirs()
        
        # Track namespaces for event routing (minimal tracking needed)
        self.namespaces = {}  # namespace -> plugin_name
        
        # Simple counter for statistics
        self.loaded_plugin_count = 0
        
    def _add_default_plugin_dirs(self):
        """Add default plugin directories."""
        # Built-in plugins
        daemon_dir = Path(__file__).parent
        builtin_plugins = daemon_dir / "plugins"
        if builtin_plugins.exists():
            self.plugin_dirs.append(builtin_plugins)
        
        # Local project plugins
        project_root = daemon_dir.parent
        local_plugins = project_root / "plugins"
        if local_plugins.exists():
            self.plugin_dirs.append(local_plugins)
    
    def discover_plugins(self) -> List[Path]:
        """
        Discover plugin files in plugin directories.
        
        Returns:
            List of plugin file paths
        """
        plugin_files = []
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            
            # Look for Python files
            for path in plugin_dir.rglob("*.py"):
                # Skip __pycache__
                if "__pycache__" in str(path):
                    continue
                
                # Skip __init__.py unless it contains plugin marker
                if path.name == "__init__.py":
                    try:
                        content = path.read_text()
                        if "ksi_plugin" not in content:
                            continue
                    except:
                        continue
                
                plugin_files.append(path)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for pf in plugin_files:
            if pf not in seen:
                seen.add(pf)
                unique_files.append(pf)
        
        return unique_files
    
    def _extract_namespaces(self, module, module_name: str):
        """Extract event namespaces from a plugin module."""
        # Look for ksi_handle_event implementation
        if hasattr(module, 'ksi_handle_event'):
            # Try to extract from source code (simple pattern matching)
            import inspect
            try:
                source = inspect.getsource(module.ksi_handle_event)
                # Look for patterns like: event_name == "namespace:..."
                import re
                pattern = r'event_name\s*==\s*["\'](\w+):'
                matches = re.findall(pattern, source)
                for namespace in set(matches):
                    if namespace not in self.namespaces:
                        self.namespaces[namespace] = module_name
                        logger.debug(f"Plugin {module_name} handles namespace: {namespace}")
            except:
                # If we can't inspect, that's OK - namespace tracking is for convenience
                pass
    
    def load_plugin(self, plugin_path: Path) -> Optional[str]:
        """
        Load a single plugin file.
        
        Args:
            plugin_path: Path to plugin Python file
            
        Returns:
            Plugin name if successful, None otherwise
        """
        try:
            # Build module name from path
            # Assumes we're loading from ksi_daemon/plugins structure
            ksi_daemon_dir = plugin_path.parent
            while ksi_daemon_dir.name != "ksi_daemon" and ksi_daemon_dir.parent != ksi_daemon_dir:
                ksi_daemon_dir = ksi_daemon_dir.parent
            
            if ksi_daemon_dir.name == "ksi_daemon":
                # Build module path like ksi_daemon.plugins.state.state_service
                rel_path = plugin_path.relative_to(ksi_daemon_dir.parent)
                module_parts = list(rel_path.parts[:-1]) + [plugin_path.stem]
                module_name = ".".join(module_parts)
            else:
                # Fallback - use simple name
                module_name = plugin_path.stem
            
            # Simple import using importlib
            module = importlib.import_module(module_name)
            logger.debug(f"Successfully imported module: {module_name}")
            
            # Check if module has ksi_plugin marker
            if hasattr(module, "ksi_plugin") and module.ksi_plugin:
                # Register the module itself (function-based plugins)
                self.pm.register(module, name=module_name)
                logger.info(f"Loaded plugin module: {module_name}")
                
                # Extract namespaces from event handlers
                # This is a simple heuristic - look for common event patterns
                self._extract_namespaces(module, module_name)
                
                return module_name
            else:
                logger.debug(f"Module {module_name} is not a KSI plugin (no ksi_plugin marker)")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")
            return None
    
    def load_all_plugins(self) -> List[str]:
        """
        Discover and load all plugins.
        
        Returns:
            List of loaded plugin names
        """
        loaded = []
        plugin_files = self.discover_plugins()
        
        logger.info(f"Discovered {len(plugin_files)} plugin files")
        
        for plugin_file in plugin_files:
            plugin_name = self.load_plugin(plugin_file)
            if plugin_name:
                loaded.append(plugin_name)
        
        logger.info(f"Successfully loaded {len(loaded)} plugins")
        self.loaded_plugin_count = len(loaded)
        return loaded
    
    def get_namespace_owner(self, namespace: str) -> Optional[str]:
        """Get the plugin that owns a namespace."""
        return self.namespaces.get(namespace)
    
    
    @property
    def loaded_plugins(self):
        """Compatibility property for event router statistics."""
        # Return a simple dict-like object with length
        return {"count": self.loaded_plugin_count}