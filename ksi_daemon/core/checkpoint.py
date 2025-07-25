#!/usr/bin/env python3
"""
Development checkpoint system for preserving state across daemon restarts.

This module provides checkpoint/restore functionality for dev mode,
allowing queued requests and session state to survive daemon restarts
during development.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, TypedDict, Literal
from typing_extensions import NotRequired
from datetime import datetime

from ksi_daemon.event_system import event_handler, EventPriority, emit_event, shutdown_handler, get_router
from ksi_common import timestamp_utc
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from .context_manager import get_context_manager

# Module state
logger = get_bound_logger("checkpoint", version="1.0.0")
is_checkpoint_disabled = os.environ.get("KSI_CHECKPOINT_DISABLED", "false").lower() == "true"
reset_db_on_startup = os.environ.get("KSI_RESET_CHECKPOINT_DB", "false").lower() == "true"

# Checkpoint database path
CHECKPOINT_DB = config.checkpoint_db_path


async def initialize_checkpoint_db():
    """Initialize checkpoint database with proper relational schema."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed. Run: pip install aiosqlite")
        return False
    
    # Conditionally delete existing database based on environment variable
    if reset_db_on_startup and CHECKPOINT_DB.exists():
        CHECKPOINT_DB.unlink()
        logger.info("Deleted existing checkpoint database for clean start (KSI_RESET_CHECKPOINT_DB=true)")
    elif CHECKPOINT_DB.exists():
        logger.info("Preserving existing checkpoint database for state restoration")
    
    async with aiosqlite.connect(CHECKPOINT_DB) as db:
        # Enable WAL mode for better concurrency
        await db.execute("PRAGMA journal_mode=WAL")
        
        # Create checkpoints table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                restored_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                total_requests INTEGER NOT NULL DEFAULT 0,
                total_sessions INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # Create checkpoint_requests table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id INTEGER NOT NULL,
                request_id TEXT NOT NULL,
                session_id TEXT,
                status TEXT NOT NULL,
                request_data TEXT NOT NULL, -- JSON blob: appropriate for temporary pass-through data
                queued_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id),
                UNIQUE(checkpoint_id, request_id)
            )
        """)
        
        # Create checkpoint_sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                queue_depth INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 0,
                active_request TEXT,
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id),
                UNIQUE(checkpoint_id, session_id)
            )
        """)
        
        # Create checkpoint_contexts table for context system state
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id INTEGER NOT NULL,
                hot_storage_snapshot TEXT NOT NULL,  -- JSON snapshot of hot storage
                active_correlations TEXT NOT NULL,   -- JSON snapshot of active correlation chains
                context_stats TEXT NOT NULL,        -- JSON metadata about context state
                created_at TEXT NOT NULL,
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id)
            )
        """)
        
        # Create checkpoint_agents table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                profile TEXT,
                composition TEXT,
                status TEXT,
                created_at TEXT,
                session_id TEXT,
                permission_profile TEXT,
                agent_type TEXT,
                purpose TEXT,
                agent_data TEXT NOT NULL, -- JSON blob for full agent data
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id),
                UNIQUE(checkpoint_id, agent_id)
            )
        """)
        
        # Create checkpoint_identities table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                identity_data TEXT NOT NULL, -- JSON blob for identity data
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id),
                UNIQUE(checkpoint_id, agent_id)
            )
        """)
        
        # Create indexes (IF NOT EXISTS)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoints(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON checkpoints(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_requests_checkpoint ON checkpoint_requests(checkpoint_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_checkpoint ON checkpoint_sessions(checkpoint_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_agents_checkpoint ON checkpoint_agents(checkpoint_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_identities_checkpoint ON checkpoint_identities(checkpoint_id)")
        
        await db.commit()
        logger.info("Checkpoint database initialized with relational schema including agent tables", path=str(CHECKPOINT_DB))
    
    return True


async def capture_context_state() -> Dict[str, Any]:
    """Capture current context system state for checkpointing."""
    try:
        cm = get_context_manager()
        if not cm._initialized:
            return {"error": "Context manager not initialized"}
        
        # Capture hot storage snapshot
        hot_snapshot = {
            "events": dict(cm.hot_storage.events),  # Convert OrderedDict to dict for JSON
            "contexts_by_ref": dict(cm.hot_storage.contexts_by_ref),
            "events_by_correlation": dict(cm.hot_storage.events_by_correlation),
            "events_by_agent": dict(cm.hot_storage.events_by_agent),
            "event_chains": dict(cm.hot_storage.event_chains)
        }
        
        # Capture active correlation IDs
        active_correlations = list(cm.hot_storage.events_by_correlation.keys())
        
        # Capture context statistics
        context_stats = {
            "hot_count": len(cm.hot_storage.events),
            "correlation_chains": len(cm.hot_storage.events_by_correlation),
            "agent_contexts": len(cm.hot_storage.events_by_agent),
            "event_chains": len(cm.hot_storage.event_chains),
            "capture_timestamp": timestamp_utc()
        }
        
        return {
            "hot_storage": hot_snapshot,
            "active_correlations": active_correlations,
            "context_stats": context_stats,
            "status": "captured"
        }
        
    except Exception as e:
        logger.error(f"Failed to capture context state: {e}")
        return {"error": f"Context capture failed: {str(e)}"}


async def restore_context_state(context_data: Dict[str, Any]) -> Dict[str, Any]:
    """Restore context system state from checkpoint data."""
    try:
        cm = get_context_manager()
        if not cm._initialized:
            await cm.initialize()
        
        hot_storage = context_data.get("hot_storage", {})
        active_correlations = context_data.get("active_correlations", [])
        context_stats = context_data.get("context_stats", {})
        
        # Clear current hot storage
        cm.hot_storage.events.clear()
        cm.hot_storage.contexts_by_ref.clear()
        cm.hot_storage.events_by_correlation.clear()
        cm.hot_storage.events_by_agent.clear()
        cm.hot_storage.event_chains.clear()
        
        # Restore hot storage data
        if "events" in hot_storage:
            cm.hot_storage.events.update(hot_storage["events"])
            
        if "contexts_by_ref" in hot_storage:
            cm.hot_storage.contexts_by_ref.update(hot_storage["contexts_by_ref"])
            
        if "events_by_correlation" in hot_storage:
            cm.hot_storage.events_by_correlation.update(hot_storage["events_by_correlation"])
            
        if "events_by_agent" in hot_storage:
            cm.hot_storage.events_by_agent.update(hot_storage["events_by_agent"])
            
        if "event_chains" in hot_storage:
            cm.hot_storage.event_chains.update(hot_storage["event_chains"])
        
        # Verify restoration
        restored_count = len(cm.hot_storage.events)
        restored_correlations = len(cm.hot_storage.events_by_correlation)
        
        logger.info(f"Context state restored: {restored_count} events, {restored_correlations} correlation chains")
        
        return {
            "status": "restored",
            "events_restored": restored_count,
            "correlations_restored": restored_correlations,
            "original_stats": context_stats,
            "restore_timestamp": timestamp_utc()
        }
        
    except Exception as e:
        logger.error(f"Failed to restore context state: {e}")
        return {"error": f"Context restore failed: {str(e)}"}


async def save_context_checkpoint(checkpoint_id: int) -> bool:
    """Save context state to checkpoint database."""
    try:
        import aiosqlite
        
        context_state = await capture_context_state()
        if "error" in context_state:
            logger.error(f"Failed to capture context state: {context_state['error']}")
            return False
        
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            await db.execute("""
                INSERT INTO checkpoint_contexts 
                (checkpoint_id, hot_storage_snapshot, active_correlations, context_stats, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                checkpoint_id,
                json.dumps(context_state["hot_storage"]),
                json.dumps(context_state["active_correlations"]),
                json.dumps(context_state["context_stats"]),
                timestamp_utc()
            ))
            await db.commit()
            
        logger.info(f"Context checkpoint saved for checkpoint {checkpoint_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save context checkpoint: {e}")
        return False


