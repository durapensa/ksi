#!/usr/bin/env python3
"""
Event-Based Plugin Loader for KSI

Discovers and loads plugins using the new pure event system.
Replaces SimplePluginLoader with event-driven patterns.
"""

import importlib
import importlib.util
import sys
import inspect
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from ksi_common.logging import get_bound_logger
from .event_system import EventRouter, event_handler

logger = get_bound_logger("plugin_loader_events", version="2.0.0")


class EventPluginLoader:
    """
    Plugin loader for the pure event system.
    """
    
    def __init__(self, router: EventRouter, plugin_dirs: Optional[List[Path]] = None):
        """
        Initialize plugin loader.
        
        Args:
            router: The event router instance
            plugin_dirs: List of directories to search for plugins
        """
        self.router = router
        self.plugin_dirs = plugin_dirs or []
        self._add_default_plugin_dirs()
        
        # Track loaded plugins
        self.loaded_plugins: Dict[str, Any] = {}
        
        # Track namespaces (for compatibility)
        self.namespaces: Dict[str, str] = {}
        
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
                    except (OSError, UnicodeDecodeError):
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
    
    async def load_plugin(self, plugin_path: Path) -> Optional[str]:
        """
        Load a single plugin file.
        
        Args:
            plugin_path: Path to plugin Python file
            
        Returns:
            Plugin name if successful, None otherwise
        """
        try:
            # Build module name from path
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
            
            # Import module
            module = importlib.import_module(module_name)
            logger.debug(f"Successfully imported module: {module_name}")
            
            # Check if module has ksi_plugin marker
            if not (hasattr(module, "ksi_plugin") and module.ksi_plugin):
                logger.debug(f"Module {module_name} is not a KSI plugin (no ksi_plugin marker)")
                return None
            
            # Register event handlers
            handlers_registered = 0
            services_registered = 0
            tasks_registered = 0
            
            for name, obj in inspect.getmembers(module):
                # Register event handlers
                if hasattr(obj, '_event_handler'):
                    handler = obj._event_handler
                    self.router.register_handler(handler.event, handler)
                    handlers_registered += 1
                    
                    # Track namespaces from event names
                    if ":" in handler.event:
                        namespace = handler.event.split(":")[0]
                        if namespace not in self.namespaces:
                            self.namespaces[namespace] = module_name
                
                # Register service providers
                if hasattr(obj, '_provides_service'):
                    service_name = obj._provides_service
                    # Call the provider to get service instance
                    if inspect.iscoroutinefunction(obj):
                        service = await obj()
                    else:
                        service = obj()
                    self.router.register_service(service_name, service)
                    services_registered += 1
                
                # Register background tasks
                if hasattr(obj, '_background_task'):
                    task_name = obj._background_task
                    # Tasks will be started later during system:ready
                    module._background_tasks = getattr(module, '_background_tasks', {})
                    module._background_tasks[task_name] = obj
                    tasks_registered += 1
            
            # Store loaded plugin
            self.loaded_plugins[module_name] = module
            
            # Emit plugin loaded event
            await self.router.emit("system:plugin_loaded", {
                "name": module_name,
                "handlers": handlers_registered,
                "services": services_registered,
                "tasks": tasks_registered
            })
            
            logger.info(f"Loaded plugin {module_name}: {handlers_registered} handlers, "
                       f"{services_registered} services, {tasks_registered} tasks")
            
            return module_name
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}", exc_info=True)
            return None
    
    async def load_all_plugins(self) -> List[str]:
        """
        Discover and load all plugins.
        
        Returns:
            List of loaded plugin names
        """
        loaded = []
        plugin_files = self.discover_plugins()
        
        logger.info(f"Discovered {len(plugin_files)} plugin files")
        
        for plugin_file in plugin_files:
            plugin_name = await self.load_plugin(plugin_file)
            if plugin_name:
                loaded.append(plugin_name)
        
        logger.info(f"Successfully loaded {len(loaded)} plugins")
        return loaded
    
    async def initialize_plugins(self, config: Dict[str, Any]):
        """Initialize all loaded plugins (replaces ksi_startup hook)."""
        # Emit startup event
        results = await self.router.emit("system:startup", config)
        
        # Log any startup issues
        for result in results:
            if isinstance(result, dict) and result.get("error"):
                logger.error(f"Plugin startup error: {result}")
    
    async def distribute_context(self, context: Dict[str, Any]):
        """Distribute runtime context to plugins (replaces ksi_plugin_context hook)."""
        await self.router.emit("system:context", context)
    
    async def start_plugin_tasks(self):
        """Start background tasks from all plugins (replaces ksi_ready hook)."""
        # Emit ready event to collect task specifications
        task_specs = await self.router.emit("system:ready", {})
        
        # Start collected tasks
        for spec_list in task_specs:
            if not isinstance(spec_list, dict):
                continue
                
            service_name = spec_list.get("service", "unknown")
            tasks = spec_list.get("tasks", [])
            
            for task in tasks:
                if isinstance(task, dict):
                    task_name = task.get("name", "unnamed")
                    coroutine = task.get("coroutine")
                    if coroutine and inspect.iscoroutine(coroutine):
                        full_name = f"{service_name}:{task_name}"
                        await self.router.start_task(full_name, lambda: coroutine)
                        
        # Also start any background tasks registered via decorator
        for module_name, module in self.loaded_plugins.items():
            if hasattr(module, '_background_tasks'):
                for task_name, task_func in module._background_tasks.items():
                    full_name = f"{module_name}:{task_name}"
                    await self.router.start_task(full_name, task_func)
    
    async def shutdown_plugins(self):
        """Shutdown all plugins cleanly (replaces ksi_shutdown hook)."""
        # Stop all background tasks first
        await self.router.stop_all_tasks()
        
        # Emit shutdown event
        await self.router.emit("system:shutdown", {})
        
    def get_namespace_owner(self, namespace: str) -> Optional[str]:
        """Get the plugin that owns a namespace."""
        return self.namespaces.get(namespace)
    
    # Compatibility properties
    @property
    def pm(self):
        """Compatibility: return self as plugin manager."""
        return self
    
    def get_plugins(self):
        """Compatibility: return loaded modules."""
        return list(self.loaded_plugins.values())