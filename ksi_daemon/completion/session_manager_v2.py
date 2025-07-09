#!/usr/bin/env python3
"""
Session Manager V2 - Compatible refactor that fixes session tracking

Key fix: Never "create" sessions - only track real sessions from claude-cli.
Maintains exact same API as original SessionManager for compatibility.
"""

import asyncio
from typing import Dict, Any, Optional, Set, List
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
    """
    Manages completion sessions with conversation locking and recovery.
    
    V2 Changes:
    - Never creates session IDs
    - Tracks requests separately from sessions
    - Handles session_id=None as "pending assignment"
    - Updates tracking when claude-cli returns real session_id
    """
    
    def __init__(self):
        """Initialize the session manager."""
        # Keep original data structures for compatibility
        self._sessions: Dict[str, SessionState] = {}
        self._agent_sessions: Dict[str, Set[str]] = {}  # agent_id -> session_ids
        self._recovery_data: Dict[str, Dict[str, Any]] = {}  # For session recovery
        
        # NEW: Track requests separately
        self._requests: Dict[str, Dict[str, Any]] = {}  # request_id -> request info
        self._pending_requests: Set[str] = set()  # Requests waiting for session assignment
        
    def get_or_create_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get existing session - NO LONGER creates sessions.
        
        IMPORTANT: Returns None if session doesn't exist or if session_id is None.
        This is the key fix - we never create sessions, only track real ones.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionState object or None
        """
        if not session_id:  # None or empty string
            return None
            
        return self._sessions.get(session_id)
    
    def register_request(self, session_id: str, request_id: str, 
                        agent_id: Optional[str] = None) -> None:
        """
        Register a new request.
        
        Args:
            session_id: Session identifier (can be None for new conversations)
            request_id: Request identifier  
            agent_id: Optional agent identifier
        """
        # Track the request
        self._requests[request_id] = {
            "session_id": session_id,
            "agent_id": agent_id,
            "registered_at": datetime.now()
        }
        
        # If no session_id, this is a pending request
        if not session_id:
            self._pending_requests.add(request_id)
            logger.debug(
                f"Registered pending request {request_id} (waiting for session assignment)",
                agent_id=agent_id
            )
            return
            
        # If we have a real session_id, track it
        if session_id not in self._sessions:
            # This is a real session from claude-cli we haven't seen before
            self._sessions[session_id] = SessionState(session_id)
            logger.info(f"Tracking new session {session_id} from claude-cli")
            
        session = self._sessions[session_id]
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
            session_id: Session identifier (might be None)
            request_id: Request identifier
        """
        # Remove from pending if it was there
        self._pending_requests.discard(request_id)
        
        # If this was a pending request that now has a session, update tracking
        if request_id in self._requests:
            request_info = self._requests[request_id]
            old_session = request_info.get("session_id")
            
            # If we have a real session_id now and didn't before, update everything
            if session_id and not old_session:
                logger.info(
                    f"Request {request_id} completed with new session {session_id}",
                    agent_id=request_info.get("agent_id")
                )
                
                # Track the new session if we haven't seen it
                if session_id not in self._sessions:
                    self._sessions[session_id] = SessionState(session_id)
                    logger.info(f"Tracking new session {session_id} from completed request")
                    
                # Update agent mapping
                agent_id = request_info.get("agent_id")
                if agent_id:
                    if agent_id not in self._agent_sessions:
                        self._agent_sessions[agent_id] = set()
                    self._agent_sessions[agent_id].add(session_id)
                    
                # Update request info
                request_info["session_id"] = session_id
        
        # Now handle the normal completion logic
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if session.active_request == request_id:
                session.active_request = None
            session.update_activity()
            logger.debug(f"Completed request {request_id} for session {session_id}")
        else:
            # This is OK - might be a request that started with no session
            logger.debug(f"Completed request {request_id} (no active session)")
    
    async def acquire_conversation_lock(self, session_id: str, agent_id: str,
                                      timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Acquire a conversation lock for exclusive access.
        
        Args:
            session_id: Session identifier
            agent_id: Agent requesting the lock
            timeout_seconds: Lock timeout in seconds
            
        Returns:
            Lock acquisition result
        """
        # Can't lock a non-existent session
        if not session_id:
            return {
                "success": False,
                "reason": "no_session_id"
            }
            
        session = self.get_or_create_session(session_id)
        if not session:
            # For compatibility, create the session here if needed
            # This preserves original behavior for explicit lock requests
            self._sessions[session_id] = SessionState(session_id)
            session = self._sessions[session_id]
            logger.info(f"Created session {session_id} for lock acquisition")
        
        # Check if already locked
        if session.is_locked():
            return {
                "success": False,
                "reason": "already_locked",
                "current_holder": session.lock_holder,
                "expires_at": session.lock_expiry.isoformat() if session.lock_expiry else None
            }
        
        # Acquire lock
        session.conversation_locked = True
        session.lock_holder = agent_id
        session.lock_expiry = datetime.now() + timedelta(seconds=timeout_seconds)
        
        logger.info(
            f"Agent {agent_id} acquired lock on session {session_id}",
            expires_at=session.lock_expiry.isoformat()
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "expires_at": session.lock_expiry.isoformat()
        }
    
    async def release_conversation_lock(self, session_id: str, 
                                      agent_id: str) -> Dict[str, Any]:
        """
        Release a conversation lock.
        
        Args:
            session_id: Session identifier
            agent_id: Agent releasing the lock
            
        Returns:
            Lock release result
        """
        if not session_id:
            return {
                "success": False,
                "reason": "no_session_id"
            }
            
        if session_id not in self._sessions:
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
                "lock_holder": session.lock_holder
            }
        
        # Release lock
        session.conversation_locked = False
        session.lock_holder = None
        session.lock_expiry = None
        
        logger.info(f"Agent {agent_id} released lock on session {session_id}")
        
        return {
            "success": True,
            "session_id": session_id
        }
    
    def save_recovery_data(self, session_id: str, request_id: str, 
                          data: Dict[str, Any]) -> None:
        """
        Save recovery data for a request.
        
        Args:
            session_id: Session identifier (can be None)
            request_id: Request identifier
            data: Data to save for recovery
        """
        self._recovery_data[request_id] = {
            "session_id": session_id,
            "timestamp": timestamp_utc(),
            "data": data
        }
        
        logger.debug(
            f"Saved recovery data for request {request_id}",
            session_id=session_id,
            data_size=len(str(data))
        )
    
    def get_recovery_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recovery data for a request.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Recovery data or None
        """
        recovery = self._recovery_data.get(request_id)
        return recovery["data"] if recovery else None
    
    def clear_recovery_data(self, request_id: str) -> None:
        """
        Clear recovery data for a request.
        
        Args:
            request_id: Request identifier
        """
        if request_id in self._recovery_data:
            del self._recovery_data[request_id]
            logger.debug(f"Cleared recovery data for request {request_id}")
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get the status of a specific session."""
        if not session_id:
            return {
                "exists": False,
                "reason": "no_session_id"
            }
            
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
    
    def get_all_sessions_status(self) -> Dict[str, Any]:
        """Get aggregated status of all sessions."""
        locked_count = sum(1 for s in self._sessions.values() if s.is_locked())
        active_count = sum(1 for s in self._sessions.values() if s.active_request)
        
        return {
            "total_sessions": len(self._sessions),
            "locked_sessions": locked_count,
            "active_sessions": active_count,
            "recovery_data_size": len(self._recovery_data),
            "agents_with_sessions": len(self._agent_sessions),
            "pending_requests": len(self._pending_requests)  # NEW metric
        }
    
    def cleanup_inactive_sessions(self, max_age_seconds: int = 3600) -> None:
        """
        Clean up inactive sessions older than max_age_seconds.
        
        Args:
            max_age_seconds: Maximum age for inactive sessions
        """
        now = datetime.now()
        to_remove = []
        
        for session_id, session in self._sessions.items():
            age = (now - session.last_activity).total_seconds()
            if age > max_age_seconds and not session.is_locked():
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._sessions[session_id]
            
            # Clean up agent mappings
            for agent_id, sessions in self._agent_sessions.items():
                sessions.discard(session_id)
        
        # Clean up empty agent entries
        empty_agents = [a for a, s in self._agent_sessions.items() if not s]
        for agent_id in empty_agents:
            del self._agent_sessions[agent_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive sessions")
    
    def cleanup_expired_locks(self) -> None:
        """Clean up expired conversation locks."""
        cleaned = 0
        for session in self._sessions.values():
            if session.is_locked():  # This checks expiry
                pass  # is_locked() already cleaned it up if expired
            else:
                cleaned += 1
                
        if cleaned:
            logger.debug(f"Cleaned up {cleaned} expired locks")
    
    # NEW: Method to update session after claude-cli returns
    def update_request_session(self, request_id: str, session_id: str) -> None:
        """
        Update a request with the real session_id from claude-cli.
        
        This is called when we get the completion result with the new session_id.
        
        Args:
            request_id: Request identifier
            session_id: Real session_id from claude-cli
        """
        if not session_id:
            logger.error(f"Attempted to update request {request_id} with None session_id")
            return
            
        # Remove from pending
        self._pending_requests.discard(request_id)
        
        # Update request info
        if request_id in self._requests:
            request_info = self._requests[request_id]
            old_session = request_info.get("session_id")
            request_info["session_id"] = session_id
            
            # Track the new session
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id)
                logger.info(f"Tracking new session {session_id} from claude-cli")
                
            # Update agent mapping
            agent_id = request_info.get("agent_id")
            if agent_id:
                if agent_id not in self._agent_sessions:
                    self._agent_sessions[agent_id] = set()
                self._agent_sessions[agent_id].add(session_id)
                
            logger.info(
                f"Updated request {request_id} with session {session_id}",
                old_session=old_session,
                agent_id=agent_id
            )