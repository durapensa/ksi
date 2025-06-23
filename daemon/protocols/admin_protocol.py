#!/usr/bin/env python3
"""
Admin Protocol - Parameters for admin socket operations

Handles system administration, monitoring, and control operations.
Commands: health_check, get_commands, get_processes, message_bus_stats,
          shutdown, reload_daemon, cleanup, reload_module
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# SYSTEM STATUS COMMANDS
# ============================================================================

# HEALTH_CHECK - No parameters needed
# GET_COMMANDS/HELP - No parameters needed  
# GET_PROCESSES - No parameters needed
# MESSAGE_BUS_STATS - No parameters needed


# ============================================================================
# SYSTEM CONTROL COMMANDS
# ============================================================================

# SHUTDOWN - No parameters needed
# RELOAD_DAEMON - No parameters needed


# ============================================================================
# MAINTENANCE COMMANDS
# ============================================================================

class CleanupParameters(BaseModel):
    """Parameters for CLEANUP command"""
    cleanup_type: Literal["logs", "sessions", "sockets", "all"]
    
    @field_validator('cleanup_type')
    def validate_cleanup_type(cls, v):
        valid_types = ["logs", "sessions", "sockets", "all"]
        if v not in valid_types:
            raise ValueError(f"Invalid cleanup_type. Must be one of: {valid_types}")
        return v


class ReloadModuleParameters(BaseModel):
    """Parameters for RELOAD_MODULE command"""
    module_name: str = "handler"
    
    @field_validator('module_name')
    def validate_module_name(cls, v):
        # Ensure module name is safe (no path traversal)
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("Invalid module name - path traversal not allowed")
        return v


# ============================================================================
# STATE MANAGEMENT (Global System State)
# ============================================================================

class LoadStateParameters(BaseModel):
    """Parameters for LOAD_STATE command - loads global system state"""
    state_data: Dict[str, Any]
    merge: bool = False  # Whether to merge with existing state or replace


# ============================================================================
# SPECIALIZED RESPONSE HELPERS
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Structured health check response data"""
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    uptime: int  # seconds
    managers: Dict[str, Dict[str, Any]]  # Manager health details
    system_info: Optional[Dict[str, Any]] = None


class ProcessInfoDetailed(BaseModel):
    """Detailed process information for GET_PROCESSES"""
    process_id: str
    type: Literal["claude", "agent_process", "worker"]
    pid: Optional[int]
    status: str
    started_at: str
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    
    
class MessageBusStats(BaseModel):
    """Statistics for MESSAGE_BUS_STATS response"""
    subscriptions: Dict[str, List[str]]  # event_type -> [agent_ids]
    message_count: int
    active_connections: int
    event_types: List[str]
    queue_sizes: Dict[str, int]