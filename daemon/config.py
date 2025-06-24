#!/usr/bin/env python3
"""
KSI Daemon Configuration Management

Centralized configuration using pydantic-settings with environment variable overrides.
Provides type-safe configuration management for all daemon components.

Environment Variables:
    KSI_ADMIN_SOCKET - Admin socket path (default: sockets/admin.sock)
    KSI_AGENTS_SOCKET - Agents socket path (default: sockets/agents.sock)
    KSI_MESSAGING_SOCKET - Messaging socket path (default: sockets/messaging.sock)
    KSI_STATE_SOCKET - State socket path (default: sockets/state.sock)
    KSI_COMPLETION_SOCKET - Completion socket path (default: sockets/completion.sock)
    KSI_PID_FILE - Process ID file path (default: var/run/ksi_daemon.pid)
    KSI_DB_PATH - SQLite database path (default: var/db/agent_shared_state.db)
    KSI_LOG_DIR - Log directory (default: var/logs/daemon)
    KSI_LOG_LEVEL - Logging level (default: INFO)
    KSI_SOCKET_TIMEOUT - Socket timeout in seconds (default: 5.0)
    KSI_SESSION_LOG_DIR - Session logs directory (default: var/logs/sessions)
    KSI_IDENTITY_STORAGE_PATH - Identity storage path (default: var/db/identities.json)
    KSI_TMP_DIR - Temporary files directory (default: var/tmp)

Example:
    export KSI_ADMIN_SOCKET=/custom/admin.sock
    export KSI_LOG_LEVEL=DEBUG
    python daemon.py
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, Literal
import logging
import structlog

class KSIConfig(BaseSettings):
    """
    KSI Daemon Configuration with environment variable overrides.
    
    All settings can be overridden with KSI_ prefixed environment variables.
    For example: KSI_SOCKET_PATH, KSI_DB_PATH, KSI_LOG_LEVEL
    """
    
    # Core daemon paths - 5-socket architecture
    admin_socket: Path = Path("sockets/admin.sock")
    agents_socket: Path = Path("sockets/agents.sock")
    messaging_socket: Path = Path("sockets/messaging.sock")
    state_socket: Path = Path("sockets/state.sock")
    completion_socket: Path = Path("sockets/completion.sock")
    
    # PID file
    pid_file: Path = Path("var/run/ksi_daemon.pid")
    
    # Database and storage
    db_path: Path = Path("var/db/agent_shared_state.db")
    identity_storage_path: Path = Path("var/db/identities.json")
    
    # Logging configuration
    log_dir: Path = Path("var/logs/daemon")
    session_log_dir: Path = Path("var/logs/sessions")
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    log_structured: bool = True
    
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
            self.admin_socket.parent,    # sockets
            self.agents_socket.parent,   # sockets
            self.messaging_socket.parent,# sockets
            self.state_socket.parent,    # sockets
            self.completion_socket.parent,# sockets
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
    
    def configure_structlog(self) -> None:
        """Configure structlog with contextvars support and format options."""
        processors = [
            structlog.contextvars.merge_contextvars,  # Auto-merge context vars
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]
        
        # Choose renderer based on format preference
        if self.log_format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            # Console format - human readable
            processors.extend([
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(colors=True)
            ])
        
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    def get_structured_logger(self, name: str) -> structlog.stdlib.BoundLogger:
        """Get a structured logger instance with automatic context support."""
        if not hasattr(self, '_structlog_configured'):
            self.configure_structlog()
            self._structlog_configured = True
        return structlog.get_logger(name)
    
    def __str__(self) -> str:
        """String representation showing key configuration values."""
        return (
            f"KSIConfig(admin={self.admin_socket}, "
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