#!/usr/bin/env python3
"""
Plugin Loader for KSI Daemon

Handles plugin discovery, loading, and lifecycle management.
Uses pluggy for the underlying plugin system.
"""

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import pluggy

from .hookspecs import hookspec
from .plugin_types import PluginInfo, KSIPlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Manages plugin discovery and loading for KSI daemon.
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
        
        # Track loaded plugins
        self.loaded_plugins: Dict[str, PluginInfo] = {}
        self.plugin_instances: Dict[str, Any] = {}
        
        # Plugin namespaces
        self.namespaces: Dict[str, str] = {}  # namespace -> plugin_name
    
    def _add_default_plugin_dirs(self):
        """Add default plugin directories."""
        # Built-in plugins
        builtin_dir = Path(__file__).parent / "plugins"
        if builtin_dir.exists():
            self.plugin_dirs.append(builtin_dir)
        
        # User plugins directory
        user_plugins = Path.home() / ".ksi" / "plugins"
        if user_plugins.exists():
            self.plugin_dirs.append(user_plugins)
        
        # Current directory plugins
        local_plugins = Path.cwd() / "ksi_plugins"
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
        
        # Also check for installed packages with ksi_ prefix
        for module_info in self._discover_installed_plugins():
            plugin_files.append(Path(module_info.origin))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for pf in plugin_files:
            if pf not in seen:
                seen.add(pf)
                unique_files.append(pf)
        
        return unique_files
    
    def _discover_installed_plugins(self) -> List[Any]:
        """Discover plugins installed as packages."""
        discovered = []
        
        # Look for packages with ksi_plugin_ prefix using importlib.metadata
        try:
            import importlib.metadata
            for dist in importlib.metadata.distributions():
                for ep in (dist.entry_points or []):
                    if ep.group == "ksi.plugins":
                        try:
                            module = ep.load()
                            if hasattr(module, "__file__"):
                                spec = importlib.util.find_spec(ep.module)
                                if spec and spec.origin:
                                    discovered.append(spec)
                        except Exception as e:
                            logger.warning(f"Failed to load entry point {ep.name}: {e}")
        except Exception as e:
            # If importlib.metadata fails, just skip installed plugins
            logger.debug(f"Could not discover installed plugins: {e}")
        
        return discovered
    
    def load_plugin(self, plugin_path: Path) -> Optional[str]:
        """
        Load a single plugin from file.
        
        Args:
            plugin_path: Path to plugin file
            
        Returns:
            Plugin name if successful, None otherwise
        """
        try:
            # Find the ksi_daemon directory to build proper module path
            ksi_daemon_dir = plugin_path.parent
            while ksi_daemon_dir.name != "ksi_daemon" and ksi_daemon_dir.parent != ksi_daemon_dir:
                ksi_daemon_dir = ksi_daemon_dir.parent
            
            # Build proper module name maintaining package hierarchy
            if ksi_daemon_dir.name == "ksi_daemon":
                # Get relative path from ksi_daemon
                rel_path = plugin_path.relative_to(ksi_daemon_dir.parent)
                # Convert path to module name (e.g., ksi_daemon.plugins.transport.unix_socket)
                module_parts = list(rel_path.parts[:-1]) + [plugin_path.stem]
                module_name = ".".join(module_parts)
                
                # Add parent of ksi_daemon to path
                parent_dir = ksi_daemon_dir.parent
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
            else:
                # Fallback to simple name
                module_name = f"ksi_plugin_{plugin_path.stem}"
            
            # Ensure parent modules exist in sys.modules for relative imports
            if "." in module_name:
                parts = module_name.split(".")
                for i in range(1, len(parts)):
                    parent_name = ".".join(parts[:i])
                    if parent_name not in sys.modules:
                        # Import parent module
                        try:
                            parent_module = importlib.import_module(parent_name)
                            sys.modules[parent_name] = parent_module
                        except ImportError:
                            # Create empty parent module if it doesn't exist
                            parent_module = type(sys)('module')
                            parent_module.__path__ = []
                            sys.modules[parent_name] = parent_module
            
            # Load module with proper package context
            spec = importlib.util.spec_from_file_location(module_name, plugin_path, submodule_search_locations=[])
            if not spec or not spec.loader:
                logger.error(f"Failed to create spec for {plugin_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            # Set __package__ for relative imports to work
            if "." in module_name:
                module.__package__ = ".".join(module_name.split(".")[:-1])
            else:
                module.__package__ = module_name
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find plugin class or instance
            plugin_instance = None
            plugin_info = None
            
            # First check if module has ksi_plugin marker
            if hasattr(module, "ksi_plugin") and module.ksi_plugin:
                logger.debug(f"Found ksi_plugin marker in {plugin_path}")
                plugin_instance = module
                # Try to get plugin info
                if hasattr(module, "PLUGIN_INFO"):
                    info = module.PLUGIN_INFO
                    # Handle both dict and PluginInfo object
                    if isinstance(info, dict):
                        plugin_info = PluginInfo(**info)
                    else:
                        plugin_info = info
            
            if not plugin_instance:
                for name, obj in inspect.getmembers(module):
                    # Check if it's a KSIPlugin subclass
                    if (inspect.isclass(obj) and 
                        hasattr(sys.modules[__name__], 'KSIPlugin') and
                        issubclass(obj, KSIPlugin) and 
                        obj is not KSIPlugin):
                        plugin_instance = obj()
                        plugin_info = plugin_instance.info
                        break
                    
                    # Check for plugin info attribute
                    if name == "plugin_info" and isinstance(obj, PluginInfo):
                        plugin_info = obj
                    
                    # Check for explicit plugin instance named "plugin"
                    if name == "plugin":
                        # Check if it's a plugin instance (has methods with hookimpl)
                        has_hook_methods = any(
                            hasattr(getattr(obj, method_name, None), "_hookimpl")
                            for method_name in dir(obj)
                            if not method_name.startswith("_")
                        )
                        
                        # Or if it's a KSIPlugin instance
                        is_plugin_instance = (
                            hasattr(obj, "info") or 
                            hasattr(obj, "_info") or
                            has_hook_methods
                        )
                        
                        if is_plugin_instance:
                            logger.info(f"Found plugin instance: {name} in {module_name}")
                            plugin_instance = obj
                            if hasattr(obj, "info"):
                                plugin_info = obj.info
                            elif hasattr(obj, "_info"):
                                plugin_info = obj._info
                            elif hasattr(obj, "PLUGIN_INFO"):
                                plugin_info = obj.PLUGIN_INFO
            
            # If no plugin class found, use module itself if it has hooks
            if not plugin_instance:
                has_hooks = any(
                    hasattr(getattr(module, name), "_hookimpl")
                    for name in dir(module)
                    if not name.startswith("_")
                )
                logger.info(f"Module {module_name} has hooks: {has_hooks}")
                if has_hooks:
                    logger.info(f"Using module as plugin instance for {module_name}")
                    plugin_instance = module
                    # Try to get plugin info from module
                    if hasattr(module, "PLUGIN_INFO"):
                        info = module.PLUGIN_INFO
                        # Handle both dict and PluginInfo object
                        if isinstance(info, dict):
                            plugin_info = PluginInfo(**info)
                        else:
                            plugin_info = info
                    else:
                        # Create default info
                        plugin_info = PluginInfo(
                            name=module_name,
                            version="1.0.0",
                            description=module.__doc__ or "No description"
                        )
            
            if not plugin_instance:
                logger.warning(f"No plugin found in {plugin_path}")
                return None
            
            # Register plugin
            plugin_name = plugin_info.name if plugin_info else module_name
            self.pm.register(plugin_instance, name=plugin_name)
            
            # Store plugin info
            if plugin_info:
                self.loaded_plugins[plugin_name] = plugin_info
                self.plugin_instances[plugin_name] = plugin_instance
                
                # Register namespaces
                for namespace in plugin_info.namespaces:
                    if namespace in self.namespaces:
                        logger.warning(
                            f"Namespace {namespace} already registered by "
                            f"{self.namespaces[namespace]}, overriding with {plugin_name}"
                        )
                    self.namespaces[namespace] = plugin_name
            
            # Call plugin loaded hook
            self.pm.hook.ksi_plugin_loaded(
                plugin_name=plugin_name,
                plugin_instance=plugin_instance
            )
            
            logger.info(f"Loaded plugin: {plugin_name} from {plugin_path}")
            return plugin_name
            
        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}", exc_info=True)
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
        
        # Check dependencies
        self._check_dependencies()
        
        return loaded
    
    def _check_dependencies(self):
        """Check plugin dependencies are satisfied."""
        for plugin_name, plugin_info in self.loaded_plugins.items():
            for dep in plugin_info.dependencies:
                if dep not in self.loaded_plugins:
                    logger.warning(
                        f"Plugin {plugin_name} depends on {dep} which is not loaded"
                    )
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            plugin_name: Name of plugin to unload
            
        Returns:
            True if successful
        """
        if plugin_name not in self.loaded_plugins:
            return False
        
        try:
            # Get plugin instance
            plugin_instance = self.plugin_instances.get(plugin_name)
            if plugin_instance:
                # Call cleanup if available
                if hasattr(plugin_instance, "cleanup"):
                    import asyncio
                    if asyncio.iscoroutinefunction(plugin_instance.cleanup):
                        asyncio.create_task(plugin_instance.cleanup())
                    else:
                        plugin_instance.cleanup()
                
                # Unregister from pluggy
                self.pm.unregister(plugin_instance)
            
            # Remove from tracking
            del self.loaded_plugins[plugin_name]
            if plugin_name in self.plugin_instances:
                del self.plugin_instances[plugin_name]
            
            # Remove namespaces
            self.namespaces = {
                ns: pn for ns, pn in self.namespaces.items()
                if pn != plugin_name
            }
            
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin.
        
        Args:
            plugin_name: Name of plugin to reload
            
        Returns:
            True if successful
        """
        # Find plugin file
        plugin_file = None
        for path in self.discover_plugins():
            if path.stem == plugin_name or f"ksi_plugin_{path.stem}" == plugin_name:
                plugin_file = path
                break
        
        if not plugin_file:
            logger.error(f"Cannot find plugin file for {plugin_name}")
            return False
        
        # Unload then load
        self.unload_plugin(plugin_name)
        new_name = self.load_plugin(plugin_file)
        return new_name is not None
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get information about a loaded plugin."""
        return self.loaded_plugins.get(plugin_name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins."""
        return list(self.loaded_plugins.values())
    
    def get_namespace_owner(self, namespace: str) -> Optional[str]:
        """Get the plugin that owns a namespace."""
        return self.namespaces.get(namespace)
    
    def get_hooks(self) -> Dict[str, List[str]]:
        """
        Get all registered hooks and their implementers.
        
        Returns:
            Dict mapping hook names to list of plugin names
        """
        hooks = {}
        
        for name in dir(self.pm.hook):
            if name.startswith("ksi_"):
                hook = getattr(self.pm.hook, name)
                implementers = []
                
                for impl in hook.get_hookimpls():
                    plugin_name = impl.plugin_name
                    if plugin_name:
                        implementers.append(plugin_name)
                
                if implementers:
                    hooks[name] = implementers
        
        return hooks