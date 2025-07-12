#!/usr/bin/env python3
"""
Conversation Lock Module - Event-Based Version

Provides distributed conversation locking to prevent conversation forking
when multiple completion requests target the same conversation_id.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Set, Tuple, TypedDict
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.timestamps import timestamp_utc
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("conversation_lock", version="1.0.0")

# Event emitter reference (set during startup)
event_emitter = None


class LockState(Enum):
    """States for conversation locks."""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    QUEUED = "queued"
    FORKED = "forked"
    EXPIRED = "expired"


@dataclass
class ConversationLock:
    """Represents a lock on a conversation."""
    conversation_id: str
    holder_request_id: str
    acquired_at: float
    state: LockState = LockState.LOCKED
    queue: List[str] = field(default_factory=list)
    fork_warning: bool = False
    parent_conversation_id: Optional[str] = None
    child_conversation_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationLockManager:
    """Global conversation lock manager."""
    
    def __init__(self):
        self.locks: Dict[str, ConversationLock] = {}
        self.request_to_conversation: Dict[str, str] = {}
        self.lock_timeout = 300  # 5 minutes default
        self.fork_tracking: Dict[str, Set[str]] = {}  # parent -> children
        self.cleanup_interval = 60  # Cleanup every minute
        self.last_cleanup = time.time()
    
    async def acquire_lock(self, request_id: str, conversation_id: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Attempt to acquire a conversation lock.
        
        Returns dict with:
            - acquired: bool
            - state: LockState value
            - position: queue position if queued
            - fork_warning: any fork warning message
        """
        
        if not conversation_id:
            # No conversation ID, no lock needed
            return {
                'acquired': True,
                'state': LockState.UNLOCKED.value,
                'conversation_id': None
            }
        
        current_time = time.time()
        
        # Periodic cleanup
        if current_time - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_expired_locks(current_time)
            self.last_cleanup = current_time
        
        # Check if conversation is already locked
        if conversation_id in self.locks:
            lock = self.locks[conversation_id]
            
            # Check if lock expired
            if current_time - lock.acquired_at > self.lock_timeout:
                await self._expire_lock(lock, current_time)
            
            if lock.state == LockState.LOCKED:
                # Add to queue
                lock.queue.append(request_id)
                self.request_to_conversation[request_id] = conversation_id
                
                position = len(lock.queue)
                logger.info(f"Request {request_id} queued at position {position} for conversation {conversation_id}")
                
                # Emit queued event
                if event_emitter:
                    await event_emitter("conversation:queued", {
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "position": position,
                        "holder": lock.holder_request_id
                    })
                
                return {
                    'acquired': False,
                    'state': LockState.QUEUED.value,
                    'position': position,
                    'holder': lock.holder_request_id
                }
            
            elif lock.state == LockState.FORKED:
                # Conversation was forked, warn but allow
                warning = (f"Conversation {conversation_id} has been forked. "
                          f"Parent: {lock.parent_conversation_id}, "
                          f"Children: {lock.child_conversation_ids}")
                logger.warning(warning)
                
                # Acquire lock on the fork
                lock.holder_request_id = request_id
                lock.acquired_at = current_time
                lock.state = LockState.LOCKED
                lock.fork_warning = True
                lock.metadata = metadata or {}
                
                self.request_to_conversation[request_id] = conversation_id
                
                # Emit fork warning event
                if event_emitter:
                    await event_emitter("conversation:fork_warning", {
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "parent_conversation": lock.parent_conversation_id,
                        "child_conversations": lock.child_conversation_ids
                    })
                
                return {
                    'acquired': True,
                    'state': LockState.LOCKED.value,
                    'fork_warning': warning
                }
        
        # Create new lock
        lock = ConversationLock(
            conversation_id=conversation_id,
            holder_request_id=request_id,
            acquired_at=current_time,
            metadata=metadata or {}
        )
        
        self.locks[conversation_id] = lock
        self.request_to_conversation[request_id] = conversation_id
        
        logger.debug(f"Lock acquired for conversation {conversation_id} by request {request_id}")
        
        # Emit lock acquired event
        if event_emitter:
            await event_emitter("conversation:locked", {
                "request_id": request_id,
                "conversation_id": conversation_id
            })
        
        return {
            'acquired': True,
            'state': LockState.LOCKED.value,
            'conversation_id': conversation_id
        }
    
    async def release_lock(self, request_id: str) -> Dict[str, Any]:
        """
        Release a conversation lock.
        
        Returns dict with:
            - released: bool
            - next_request: request_id of next in queue if any
            - conversation_id: the conversation that was unlocked
        """
        
        conversation_id = self.request_to_conversation.get(request_id)
        if not conversation_id:
            return {
                'released': False,
                'error': 'No lock held by this request'
            }
        
        lock = self.locks.get(conversation_id)
        if not lock or lock.holder_request_id != request_id:
            logger.warning(f"Request {request_id} tried to release lock it doesn't hold")
            return {
                'released': False,
                'error': 'Request does not hold this lock'
            }
        
        # Clean up request mapping
        del self.request_to_conversation[request_id]
        
        # Check if there are queued requests
        next_request_id = None
        if lock.queue:
            next_request_id = lock.queue.pop(0)
            lock.holder_request_id = next_request_id
            lock.acquired_at = time.time()
            
            logger.info(f"Lock for conversation {conversation_id} transferred to {next_request_id}")
            
            # Emit lock transferred event
            if event_emitter:
                await event_emitter("conversation:lock_transferred", {
                    "conversation_id": conversation_id,
                    "previous_holder": request_id,
                    "new_holder": next_request_id,
                    "queue_length": len(lock.queue)
                })
        else:
            # No queue, remove lock
            del self.locks[conversation_id]
            logger.debug(f"Lock released for conversation {conversation_id}")
            
            # Emit unlocked event
            if event_emitter:
                await event_emitter("conversation:unlocked", {
                    "conversation_id": conversation_id,
                    "released_by": request_id
                })
        
        return {
            'released': True,
            'conversation_id': conversation_id,
            'next_request': next_request_id
        }
    
    async def detect_fork(self, request_id: str, expected_conversation_id: str, 
                         actual_conversation_id: str) -> Dict[str, Any]:
        """
        Handle conversation fork detection.
        
        Called when completion returns different conversation_id than expected.
        """
        
        logger.warning(f"Fork detected: {expected_conversation_id} -> {actual_conversation_id}")
        
        # Update lock state for old conversation
        if expected_conversation_id in self.locks:
            lock = self.locks[expected_conversation_id]
            lock.state = LockState.FORKED
            if actual_conversation_id not in lock.child_conversation_ids:
                lock.child_conversation_ids.append(actual_conversation_id)
        
        # Create fork tracking
        if expected_conversation_id not in self.fork_tracking:
            self.fork_tracking[expected_conversation_id] = set()
        self.fork_tracking[expected_conversation_id].add(actual_conversation_id)
        
        # Create lock for new conversation
        new_lock = ConversationLock(
            conversation_id=actual_conversation_id,
            holder_request_id=request_id,
            acquired_at=time.time(),
            parent_conversation_id=expected_conversation_id,
            state=LockState.FORKED
        )
        self.locks[actual_conversation_id] = new_lock
        self.request_to_conversation[request_id] = actual_conversation_id
        
        # Emit fork detected event
        if event_emitter:
            await event_emitter("conversation:forked", {
                "request_id": request_id,
                "parent_conversation": expected_conversation_id,
                "child_conversation": actual_conversation_id,
                "total_forks": len(self.fork_tracking.get(expected_conversation_id, set()))
            })
        
        return {
            'fork_detected': True,
            'parent_conversation': expected_conversation_id,
            'child_conversation': actual_conversation_id,
            'total_forks': len(self.fork_tracking.get(expected_conversation_id, set()))
        }
    
    async def get_lock_status(self, conversation_id: str) -> Dict[str, Any]:
        """Get current status of a conversation lock."""
        
        lock = self.locks.get(conversation_id)
        if not lock:
            return {
                'locked': False,
                'state': LockState.UNLOCKED.value
            }
        
        # Check if expired
        if time.time() - lock.acquired_at > self.lock_timeout:
            return {
                'locked': True,
                'state': LockState.EXPIRED.value,
                'holder': lock.holder_request_id,
                'acquired_at': lock.acquired_at,
                'expired': True
            }
        
        return {
            'locked': True,
            'state': lock.state.value,
            'holder': lock.holder_request_id,
            'acquired_at': lock.acquired_at,
            'queue_length': len(lock.queue),
            'queue': lock.queue[:5],  # First 5 in queue
            'fork_warning': lock.fork_warning,
            'parent_conversation': lock.parent_conversation_id,
            'child_conversations': lock.child_conversation_ids,
            'metadata': lock.metadata
        }
    
    async def get_all_locks(self) -> Dict[str, Any]:
        """Get status of all conversation locks."""
        
        locks_info = {}
        current_time = time.time()
        
        for conv_id, lock in self.locks.items():
            locks_info[conv_id] = {
                'state': lock.state.value,
                'holder': lock.holder_request_id,
                'age_seconds': int(current_time - lock.acquired_at),
                'queue_length': len(lock.queue),
                'is_fork': lock.state == LockState.FORKED
            }
        
        return {
            'total_locks': len(self.locks),
            'total_forks': len(self.fork_tracking),
            'locks': locks_info
        }
    
    async def _cleanup_expired_locks(self, current_time: float):
        """Remove expired locks and process their queues."""
        
        expired = []
        for conv_id, lock in self.locks.items():
            if current_time - lock.acquired_at > self.lock_timeout:
                expired.append((conv_id, lock))
        
        for conv_id, lock in expired:
            await self._expire_lock(lock, current_time)
    
    async def _expire_lock(self, lock: ConversationLock, current_time: float):
        """Handle lock expiration."""
        
        logger.warning(f"Lock expired for conversation {lock.conversation_id}, held by {lock.holder_request_id}")
        
        # Emit expiration event
        if event_emitter:
            await event_emitter("conversation:lock_expired", {
                "conversation_id": lock.conversation_id,
                "expired_holder": lock.holder_request_id,
                "queue_length": len(lock.queue)
            })
        
        # Process queue if any
        if lock.queue:
            next_request = lock.queue.pop(0)
            lock.holder_request_id = next_request
            lock.acquired_at = current_time
            lock.state = LockState.LOCKED
            
            logger.info(f"Lock transferred to {next_request} after expiry")
            
            # Emit transfer event
            if event_emitter:
                await event_emitter("conversation:lock_transferred", {
                    "conversation_id": lock.conversation_id,
                    "reason": "expiration",
                    "new_holder": next_request
                })
        else:
            # Remove expired lock
            del self.locks[lock.conversation_id]
            
            # Clean up request mapping
            requests_to_remove = [
                req_id for req_id, conv_id in self.request_to_conversation.items()
                if conv_id == lock.conversation_id
            ]
            for req_id in requests_to_remove:
                del self.request_to_conversation[req_id]