async def load_context_checkpoint(checkpoint_id: int) -> Optional[Dict[str, Any]]:
    """Load context state from checkpoint database."""
    try:
        import aiosqlite
        
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            async with db.execute("""
                SELECT hot_storage_snapshot, active_correlations, context_stats, created_at
                FROM checkpoint_contexts 
                WHERE checkpoint_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (checkpoint_id,)) as cursor:
                row = await cursor.fetchone()
                
        if not row:
            return None
            
        return {
            "hot_storage": json.loads(row[0]),
            "active_correlations": json.loads(row[1]),
            "context_stats": json.loads(row[2]),
            "created_at": row[3]
        }
        
    except Exception as e:
        logger.error(f"Failed to load context checkpoint: {e}")
        return None


async def save_checkpoint(checkpoint_data: Dict[str, Any]) -> bool:
    """Save checkpoint to database using relational schema."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed")
        return False
    
    try:
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            # Count totals
            total_requests = len(checkpoint_data.get("active_completions", {}))
            total_sessions = len(checkpoint_data.get("session_queues", {}))
            
            # Create checkpoint record
            cursor = await db.execute(
                """INSERT INTO checkpoints (created_at, reason, status, total_requests, total_sessions) 
                   VALUES (?, ?, 'active', ?, ?)""",
                (
                    checkpoint_data.get("timestamp", timestamp_utc()),
                    checkpoint_data.get("reason", "manual"),
                    total_requests,
                    total_sessions
                )
            )
            checkpoint_id = cursor.lastrowid
            
            # Save requests
            for request_id, completion_data in checkpoint_data.get("active_completions", {}).items():
                await db.execute(
                    """INSERT INTO checkpoint_requests 
                       (checkpoint_id, request_id, session_id, status, request_data, 
                        queued_at, started_at, completed_at, error)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        checkpoint_id,
                        request_id,
                        completion_data.get("session_id"),
                        completion_data.get("status", "unknown"),
                        json.dumps(completion_data.get("data", {})),
                        completion_data.get("queued_at"),
                        completion_data.get("started_at"),
                        completion_data.get("completed_at"),
                        completion_data.get("error")
                    )
                )
            
            # Save sessions with queue items
            for session_id, session_data in checkpoint_data.get("session_queues", {}).items():
                # Handle both list (old format) and dict (new format)
                if isinstance(session_data, list):
                    queue_items = session_data
                    is_active = False
                    active_request = None
                else:
                    queue_items = session_data.get("items", [])
                    is_active = session_data.get("is_active", False)
                    active_request = session_data.get("active_request")
                
                # Save session metadata
                await db.execute(
                    """INSERT INTO checkpoint_sessions 
                       (checkpoint_id, session_id, queue_depth, is_active, active_request)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        checkpoint_id,
                        session_id,
                        len(queue_items),
                        1 if is_active else 0,
                        active_request
                    )
                )
                
                # Save queued items as pending requests
                for item in queue_items:
                    await db.execute(
                        """INSERT INTO checkpoint_requests 
                           (checkpoint_id, request_id, session_id, status, request_data, queued_at)
                           VALUES (?, ?, ?, 'queued', ?, ?)""",
                        (
                            checkpoint_id,
                            item.get("request_id"),
                            session_id,
                            json.dumps(item.get("data", {})),
                            item.get("timestamp", timestamp_utc())
                        )
                    )
            
            
            # Keep only last 5 checkpoints
            await db.execute("""
                UPDATE checkpoints SET status = 'archived'
                WHERE id NOT IN (
                    SELECT id FROM checkpoints 
                    WHERE status = 'active'
                    ORDER BY id DESC LIMIT 5
                )
            """)
            
            await db.commit()
            
        # Save context state checkpoint (separate transaction for safety)
        try:
            await save_context_checkpoint(checkpoint_id)
        except Exception as e:
            logger.warning(f"Failed to save context checkpoint for {checkpoint_id}: {e}")
            # Don't fail the entire checkpoint if context save fails
            
        logger.info(
            f"Checkpoint {checkpoint_id} saved: {total_requests} requests, "
            f"{total_sessions} sessions, context state included"
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}", exc_info=True)
        return False


