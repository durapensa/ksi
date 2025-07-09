#!/usr/bin/env python3
"""
Conversation Tracker

Tracks completion requests and their associated sessions WITHOUT creating session IDs.
Only claude-cli can create session IDs - we just track them.

Key principle: session_id=None means "pending session assignment from claude-cli"
"""

import asyncio
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, utc_now
from ksi_daemon.event_system import emit_event


logger = get_bound_logger("completion.conversation_tracker")


@dataclass
class RequestState:
    """Tracks a single completion request."""
    request_id: str
    agent_id: Optional[str]
    session_id: Optional[str]  # None = pending assignment from claude-cli
    status: str  # "pending", "active", "completed", "failed"
    created_at: datetime = field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    recovery_data: Optional[Dict[str, Any]] = None
    
    def is_pending_session(self) -> bool:
        """Check if this request is waiting for session assignment."""
        return self.session_id is None


@dataclass  
class SessionMetadata:
    """Tracks metadata for REAL sessions created by claude-cli."""
    session_id: str  # Real session_id from claude-cli - NEVER None
    agent_id: Optional[str]  # Which agent owns this session
    last_activity: datetime = field(default_factory=utc_now)
    request_count: int = 0
    conversation_locked: bool = False
    lock_holder: Optional[str] = None
    lock_expiry: Optional[datetime] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = utc_now()
        
    def is_locked(self) -> bool:
        """Check if conversation is currently locked."""
        if not self.conversation_locked:
            return False
            
        # Check lock expiry
        if self.lock_expiry and utc_now() > self.lock_expiry:
            self.conversation_locked = False
            self.lock_holder = None
            self.lock_expiry = None
            return False
            
        return True


