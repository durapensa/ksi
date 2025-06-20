#!/usr/bin/env python3

"""
Utilities - Cleanup and module management
Extracted from daemon_clean.py with 100% functionality preservation
"""

import importlib
import importlib.util
import sys
import os
from pathlib import Path
import logging

logger = logging.getLogger('daemon')

class UtilsManager:
    """Manages cleanup operations and module loading"""
    
    def __init__(self, state_manager=None):
        self.modules_dir = Path("claude_modules")
        self.loaded_module = None
        self.state_manager = state_manager
    
    def cleanup(self, cleanup_type: str) -> str:
        """Cleanup various daemon resources - EXACT copy from daemon_clean.py"""
        try:
            if cleanup_type == 'logs':
                # Clean up old log files
                logs_dir = Path('claude_logs')
                if logs_dir.exists():
                    files_removed = 0
                    for log_file in logs_dir.glob('*.jsonl'):
                        if log_file.name != 'latest.jsonl' and not log_file.is_symlink():
                            log_file.unlink()
                            files_removed += 1
                    
                    # Remove broken symlinks
                    latest_link = logs_dir / 'latest.jsonl'
                    if latest_link.is_symlink() and not latest_link.exists():
                        latest_link.unlink()
                    
                    return f"Removed {files_removed} log files"
                return "No logs directory found"
                
            elif cleanup_type == 'sessions':
                # Clear session tracking
                if self.state_manager:
                    sessions_cleared = self.state_manager.clear_sessions()
                    return f"Cleared {sessions_cleared} tracked sessions"
                else:
                    return "No state manager available"
                
            elif cleanup_type == 'sockets':
                # Clean up socket files
                sockets_dir = Path('sockets')
                if sockets_dir.exists():
                    files_removed = 0
                    for socket_file in sockets_dir.glob('*'):
                        if socket_file.name != 'claude_daemon.sock':  # Don't remove active daemon socket
                            socket_file.unlink()
                            files_removed += 1
                    return f"Removed {files_removed} socket files"
                return "No sockets directory found"
                
            elif cleanup_type == 'all':
                # Clean up everything
                results = []
                results.append(self.cleanup('logs'))
                results.append(self.cleanup('sessions'))
                results.append(self.cleanup('sockets'))
                return f"Complete cleanup: {'; '.join(results)}"
                
            else:
                return f"Unknown cleanup type: {cleanup_type}. Use: logs, sessions, sockets, or all"
                
        except Exception as e:
            return f"Cleanup failed: {type(e).__name__}: {str(e)}"
    
    def reload_module(self, module_name: str = 'handler'):
        """Reload a module from claude_modules/ - EXACT copy from daemon_clean.py"""
        try:
            module_path = self.modules_dir / f"{module_name}.py"
            if not module_path.exists():
                logger.info(f"No module at {module_path}")
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
                    
                logger.info(f"Loaded module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to load module: {e}")
    
    def get_loaded_module(self):
        """Get the currently loaded module for cognitive observer calls"""
        return self.loaded_module