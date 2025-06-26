"""Shared configuration management using pydantic-settings.

Provides centralized configuration with environment variable support
for all KSI components. This ensures consistent configuration across
the daemon, clients, and interfaces.

Environment Variables:
    KSI_SOCKET_PATH - Unix socket path (default: var/run/daemon.sock)
    KSI_LOG_LEVEL - Logging level (default: INFO)
    KSI_LOG_FORMAT - Log format: json or console (default: console)
    KSI_LOG_DIR - Log directory (default: var/logs)  
    KSI_SESSION_LOG_DIR - Session logs directory (default: var/logs/sessions)
    KSI_STATE_DIR - State directory (default: var/state)
    KSI_SOCKET_TIMEOUT - Socket timeout in seconds (default: 5.0)
    KSI_DEBUG - Enable debug mode (default: false)

Example:
    export KSI_SOCKET_PATH=/custom/daemon.sock
    export KSI_LOG_LEVEL=DEBUG
    python3 chat.py
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, Literal
import logging

from .paths import KSIPaths


class KSIBaseConfig(BaseSettings):
    """Base configuration shared by all KSI components.
    
    This provides the minimal configuration needed by all components.
    The daemon can extend this with additional settings.
    
    All paths are relative by default and resolved at runtime.
    """
    
    # Core paths - matching ksi_daemon patterns
    socket_path: Path = Path("var/run/daemon.sock")
    
    # Logging configuration
    log_dir: Path = Path("var/logs")
    session_log_dir: Path = Path("var/logs/sessions")
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    
    # State and data
    state_dir: Path = Path("var/state")
    
    # Network settings
    socket_timeout: float = 5.0
    
    # Debug mode
    debug: bool = False
    
    # Model configuration - same as ksi_daemon
    model_config = {
        "env_prefix": "KSI_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore unknown environment variables
    }
    
    def ensure_directories(self) -> None:
        """Ensure critical directories exist."""
        directories = [
            self.socket_path.parent,  # var/run
            self.log_dir,            # var/logs
            self.session_log_dir,    # var/logs/sessions
            self.state_dir,          # var/state
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_log_level(self) -> int:
        """Convert log level string to logging constant."""
        return getattr(logging, self.log_level.upper(), logging.INFO)
    
    @property
    def paths(self) -> KSIPaths:
        """Get KSIPaths instance for additional path resolution.
        
        This provides backward compatibility and additional paths
        not directly configured.
        """
        # Infer base_dir from our paths
        base_dir = Path.cwd()
        if self.socket_path.parts[0] == "var":
            # We're using relative paths from cwd
            base_dir = Path.cwd()
        elif self.socket_path.is_absolute():
            # Find common base from absolute paths
            base_dir = self.socket_path.parent.parent
        
        return KSIPaths(base_dir=base_dir)
    
    @property
    def claude_logs_dir(self) -> Path:
        """Alias for session_log_dir for backward compatibility."""
        return self.session_log_dir
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return (
            f"KSIConfig(socket={self.socket_path}, "
            f"log_level={self.log_level})"
        )


# Global configuration instance
# This will be imported throughout KSI components
config = KSIBaseConfig()

# Convenience functions for common operations
def get_config() -> KSIBaseConfig:
    """Get the global configuration instance."""
    return config

def reload_config() -> KSIBaseConfig:
    """Reload configuration from environment and files."""
    global config
    config = KSIBaseConfig()
    return config