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

from ksi_daemon.event_system import event_handler, EventPriority, emit_event
from ksi_common import timestamp_utc
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("checkpoint", version="1.0.0")
is_dev_mode = os.environ.get("KSI_DEV_MODE", "false").lower() == "true"

# Checkpoint database path
CHECKPOINT_DB = config.db_dir / "dev_checkpoint.db"


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
    
    # Check for lost processing requests
    for request_id, completion in state.get("active_completions", {}).items():
        if completion.get("status") == "processing":
            results["lost_processing"].append({
                "request_id": request_id,
                "session_id": completion.get("session_id"),
                "started_at": completion.get("started_at")
            })
            
            # Emit failure notification
            await emit_event("completion:failed", {
                "request_id": request_id,
                "reason": "daemon_restart",
                "message": "Request interrupted by development mode restart"
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
    """Initialize checkpoint system and restore if in dev mode."""
    if not is_dev_mode:
        logger.debug("Not in dev mode, checkpoint system inactive")
        return {"checkpoint": "inactive"}
    
    # Initialize database
    if not await initialize_checkpoint_db():
        return {"checkpoint": "failed_init"}
    
    # Try to restore checkpoint
    checkpoint = await load_latest_checkpoint()
    if checkpoint:
        logger.info(
            "Found checkpoint to restore",
            timestamp=checkpoint.get("timestamp")
        )
        
        # Wait a moment for services to initialize
        await asyncio.sleep(0.5)
        
        # Restore state
        results = await restore_completion_state(checkpoint)
        return {"checkpoint": "restored", "results": results}
    
    return {"checkpoint": "ready"}


@event_handler("dev:checkpoint")
async def handle_checkpoint(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a checkpoint of current state."""
    if not is_dev_mode:
        return {"error": "Not in dev mode"}
    
    try:
        # Extract current state
        state = await extract_completion_state()
        
        # Save checkpoint
        if await save_checkpoint(state):
            return {
                "status": "saved",
                "timestamp": state["timestamp"],
                "sessions": len(state["session_queues"]),
                "active_requests": len(state["active_completions"])
            }
        else:
            return {"error": "Failed to save checkpoint"}
            
    except Exception as e:
        logger.error(f"Checkpoint failed: {e}", exc_info=True)
        return {"error": str(e)}


@event_handler("dev:restore")
async def handle_restore(data: Dict[str, Any]) -> Dict[str, Any]:
    """Manually trigger checkpoint restore."""
    if not is_dev_mode:
        return {"error": "Not in dev mode"}
    
    checkpoint = await load_latest_checkpoint()
    if not checkpoint:
        return {"error": "No checkpoint found"}
    
    results = await restore_completion_state(checkpoint)
    return {
        "status": "restored",
        "checkpoint_time": checkpoint.get("timestamp"),
        "results": results
    }