class ConversationTracker:
    """
    Tracks completion requests and their sessions without creating session IDs.
    
    Key responsibilities:
    1. Track requests (with or without session_id)
    2. Update request->session mapping when claude-cli returns
    3. Track agent->session mapping for conversation continuity
    4. Handle conversation locking
    """
    
    def __init__(self):
        """Initialize the conversation tracker."""
        # Request tracking
        self._requests: Dict[str, RequestState] = {}
        
        # Session tracking (only REAL sessions from claude-cli)
        self._sessions: Dict[str, SessionMetadata] = {}
        
        # Agent to current session mapping for continuity
        self._agent_sessions: Dict[str, str] = {}  # agent_id -> current session_id
        
        # Recovery data for crash recovery
        self._recovery_data: Dict[str, Dict[str, Any]] = {}
        
    def track_request(self, request_id: str, agent_id: Optional[str] = None,
                     session_id: Optional[str] = None) -> None:
        """
        Track a new completion request.
        
        Args:
            request_id: Unique request identifier
            agent_id: Optional agent making the request
            session_id: Optional session_id (None for new conversations)
        """
        request = RequestState(
            request_id=request_id,
            agent_id=agent_id,
            session_id=session_id,
            status="pending"
        )
        self._requests[request_id] = request
        
        logger.info(
            f"Tracking request {request_id}",
            agent_id=agent_id,
            session_id=session_id,
            is_new_conversation=session_id is None
        )
        
    def update_request_session(self, request_id: str, session_id: str) -> None:
        """
        Update request with the session_id returned by claude-cli.
        
        Args:
            request_id: Request identifier
            session_id: Real session_id from claude-cli (never None)
        """
        if not session_id:
            logger.error(f"Attempted to update request {request_id} with None session_id")
            return
            
        if request_id not in self._requests:
            logger.warning(f"Unknown request {request_id}")
            return
            
        request = self._requests[request_id]
        old_session = request.session_id
        request.session_id = session_id
        request.status = "active"
        
        # Track the REAL session if we haven't seen it before
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMetadata(
                session_id=session_id,
                agent_id=request.agent_id
            )
            logger.info(f"Tracking new session {session_id} from claude-cli")
        
        # Update session metadata
        session = self._sessions[session_id]
        session.update_activity()
        session.request_count += 1
        
        # Update agent->session mapping for conversation continuity
        if request.agent_id:
            old_agent_session = self._agent_sessions.get(request.agent_id)
            self._agent_sessions[request.agent_id] = session_id
            logger.info(
                f"Updated agent {request.agent_id} session mapping",
                old_session=old_agent_session,
                new_session=session_id
            )
            
        logger.info(
            f"Updated request {request_id} with session {session_id}",
            old_session=old_session,
            agent_id=request.agent_id
        )
        
    def complete_request(self, request_id: str) -> None:
        """
        Mark a request as completed.
        
        Args:
            request_id: Request identifier
        """
        if request_id not in self._requests:
            logger.warning(f"Completing unknown request {request_id}")
            return
            
        request = self._requests[request_id]
        request.status = "completed"
        request.completed_at = utc_now()
        
        # Update session activity if we have a real session
        if request.session_id and request.session_id in self._sessions:
            self._sessions[request.session_id].update_activity()
            
        logger.debug(
            f"Completed request {request_id}",
            session_id=request.session_id,
            agent_id=request.agent_id
        )
        
    def get_agent_session(self, agent_id: str) -> Optional[str]:
        """
        Get the current session_id for an agent (for conversation continuity).
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Current session_id for the agent, or None if no active session
        """
        return self._agent_sessions.get(agent_id)
        
    def save_recovery_data(self, request_id: str, data: Dict[str, Any]) -> None:
        """Save recovery data for a request."""
        self._recovery_data[request_id] = {
            "timestamp": timestamp_utc(),
            "data": data
        }
        
    def get_recovery_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get recovery data for a request."""
        recovery = self._recovery_data.get(request_id)
        return recovery["data"] if recovery else None
        
    def clear_recovery_data(self, request_id: str) -> None:
        """Clear recovery data for a completed request."""
        self._recovery_data.pop(request_id, None)
        
    async def acquire_conversation_lock(self, session_id: str, agent_id: str,
                                      lock_timeout: int = 300) -> Dict[str, Any]:
        """
        Acquire a conversation lock for exclusive access.
        
        Args:
            session_id: Session to lock (must be a real session)
            agent_id: Agent requesting the lock
            lock_timeout: Lock timeout in seconds
            
        Returns:
            Lock acquisition result
        """
        if not session_id:
            return {
                "success": False,
                "reason": "cannot_lock_pending_session"
            }
            
        if session_id not in self._sessions:
            return {
                "success": False,
                "reason": "unknown_session"
            }
            
        session = self._sessions[session_id]
        
        # Check if already locked
        if session.is_locked():
            return {
                "success": False,
                "reason": "already_locked",
                "lock_holder": session.lock_holder,
                "expires_at": session.lock_expiry.isoformat() if session.lock_expiry else None
            }
            
        # Acquire lock
        session.conversation_locked = True
        session.lock_holder = agent_id
        session.lock_expiry = utc_now() + timedelta(seconds=lock_timeout)
        
        logger.info(
            f"Acquired conversation lock",
            session_id=session_id,
            agent_id=agent_id,
            expires_at=session.lock_expiry.isoformat()
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "expires_at": session.lock_expiry.isoformat()
        }
        
    async def release_conversation_lock(self, session_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Release a conversation lock.
        
        Args:
            session_id: Session to unlock
            agent_id: Agent releasing the lock
            
        Returns:
            Lock release result
        """
        if not session_id or session_id not in self._sessions:
            return {
                "success": False,
                "reason": "session_not_found"
            }
            
        session = self._sessions[session_id]
        
        # Check if agent holds the lock
        if not session.conversation_locked:
            return {
                "success": False,
                "reason": "not_locked"
            }
            
        if session.lock_holder != agent_id:
            return {
                "success": False,
                "reason": "not_lock_holder",
                "actual_holder": session.lock_holder
            }
            
        # Release lock
        session.conversation_locked = False
        session.lock_holder = None
        session.lock_expiry = None
        
        logger.info(
            f"Released conversation lock",
            session_id=session_id,
            agent_id=agent_id
        )
        
        return {
            "success": True,
            "session_id": session_id
        }
        
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get status of a specific session."""
        if not session_id:
            return {
                "exists": False,
                "reason": "pending_session"
            }
            
        if session_id not in self._sessions:
            return {
                "exists": False,
                "session_id": session_id
            }
            
        session = self._sessions[session_id]
        return {
            "exists": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "last_activity": session.last_activity.isoformat(),
            "request_count": session.request_count,
            "is_locked": session.is_locked(),
            "lock_holder": session.lock_holder,
            "lock_expiry": session.lock_expiry.isoformat() if session.lock_expiry else None
        }
        
    def get_all_sessions_status(self) -> Dict[str, Any]:
        """Get status of all tracking."""
        active_requests = [r for r in self._requests.values() if r.status in ["pending", "active"]]
        pending_requests = [r for r in self._requests.values() if r.is_pending_session()]
        
        return {
            "total_sessions": len(self._sessions),
            "locked_sessions": sum(1 for s in self._sessions.values() if s.is_locked()),
            "active_sessions": len(self._agent_sessions),
            "recovery_data_size": len(self._recovery_data),
            "agents_with_sessions": len(self._agent_sessions),
            "active_requests": len(active_requests),
            "pending_session_assignments": len(pending_requests)
        }
        
    def cleanup_inactive_sessions(self, inactive_threshold: int = 3600) -> None:
        """
        Clean up inactive sessions.
        
        Args:
            inactive_threshold: Inactivity threshold in seconds
        """
        threshold = utc_now() - timedelta(seconds=inactive_threshold)
        to_remove = []
        
        for session_id, session in self._sessions.items():
            if session.last_activity < threshold and not session.is_locked():
                to_remove.append(session_id)
                
        for session_id in to_remove:
            del self._sessions[session_id]
            
            # Clean up agent mappings
            for agent_id, agent_session in list(self._agent_sessions.items()):
                if agent_session == session_id:
                    del self._agent_sessions[agent_id]
                    
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive sessions")
            
    def cleanup_expired_locks(self) -> None:
        """Clean up expired conversation locks."""
        expired_count = 0
        for session in self._sessions.values():
            if session.conversation_locked and session.lock_expiry and utc_now() > session.lock_expiry:
                session.conversation_locked = False
                session.lock_holder = None  
                session.lock_expiry = None
                expired_count += 1
                
        if expired_count:
            logger.info(f"Cleaned up {expired_count} expired locks")