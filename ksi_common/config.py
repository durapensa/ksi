"""Shared configuration management using pydantic-settings.

Provides centralized configuration with environment variable support
for all KSI components. This ensures consistent configuration across
the daemon, clients, and interfaces.

Environment Variables:
    KSI_SOCKET_PATH - Unix socket path (default: var/run/daemon.sock)
    KSI_LOG_LEVEL - Logging level (default: INFO)
    KSI_LOG_FORMAT - Log format: json or console (default: console)
    KSI_LOG_DIR - Log directory (default: var/logs)  
    KSI_RESPONSE_LOG_DIR - Response logs directory (default: var/logs/responses)
    KSI_STATE_DIR - State directory (default: var/state)
    KSI_SOCKET_TIMEOUT - Socket timeout in seconds (default: 5.0)
    KSI_DEBUG - Enable debug mode (default: false)
    KSI_ERROR_VERBOSITY - Error message verbosity level: minimal, medium, verbose (default: medium)
    
    WebSocket Bridge Configuration:
    KSI_WEBSOCKET_BRIDGE_HOST - WebSocket host (default: localhost)
    KSI_WEBSOCKET_BRIDGE_PORT - WebSocket port (default: 8765)
    KSI_WEBSOCKET_BRIDGE_CORS_ORIGINS - Comma-separated CORS origins (default: http://localhost:8080,http://localhost:3000,file://)
    
    Event Log Configuration:
    KSI_EVENT_LOG_DIR - Event log directory (default: var/logs/events)
    KSI_EVENT_REFERENCE_THRESHOLD - Size threshold for payload references in bytes (default: 5120)
    KSI_EVENT_DAILY_FILE_NAME - Daily event log filename (default: events.jsonl)
    
    Model Configuration:
    KSI_COMPLETION_DEFAULT_MODEL - Default model for completions (default: claude-cli/claude-sonnet-4-20250514)
    KSI_SUMMARY_DEFAULT_MODEL - Default model for summaries (default: claude-cli/claude-sonnet-4-20250514)
    KSI_SEMANTIC_EVAL_DEFAULT_MODEL - Default model for semantic evaluation (default: claude-cli/claude-sonnet-4-20250514)
    
    TUI Configuration:
    KSI_TUI_DEFAULT_MODEL - Default model for TUI apps (default: claude-cli/sonnet)
    KSI_TUI_CHAT_CLIENT_ID - Client ID for chat app (default: ksi-chat)
    KSI_TUI_MONITOR_CLIENT_ID - Client ID for monitor app (default: ksi-monitor)
    KSI_TUI_MONITOR_UPDATE_INTERVAL - Monitor refresh interval (default: 1.0)
    KSI_TUI_THEME - Default TUI theme (default: catppuccin)

Example:
    export KSI_SOCKET_PATH=/custom/daemon.sock
    export KSI_LOG_LEVEL=DEBUG
    export KSI_TUI_DEFAULT_MODEL=claude-cli/opus
    export KSI_TUI_MONITOR_UPDATE_INTERVAL=0.5
    ./ksi-chat
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from pathlib import Path
from typing import Optional, Literal, List, Dict, Any, Union
import json
# Note: Removed stdlib logging import - using pure structlog

from .paths import KSIPaths
from .ksi_root import find_ksi_root
from .constants import (
    DEFAULT_VAR_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_RESPONSE_LOG_DIR,
    DEFAULT_DAEMON_LOG_DIR,
    DEFAULT_STATE_DIR,
    DEFAULT_DB_DIR,
    DEFAULT_RUN_DIR,
    DEFAULT_CLAUDE_BIN,
    DEFAULT_GEMINI_BIN,
    DEFAULT_MODEL,
    DEFAULT_EXPORT_DIR,
    DEFAULT_SOCKET_PATH,
    DEFAULT_SOCKET_TIMEOUT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PID_FILE,
    DEFAULT_WEBSOCKET_HOST,
    DEFAULT_WEBSOCKET_PORT,
    DEFAULT_WEBSOCKET_CORS_ORIGINS,
    DEFAULT_STATE_DB_NAME,
    DEFAULT_CHECKPOINT_DB_NAME,
    DEFAULT_EVENTS_DB_NAME,
    DEFAULT_COMPOSITION_INDEX_DB_NAME,
)


class KSIBaseConfig(BaseSettings):
    """Base configuration shared by all KSI components.
    
    This provides the minimal configuration needed by all components.
    The daemon can extend this with additional settings.
    
    All paths are relative by default and resolved at runtime.
    """
    
    # Core paths - matching ksi_daemon patterns
    socket_path: Path = Path(DEFAULT_SOCKET_PATH)
    
    # Logging configuration
    log_dir: Path = Path(DEFAULT_LOG_DIR)
    response_log_dir: Path = Path(DEFAULT_RESPONSE_LOG_DIR)  # Provider-agnostic completion responses
    log_level: str = DEFAULT_LOG_LEVEL
    log_format: Literal["json", "console"] = "console"
    
    # State and data
    state_dir: Path = Path(DEFAULT_STATE_DIR)
    
    # Database paths (shared infrastructure) - single database for all components
    db_dir: Path = Path(DEFAULT_DB_DIR)
    db_path: Path = Path(DEFAULT_DB_DIR) / DEFAULT_STATE_DB_NAME  # Single shared database
    async_state_db_path: Path = Path(DEFAULT_DB_DIR) / DEFAULT_STATE_DB_NAME  # Use same shared database
    identity_storage_path: Path = Path(DEFAULT_DB_DIR) / "identities.json"
    
    # Checkpoint system database
    checkpoint_db_path: Path = Path(DEFAULT_DB_DIR) / DEFAULT_CHECKPOINT_DB_NAME
    
    # Agent relationships database
    agent_relationships_db_path: Path = Path(DEFAULT_DB_DIR) / "agent_relationships.db"
    
    # Event logging database (separate from state)
    event_db_path: Path = Path(DEFAULT_DB_DIR) / DEFAULT_EVENTS_DB_NAME
    event_write_queue_size: int = 5000
    event_batch_size: int = 100
    event_flush_interval: float = 1.0  # seconds
    event_retention_days: int = 30
    event_recovery: bool = False  # Set KSI_EVENT_RECOVERY=true to enable
    
    # Composition index database
    composition_index_db_path: Path = Path(DEFAULT_DB_DIR) / DEFAULT_COMPOSITION_INDEX_DB_NAME
    
    # Reference-based event log configuration
    event_log_dir: Path = Path(DEFAULT_LOG_DIR) / "events"
    event_reference_threshold: int = 5 * 1024  # 5KB - payloads larger than this are stored as references
    event_daily_file_name: str = "events.jsonl"  # Name for daily event log files
    
    # Library and composition paths (shared infrastructure)
    lib_dir: Path = Path(DEFAULT_VAR_DIR) / "lib"
    compositions_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/compositions"
    evaluations_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/evaluations"
    components_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/compositions/components"
    schemas_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/schemas"
    capabilities_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/capabilities"
    
    # Composition type to directory mapping
    COMPOSITION_TYPE_DIRS: Dict[str, str] = {
        "profile": "profiles",
        "orchestration": "orchestrations",
        "component": "components",
        "experiment": "experiments",
        "system": "system"
    }
    
    def get_composition_type_dir(self, composition_type: str) -> Path:
        """Get the directory path for a specific composition type."""
        dir_name = self.COMPOSITION_TYPE_DIRS.get(composition_type, composition_type)
        return self.compositions_dir / dir_name
    
    # Permission and sandbox paths
    permissions_dir: Path = Path(DEFAULT_VAR_DIR) / "lib/permissions"
    sandbox_dir: Path = Path(DEFAULT_VAR_DIR) / "sandbox"
    
    # Sandbox configuration
    sandbox_enabled: bool = True                   # Enable sandboxing for completions
    sandbox_temp_ttl: int = 3600                  # Temporary sandbox lifetime (1 hour)
    sandbox_default_mode: Literal["ISOLATED", "SHARED", "NESTED"] = "ISOLATED"
    
    # Network settings
    socket_timeout: float = DEFAULT_SOCKET_TIMEOUT
    
    # WebSocket Bridge Configuration
    websocket_bridge_host: str = DEFAULT_WEBSOCKET_HOST
    websocket_bridge_port: int = DEFAULT_WEBSOCKET_PORT
    websocket_bridge_cors_origins: Union[str, List[str]] = Field(
        default=DEFAULT_WEBSOCKET_CORS_ORIGINS,
        description="Comma-separated CORS origins or JSON array"
    )
    
    @field_validator('websocket_bridge_cors_origins', mode='after')
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            # Parse comma-separated string
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        elif isinstance(v, list):
            return v
        else:
            return DEFAULT_WEBSOCKET_CORS_ORIGINS
    
    # Native Transport Configuration
    transports: str = Field(
        default="unix",
        description="Comma-separated list of enabled transports (unix, websocket)"
    )
    
    # Native WebSocket Transport Configuration
    websocket_enabled: bool = Field(
        default=False,
        description="Enable native WebSocket transport in daemon"
    )
    websocket_host: str = Field(
        default=DEFAULT_WEBSOCKET_HOST,
        description="Host for native WebSocket transport"
    )
    websocket_port: int = Field(
        default=DEFAULT_WEBSOCKET_PORT,
        description="Port for native WebSocket transport"
    )
    websocket_cors_origins: Union[str, List[str]] = Field(
        default=DEFAULT_WEBSOCKET_CORS_ORIGINS,
        description="CORS origins for native WebSocket transport"
    )
    
    @field_validator('transports', mode='after')
    @classmethod
    def parse_transports(cls, v: str) -> str:
        """Parse and validate transport list."""
        transports = [t.strip() for t in v.split(',') if t.strip()]
        valid_transports = {'unix', 'websocket'}
        invalid = set(transports) - valid_transports
        if invalid:
            raise ValueError(f"Invalid transports: {invalid}. Valid: {valid_transports}")
        return ','.join(transports)
    
    @field_validator('websocket_cors_origins', mode='after')
    @classmethod
    def parse_ws_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse WebSocket CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        elif isinstance(v, list):
            return v
        else:
            return DEFAULT_WEBSOCKET_CORS_ORIGINS
    
    @property
    def enabled_transports(self) -> List[str]:
        """Get list of enabled transports."""
        return [t.strip() for t in self.transports.split(',') if t.strip()]
    
    @property
    def is_websocket_enabled(self) -> bool:
        """Check if WebSocket transport is enabled."""
        return 'websocket' in self.enabled_transports or self.websocket_enabled
    
    # Debug mode
    debug: bool = False
    
    # Daemon-specific settings
    daemon_pid_file: Path = Path(DEFAULT_RUN_DIR) / DEFAULT_PID_FILE
    daemon_log_dir: Path = Path(DEFAULT_DAEMON_LOG_DIR)
    
    # Error handling configuration
    error_verbosity: Literal["minimal", "medium", "verbose"] = "medium"
    
    @property
    def daemon_log_file(self) -> Path:
        """Get the daemon log file path."""
        return self.daemon_log_dir / "daemon.log.jsonl"
    
    @property
    def tool_usage_log_file(self) -> Path:
        """Get the tool usage log file path."""
        return self.daemon_log_dir / "tool_usage.jsonl"
    
    daemon_tmp_dir: Path = Path(DEFAULT_VAR_DIR) / "tmp"
    
    # Completion timeouts (in seconds)
    completion_timeout_default: int = 300  # 5 minutes default
    completion_timeout_min: int = 60       # 1 minute minimum
    completion_timeout_max: int = 1800     # 30 minutes maximum
    
    # Completion queue settings
    completion_queue_processor_timeout: float = 1.0  # Queue check timeout in seconds
    
    # Model defaults for different purposes
    completion_default_model: str = f"claude-cli/{DEFAULT_MODEL}"
    summary_default_model: str = f"claude-cli/{DEFAULT_MODEL}"
    semantic_eval_default_model: str = f"claude-cli/{DEFAULT_MODEL}"
    
    # Optimization Configuration
    optimization_prompt_model: str = DEFAULT_MODEL  # Model for generating optimized prompts (same as task model)
    optimization_task_model: str = DEFAULT_MODEL  # Model for evaluation tasks
    optimization_auto_mode: str = "medium"  # Default MIPROv2 auto mode: light, medium, heavy
    optimization_max_bootstrapped_demos: int = 4  # Max bootstrapped examples
    optimization_max_labeled_demos: int = 4  # Max labeled examples  
    optimization_num_candidates: int = 10  # Number of prompt candidates to try
    optimization_init_temperature: float = 0.5  # Initial sampling temperature
    optimization_metric_threshold: Optional[float] = None  # Minimum metric score threshold
    
    # Claude CLI progressive timeouts (in seconds)
    claude_timeout_attempts: List[int] = [300, 900, 1800]  # 5min, 15min, 30min
    claude_progress_timeout: int = 300     # 5 minutes without progress
    claude_max_workers: int = 2            # Max concurrent Claude processes
    claude_retry_backoff: int = 30         # Seconds between retry attempts
    claude_bin: Optional[str] = DEFAULT_CLAUDE_BIN  # Path to claude binary
    
    # Gemini CLI settings
    gemini_timeout_attempts: List[int] = [300]  # 5min (simpler than Claude)
    gemini_progress_timeout: int = 300     # 5 minutes without progress
    gemini_retry_backoff: int = 2          # Seconds between retry attempts
    gemini_bin: Optional[str] = DEFAULT_GEMINI_BIN  # Path to gemini binary
    
    # MCP Server settings
    mcp_enabled: bool = False              # Enable MCP server (disabled by default)
    mcp_server_port: int = 8080           # MCP server port
    
    # Test timeouts (in seconds)
    test_completion_timeout: int = 120     # 2 minutes for tests
    
    # TUI Application Configuration
    tui_default_model: str = "claude-cli/sonnet"  # Default model for TUI apps
    tui_chat_client_id: str = "ksi-chat"         # Default client ID for chat
    tui_monitor_client_id: str = "ksi-monitor"   # Default client ID for monitor
    tui_monitor_update_interval: float = 1.0     # Monitor refresh interval (seconds)
    tui_theme: str = "catppuccin"                # Default TUI theme
    
    # Daemon control timeouts (in seconds)
    daemon_shutdown_socket_timeout: float = 2.0   # Socket communication timeout for shutdown
    daemon_shutdown_grace_period: int = 10        # Time to wait for graceful shutdown
    daemon_shutdown_timeout: int = 15             # Total timeout before SIGTERM
    daemon_kill_timeout: int = 5                  # Time to wait after SIGTERM before SIGKILL
    
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
            self.response_log_dir,   # var/logs/responses
            self.event_log_dir,      # var/logs/events
            self.state_dir,          # var/state
            self.db_dir,             # var/db
            self.lib_dir,            # var/lib
            self.compositions_dir,   # var/lib/compositions
            self.evaluations_dir,    # var/lib/evaluations
            self.components_dir,      # var/lib/compositions/components
            self.schemas_dir,        # var/lib/schemas
            self.capabilities_dir,   # var/lib/capabilities
            self.daemon_log_dir,     # var/logs/daemon
            self.daemon_tmp_dir,     # var/tmp
            self.experiments_cognitive_dir,  # var/experiments/cognitive
            self.experiments_results_dir,    # var/experiments/results
            self.experiments_workspaces_dir, # var/experiments/workspaces
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_log_level(self) -> str:
        """Get log level string for structlog."""
        return self.log_level.upper()
    
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
    def responses_dir(self) -> Path:
        """Get provider-agnostic response logs directory."""
        return self.response_log_dir
    
    @property
    def last_session_id_file(self) -> Path:
        """Get path to last session ID file."""
        return self.state_dir / "last_session_id"
    
    @property
    def experiments_dir(self) -> Path:
        """Get experiments data directory."""
        return Path(DEFAULT_VAR_DIR) / "experiments"
    
    @property
    def experiments_cognitive_dir(self) -> Path:
        """Get cognitive experiments data directory."""
        return self.experiments_dir / "cognitive"
    
    @property
    def experiments_results_dir(self) -> Path:
        """Get experiments results directory."""
        return self.experiments_dir / "results"
    
    @property
    def experiments_workspaces_dir(self) -> Path:
        """Get experiments workspaces directory."""
        return self.experiments_dir / "workspaces"
    
    def get_client_log_file(self) -> Path:
        """Generate log file path for the current client script.
        
        Automatically detects the calling script name from sys.argv[0].
        
        Returns:
            Path to log file in format: var/logs/{script_name}.log
        """
        import sys
        from pathlib import Path
        
        # Get script name from sys.argv[0], removing path and extension
        script_path = Path(sys.argv[0])
        script_name = script_path.stem  # Gets filename without extension
        
        return self.log_dir / f"{script_name}.log"
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return (
            f"KSIConfig(socket={self.socket_path}, "
            f"log_level={self.log_level})"
        )


# Global configuration instance
# This will be imported throughout KSI components
# KSI root detection is handled by KSIPaths when resolving paths
config = KSIBaseConfig()

# These functions have been removed per CLAUDE.md: "Never use get_config()"
# Use the global 'config' instance directly