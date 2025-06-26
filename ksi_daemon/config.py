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
import structlog


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
    agent_profiles_dir: Path = Path("var/agent_profiles")
    prompts_dir: Path = Path("var/prompts")
    
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
            self.agent_profiles_dir,     # var/agent_profiles
            self.prompts_dir,            # var/prompts
        ]
        
        for directory in daemon_dirs:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_log_file_path(self) -> Path:
        """Get the daemon log file path."""
        return self.daemon_log_dir / "daemon.log"
    
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


# Global daemon configuration instance
config = KSIDaemonConfig()

# Re-export for compatibility
get_config = lambda: config
reload_config = lambda: globals().update({'config': KSIDaemonConfig()}) or config