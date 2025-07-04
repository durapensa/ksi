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
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from ksi_daemon.event_system import event_handler, EventPriority, emit_event, shutdown_handler, get_router
from ksi_common import timestamp_utc
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("checkpoint", version="1.0.0")
is_checkpoint_disabled = os.environ.get("KSI_CHECKPOINT_DISABLED", "false").lower() == "true"

# Checkpoint database path
CHECKPOINT_DB = config.checkpoint_db_path


async def initialize_checkpoint_db():
    """Initialize checkpoint database with schema."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed. Run: pip install aiosqlite")
        return False
    
    async with aiosqlite.connect(CHECKPOINT_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                checkpoint_data TEXT NOT NULL
            )
        """)
        await db.commit()
        logger.info("Checkpoint database initialized", path=str(CHECKPOINT_DB))
    
    return True


async def save_checkpoint(checkpoint_data: Dict[str, Any]) -> bool:
    """Save checkpoint to database."""
    try:
        import aiosqlite
    except ImportError:
        logger.error("aiosqlite not installed")
        return False
    
    try:
        async with aiosqlite.connect(CHECKPOINT_DB) as db:
            await db.execute(
                "INSERT INTO checkpoints (timestamp, checkpoint_data) VALUES (?, ?)",
                (timestamp_utc(), json.dumps(checkpoint_data))
            )
            await db.commit()
            
            # Keep only last 5 checkpoints
            await db.execute("""
                DELETE FROM checkpoints 
                WHERE id NOT IN (
                    SELECT id FROM checkpoints 
                    ORDER BY id DESC LIMIT 5
                )
            """)
            await db.commit()
            
        logger.info("Checkpoint saved successfully")
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
            async with db.execute(
                "SELECT checkpoint_data FROM checkpoints ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                    
        logger.info("No checkpoint found")
        return None
        
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}", exc_info=True)
        return None


async def extract_completion_state() -> Dict[str, Any]:
    """Extract state from completion service."""
    # Import here to avoid circular dependency
    from ksi_daemon.completion import completion_service
    
    state = {
        "timestamp": timestamp_utc(),
        "session_queues": {},
        "active_completions": {}
    }
    
    # Extract session queue contents
    # We can't serialize asyncio.Queue directly, so extract items
    for session_id, queue in completion_service.session_processors.items():
        queue_items = []
        
        # Temporarily drain queue to list
        temp_items = []
        try:
            while True:
                item = queue.get_nowait()
                temp_items.append(item)
        except asyncio.QueueEmpty:
            pass
        
        # Put items back and record them
        for item in temp_items:
            queue.put_nowait(item)
            # item is (request_id, data)
            queue_items.append({
                "request_id": item[0],
                "data": item[1]
            })
        
        state["session_queues"][session_id] = queue_items
    
    # Extract active completions (already serializable)
    state["active_completions"] = dict(completion_service.active_completions)
    
    # Count items
    total_queued = sum(len(items) for items in state["session_queues"].values())
    total_active = len(state["active_completions"])
    
    logger.info(
        "Extracted completion state",
        sessions=len(state["session_queues"]),
        queued_requests=total_queued,
        active_requests=total_active
    )
    
    return state


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


# Event handlers

@event_handler("system:startup", priority=EventPriority.LOW)
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize checkpoint system database."""
    if is_checkpoint_disabled:
        logger.debug("Checkpoint system disabled via KSI_CHECKPOINT_DISABLED")
        return {"checkpoint": "disabled"}
    
    # Initialize database only - don't restore yet
    if not await initialize_checkpoint_db():
        return {"checkpoint": "failed_init"}
    
    return {"checkpoint": "initialized"}


@event_handler("system:ready", priority=EventPriority.LOW)
async def handle_ready_restore(data: Dict[str, Any]) -> Dict[str, Any]:
    """Restore checkpoint after all services are ready."""
    if is_checkpoint_disabled:
        return {"checkpoint": "disabled"}
    
    # Try to restore checkpoint now that services are ready
    checkpoint = await load_latest_checkpoint()
    if checkpoint:
        logger.info(
            "Restoring checkpoint after services ready",
            timestamp=checkpoint.get("timestamp")
        )
        
        # Services are ready, no need to wait
        results = await restore_completion_state(checkpoint)
        return {"checkpoint": "restored", "results": results}
    
    return {"checkpoint": "no_checkpoint"}


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
            logger.info(f"Creating {reason} checkpoint: {total_queued} queued, {total_active} active requests")
        else:
            logger.debug(f"Creating {reason} checkpoint (empty state)")
        
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


@event_handler("dev:checkpoint")
async def handle_checkpoint(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a checkpoint of current state."""
    return await _create_checkpoint(save_if_empty=True, reason="manual")


@event_handler("dev:restore")
async def handle_restore(data: Dict[str, Any]) -> Dict[str, Any]:
    """Manually trigger checkpoint restore."""
    if is_checkpoint_disabled:
        return {"error": "Checkpoint system disabled"}
    
    checkpoint = await load_latest_checkpoint()
    if not checkpoint:
        return {"error": "No checkpoint found"}
    
    results = await restore_completion_state(checkpoint)
    return {
        "status": "restored",
        "checkpoint_time": checkpoint.get("timestamp"),
        "results": results
    }


@shutdown_handler("checkpoint", priority=EventPriority.HIGH)
async def handle_shutdown_checkpoint(data: Dict[str, Any]) -> Dict[str, Any]:
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