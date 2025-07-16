"""Path resolution utilities for KSI.

Provides consistent path resolution across all KSI components.
"""

from pathlib import Path
from typing import Optional
from .ksi_root import find_ksi_root

from .constants import (
    DEFAULT_VAR_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_RESPONSE_LOG_DIR,
    DEFAULT_DAEMON_LOG_DIR,
    DEFAULT_STATE_DIR,
    DEFAULT_DB_DIR,
    DEFAULT_RUN_DIR,
    DEFAULT_EXPORT_DIR,
    DEFAULT_SOCKET_PATH,
)


class KSIPaths:
    """Resolve standard KSI paths relative to base directory.
    
    This class provides a single source of truth for all path resolution
    in the KSI system. All paths are resolved relative to a base directory,
    which defaults to the current working directory.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize with optional base directory.
        
        Args:
            base_dir: Base directory for all paths. Defaults to KSI root if found, else cwd.
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Try to find KSI root first
            ksi_root = find_ksi_root()
            self.base_dir = ksi_root if ksi_root else Path.cwd()
        
        # Create critical directories on initialization
        self._ensure_critical_dirs()
    
    def _ensure_critical_dirs(self) -> None:
        """Ensure critical directories exist."""
        # Only create the most essential directories
        # Others will be created on demand by components
        critical_dirs = [
            self.var_dir,
            self.run_dir,
        ]
        for dir_path in critical_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def var_dir(self) -> Path:
        """Get var directory path."""
        return self.base_dir / DEFAULT_VAR_DIR
    
    @property
    def socket_path(self) -> Path:
        """Get daemon socket path."""
        return self.base_dir / DEFAULT_SOCKET_PATH
    
    @property
    def log_dir(self) -> Path:
        """Get main log directory path."""
        return self.base_dir / DEFAULT_LOG_DIR
    
    @property
    def response_logs_dir(self) -> Path:
        """Get response logs directory path."""
        return self.base_dir / DEFAULT_RESPONSE_LOG_DIR
    
    @property
    def daemon_logs_dir(self) -> Path:
        """Get daemon logs directory path."""
        return self.base_dir / DEFAULT_DAEMON_LOG_DIR
    
    @property
    def state_dir(self) -> Path:
        """Get state directory path."""
        return self.base_dir / DEFAULT_STATE_DIR
    
    @property
    def db_dir(self) -> Path:
        """Get database directory path."""
        return self.base_dir / DEFAULT_DB_DIR
    
    @property
    def run_dir(self) -> Path:
        """Get run directory path (for PID files, sockets)."""
        return self.base_dir / DEFAULT_RUN_DIR
    
    @property
    def exports_dir(self) -> Path:
        """Get exports directory path."""
        return self.base_dir / DEFAULT_EXPORT_DIR
    
    @property
    def pid_file(self) -> Path:
        """Get daemon PID file path."""
        return self.run_dir / "ksi_daemon.pid"
    
    @property
    def responses_dir(self) -> Path:
        """Get provider-agnostic response logs directory."""
        return self.base_dir / "var/logs/responses"
    
    
    def ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists and return it.
        
        Args:
            path: Directory path to ensure exists
            
        Returns:
            Path: The directory path
        """
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_response_log_path(self, session_id: str) -> Path:
        """Get path for a specific response log file.
        
        Args:
            session_id: Session ID
            
        Returns:
            Path: Full path to response log file
        """
        return self.response_logs_dir / f"{session_id}.jsonl"
    
    def get_message_bus_log_path(self) -> Path:
        """Get path for message bus log file.
        
        Returns:
            Path: Full path to message bus log file
        """
        return self.response_logs_dir / "message_bus.jsonl"
    
    
    def get_export_path(self, filename: str) -> Path:
        """Get path for an export file.
        
        Args:
            filename: Export filename
            
        Returns:
            Path: Full path to export file
        """
        return self.exports_dir / filename
    
    def resolve_path(self, path: str) -> Path:
        """Resolve a path relative to base directory.
        
        Args:
            path: Path string (absolute or relative)
            
        Returns:
            Path: Resolved path
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_dir / p