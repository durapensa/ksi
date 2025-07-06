"""
KSI State Management Tools for Claude Code

Provides tools for managing shared state via KSI's simple key-value store.
"""
from typing import Dict, Any, Optional, List, Union
from .ksi_base_tool import KSIBaseTool
import logging
import json

logger = logging.getLogger(__name__)


class StateManagementTool(KSIBaseTool):
    """Manage shared state via KSI's key-value store"""
    
    name = "ksi_state"
    description = "Get, set, and query shared state"
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Set a value in shared state
        
        Args:
            key: State key
            value: Value to store (will be JSON serialized)
            ttl: Optional time-to-live in seconds
            
        Returns:
            Success result
        """
        set_data = {
            "key": key,
            "value": value
        }
        
        if ttl:
            set_data["ttl"] = ttl
        
        logger.info(f"Setting state key: {key}")
        
        response = await self.send_event("state:set", set_data)
        
        if not response.get("success", False):
            error = response.get("error", "Unknown error")
            raise RuntimeError(f"Failed to set state: {error}")
        
        return {"success": True, "key": key}
    
    async def get(
        self,
        key: str,
        default: Optional[Any] = None
    ) -> Any:
        """
        Get a value from shared state
        
        Args:
            key: State key
            default: Default value if key not found
            
        Returns:
            Stored value or default
        """
        response = await self.send_event(
            "state:get",
            {"key": key}
        )
        
        if not response.get("success", False):
            logger.debug(f"Key not found: {key}")
            return default
        
        return response.get("value", default)
    
    async def delete(self, key: str) -> Dict[str, Any]:
        """
        Delete a key from shared state
        
        Args:
            key: State key to delete
            
        Returns:
            Deletion result
        """
        response = await self.send_event(
            "state:delete",
            {"key": key}
        )
        
        return {
            "success": response.get("success", False),
            "deleted": response.get("deleted", False)
        }
    
    async def query_pattern(
        self,
        pattern: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query state keys by pattern
        
        Args:
            pattern: Pattern to match (e.g., "project:*")
            limit: Maximum keys to return
            
        Returns:
            Dictionary of matching key-value pairs
        """
        query_data = {"pattern": pattern}
        if limit:
            query_data["limit"] = limit
        
        response = await self.send_event(
            "state:query",
            query_data
        )
        
        if not response.get("success", False):
            logger.error(f"Query failed: {response.get('error')}")
            return {}
        
        return response.get("results", {})
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists
        
        Args:
            key: State key
            
        Returns:
            True if key exists
        """
        response = await self.send_event(
            "state:exists",
            {"key": key}
        )
        
        return response.get("exists", False)
    
    async def increment(
        self,
        key: str,
        amount: int = 1
    ) -> int:
        """
        Increment a numeric value
        
        Args:
            key: State key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        response = await self.send_event(
            "state:increment",
            {
                "key": key,
                "amount": amount
            }
        )
        
        if not response.get("success", False):
            raise RuntimeError(f"Failed to increment: {response.get('error')}")
        
        return response.get("value", 0)
    
    async def append(
        self,
        key: str,
        value: Any
    ) -> List[Any]:
        """
        Append to a list value
        
        Args:
            key: State key
            value: Value to append
            
        Returns:
            Updated list
        """
        current = await self.get(key, [])
        if not isinstance(current, list):
            current = [current] if current is not None else []
        
        current.append(value)
        await self.set(key, current)
        
        return current
    
    async def update_dict(
        self,
        key: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a dictionary value
        
        Args:
            key: State key
            updates: Dictionary updates to merge
            
        Returns:
            Updated dictionary
        """
        current = await self.get(key, {})
        if not isinstance(current, dict):
            current = {}
        
        current.update(updates)
        await self.set(key, current)
        
        return current
    
    async def list_keys(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """
        List all keys or keys with prefix
        
        Args:
            prefix: Optional key prefix
            limit: Maximum keys to return
            
        Returns:
            List of keys
        """
        pattern = f"{prefix}*" if prefix else "*"
        results = await self.query_pattern(pattern, limit)
        
        return list(results.keys())
    
    async def clear_pattern(
        self,
        pattern: str
    ) -> int:
        """
        Delete all keys matching a pattern
        
        Args:
            pattern: Pattern to match
            
        Returns:
            Number of keys deleted
        """
        # Get matching keys
        results = await self.query_pattern(pattern)
        
        # Delete each key
        deleted = 0
        for key in results:
            result = await self.delete(key)
            if result.get("deleted", False):
                deleted += 1
        
        logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
        return deleted
    
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
                        "enum": ["get", "set", "delete", "query", "exists"],
                        "description": "State operation to perform"
                    },
                    "key": {
                        "type": "string",
                        "description": "State key"
                    },
                    "value": {
                        "type": ["string", "number", "object", "array", "boolean", "null"],
                        "description": "Value to store (for set)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Pattern for query (e.g., 'project:*')"
                    }
                },
                "required": ["action"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute state operation"""
        action = kwargs.get("action", "get")
        
        if action == "get":
            key = kwargs.get("key")
            if not key:
                raise ValueError("Key required for get action")
            value = await self.get(key, kwargs.get("default"))
            return {"value": value}
        
        elif action == "set":
            key = kwargs.get("key")
            value = kwargs.get("value")
            if not key:
                raise ValueError("Key required for set action")
            return await self.set(key, value)
        
        elif action == "delete":
            key = kwargs.get("key")
            if not key:
                raise ValueError("Key required for delete action")
            return await self.delete(key)
        
        elif action == "query":
            pattern = kwargs.get("pattern", "*")
            results = await self.query_pattern(pattern)
            return {"results": results}
        
        elif action == "exists":
            key = kwargs.get("key")
            if not key:
                raise ValueError("Key required for exists action")
            exists = await self.exists(key)
            return {"exists": exists}
        
        else:
            raise ValueError(f"Unknown action: {action}")


# Convenience aliases for backward compatibility
StateQueryTool = StateManagementTool
StateWriteTool = StateManagementTool