async def load_latest_checkpoint() -> Optional[Dict[str, Any]]:
    """Load the most recent checkpoint from database."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed")
        return None
    
    try:
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            # Get latest active checkpoint
            async with db.execute(
                """SELECT id, created_at, reason, total_requests, total_sessions 
                   FROM checkpoints 
                   WHERE status = 'active' 
                   ORDER BY id DESC LIMIT 1"""
            ) as cursor:
                checkpoint_row = await cursor.fetchone()
                if not checkpoint_row:
                    logger.info("No active checkpoint found")
                    return None
                
            checkpoint_id, created_at, reason, total_requests, total_sessions = checkpoint_row
            
            # Build checkpoint data structure
            checkpoint_data = {
                "timestamp": created_at,
                "reason": reason,
                "checkpoint_id": checkpoint_id,
                "active_completions": {},
                "session_queues": {}
            }
            
            # Load requests
            async with db.execute(
                """SELECT request_id, session_id, status, request_data, 
                          queued_at, started_at, completed_at, error
                   FROM checkpoint_requests
                   WHERE checkpoint_id = ?""",
                (checkpoint_id,)
            ) as cursor:
                async for row in cursor:
                    request_id, session_id, status, request_data, queued_at, started_at, completed_at, error = row
                    checkpoint_data["active_completions"][request_id] = {
                        "session_id": session_id,
                        "status": status,
                        "data": json.loads(request_data) if request_data else {},
                        "queued_at": queued_at,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "error": error
                    }
            
            # Load sessions  
            async with db.execute(
                """SELECT session_id, queue_depth, is_active, active_request
                   FROM checkpoint_sessions
                   WHERE checkpoint_id = ?""",
                (checkpoint_id,)
            ) as cursor:
                async for row in cursor:
                    session_id, queue_depth, is_active, active_request = row
                    
                    # Load queued items for this session
                    queue_items = []
                    async with db.execute(
                        """SELECT request_id, request_data, queued_at
                           FROM checkpoint_requests
                           WHERE checkpoint_id = ? AND session_id = ? AND status = 'queued'
                           ORDER BY id""",
                        (checkpoint_id, session_id)
                    ) as item_cursor:
                        async for item_row in item_cursor:
                            req_id, req_data, queued_at = item_row
                            queue_items.append({
                                "request_id": req_id,
                                "data": json.loads(req_data) if req_data else {},
                                "timestamp": queued_at
                            })
                    
                    checkpoint_data["session_queues"][session_id] = {
                        "items": queue_items,
                        "is_active": bool(is_active),
                        "active_request": active_request
                    }
            
            logger.info(
                f"Loaded checkpoint {checkpoint_id} with {total_requests} requests, "
                f"{total_sessions} sessions"
            )
            return checkpoint_data
                    
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}", exc_info=True)
        return None


async def extract_completion_state() -> Dict[str, Any]:
    """Extract state from ALL services via event system."""
    try:
        # Use event system to collect checkpoint data
        result = await emit_event("checkpoint:collect", {})
        
        # Initialize checkpoint data with all expected fields
        checkpoint_data = {
            "timestamp": timestamp_utc(),
            "session_queues": {},
            "active_completions": {},
            "observation_subscriptions": {}
        }
        
        # Handle both single and multi-handler responses
        responses = result if isinstance(result, list) else [result]
        
        for response in responses:
            if not isinstance(response, dict):
                continue
                
            # Merge data from different services
            if "session_queues" in response:
                # Completion service data
                checkpoint_data["session_queues"] = response.get("session_queues", {})
                checkpoint_data["active_completions"] = response.get("active_completions", {})
                
            if "observation_subscriptions" in response:
                # Observation service data
                checkpoint_data["observation_subscriptions"] = response.get("observation_subscriptions", {})
        
        logger.info(
            "Collected checkpoint data",
            sessions=len(checkpoint_data.get("session_queues", {})),
            requests=len(checkpoint_data.get("active_completions", {}))
        )
        
        return checkpoint_data
        
    except Exception as e:
        logger.error(f"Failed to extract checkpoint state: {e}", exc_info=True)
        return {
            "timestamp": timestamp_utc(),
            "session_queues": {},
            "active_completions": {},
            "agents": {},
            "identities": {}
        }


async def restore_completion_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Restore state to completion service and re-emit queued requests."""
    results = {
        "restored_sessions": 0,
        "restored_requests": 0,
        "failed_requests": 0,
        "lost_processing": []
    }
    
    # For each session with queued requests
    for session_id, queue_items in state.get("session_queues", {}).items():
        if queue_items:
            results["restored_sessions"] += 1
            
            # Re-emit each queued request
            for item in queue_items:
                request_id = item["request_id"]
                data = item["data"]
                
                try:
                    # Re-emit the original completion request
                    await emit_event("completion:async", data)
                    results["restored_requests"] += 1
                    logger.debug(f"Re-emitted request {request_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to restore request {request_id}: {e}")
                    results["failed_requests"] += 1
    
    # Handle lost processing requests - emit failure events for retry
    for request_id, completion in state.get("active_completions", {}).items():
        status = completion.get("status")
        error = completion.get("error", "")
        
        # Check if this request should be retried:
        # 1. Was processing when daemon stopped
        # 2. Failed due to shutdown-related causes (signal -9, daemon termination, etc.)
        should_retry = False
        retry_reason = ""
        
        if status == "processing":
            should_retry = True
            retry_reason = "Request was processing when daemon restarted"
        elif status == "failed" and error:
            # Check for shutdown-related error patterns
            shutdown_patterns = [
                "signal -9",
                "SIGKILL",
                "terminated with signal",
                "daemon restart",
                "shutdown",
                "Connection lost",
                "CancelledError"
            ]
            if any(pattern in str(error) for pattern in shutdown_patterns):
                should_retry = True
                retry_reason = f"Request failed due to daemon shutdown: {error[:100]}"
        
        if should_retry:
            results["lost_processing"].append({
                "request_id": request_id,
                "session_id": completion.get("session_id"),
                "started_at": completion.get("started_at"),
                "status": status,
                "reason": retry_reason
            })
            
            # Emit failure event - retry manager will handle retry logic
            # Include the original request data so retry manager can retry it
            await emit_event("completion:failed", {
                "request_id": request_id,
                "reason": "daemon_restart",
                "message": retry_reason,
                "original_error": error[:500] if error else None,  # Include some error context
                "completion_data": completion  # Include full completion data for retry
            })
    
    logger.info(
        "Checkpoint restore complete",
        restored_sessions=results["restored_sessions"],
        restored_requests=results["restored_requests"],
        lost_processing=len(results["lost_processing"])
    )
    
    return results


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for checkpoint
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for checkpoint restore
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class DevCheckpointData(TypedDict):
    """Handle checkpoint operations with multiple actions."""
    action: Literal['create', 'status', 'list_requests', 'remove_request', 'clear_failed', 'clear_all']  # Action to perform
    request_id: NotRequired[str]  # Request ID for remove_request action
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class DevRestoreData(TypedDict):
    """Manually trigger checkpoint restore."""
    # No specific fields - restores latest checkpoint
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for checkpoint shutdown
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


