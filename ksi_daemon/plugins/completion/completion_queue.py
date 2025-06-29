#!/usr/bin/env python3
"""
Completion Queue with Conversation Lock Management

Manages prioritized completion requests while preventing conversation forking
through distributed locks. Ensures conversation linearity by queuing parallel
requests to the same conversation_id.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
from typing import Dict, Any, Optional, List, Set, Tuple
import json
import heapq

from ksi_daemon.plugin_utils import get_logger, plugin_metadata
from ksi_common import TimestampManager
from ksi_daemon.plugins.injection.circuit_breakers import check_completion_allowed

# Plugin metadata
plugin_metadata("completion_queue", version="1.0.0",
                description="Manages completion request queue with conversation locks")

logger = get_logger("completion_queue")


class Priority(Enum):
    """Request priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class CompletionRequest:
    """Represents a queued completion request."""
    request_id: str
    conversation_id: Optional[str]
    priority: Priority
    timestamp: float
    data: Dict[str, Any]
    injection_metadata: Optional[Dict[str, Any]] = None
    parent_request_id: Optional[str] = None
    
    def __lt__(self, other):
        """For priority queue ordering."""
        # Lower priority value = higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # Earlier timestamp wins for same priority
        return self.timestamp < other.timestamp


class ConversationLockState(Enum):
    """States for conversation locks."""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    QUEUED = "queued"
    FORKED = "forked"


@dataclass
class ConversationLock:
    """Represents a lock on a conversation."""
    conversation_id: str
    holder_request_id: str
    acquired_at: float
    state: ConversationLockState = ConversationLockState.LOCKED
    queue: List[str] = field(default_factory=list)
    fork_warning: bool = False
    parent_conversation_id: Optional[str] = None
    child_conversation_ids: List[str] = field(default_factory=list)


class ConversationLockManager:
    """Manages conversation locks to prevent forking."""
    
    def __init__(self):
        self.locks: Dict[str, ConversationLock] = {}
        self.request_to_conversation: Dict[str, str] = {}
        self.lock_timeout = 300  # 5 minutes default
        self.fork_tracking: Dict[str, Set[str]] = {}  # parent -> children
    
    async def acquire_lock(self, request_id: str, conversation_id: str) -> Tuple[bool, Optional[str]]:
        """
        Attempt to acquire a conversation lock.
        
        Returns:
            (success, fork_warning_message)
        """
        
        if not conversation_id:
            # No conversation ID, no lock needed
            return True, None
        
        current_time = time.time()
        
        # Clean up expired locks
        self._cleanup_expired_locks(current_time)
        
        # Check if conversation is already locked
        if conversation_id in self.locks:
            lock = self.locks[conversation_id]
            
            if lock.state == ConversationLockState.LOCKED:
                # Add to queue
                lock.queue.append(request_id)
                self.request_to_conversation[request_id] = conversation_id
                
                logger.info(f"Request {request_id} queued for conversation {conversation_id}")
                return False, None
            
            elif lock.state == ConversationLockState.FORKED:
                # Conversation was forked, warn but allow
                warning = (f"Warning: Conversation {conversation_id} has been forked. "
                          f"Parent: {lock.parent_conversation_id}, "
                          f"Children: {lock.child_conversation_ids}")
                logger.warning(warning)
                
                # Still acquire lock on the fork
                lock.holder_request_id = request_id
                lock.acquired_at = current_time
                lock.state = ConversationLockState.LOCKED
                lock.fork_warning = True
                
                self.request_to_conversation[request_id] = conversation_id
                return True, warning
        
        # Create new lock
        lock = ConversationLock(
            conversation_id=conversation_id,
            holder_request_id=request_id,
            acquired_at=current_time
        )
        
        self.locks[conversation_id] = lock
        self.request_to_conversation[request_id] = conversation_id
        
        logger.debug(f"Lock acquired for conversation {conversation_id} by request {request_id}")
        return True, None
    
    async def release_lock(self, request_id: str) -> Optional[str]:
        """
        Release a conversation lock and return next queued request if any.
        
        Returns:
            Next request_id from queue, or None
        """
        
        conversation_id = self.request_to_conversation.get(request_id)
        if not conversation_id:
            return None
        
        lock = self.locks.get(conversation_id)
        if not lock or lock.holder_request_id != request_id:
            logger.warning(f"Request {request_id} tried to release lock it doesn't hold")
            return None
        
        # Clean up request mapping
        del self.request_to_conversation[request_id]
        
        # Check if there are queued requests
        if lock.queue:
            next_request_id = lock.queue.pop(0)
            lock.holder_request_id = next_request_id
            lock.acquired_at = time.time()
            
            logger.info(f"Lock for conversation {conversation_id} transferred to {next_request_id}")
            return next_request_id
        
        # No queue, remove lock
        del self.locks[conversation_id]
        logger.debug(f"Lock released for conversation {conversation_id}")
        
        return None
    
    def detect_fork(self, request_id: str, old_conversation_id: str, 
                   new_conversation_id: str) -> Dict[str, Any]:
        """
        Detect and track conversation fork.
        
        Called when Claude CLI returns a different conversation_id than requested.
        """
        
        logger.warning(f"Fork detected: {old_conversation_id} -> {new_conversation_id}")
        
        # Update lock state for old conversation
        if old_conversation_id in self.locks:
            lock = self.locks[old_conversation_id]
            lock.state = ConversationLockState.FORKED
            lock.child_conversation_ids.append(new_conversation_id)
        
        # Create fork tracking
        if old_conversation_id not in self.fork_tracking:
            self.fork_tracking[old_conversation_id] = set()
        self.fork_tracking[old_conversation_id].add(new_conversation_id)
        
        # Create lock for new conversation
        new_lock = ConversationLock(
            conversation_id=new_conversation_id,
            holder_request_id=request_id,
            acquired_at=time.time(),
            parent_conversation_id=old_conversation_id,
            state=ConversationLockState.FORKED
        )
        self.locks[new_conversation_id] = new_lock
        
        return {
            'fork_detected': True,
            'parent_conversation': old_conversation_id,
            'child_conversation': new_conversation_id,
            'total_forks': len(self.fork_tracking.get(old_conversation_id, set()))
        }
    
    def get_lock_status(self, conversation_id: str) -> Dict[str, Any]:
        """Get current lock status for a conversation."""
        
        lock = self.locks.get(conversation_id)
        if not lock:
            return {'locked': False, 'state': 'unlocked'}
        
        return {
            'locked': True,
            'state': lock.state.value,
            'holder': lock.holder_request_id,
            'acquired_at': lock.acquired_at,
            'queue_length': len(lock.queue),
            'fork_warning': lock.fork_warning,
            'parent_conversation': lock.parent_conversation_id,
            'child_conversations': lock.child_conversation_ids
        }
    
    def _cleanup_expired_locks(self, current_time: float):
        """Remove locks that have exceeded timeout."""
        
        expired = []
        for conv_id, lock in self.locks.items():
            if current_time - lock.acquired_at > self.lock_timeout:
                expired.append(conv_id)
        
        for conv_id in expired:
            lock = self.locks[conv_id]
            logger.warning(f"Lock expired for conversation {conv_id}, held by {lock.holder_request_id}")
            
            # Process queue if any
            if lock.queue:
                next_request = lock.queue.pop(0)
                lock.holder_request_id = next_request
                lock.acquired_at = current_time
                logger.info(f"Lock transferred to {next_request} after expiry")
            else:
                del self.locks[conv_id]