# Global lock manager instance
lock_manager = ConversationLockManager()


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for conversation lock service
    pass


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


class ConversationAcquireLockData(TypedDict):
    """Acquire lock for a conversation."""
    request_id: Required[str]  # Request ID attempting to acquire lock
    conversation_id: Required[str]  # Conversation ID to lock
    metadata: NotRequired[Dict[str, Any]]  # Optional lock metadata


class ConversationReleaseLockData(TypedDict):
    """Release a conversation lock."""
    request_id: Required[str]  # Request ID releasing the lock


class ConversationForkDetectedData(TypedDict):
    """Handle conversation fork detection."""
    request_id: Required[str]  # Request ID that detected the fork
    expected_conversation_id: Required[str]  # Expected conversation ID
    actual_conversation_id: Required[str]  # Actual conversation ID returned


class ConversationLockStatusData(TypedDict):
    """Get lock status for conversations."""
    conversation_id: NotRequired[str]  # Specific conversation ID (if omitted, returns all)


class ConversationActiveData(TypedDict):
    """Get all active (locked) conversations."""
    # No specific fields - returns all active conversations
    pass


# System event handlers
@event_handler("system:context")
async def handle_context(context: SystemContextData) -> None:
    """Store event emitter reference."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Conversation lock service received context, event_emitter configured")


@event_handler("system:startup")
async def handle_startup(config_data: SystemStartupData) -> Dict[str, Any]:
    """Initialize conversation lock service on startup."""
    logger.info("Conversation lock service started")
    return {"status": "conversation_lock_ready"}


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean up on shutdown."""
    logger.info("Conversation lock service stopped")