# Event handlers

@event_handler("system:startup", priority=EventPriority.LOW)
async def handle_startup(data: SystemStartupData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize checkpoint system database."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    if is_checkpoint_disabled:
        logger.debug("Checkpoint system disabled via KSI_CHECKPOINT_DISABLED")
        return event_response_builder(
            {"checkpoint": "disabled"},
            context=context
        )
    
    # Initialize database only - don't restore yet
    if not await initialize_checkpoint_db():
        return event_response_builder(
            {"checkpoint": "failed_init"},
            context=context
        )
    
    return event_response_builder(
        {"checkpoint": "initialized"},
        context=context
    )


@event_handler("system:ready", priority=EventPriority.LOW)
async def handle_ready_restore(data: SystemReadyData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restore checkpoint after all services are ready."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    if is_checkpoint_disabled:
        return event_response_builder(
            {"checkpoint": "disabled"},
            context=context
        )
    
    # Try to restore checkpoint now that services are ready
    checkpoint = await load_latest_checkpoint()
    if checkpoint:
        logger.info(
            "Restoring checkpoint after services ready",
            timestamp=checkpoint.get("timestamp")
        )
        
        # Services are ready, restore both completion and context state
        results = await restore_completion_state(checkpoint)
        
        # Try to restore context state
        context_results = {"status": "skipped", "reason": "no_context_checkpoint"}
        try:
            checkpoint_id = checkpoint.get("checkpoint_id")
            if checkpoint_id:
                context_checkpoint = await load_context_checkpoint(checkpoint_id)
                if context_checkpoint:
                    context_results = await restore_context_state(context_checkpoint)
                    logger.info("Context state automatically restored from checkpoint")
                else:
                    context_results = {"status": "skipped", "reason": "no_context_data"}
        except Exception as e:
            logger.warning(f"Failed to restore context state during auto-restore: {e}")
            context_results = {"status": "failed", "error": str(e)}
            
        return event_response_builder(
            {
                "checkpoint": "restored", 
                "completion_results": results,
                "context_results": context_results
            },
            context=context
        )
    
    return event_response_builder(
        {"checkpoint": "no_checkpoint"},
        context=context
    )


async def _create_checkpoint(save_if_empty: bool = True, reason: str = "manual") -> Dict[str, Any]:
    """Create a checkpoint with optional empty-state filtering."""
    if is_checkpoint_disabled:
        return {"error": "Checkpoint system disabled"}
    
    try:
        # Extract current state
        state = await extract_completion_state()
        
        # Check if there's meaningful state
        total_queued = sum(len(items) for items in state["session_queues"].values())
        total_active = len(state["active_completions"])
        
        # Skip saving if empty and not forced
        if not save_if_empty and total_queued == 0 and total_active == 0:
            logger.debug(f"No active state to checkpoint ({reason})")
            return {"checkpoint": "empty"}
        
        # Log checkpoint creation
        if total_queued > 0 or total_active > 0:
            logger.info(
                f"Creating {reason} checkpoint: {total_queued} queued, "
                f"{total_active} active requests"
            )
        else:
            logger.debug(f"Creating {reason} checkpoint (empty state)")
        
        # Add metadata
        state["timestamp"] = timestamp_utc()
        state["reason"] = reason
        
        # Save checkpoint - shield from cancellation during shutdown
        try:
            save_result = await asyncio.shield(save_checkpoint(state))
            if save_result:
                logger.info(f"{reason.title()} checkpoint saved successfully")
                return {
                    "status": "saved",
                    "timestamp": state["timestamp"],
                    "sessions": len(state["session_queues"]),
                    "queued_requests": total_queued,
                    "active_requests": total_active
                }
            else:
                logger.warning(f"Failed to save {reason} checkpoint")
                return {"error": "Failed to save checkpoint"}
        except asyncio.CancelledError:
            logger.warning(f"{reason.title()} checkpoint save was cancelled - attempting synchronous save")
            # Try one more time without cancellation protection
            if await save_checkpoint(state):
                logger.info(f"{reason.title()} checkpoint saved on retry")
                return {"status": "saved_on_retry"}
            raise
            
    except Exception as e:
        logger.error(f"{reason.title()} checkpoint failed: {e}", exc_info=True)
        return {"error": str(e)}


async def _list_checkpoint_requests() -> Dict[str, Any]:
    """List completion requests in the latest checkpoint."""
    if is_checkpoint_disabled:
        return {"error": "Checkpoint system disabled"}
    
    checkpoint = await load_latest_checkpoint()
    if not checkpoint:
        return {"requests": [], "count": 0}
    
    active_completions = checkpoint.get("active_completions", {})
    requests = []
    
    for request_id, completion_data in active_completions.items():
        requests.append({
            "request_id": request_id,
            "status": completion_data.get("status", "unknown"),
            "session_id": completion_data.get("session_id"),
            "queued_at": completion_data.get("queued_at"),
            "error": completion_data.get("error")
        })
    
    return {
        "requests": requests,
        "count": len(requests),
        "checkpoint_timestamp": checkpoint.get("timestamp")
    }


async def _update_checkpoint(modified_data: Dict[str, Any]) -> bool:
    """Update the latest checkpoint with modified data."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed")
        return False
    
    try:
        # Since we're using a relational schema now, we need to 
        # delete and recreate rather than update a JSON blob
        # This is more complex but maintains relational integrity
        
        # For now, just save as a new checkpoint
        # In practice, we'd update individual rows
        return await save_checkpoint(modified_data)
                
    except Exception as e:
        logger.error(f"Failed to update checkpoint: {e}", exc_info=True)
        return False


async def _remove_checkpoint_request(request_id: str) -> Dict[str, Any]:
    """Remove a specific request from the latest checkpoint."""
    if is_checkpoint_disabled:
        return {"error": "Checkpoint system disabled"}
    
    try:
        import aiosqlite
    except ImportError:
        return {"error": "aiosqlite not installed"}
        
    try:
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            # Get latest active checkpoint
            async with db.execute(
                "SELECT id FROM checkpoints WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"error": "No active checkpoint found"}
                    
            checkpoint_id = row[0]
            
            # Check if request exists
            async with db.execute(
                "SELECT id FROM checkpoint_requests WHERE checkpoint_id = ? AND request_id = ?",
                (checkpoint_id, request_id)
            ) as cursor:
                if not await cursor.fetchone():
                    return {"error": f"Request {request_id} not found in checkpoint"}
            
            # Delete the request
            await db.execute(
                "DELETE FROM checkpoint_requests WHERE checkpoint_id = ? AND request_id = ?",
                (checkpoint_id, request_id)
            )
            
            # Update checkpoint totals
            await db.execute(
                "UPDATE checkpoints SET total_requests = total_requests - 1 WHERE id = ?",
                (checkpoint_id,)
            )
            
            await db.commit()
            
        logger.info(f"Removed checkpoint request {request_id}")
        return {"status": "removed", "request_id": request_id}
        
    except Exception as e:
        logger.error(f"Failed to remove checkpoint request: {e}", exc_info=True)
        return {"error": str(e)}


async def _clear_checkpoint_requests(filter_type: str = "all") -> Dict[str, Any]:
    """Clear requests from the latest checkpoint based on filter."""
    if is_checkpoint_disabled:
        return {"error": "Checkpoint system disabled"}
    
    try:
        import aiosqlite
    except ImportError:
        return {"error": "aiosqlite not installed"}
        
    try:
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            # Get latest active checkpoint
            async with db.execute(
                "SELECT id FROM checkpoints WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"error": "No active checkpoint found"}
                    
            checkpoint_id = row[0]
            
            # Count requests before clearing
            async with db.execute(
                "SELECT COUNT(*) FROM checkpoint_requests WHERE checkpoint_id = ? AND status != 'queued'",
                (checkpoint_id,)
            ) as cursor:
                original_count = (await cursor.fetchone())[0]
            
            if filter_type == "failed":
                # Delete only failed requests
                result = await db.execute(
                    "DELETE FROM checkpoint_requests WHERE checkpoint_id = ? AND status = 'failed'",
                    (checkpoint_id,)
                )
                removed_count = result.rowcount
                
            elif filter_type == "all":
                # Delete all non-queued requests
                result = await db.execute(
                    "DELETE FROM checkpoint_requests WHERE checkpoint_id = ? AND status != 'queued'",
                    (checkpoint_id,)
                )
                removed_count = result.rowcount
                
            else:
                return {"error": f"Unknown filter type: {filter_type}"}
            
            # Update checkpoint totals
            await db.execute(
                "UPDATE checkpoints SET total_requests = total_requests - ? WHERE id = ?",
                (removed_count, checkpoint_id)
            )
            
            # Count remaining
            async with db.execute(
                "SELECT COUNT(*) FROM checkpoint_requests WHERE checkpoint_id = ? AND status != 'queued'",
                (checkpoint_id,)
            ) as cursor:
                remaining_count = (await cursor.fetchone())[0]
            
            await db.commit()
            
        logger.info(f"Cleared {removed_count} {filter_type} requests from checkpoint")
        return {
            "status": "cleared",
            "filter": filter_type,
            "removed_count": removed_count,
            "remaining_count": remaining_count
        }
        
    except Exception as e:
        logger.error(f"Failed to clear checkpoint requests: {e}", exc_info=True)
        return {"error": str(e)}


@event_handler("dev:checkpoint")
async def handle_checkpoint(data: DevCheckpointData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle checkpoint operations with multiple actions."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    action = data.get("action")
    if not action:
        return error_response(
            "action parameter required. Valid actions: create, status, list_requests, remove_request, clear_failed, clear_all",
            context=context
        )
    
    if action == "create":
        result = await _create_checkpoint(save_if_empty=True, reason="manual")
        return event_response_builder(result, context=context)
    
    elif action == "status":
        # Get status from latest checkpoint 
        checkpoint = await load_latest_checkpoint()
        if not checkpoint:
            return event_response_builder(
                {"status": "no_checkpoint"},
                context=context
            )
        
        active_completions = checkpoint.get("active_completions", {})
        session_queues = checkpoint.get("session_queues", {})
        
        return event_response_builder(
            {
                "status": "saved",
                "timestamp": checkpoint.get("timestamp"),
                "sessions": len(session_queues),
                "queued_requests": sum(len(items) for items in session_queues.values()),
                "active_requests": len(active_completions)
            },
            context=context
        )
    
    elif action == "list_requests":
        result = await _list_checkpoint_requests()
        return event_response_builder(result, context=context)
    
    elif action == "remove_request":
        request_id = data.get("request_id")
        if not request_id:
            return error_response(
                "request_id required for remove_request action",
                context=context
            )
        result = await _remove_checkpoint_request(request_id)
        return event_response_builder(result, context=context)
    
    elif action == "clear_failed":
        result = await _clear_checkpoint_requests("failed")
        return event_response_builder(result, context=context)
    
    elif action == "clear_all":
        result = await _clear_checkpoint_requests("all")
        return event_response_builder(result, context=context)
    
    else:
        return error_response(
            f"Unknown action: {action}. Valid actions: create, status, list_requests, remove_request, clear_failed, clear_all",
            context=context
        )


@event_handler("dev:restore")
async def handle_restore(data: DevRestoreData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Manually trigger checkpoint restore."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    if is_checkpoint_disabled:
        return error_response(
            "Checkpoint system disabled",
            context=context
        )
    
    checkpoint = await load_latest_checkpoint()
    if not checkpoint:
        return error_response(
            "No checkpoint found",
            context=context
        )
    
    # Restore completion state
    results = await restore_completion_state(checkpoint)
    
    # Try to restore context state if available
    context_results = {"status": "skipped", "reason": "no_context_checkpoint"}
    try:
        checkpoint_id = checkpoint.get("checkpoint_id")
        if checkpoint_id:
            context_checkpoint = await load_context_checkpoint(checkpoint_id)
            if context_checkpoint:
                context_results = await restore_context_state(context_checkpoint)
                logger.info("Context state restored from checkpoint")
            else:
                context_results = {"status": "skipped", "reason": "no_context_data"}
    except Exception as e:
        logger.warning(f"Failed to restore context state: {e}")
        context_results = {"status": "failed", "error": str(e)}
    
    return event_response_builder(
        {
            "status": "restored",
            "checkpoint_time": checkpoint.get("timestamp"),
            "completion_results": results,
            "context_results": context_results
        },
        context=context
    )


@shutdown_handler("checkpoint", priority=EventPriority.HIGH)
async def handle_shutdown_checkpoint(data: SystemShutdownData) -> Dict[str, Any]:
    """Create checkpoint before shutdown to preserve state.
    
    This is a critical shutdown handler that must complete before daemon exits.
    """
    try:
        result = await _create_checkpoint(save_if_empty=False, reason="shutdown")
        
        # Always acknowledge shutdown, even if checkpoint failed
        router = get_router()
        await router.acknowledge_shutdown("checkpoint")
        
        return result
    except Exception as e:
        logger.error(f"Error in shutdown checkpoint handler: {e}", exc_info=True)
        # Still acknowledge to prevent hanging
        router = get_router()
        await router.acknowledge_shutdown("checkpoint")
        raise