#!/usr/bin/env python3
"""
Utilities - Refactored with strategy pattern and better abstractions
Cleanup and module management with reduced if/elif chains
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Optional, Callable
from .base_manager import BaseManager, CleanupStrategy, FileCleanupStrategy, with_error_handling, log_operation


class SessionCleanupStrategy(CleanupStrategy):
    """Strategy for cleaning up sessions"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def cleanup(self, context: Dict[str, any]) -> str:
        if self.state_manager:
            sessions_cleared = self.state_manager.clear_sessions()
            return f"Cleared {sessions_cleared} tracked sessions"
        return "No state manager available"


class CompositeCleanupStrategy(CleanupStrategy):
    """Strategy for cleaning up everything"""
    
    def __init__(self, strategies: Dict[str, CleanupStrategy]):
        self.strategies = strategies
    
    def cleanup(self, context: Dict[str, any]) -> str:
        results = []
        for name, strategy in self.strategies.items():
            if name != 'all':  # Avoid recursion
                results.append(strategy.cleanup(context))
        return f"Complete cleanup: {'; '.join(results)}"


class UtilsManager(BaseManager):
    """Manages cleanup operations and module loading with improved patterns"""
    
    def __init__(self, state_manager=None):
        self.state_manager = state_manager
        self.modules_dir = Path("claude_modules")
        self.loaded_module = None
        
        # Initialize cleanup strategies
        self._init_cleanup_strategies()
        
        super().__init__(
            manager_name="utils",
            required_dirs=["claude_logs", "sockets", "claude_modules"]
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.logger.info("UtilsManager initialized")
    
    def _init_cleanup_strategies(self):
        """Initialize cleanup strategies to replace if/elif chain"""
        self.cleanup_strategies: Dict[str, CleanupStrategy] = {
            'logs': FileCleanupStrategy(
                directory='claude_logs',
                pattern='*.jsonl',
                exclude=['latest.jsonl']
            ),
            'sessions': SessionCleanupStrategy(self.state_manager),
            'sockets': FileCleanupStrategy(
                directory='sockets',
                pattern='*',
                exclude=['claude_daemon.sock']
            ),
        }
        
        # Add composite strategy for 'all'
        self.cleanup_strategies['all'] = CompositeCleanupStrategy(self.cleanup_strategies)
    
    @log_operation()
    @with_error_handling("cleanup")
    def cleanup(self, cleanup_type: str) -> str:
        """Cleanup various daemon resources using strategy pattern"""
        strategy = self.cleanup_strategies.get(cleanup_type)
        
        if not strategy:
            return f"Unknown cleanup type: {cleanup_type}. Use: {', '.join(self.cleanup_strategies.keys())}"
        
        return strategy.cleanup({})
    
    @log_operation()
    @with_error_handling("reload_module")
    def reload_module(self, module_name: str = 'handler'):
        """Reload a module from claude_modules/"""
        module_path = self.modules_dir / f"{module_name}.py"
        if not module_path.exists():
            self.logger.info(f"No module at {module_path}")
            return
        
        spec = importlib.util.spec_from_file_location(
            f"claude_modules.{module_name}",
            module_path
        )
        
        if spec and spec.loader:
            if self.loaded_module:
                # Reload existing
                importlib.reload(self.loaded_module)
            else:
                # Load new
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"claude_modules.{module_name}"] = module
                spec.loader.exec_module(module)
                self.loaded_module = module
            
            self.logger.info(f"Loaded module: {module_name}")
    
    def get_loaded_module(self):
        """Get the currently loaded module for cognitive observer calls"""
        return self.loaded_module
    
    def serialize_state(self) -> Dict[str, any]:
        """Serialize manager state for hot reload"""
        return {
            'loaded_module_name': self.loaded_module.__name__ if self.loaded_module else None
        }
    
    def deserialize_state(self, state: Dict[str, any]):
        """Deserialize manager state from hot reload"""
        module_name = state.get('loaded_module_name')
        if module_name:
            # Extract just the module name from full path
            module_name = module_name.split('.')[-1]
            self.reload_module(module_name)