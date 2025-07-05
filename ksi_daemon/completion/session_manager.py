#!/usr/bin/env python3
"""
Completion Session Manager

Manages session continuity, conversation locks, and session state tracking.
Provides session-aware request routing and recovery mechanisms.
"""

import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.event_system import emit_event


logger = get_bound_logger("completion.session_manager")


class SessionState:
    """Represents the state of a completion session."""
    
    def __init__(self, session_id: str):
        """Initialize session state."""
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.request_count = 0
        self.active_request: Optional[str] = None
        self.conversation_locked = False
        self.lock_holder: Optional[str] = None
        self.lock_expiry: Optional[datetime] = None
        self.metadata: Dict[str, Any] = {}
        
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
        
    def is_locked(self) -> bool:
        """Check if conversation is currently locked."""
        if not self.conversation_locked:
            return False
            
        # Check lock expiry
        if self.lock_expiry and datetime.now() > self.lock_expiry:
            self.conversation_locked = False
            self.lock_holder = None
            self.lock_expiry = None
            return False
            
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "request_count": self.request_count,
            "active_request": self.active_request,
            "conversation_locked": self.is_locked(),
            "lock_holder": self.lock_holder,
            "lock_expiry": self.lock_expiry.isoformat() if self.lock_expiry else None,
            "metadata": self.metadata
        }


