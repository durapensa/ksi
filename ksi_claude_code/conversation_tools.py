"""
Conversation tools for managing agent conversations in KSI.

These tools help track active conversations, export them, and find
relevant sessions to continue.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .ksi_base_tool import KSIBaseTool
import logging

logger = logging.getLogger(__name__)


class ConversationTool(KSIBaseTool):
    """Manage and query agent conversations"""
    
    name = "ksi_conversation"
    description = "List, search, and export agent conversations"
    
    async def get_active_conversations(
        self,
        max_age_hours: int = 24,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get recently active conversations
        
        Args:
            max_age_hours: Maximum age in hours
            limit: Maximum number to return
            
        Returns:
            Dictionary with active conversations
        """
        response = await self.send_event(
            "conversation:active",
            {
                "max_age_hours": max_age_hours,
                "limit": limit
            }
        )
        
        if not response.get("success", False):
            logger.error(f"Failed to get active conversations: {response.get('error')}")
            return {"conversations": []}
        
        return {
            "conversations": response.get("conversations", []),
            "total": response.get("total", 0)
        }
    
    async def search_conversations(
        self,
        query: str,
        search_in: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search conversations by content
        
        Args:
            query: Search query
            search_in: Fields to search (prompt, response, all)
            limit: Maximum results
            
        Returns:
            List of matching conversations
        """
        search_data = {
            "query": query,
            "limit": limit
        }
        
        if search_in:
            search_data["search_in"] = search_in
        
        response = await self.send_event(
            "conversation:search",
            search_data
        )
        
        if not response.get("success", False):
            logger.error(f"Search failed: {response.get('error')}")
            return []
        
        return response.get("results", [])
    
    async def get_conversation(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get a specific conversation
        
        Args:
            session_id: Session ID to retrieve
            limit: Maximum messages to return
            offset: Message offset
            
        Returns:
            Conversation details and messages
        """
        get_data = {
            "session_id": session_id,
            "offset": offset
        }
        
        if limit:
            get_data["limit"] = limit
        
        response = await self.send_event(
            "conversation:get",
            get_data
        )
        
        if not response.get("success", False):
            logger.error(f"Failed to get conversation: {response.get('error')}")
            return {}
        
        return response.get("conversation", {})
    
    async def export_conversation(
        self,
        session_id: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Export a conversation
        
        Args:
            session_id: Session to export
            format: Export format (json, markdown, text)
            
        Returns:
            Export result with path
        """
        response = await self.send_event(
            "conversation:export",
            {
                "session_id": session_id,
                "format": format
            }
        )
        
        if not response.get("success", False):
            logger.error(f"Export failed: {response.get('error')}")
            return {}
        
        return {
            "path": response.get("export_path"),
            "format": format,
            "size": response.get("size", 0)
        }
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """
        Get conversation statistics
        
        Returns:
            Statistics about conversations
        """
        response = await self.send_event(
            "conversation:stats",
            {}
        )
        
        if not response.get("success", False):
            return {
                "total_conversations": 0,
                "active_last_hour": 0,
                "active_last_day": 0
            }
        
        return response.get("stats", {})
    
    async def find_related_conversations(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find conversations related to a given session
        
        Args:
            session_id: Reference session
            limit: Maximum results
            
        Returns:
            List of related conversations
        """
        # First get the reference conversation
        conv = await self.get_conversation(session_id, limit=1)
        
        if not conv:
            return []
        
        # Extract key terms from the prompt
        prompt = conv.get("messages", [{}])[0].get("prompt", "")
        
        # Search for similar conversations
        # Simple keyword extraction - could be more sophisticated
        keywords = [word for word in prompt.split() if len(word) > 4][:5]
        query = " ".join(keywords)
        
        if query:
            results = await self.search_conversations(query, limit=limit)
            # Filter out the reference conversation
            return [r for r in results if r.get("session_id") != session_id]
        
        return []
    
    async def cleanup_old_conversations(
        self,
        older_than_days: int = 30
    ) -> Dict[str, Any]:
        """
        Clean up old conversations (if supported)
        
        Args:
            older_than_days: Age threshold
            
        Returns:
            Cleanup results
        """
        response = await self.send_event(
            "conversation:cleanup",
            {
                "older_than_days": older_than_days
            }
        )
        
        return {
            "success": response.get("success", False),
            "cleaned": response.get("cleaned_count", 0),
            "error": response.get("error")
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["active", "search", "get", "export", "stats"],
                        "description": "Action to perform"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID (for get/export)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (for search)"
                    },
                    "max_age_hours": {
                        "type": "integer",
                        "description": "Maximum age in hours (for active)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown", "text"],
                        "description": "Export format"
                    }
                },
                "required": ["action"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute conversation operation"""
        action = kwargs.get("action", "active")
        
        if action == "active":
            return await self.get_active_conversations(
                max_age_hours=kwargs.get("max_age_hours", 24)
            )
        
        elif action == "search":
            query = kwargs.get("query")
            if not query:
                raise ValueError("Query required for search action")
            
            results = await self.search_conversations(query)
            return {"results": results}
        
        elif action == "get":
            session_id = kwargs.get("session_id")
            if not session_id:
                raise ValueError("Session ID required for get action")
            
            return await self.get_conversation(session_id)
        
        elif action == "export":
            session_id = kwargs.get("session_id")
            if not session_id:
                raise ValueError("Session ID required for export action")
            
            return await self.export_conversation(
                session_id,
                format=kwargs.get("format", "json")
            )
        
        elif action == "stats":
            return await self.get_conversation_stats()
        
        else:
            raise ValueError(f"Unknown action: {action}")