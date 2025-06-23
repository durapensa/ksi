#!/usr/bin/env python3
"""
KSI Daemon Configuration Management

Centralized configuration using pydantic-settings with environment variable overrides.
Provides type-safe configuration management for all daemon components.

Environment Variables:
    KSI_SOCKET_PATH - Unix socket path (default: var/run/ksi_daemon.sock)
    KSI_PID_FILE - Process ID file path (default: var/run/ksi_daemon.pid)
    KSI_DB_PATH - SQLite database path (default: var/db/agent_shared_state.db)
    KSI_LOG_DIR - Log directory (default: var/logs/daemon)
    KSI_LOG_LEVEL - Logging level (default: INFO)
    KSI_SOCKET_TIMEOUT - Socket timeout in seconds (default: 5.0)
    KSI_SESSION_LOG_DIR - Session logs directory (default: var/logs/sessions)
    KSI_IDENTITY_STORAGE_PATH - Identity storage path (default: var/db/identities.json)
    KSI_TMP_DIR - Temporary files directory (default: var/tmp)

Example:
    export KSI_SOCKET_PATH=/custom/ksi_daemon.sock
    export KSI_LOG_LEVEL=DEBUG
    python daemon.py
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional
import logging

class KSIConfig(BaseSettings):
    """
    KSI Daemon Configuration with environment variable overrides.
    
    All settings can be overridden with KSI_ prefixed environment variables.
    For example: KSI_SOCKET_PATH, KSI_DB_PATH, KSI_LOG_LEVEL
    """
    
    # Core daemon paths
    socket_path: Path = Path("var/run/ksi_daemon.sock")
    pid_file: Path = Path("var/run/ksi_daemon.pid")
    
    # Database and storage
    db_path: Path = Path("var/db/agent_shared_state.db")
    identity_storage_path: Path = Path("var/db/identities.json")
    
    # Logging configuration
    log_dir: Path = Path("var/logs/daemon")
    session_log_dir: Path = Path("var/logs/sessions")
    log_level: str = "INFO"
    
    # Temporary files
    tmp_dir: Path = Path("var/tmp")
    
    # Network settings
    socket_timeout: float = 5.0
    
    # Optional hot reload socket
    hot_reload_socket: Optional[Path] = None
    
    model_config = {
        "env_prefix": "KSI_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore unknown environment variables
    }
    
    def ensure_directories(self) -> None:
        """Ensure all configured directories exist."""
        directories = [
            self.socket_path.parent,     # var/run
            self.pid_file.parent,        # var/run  
            self.db_path.parent,         # var/db
            self.identity_storage_path.parent,  # var/db
            self.log_dir,                # var/logs/daemon
            self.session_log_dir,        # var/logs/sessions
            self.tmp_dir                 # var/tmp
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_log_level(self) -> int:
        """Convert log level string to logging constant."""
        return getattr(logging, self.log_level.upper(), logging.INFO)
    
    def get_log_file_path(self) -> Path:
        """Get the daemon log file path."""
        return self.log_dir / "daemon.log"
    
    def __str__(self) -> str:
        """String representation showing key configuration values."""
        return (
            f"KSIConfig(socket={self.socket_path}, "
            f"db={self.db_path}, "
            f"log_level={self.log_level})"
        )

# Global configuration instance
# This will be imported throughout the daemon components
config = KSIConfig()

# Convenience functions for common operations
def get_config() -> KSIConfig:
    """Get the global configuration instance."""
    return config

def reload_config() -> KSIConfig:
    """Reload configuration from environment and files."""
    global config
    config = KSIConfig()
    return config