class CompletionQueue:
    """
    Manages prioritized completion request queue with injection support.
    """
    
    def __init__(self):
        self.queue: List[CompletionRequest] = []  # Using list as heap
        self.lock_manager = ConversationLockManager()
        self.active_requests: Dict[str, CompletionRequest] = {}
        self.completed_requests: Set[str] = set()
        self.request_counter = 0
    
    async def enqueue(self, request_data: Dict[str, Any], 
                     priority: Priority = Priority.NORMAL) -> Dict[str, Any]:
        """
        Add a completion request to the queue.
        
        Returns:
            Dict with request_id and queue status
        """
        
        # Generate request ID if not provided
        request_id = request_data.get('request_id') or f"req_{uuid.uuid4().hex[:12]}"
        conversation_id = request_data.get('session_id')  # Claude uses session_id
        
        # Extract injection metadata if present
        injection_config = request_data.get('injection_config')
        circuit_breaker_config = request_data.get('circuit_breaker_config', {})
        parent_request_id = circuit_breaker_config.get('parent_request_id')
        
        # Check circuit breakers
        cb_request = {
            'id': request_id,
            'prompt': request_data.get('prompt', ''),
            'circuit_breaker_config': circuit_breaker_config,
            'estimated_tokens': request_data.get('max_tokens', 4096)
        }
        
        if not check_completion_allowed(cb_request):
            logger.warning(f"Request {request_id} blocked by circuit breaker")
            return {
                'request_id': request_id,
                'status': 'blocked',
                'reason': 'circuit_breaker'
            }
        
        # Create request object
        request = CompletionRequest(
            request_id=request_id,
            conversation_id=conversation_id,
            priority=priority,
            timestamp=time.time(),
            data=request_data,
            injection_metadata=injection_config,
            parent_request_id=parent_request_id
        )
        
        # Try to acquire conversation lock
        can_proceed, fork_warning = await self.lock_manager.acquire_lock(
            request_id, conversation_id
        )
        
        if can_proceed:
            # Can proceed immediately
            self.active_requests[request_id] = request
            
            return {
                'request_id': request_id,
                'status': 'ready',
                'position': 0,
                'fork_warning': fork_warning
            }
        else:
            # Need to queue
            heapq.heappush(self.queue, request)
            
            # Find position in queue
            position = self._find_queue_position(request_id)
            
            return {
                'request_id': request_id,
                'status': 'queued',
                'position': position,
                'conversation_locked': True
            }
    
    async def dequeue(self) -> Optional[CompletionRequest]:
        """
        Get the next request that can be processed.
        
        Returns None if no requests are ready.
        """
        
        # First check if there are any active requests ready for processing
        # These were marked as "ready" and put directly in active_requests
        if self.active_requests:
            # Get first active request (they're already ready to process)
            request_id = next(iter(self.active_requests))
            request = self.active_requests[request_id]
            # Don't remove from active_requests yet - processor will do that
            return request
        
        # If no active requests, check queued requests that can now proceed
        ready_requests = []
        remaining_queue = []
        
        while self.queue:
            request = heapq.heappop(self.queue)
            
            # Check if this request's conversation is now unlocked
            if request.conversation_id:
                lock_status = self.lock_manager.get_lock_status(request.conversation_id)
                
                if (not lock_status['locked'] or 
                    lock_status['holder'] == request.request_id):
                    # This request can proceed
                    ready_requests.append(request)
                else:
                    # Still locked, keep in queue
                    remaining_queue.append(request)
            else:
                # No conversation lock needed
                ready_requests.append(request)
        
        # Rebuild queue with remaining requests
        self.queue = remaining_queue
        heapq.heapify(self.queue)
        
        # Return highest priority ready request
        if ready_requests:
            # Sort by priority and timestamp
            ready_requests.sort()
            request = ready_requests[0]
            
            # Re-queue the rest
            for r in ready_requests[1:]:
                heapq.heappush(self.queue, r)
            
            self.active_requests[request.request_id] = request
            return request
        
        return None
    
    async def complete(self, request_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark a request as completed and handle lock release.
        
        Returns:
            Dict with completion status and any fork information
        """
        
        request = self.active_requests.get(request_id)
        if not request:
            logger.warning(f"Completion for unknown request {request_id}")
            return {'status': 'unknown_request'}
        
        # Check for conversation fork
        original_conversation = request.conversation_id
        returned_conversation = result.get('session_id')
        
        fork_info = None
        if (original_conversation and returned_conversation and 
            original_conversation != returned_conversation):
            # Fork detected!
            fork_info = self.lock_manager.detect_fork(
                request_id, original_conversation, returned_conversation
            )
        
        # Release conversation lock
        next_request_id = await self.lock_manager.release_lock(request_id)
        
        # Clean up
        del self.active_requests[request_id]
        self.completed_requests.add(request_id)
        
        # Process next queued request if any
        next_request = None
        if next_request_id:
            # Find and activate the next request
            for i, req in enumerate(self.queue):
                if req.request_id == next_request_id:
                    next_request = self.queue.pop(i)
                    heapq.heapify(self.queue)
                    self.active_requests[next_request_id] = next_request
                    break
        
        return {
            'status': 'completed',
            'fork_info': fork_info,
            'next_request': next_request_id if next_request else None
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        
        return {
            'queued': len(self.queue),
            'active': len(self.active_requests),
            'completed': len(self.completed_requests),
            'locked_conversations': len(self.lock_manager.locks),
            'forked_conversations': len(self.lock_manager.fork_tracking)
        }
    
    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """Get status of a specific request."""
        
        # Check if active
        if request_id in self.active_requests:
            request = self.active_requests[request_id]
            return {
                'status': 'active',
                'conversation_id': request.conversation_id,
                'priority': request.priority.name
            }
        
        # Check if completed
        if request_id in self.completed_requests:
            return {'status': 'completed'}
        
        # Check if queued
        position = self._find_queue_position(request_id)
        if position >= 0:
            return {
                'status': 'queued',
                'position': position
            }
        
        return {'status': 'unknown'}
    
    def _find_queue_position(self, request_id: str) -> int:
        """Find position of request in queue."""
        
        for i, request in enumerate(self.queue):
            if request.request_id == request_id:
                return i
        
        return -1


# Global queue instance
completion_queue = CompletionQueue()


# Public API
async def enqueue_completion(request_data: Dict[str, Any], 
                           priority: str = "normal") -> Dict[str, Any]:
    """Enqueue a completion request."""
    
    priority_map = {
        'critical': Priority.CRITICAL,
        'high': Priority.HIGH,
        'normal': Priority.NORMAL,
        'low': Priority.LOW,
        'background': Priority.BACKGROUND
    }
    
    priority_enum = priority_map.get(priority.lower(), Priority.NORMAL)
    
    return await completion_queue.enqueue(request_data, priority_enum)


async def get_next_completion() -> Optional[Dict[str, Any]]:
    """Get the next completion request to process."""
    
    request = await completion_queue.dequeue()
    if request:
        return {
            'request_id': request.request_id,
            'data': request.data,
            'injection_metadata': request.injection_metadata,
            'parent_request_id': request.parent_request_id
        }
    
    return None


async def mark_completion_done(request_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Mark a completion as done and handle cleanup."""
    return await completion_queue.complete(request_id, result)


def get_queue_status() -> Dict[str, Any]:
    """Get current queue status."""
    return completion_queue.get_status()


def get_conversation_lock_status(conversation_id: str) -> Dict[str, Any]:
    """Get lock status for a specific conversation."""
    return completion_queue.lock_manager.get_lock_status(conversation_id)