# Conversation lock event handlers
@event_handler("conversation:acquire_lock")
async def handle_acquire_lock(data: ConversationAcquireLockData) -> Dict[str, Any]:
    """Acquire lock for a conversation."""
    request_id = data.get("request_id")
    conversation_id = data.get("conversation_id")
    metadata = data.get("metadata", {})
    
    if not request_id or not conversation_id:
        return {"error": "request_id and conversation_id required"}
    
    # Execute async lock acquisition
    return await lock_manager.acquire_lock(request_id, conversation_id, metadata)


@event_handler("conversation:release_lock")
async def handle_release_lock(data: ConversationReleaseLockData) -> Dict[str, Any]:
    """Release a conversation lock."""
    request_id = data.get("request_id")
    
    if not request_id:
        return {"error": "request_id required"}
    
    return await lock_manager.release_lock(request_id)


@event_handler("conversation:fork_detected")
async def handle_fork_detected(data: ConversationForkDetectedData) -> Dict[str, Any]:
    """Handle fork detection."""
    request_id = data.get("request_id")
    expected_id = data.get("expected_conversation_id")
    actual_id = data.get("actual_conversation_id")
    
    if not all([request_id, expected_id, actual_id]):
        return {"error": "request_id, expected_conversation_id, and actual_conversation_id required"}
    
    return await lock_manager.detect_fork(request_id, expected_id, actual_id)


@event_handler("conversation:lock_status")
async def handle_lock_status(data: ConversationLockStatusData) -> Dict[str, Any]:
    """Get lock status for a conversation."""
    conversation_id = data.get("conversation_id")
    
    if conversation_id:
        return await lock_manager.get_lock_status(conversation_id)
    else:
        return await lock_manager.get_all_locks()


@event_handler("conversation:active")
async def handle_active_conversations(data: ConversationActiveData) -> Dict[str, Any]:
    """Get all active (locked) conversations."""
    all_locks = await lock_manager.get_all_locks()
    active = {
        conv_id: info for conv_id, info in all_locks['locks'].items()
        if info['state'] == LockState.LOCKED.value
    }
    
    return {
        'active_count': len(active),
        'active_conversations': active
    }


