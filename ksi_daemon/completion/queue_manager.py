#!/usr/bin/env python3
"""
Completion Queue Manager

Manages per-session completion queues to prevent request forking while
allowing multi-session parallelism. Provides queue depth monitoring and
session lifecycle management.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Any, Optional

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.config import config


logger = get_bound_logger("completion.queue_manager")


# Priority levels for completion requests
class CompletionPriority:
    """Priority levels for completion requests."""
    INJECT = 1    # High priority - completion:inject for agent coordination
    ASYNC = 2     # Normal priority - completion:async for regular requests


@dataclass
class PriorityQueueItem:
    """Item for priority queue with proper ordering."""
    priority: int
    timestamp: str  # For FIFO within same priority
    request_id: str
    request_data: Dict[str, Any]
    
    def __lt__(self, other):
        """Compare items for priority queue ordering."""
        if self.priority != other.priority:
            return self.priority < other.priority  # Lower number = higher priority
        return self.timestamp < other.timestamp  # FIFO within same priority


class CompletionQueueManager:
    """Manages per-session completion queues."""
    
    def __init__(self):
        """Initialize the queue manager."""
        self._session_queues: Dict[str, asyncio.PriorityQueue] = {}
        self._active_sessions: Set[str] = set()
        self._queue_sizes: Dict[str, int] = {}  # Track sizes for monitoring
        self._queue_timeout = config.completion_queue_processor_timeout
        
    async def enqueue(self, session_id: str, request_id: str, 
                     request_data: Dict[str, Any], priority: int = CompletionPriority.ASYNC) -> Dict[str, Any]:
        """
        Add a completion request to the appropriate session queue.
        
        Args:
            session_id: The session identifier
            request_id: Unique request identifier
            request_data: The completion request data
            priority: Request priority (CompletionPriority.INJECT or CompletionPriority.ASYNC)
            
        Returns:
            Queue status information
        """
        # Get or create priority queue for session
        if session_id not in self._session_queues:
            self._session_queues[session_id] = asyncio.PriorityQueue()
            logger.debug(f"Created new priority queue for session {session_id}")
        
        queue = self._session_queues[session_id]
        
        # Create priority queue item
        item = PriorityQueueItem(
            priority=priority,
            timestamp=timestamp_utc(),
            request_id=request_id,
            request_data=request_data
        )
        
        # Add to priority queue
        await queue.put(item)
        
        # Update size tracking
        self._queue_sizes[session_id] = queue.qsize()
        
        priority_name = "INJECT" if priority == CompletionPriority.INJECT else "ASYNC"
        logger.info(
            "Enqueued completion request",
            request_id=request_id,
            session_id=session_id,
            priority=priority_name,
            queue_depth=queue.qsize()
        )
        
        return {
            "queued": True,
            "queue_depth": queue.qsize(),
            "session_active": session_id in self._active_sessions,
            "priority": priority_name
        }
    
    async def dequeue(self, session_id: str, timeout: float = 1.0) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Get the next request from a session queue (highest priority first).
        
        Args:
            session_id: The session identifier
            timeout: How long to wait for a request
            
        Returns:
            Tuple of (request_id, request_data) or None if timeout
        """
        if session_id not in self._session_queues:
            return None
            
        queue = self._session_queues[session_id]
        
        try:
            item = await asyncio.wait_for(queue.get(), timeout=timeout)
            self._queue_sizes[session_id] = queue.qsize()
            return (item.request_id, item.request_data)
        except asyncio.TimeoutError:
            return None
    
    def mark_session_active(self, session_id: str) -> None:
        """Mark a session as actively processing."""
        self._active_sessions.add(session_id)
        logger.debug(f"Session {session_id} marked as active")
    
    def mark_session_inactive(self, session_id: str) -> None:
        """Mark a session as no longer processing."""
        self._active_sessions.discard(session_id)
        logger.debug(f"Session {session_id} marked as inactive")
    
    def is_session_active(self, session_id: str) -> bool:
        """Check if a session is actively processing."""
        return session_id in self._active_sessions
    
    def should_create_processor(self, session_id: str) -> bool:
        """
        Determine if a new processor should be created for this session.
        
        Returns True if the session has a queue but no active processor.
        One processor per conversation to maintain serial execution.
        """
        return (session_id in self._session_queues and 
                session_id not in self._active_sessions)
    
    def get_queue_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed status for a session queue.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Queue status information
        """
        if session_id not in self._session_queues:
            return {
                "exists": False,
                "session_id": session_id
            }
        
        queue = self._session_queues[session_id]
        
        return {
            "exists": True,
            "session_id": session_id,
            "queue_size": queue.qsize(),
            "is_active": session_id in self._active_sessions,
            "is_empty": queue.empty()
        }
    
    def get_all_queue_status(self) -> Dict[str, Any]:
        """
        Get status for all session queues.
        
        Returns:
            Dictionary with overall statistics and per-session info
        """
        session_info = {}
        total_queued = 0
        
        for session_id, queue in self._session_queues.items():
            size = queue.qsize()
            total_queued += size
            session_info[session_id] = {
                "queue_size": size,
                "is_active": session_id in self._active_sessions
            }
        
        return {
            "total_sessions": len(self._session_queues),
            "active_sessions": len(self._active_sessions),
            "total_queued": total_queued,
            "sessions": session_info
        }
    
    async def clear_session(self, session_id: str) -> int:
        """
        Clear all queued requests for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Number of requests cleared
        """
        if session_id not in self._session_queues:
            return 0
        
        queue = self._session_queues[session_id]
        cleared = 0
        
        # Drain the priority queue
        while not queue.empty():
            try:
                item = queue.get_nowait()  # Returns PriorityQueueItem
                cleared += 1
            except asyncio.QueueEmpty:
                break
        
        # Update tracking
        self._queue_sizes[session_id] = 0
        
        logger.info(f"Cleared {cleared} requests from session {session_id}")
        return cleared
    
    def cleanup_empty_queues(self) -> int:
        """
        Remove empty, inactive session queues.
        
        Returns:
            Number of queues cleaned up
        """
        to_remove = []
        
        for session_id, queue in self._session_queues.items():
            if (queue.empty() and 
                session_id not in self._active_sessions):
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._session_queues[session_id]
            self._queue_sizes.pop(session_id, None)
            logger.debug(f"Removed empty queue for session {session_id}")
        
        return len(to_remove)
    
    def shutdown(self) -> Dict[str, Any]:
        """
        Shutdown the queue manager and return statistics.
        
        Returns:
            Shutdown statistics
        """
        stats = {
            "sessions_cleared": len(self._session_queues),
            "requests_pending": sum(q.qsize() for q in self._session_queues.values()),
            "active_sessions": len(self._active_sessions)
        }
        
        # Clear all state
        self._session_queues.clear()
        self._active_sessions.clear()
        self._queue_sizes.clear()
        
        logger.info("Queue manager shutdown", **stats)
        return stats