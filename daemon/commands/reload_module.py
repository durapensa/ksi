#!/usr/bin/env python3
"""
RELOAD_MODULE command handler - Manages dynamic module reloading
Handles loading and reloading of extension modules from extension_modules/ directory
"""

import asyncio
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, ReloadModuleParameters
from ..manager_framework import log_operation


@command_handler("RELOAD_MODULE")
class ReloadModuleHandler(CommandHandler):
    """Handles RELOAD_MODULE command for dynamic module reloading"""
    
    def __init__(self):
        super().__init__()
        self.modules_dir = Path('extension_modules')
        self.loaded_modules: Dict[str, Any] = {}
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute module reload"""
        # Validate parameters
        try:
            params = ReloadModuleParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("RELOAD_MODULE", "INVALID_PARAMETERS", str(e))
        
        # Reload the module
        result = self._reload_module(params.module_name)
        
        if result['success']:
            return SocketResponse.success("RELOAD_MODULE", {
                'status': 'reloaded',
                'module': params.module_name,
                'message': result['message']
            })
        else:
            return SocketResponse.error("RELOAD_MODULE", "RELOAD_FAILED", result['message'])
    
    def _reload_module(self, module_name: str) -> Dict[str, Any]:
        """Reload a module from extension_modules/"""
        module_path = self.modules_dir / f"{module_name}.py"
        
        if not module_path.exists():
            return {
                'success': False,
                'message': f"No module found at {module_path}"
            }
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"extension_modules.{module_name}",
                module_path
            )
            
            if spec and spec.loader:
                # Check if module already loaded
                existing_module = self.loaded_modules.get(module_name)
                full_module_name = f"extension_modules.{module_name}"
                
                if existing_module and full_module_name in sys.modules:
                    # Reload existing module
                    importlib.reload(sys.modules[full_module_name])
                    message = f"Reloaded existing module: {module_name}"
                else:
                    # Load new module
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[full_module_name] = module
                    spec.loader.exec_module(module)
                    self.loaded_modules[module_name] = module
                    message = f"Loaded new module: {module_name}"
                
                # Store reference for cognitive observer
                self.context.loaded_extension_module = sys.modules[full_module_name]
                
                return {
                    'success': True,
                    'message': message
                }
            else:
                return {
                    'success': False,
                    'message': f"Failed to create module spec for {module_name}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error reloading module: {str(e)}"
            }
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "RELOAD_MODULE",
            "description": "Reload an extension module from extension_modules/ directory",
            "parameters": {
                "module_name": {
                    "type": "string",
                    "description": "Name of module to reload (without .py extension)",
                    "default": "handler",
                    "optional": True
                }
            },
            "examples": [
                {"module_name": "handler"},
                {"module_name": "autonomous_researcher"},
                {}  # Uses default "handler"
            ],
            "notes": [
                "Modules are loaded from extension_modules/ directory",
                "If module is already loaded, it will be reloaded",
                "The loaded module is available for cognitive observer calls"
            ]
        }