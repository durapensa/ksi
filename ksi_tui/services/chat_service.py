"""
ChatService - Clean abstraction for chat operations with KSI daemon.

Provides a high-level interface for chat functionality, handling:
- Session management
- Message sending and receiving
- Conversation history
- Error handling and retries
"""

from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import logging

# Import KSI client components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ksi_client import EventChatClient, EventBasedClient
from ksi_common import config

logger = logging.getLogger(__name__)


class ChatError(Exception):
    """Base exception for chat service errors."""
    pass


class ConnectionError(ChatError):
    """Connection-related errors."""
    pass


class SessionError(ChatError):
    """Session-related errors."""
    pass


@dataclass
class ChatMessage:
    """Represents a chat message."""
    content: str
    sender: str  # "user", "assistant", "system"
    timestamp: datetime
    session_id: Optional[str] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Create from dictionary."""
        return cls(
            content=data.get("content", ""),
            sender=data.get("sender", "unknown"),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            session_id=data.get("session_id"),
            tokens=data.get("tokens"),
            cost=data.get("cost"),
        )


@dataclass
class ChatSession:
    """Represents a chat session."""
    session_id: str
    started_at: datetime
    last_activity: datetime
    message_count: int
    total_tokens: int = 0
    total_cost: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create from dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            started_at=datetime.fromisoformat(data.get("started_at", datetime.now().isoformat())),
            last_activity=datetime.fromisoformat(data.get("last_activity", datetime.now().isoformat())),
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost=data.get("total_cost", 0.0),
        )


class ChatService:
    """Service for managing chat interactions with KSI daemon."""
    
    def __init__(
        self,
        client_id: str = "chat_service",
        socket_path: Optional[str] = None,
        model: str = "sonnet",
    ):
        """
        Initialize the chat service.
        
        Args:
            client_id: Client identifier
            socket_path: Path to daemon socket
            model: Default model to use
        """
        self.client_id = client_id
        self.socket_path = socket_path or str(config.socket_path)
        self.model = model
        
        # Client instances
        self._chat_client: Optional[EventChatClient] = None
        self._event_client: Optional[EventBasedClient] = None
        
        # State
        self._connected = False
        self._current_session_id: Optional[str] = None
        self._message_handlers: List[Callable[[ChatMessage], None]] = []
        
        # Metrics
        self.total_messages = 0
        self.total_tokens = 0
        self.total_cost = 0.0
    
    @property
    def connected(self) -> bool:
        """Check if service is connected."""
        return self._connected
    
    @property
    def current_session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._current_session_id
    
    async def connect(self) -> bool:
        """
        Connect to the KSI daemon.
        
        Returns:
            True if connected successfully
            
        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Create client instances
            self._chat_client = EventChatClient(
                client_id=f"{self.client_id}_chat",
                socket_path=self.socket_path
            )
            
            self._event_client = EventBasedClient(
                client_id=f"{self.client_id}_event",
                socket_path=self.socket_path
            )
            
            # Connect both clients
            if not await self._chat_client.connect():
                raise ConnectionError("Failed to connect chat client")
            
            if not await self._event_client.connect():
                raise ConnectionError("Failed to connect event client")
            
            self._connected = True
            logger.info(f"ChatService connected to {self.socket_path}")
            return True
            
        except Exception as e:
            self._connected = False
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Failed to connect: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from the daemon."""
        if self._chat_client:
            try:
                await self._chat_client.disconnect()
            except Exception:
                pass
        
        if self._event_client:
            try:
                await self._event_client.disconnect()
            except Exception:
                pass
        
        self._connected = False
        logger.info("ChatService disconnected")
    
    async def send_message(
        self,
        content: str,
        session_id: Optional[str] = None,
    ) -> Tuple[ChatMessage, str]:
        """
        Send a message and get response.
        
        Args:
            content: Message content
            session_id: Session ID (uses current if not provided)
            
        Returns:
            Tuple of (response message, session_id)
            
        Raises:
            ChatError: If sending fails
        """
        if not self._connected:
            raise ConnectionError("Not connected to daemon")
        
        # Use provided session or current
        use_session_id = session_id or self._current_session_id
        
        try:
            # Send via chat client
            response, new_session_id = await self._chat_client.send_prompt(
                prompt=content,
                session_id=use_session_id,
                model=self.model
            )
            
            # Update current session
            if new_session_id:
                self._current_session_id = new_session_id
            
            # Create response message
            response_msg = ChatMessage(
                content=response,
                sender="assistant",
                timestamp=datetime.now(),
                session_id=new_session_id or use_session_id,
            )
            
            # Update metrics
            self.total_messages += 2  # User + assistant
            
            # Estimate tokens (rough)
            tokens = len(content.split()) + len(response.split())
            self.total_tokens += int(tokens * 1.3)
            self.total_cost += tokens * 0.00001
            
            # Notify handlers
            user_msg = ChatMessage(
                content=content,
                sender="user",
                timestamp=datetime.now(),
                session_id=new_session_id or use_session_id,
            )
            self._notify_handlers(user_msg)
            self._notify_handlers(response_msg)
            
            return response_msg, new_session_id or use_session_id
            
        except asyncio.TimeoutError:
            raise ChatError("Request timed out")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise ChatError(f"Failed to send message: {str(e)}")
    
    async def start_new_session(self) -> str:
        """
        Start a new chat session.
        
        Returns:
            New session ID
        """
        self._current_session_id = None
        # First message will create new session
        return "new_session"
    
    async def resume_session(self, session_id: str) -> bool:
        """
        Resume an existing session.
        
        Args:
            session_id: Session to resume
            
        Returns:
            True if session exists and can be resumed
        """
        # Verify session exists
        sessions = await self.list_sessions(limit=100)
        if any(s.session_id == session_id for s in sessions):
            self._current_session_id = session_id
            return True
        return False
    
    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ChatSession]:
        """
        List available chat sessions.
        
        Args:
            limit: Maximum sessions to return
            offset: Offset for pagination
            
        Returns:
            List of chat sessions
        """
        if not self._connected:
            return []
        
        try:
            # Query conversation service
            result = await self._event_client.request_event("conversation:list", {
                "limit": limit,
                "offset": offset,
                "sort_by": "last_timestamp",
                "reverse": True,
            })
            
            sessions = []
            for conv in result.get("conversations", []):
                session = ChatSession(
                    session_id=conv.get("session_id", ""),
                    started_at=datetime.fromisoformat(conv.get("first_timestamp", datetime.now().isoformat())),
                    last_activity=datetime.fromisoformat(conv.get("last_timestamp", datetime.now().isoformat())),
                    message_count=conv.get("message_count", 0),
                )
                sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[ChatMessage]:
        """
        Get messages from a session.
        
        Args:
            session_id: Session to load
            limit: Maximum messages to return
            
        Returns:
            List of messages in chronological order
        """
        if not self._connected:
            return []
        
        try:
            # Query conversation service
            result = await self._event_client.request_event("conversation:get", {
                "session_id": session_id,
                "limit": limit,
            })
            
            messages = []
            for msg_data in result.get("messages", []):
                message = ChatMessage(
                    content=msg_data.get("content", ""),
                    sender=msg_data.get("sender", "unknown"),
                    timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.now().isoformat())),
                    session_id=session_id,
                )
                messages.append(message)
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get session messages: {e}")
            return []
    
    async def export_session(
        self,
        session_id: str,
        format: str = "markdown",
    ) -> Optional[str]:
        """
        Export a session to file.
        
        Args:
            session_id: Session to export
            format: Export format (markdown or json)
            
        Returns:
            Path to exported file
        """
        if not self._connected:
            return None
        
        try:
            result = await self._event_client.request_event("conversation:export", {
                "session_id": session_id,
                "format": format,
            })
            
            if "error" not in result:
                return result.get("export_path")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return None
    
    async def search_sessions(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search across all sessions.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of search results
        """
        if not self._connected:
            return []
        
        try:
            result = await self._event_client.request_event("conversation:search", {
                "query": query,
                "limit": limit,
            })
            
            return result.get("results", [])
            
        except Exception as e:
            logger.error(f"Failed to search sessions: {e}")
            return []
    
    def add_message_handler(self, handler: Callable[[ChatMessage], None]) -> None:
        """Add a handler for new messages."""
        self._message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable[[ChatMessage], None]) -> None:
        """Remove a message handler."""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)
    
    def _notify_handlers(self, message: ChatMessage) -> None:
        """Notify all handlers of a new message."""
        for handler in self._message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()