#!/usr/bin/env python3
"""
KSI Daemon Configuration Management

Extends the base configuration from ksi_common with daemon-specific settings.
Provides type-safe configuration management for all daemon components.

This replaces the old config.py and shows the new pattern for extending
the shared base configuration.
"""

from pathlib import Path
from typing import Optional, List

from ksi_common import KSIBaseConfig


class KSIDaemonConfig(KSIBaseConfig):
    """
    Extended configuration for KSI daemon.
    
    Inherits all base settings and adds daemon-specific configuration.
    """
    
    # PID file (daemon-specific)
    pid_file: Path = Path("var/run/ksi_daemon.pid")
    
    # Database and storage (daemon-specific)
    db_path: Path = Path("var/db/agent_shared_state.db")
    identity_storage_path: Path = Path("var/db/identities.json")
    
    # Daemon-specific logging
    daemon_log_dir: Path = Path("var/logs/daemon")
    log_structured: bool = True
    
    # Temporary files
    tmp_dir: Path = Path("var/tmp")
    
    # Completion timeouts (in seconds)
    completion_timeout_default: int = 300  # 5 minutes default
    completion_timeout_min: int = 60       # 1 minute minimum
    completion_timeout_max: int = 1800     # 30 minutes maximum
    
    # Claude CLI progressive timeouts (in seconds)
    claude_timeout_attempts: List[int] = [300, 900, 1800]  # 5min, 15min, 30min
    claude_progress_timeout: int = 300     # 5 minutes without progress
    
    # Test timeouts (in seconds)
    test_completion_timeout: int = 120     # 2 minutes for tests
    
    # Optional hot reload socket
    hot_reload_socket: Optional[Path] = None
    
    def ensure_directories(self) -> None:
        """Ensure all daemon directories exist."""
        # First ensure base directories
        super().ensure_directories()
        
        # Then ensure daemon-specific directories
        daemon_dirs = [
            self.pid_file.parent,        # var/run
            self.db_path.parent,         # var/db
            self.identity_storage_path.parent,  # var/db
            self.daemon_log_dir,         # var/logs/daemon
            self.tmp_dir,                # var/tmp
        ]
        
        for directory in daemon_dirs:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_log_file_path(self) -> Path:
        """Get the daemon log file path."""
        return self.daemon_log_dir / "daemon.log"


# Global daemon configuration instance
config = KSIDaemonConfig()

# Re-export for compatibility
get_config = lambda: config
reload_config = lambda: globals().update({'config': KSIDaemonConfig()}) or config