class SessionManager:
    """Manages completion sessions with conversation locking and recovery."""
    
    def __init__(self):
        """Initialize the session manager."""
        self._sessions: Dict[str, SessionState] = {}
        self._agent_sessions: Dict[str, Set[str]] = {}  # agent_id -> session_ids
        self._recovery_data: Dict[str, Dict[str, Any]] = {}  # For session recovery
        
    def get_or_create_session(self, session_id: str) -> SessionState:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionState object
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id)
            logger.info(f"Created new session {session_id}")
        
        session = self._sessions[session_id]
        session.update_activity()
        return session
    
    def register_request(self, session_id: str, request_id: str, 
                        agent_id: Optional[str] = None) -> None:
        """
        Register a new request for a session.
        
        Args:
            session_id: Session identifier
            request_id: Request identifier
            agent_id: Optional agent identifier
        """
        session = self.get_or_create_session(session_id)
        session.active_request = request_id
        session.request_count += 1
        session.update_activity()
        
        # Track agent-session mapping
        if agent_id:
            if agent_id not in self._agent_sessions:
                self._agent_sessions[agent_id] = set()
            self._agent_sessions[agent_id].add(session_id)
        
        logger.debug(
            f"Registered request {request_id} for session {session_id}",
            request_count=session.request_count,
            agent_id=agent_id
        )
    
    def complete_request(self, session_id: str, request_id: str) -> None:
        """
        Mark a request as completed.
        
        Args:
            session_id: Session identifier
            request_id: Request identifier
        """
        if session_id not in self._sessions:
            logger.warning(f"Completing request for unknown session {session_id}")
            return
        
        session = self._sessions[session_id]
        if session.active_request == request_id:
            session.active_request = None
        session.update_activity()
        
        logger.debug(f"Completed request {request_id} for session {session_id}")
    
    async def acquire_conversation_lock(self, session_id: str, agent_id: str,
                                      timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Acquire conversation lock for a session.
        
        Args:
            session_id: Session identifier
            agent_id: Agent requesting the lock
            timeout_seconds: Lock timeout in seconds
            
        Returns:
            Lock acquisition result
        """
        session = self.get_or_create_session(session_id)
        
        # Check if already locked
        if session.is_locked():
            if session.lock_holder == agent_id:
                # Same agent, extend lock
                session.lock_expiry = datetime.now() + timedelta(seconds=timeout_seconds)
                logger.debug(f"Extended lock for {agent_id} on session {session_id}")
                return {
                    "locked": True,
                    "extended": True,
                    "lock_holder": agent_id,
                    "expires_at": session.lock_expiry.isoformat()
                }
            else:
                # Different agent, deny
                logger.warning(
                    f"Lock denied for {agent_id} on session {session_id}",
                    current_holder=session.lock_holder
                )
                return {
                    "locked": False,
                    "reason": "already_locked",
                    "lock_holder": session.lock_holder,
                    "expires_at": session.lock_expiry.isoformat() if session.lock_expiry else None
                }
        
        # Acquire lock
        session.conversation_locked = True
        session.lock_holder = agent_id
        session.lock_expiry = datetime.now() + timedelta(seconds=timeout_seconds)
        
        logger.info(
            f"Lock acquired for {agent_id} on session {session_id}",
            timeout_seconds=timeout_seconds
        )
        
        # Emit lock event
        await emit_event("conversation:locked", {
            "session_id": session_id,
            "agent_id": agent_id,
            "expires_at": session.lock_expiry.isoformat()
        })
        
        return {
            "locked": True,
            "lock_holder": agent_id,
            "expires_at": session.lock_expiry.isoformat()
        }
    
    async def release_conversation_lock(self, session_id: str, 
                                      agent_id: str) -> Dict[str, Any]:
        """
        Release conversation lock for a session.
        
        Args:
            session_id: Session identifier
            agent_id: Agent releasing the lock
            
        Returns:
            Lock release result
        """
        if session_id not in self._sessions:
            return {
                "released": False,
                "reason": "session_not_found"
            }
        
        session = self._sessions[session_id]
        
        # Check if agent holds the lock
        if not session.conversation_locked:
            return {
                "released": False,
                "reason": "not_locked"
            }
        
        if session.lock_holder != agent_id:
            return {
                "released": False,
                "reason": "not_lock_holder",
                "lock_holder": session.lock_holder
            }
        
        # Release lock
        session.conversation_locked = False
        session.lock_holder = None
        session.lock_expiry = None
        
        logger.info(f"Lock released by {agent_id} on session {session_id}")
        
        # Emit unlock event
        await emit_event("conversation:unlocked", {
            "session_id": session_id,
            "agent_id": agent_id
        })
        
        return {
            "released": True,
            "session_id": session_id,
            "agent_id": agent_id
        }
    
    def save_recovery_data(self, session_id: str, request_id: str,
                          request_data: Dict[str, Any]) -> None:
        """
        Save request data for potential recovery.
        
        Args:
            session_id: Session identifier
            request_id: Request identifier
            request_data: Complete request data
        """
        self._recovery_data[request_id] = {
            "session_id": session_id,
            "saved_at": timestamp_utc(),
            "request_data": request_data
        }
        
        # Limit recovery data size
        if len(self._recovery_data) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._recovery_data.keys(),
                key=lambda k: self._recovery_data[k]["saved_at"]
            )
            for key in sorted_keys[:100]:
                del self._recovery_data[key]
    
    def get_recovery_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recovery data for a request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Recovery data if available
        """
        return self._recovery_data.get(request_id)
    
    def clear_recovery_data(self, request_id: str) -> None:
        """Clear recovery data for a completed request."""
        self._recovery_data.pop(request_id, None)
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get detailed status for a session."""
        if session_id not in self._sessions:
            return {
                "exists": False,
                "session_id": session_id
            }
        
        session = self._sessions[session_id]
        return {
            "exists": True,
            **session.to_dict()
        }
    
    def get_agent_sessions(self, agent_id: str) -> List[str]:
        """Get all sessions associated with an agent."""
        return list(self._agent_sessions.get(agent_id, set()))
    
    def cleanup_expired_locks(self) -> int:
        """
        Clean up expired conversation locks.
        
        Returns:
            Number of locks cleaned up
        """
        cleaned = 0
        now = datetime.now()
        
        for session in self._sessions.values():
            if (session.conversation_locked and 
                session.lock_expiry and 
                now > session.lock_expiry):
                session.conversation_locked = False
                session.lock_holder = None
                session.lock_expiry = None
                cleaned += 1
                logger.info(f"Cleaned up expired lock on session {session.session_id}")
        
        return cleaned
    
    def cleanup_inactive_sessions(self, inactive_minutes: int = 60) -> int:
        """
        Clean up inactive sessions.
        
        Args:
            inactive_minutes: Minutes of inactivity before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        cutoff = datetime.now() - timedelta(minutes=inactive_minutes)
        to_remove = []
        
        for session_id, session in self._sessions.items():
            if (session.last_activity < cutoff and 
                not session.active_request and
                not session.is_locked()):
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._sessions[session_id]
            
            # Clean up agent mappings
            for agent_id, sessions in self._agent_sessions.items():
                sessions.discard(session_id)
            
            logger.debug(f"Cleaned up inactive session {session_id}")
        
        # Clean up empty agent entries
        self._agent_sessions = {
            k: v for k, v in self._agent_sessions.items() if v
        }
        
        return len(to_remove)
    
    def get_all_sessions_status(self) -> Dict[str, Any]:
        """Get overview of all sessions."""
        total_locked = sum(1 for s in self._sessions.values() if s.is_locked())
        total_active = sum(1 for s in self._sessions.values() if s.active_request)
        
        return {
            "total_sessions": len(self._sessions),
            "locked_sessions": total_locked,
            "active_sessions": total_active,
            "recovery_data_size": len(self._recovery_data),
            "agents_with_sessions": len(self._agent_sessions)
        }