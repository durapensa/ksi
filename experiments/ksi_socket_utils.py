#!/usr/bin/env python3
"""
KSI socket communication utilities for experiments.

Provides reliable direct socket communication to KSI daemon,
bypassing the broken EventClient discovery mechanism.
"""

import json
import socket
import asyncio
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from pathlib import Path


class KSISocketClient:
    """
    Direct socket client for KSI daemon communication.
    
    More reliable than EventClient for experiments.
    """
    
    def __init__(self, socket_path: str = "var/run/daemon.sock"):
        self.socket_path = socket_path
        
    def send_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send command and receive response via Unix socket.
        
        Args:
            cmd: Command dict with 'event' and 'data' keys
            
        Returns:
            Response dict
            
        Raises:
            ConnectionError: If daemon not running
            json.JSONDecodeError: If response malformed
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        try:
            sock.connect(self.socket_path)
            
            # Send command
            message = json.dumps(cmd) + '\n'
            sock.sendall(message.encode())
            
            # Read response
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                
                # Try to parse as complete JSON
                try:
                    result = json.loads(response.decode())
                    return result
                except json.JSONDecodeError:
                    # Keep reading
                    continue
            
            # If we get here, connection closed without complete response
            if response:
                # Try to parse what we have
                return json.loads(response.decode())
            else:
                raise ConnectionError("No response from daemon")
                
        finally:
            sock.close()
    
    async def send_command_async(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of send_command using thread pool."""
        return await asyncio.to_thread(self.send_command, cmd)
    
    def check_health(self) -> bool:
        """Check if daemon is healthy."""
        try:
            result = self.send_command({"event": "system:health", "data": {}})
            return result.get("data", {}).get("status") == "healthy"
        except:
            return False
    
    # High-level convenience methods
    
    async def spawn_agent(self, 
                         profile: str,
                         prompt: str,
                         agent_id: Optional[str] = None,
                         model: str = "claude-cli/sonnet",
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Spawn an agent."""
        data = {
            "profile": profile,
            "prompt": prompt,
            "model": model
        }
        
        if agent_id:
            data["agent_id"] = agent_id
        if metadata:
            data["metadata"] = metadata
            
        return await self.send_command_async({
            "event": "agent:spawn",
            "data": data
        })
    
    async def continue_conversation(self,
                                   session_id: str,
                                   prompt: str,
                                   timeout: int = 300) -> Dict[str, Any]:
        """Continue an agent conversation."""
        return await self.send_command_async({
            "event": "completion:async",
            "data": {
                "session_id": session_id,
                "prompt": prompt,
                "timeout": timeout
            }
        })
    
    async def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of active agents."""
        result = await self.send_command_async({
            "event": "agent:list",
            "data": {}
        })
        return result.get("data", {}).get("agents", [])
    
    async def terminate_agent(self, agent_id: str) -> Dict[str, Any]:
        """Terminate an agent."""
        return await self.send_command_async({
            "event": "agent:terminate",
            "data": {"agent_id": agent_id}
        })
    
    async def get_events(self,
                        event_patterns: Optional[List[str]] = None,
                        since: Optional[float] = None,
                        limit: int = 100,
                        reverse: bool = True) -> List[Dict[str, Any]]:
        """Query event log."""
        data = {
            "limit": limit,
            "reverse": reverse
        }
        
        if event_patterns:
            data["event_patterns"] = event_patterns
        if since:
            data["since"] = since
            
        result = await self.send_command_async({
            "event": "monitor:get_events",
            "data": data
        })
        
        return result.get("data", {}).get("events", [])
    
    async def create_entity(self,
                           entity_type: str,
                           entity_id: Optional[str] = None,
                           properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an entity in the graph database."""
        data = {"type": entity_type}
        
        if entity_id:
            data["id"] = entity_id
        if properties:
            data["properties"] = properties
            
        result = await self.send_command_async({
            "event": "state:entity:create",
            "data": data
        })
        
        return result.get("data", {})
    
    async def create_relationship(self,
                                 from_id: str,
                                 to_id: str,
                                 relationship_type: str,
                                 metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a relationship between entities."""
        data = {
            "from": from_id,
            "to": to_id,
            "type": relationship_type
        }
        
        if metadata:
            data["metadata"] = metadata
            
        result = await self.send_command_async({
            "event": "state:relationship:create",
            "data": data
        })
        
        return result.get("data", {})
    
    async def traverse_graph(self,
                            from_id: str,
                            direction: str = "outgoing",
                            relationship_types: Optional[List[str]] = None,
                            depth: int = 1,
                            include_entities: bool = False) -> Dict[str, Any]:
        """Traverse the graph from an entity."""
        data = {
            "from": from_id,
            "direction": direction,
            "depth": depth,
            "include_entities": include_entities
        }
        
        if relationship_types:
            data["types"] = relationship_types
            
        result = await self.send_command_async({
            "event": "state:graph:traverse",
            "data": data
        })
        
        return result.get("data", {})


class EventStream:
    """
    Stream events from KSI daemon with filtering.
    
    Usage:
        async with EventStream(patterns=["agent:*", "completion:*"]) as stream:
            async for event in stream:
                print(event)
    """
    
    def __init__(self, 
                 patterns: Optional[List[str]] = None,
                 since: Optional[float] = None,
                 poll_interval: float = 1.0,
                 socket_path: str = "var/run/daemon.sock"):
        
        self.patterns = patterns or ["*"]
        self.since = since or time.time()
        self.poll_interval = poll_interval
        self.client = KSISocketClient(socket_path)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def __aenter__(self):
        self._running = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def __aiter__(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield new events as they arrive."""
        last_timestamp = self.since
        
        while self._running:
            try:
                # Query for new events
                events = await self.client.get_events(
                    event_patterns=self.patterns,
                    since=last_timestamp,
                    limit=100,
                    reverse=False  # Oldest first for processing
                )
                
                # Yield new events
                for event in events:
                    yield event
                    
                    # Update timestamp
                    event_time = event.get("timestamp", 0)
                    if event_time > last_timestamp:
                        last_timestamp = event_time
                
                # Brief pause before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"[EventStream] Error: {e}")
                await asyncio.sleep(self.poll_interval * 2)  # Longer pause on error


class BatchProcessor:
    """
    Process commands in batches for efficiency.
    
    Usage:
        async with BatchProcessor() as batch:
            # Queue up commands
            batch.add_entity("user_1", "person", {"name": "Alice"})
            batch.add_entity("user_2", "person", {"name": "Bob"})
            batch.add_relationship("user_1", "user_2", "knows")
            
            # Execute all at once
            results = await batch.execute()
    """
    
    def __init__(self, socket_path: str = "var/run/daemon.sock"):
        self.client = KSISocketClient(socket_path)
        self.commands: List[Dict[str, Any]] = []
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.commands and exc_type is None:
            # Auto-execute remaining commands
            await self.execute()
    
    def add_command(self, event: str, data: Dict[str, Any]):
        """Add a raw command to the batch."""
        self.commands.append({"event": event, "data": data})
    
    def add_entity(self, entity_id: str, entity_type: str, properties: Optional[Dict[str, Any]] = None):
        """Add entity creation to batch."""
        data = {"id": entity_id, "type": entity_type}
        if properties:
            data["properties"] = properties
        self.add_command("state:entity:create", data)
    
    def add_relationship(self, from_id: str, to_id: str, rel_type: str, metadata: Optional[Dict[str, Any]] = None):
        """Add relationship creation to batch."""
        data = {"from": from_id, "to": to_id, "type": rel_type}
        if metadata:
            data["metadata"] = metadata
        self.add_command("state:relationship:create", data)
    
    def add_spawn(self, profile: str, prompt: str, agent_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Add agent spawn to batch."""
        data = {"profile": profile, "prompt": prompt}
        if agent_id:
            data["agent_id"] = agent_id
        if metadata:
            data["metadata"] = metadata
        self.add_command("agent:spawn", data)
    
    async def execute(self) -> List[Dict[str, Any]]:
        """Execute all batched commands."""
        if not self.commands:
            return []
        
        print(f"[Batch] Executing {len(self.commands)} commands")
        
        results = []
        for cmd in self.commands:
            try:
                result = await self.client.send_command_async(cmd)
                results.append(result)
            except Exception as e:
                results.append({
                    "event": cmd["event"],
                    "error": str(e),
                    "data": {}
                })
        
        # Clear commands after execution
        self.commands.clear()
        
        return results


# Utility functions for common patterns

async def wait_for_completion(request_id: str, 
                             timeout: int = 300,
                             poll_interval: float = 2.0,
                             socket_path: str = "var/run/daemon.sock") -> Optional[Dict[str, Any]]:
    """
    Wait for a completion to finish by monitoring the event log.
    
    Returns the completion result or None if timeout.
    """
    client = KSISocketClient(socket_path)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Query event log for completion:result with actual data
        events = await client.get_events(
            event_patterns=["completion:result"],
            since=start_time - 1,  # 1 second before we started
            limit=20,
            reverse=True  # Newest first
        )
        
        # Look for our request_id with actual result data
        for event in events:
            event_data = event.get("data", {})
            if (event_data.get("request_id") == request_id and 
                "result" in event_data):
                # Found the actual result!
                result = event_data["result"]
                # Extract the response text
                response = result.get("response", {})
                return {
                    "request_id": request_id,
                    "response": response.get("result", ""),
                    "session_id": response.get("session_id"),
                    "model": result.get("ksi", {}).get("provider", "unknown"),
                    "usage": response.get("usage", {}),
                    "duration_ms": result.get("ksi", {}).get("duration_ms", 0),
                    "status": "completed"
                }
        
        # Still waiting
        await asyncio.sleep(poll_interval)
    
    return None  # Timeout


async def spawn_and_wait(profile: str,
                        prompt: str,
                        model: str = "claude-cli/sonnet",
                        timeout: int = 300,
                        socket_path: str = "var/run/daemon.sock") -> Optional[Dict[str, Any]]:
    """
    Spawn an agent and wait for initial response.
    
    Returns the completion result or None if failed.
    """
    client = KSISocketClient(socket_path)
    
    # Spawn agent
    spawn_result = await client.spawn_agent(profile, prompt, model=model)
    
    if "error" in spawn_result:
        print(f"Spawn error: {spawn_result['error']}")
        return None
    
    # Extract session ID from spawn result
    session_id = spawn_result.get("data", {}).get("session_id")
    if not session_id:
        print("No session_id in spawn result")
        return None
    
    # Wait for completion
    return await wait_for_completion(session_id, timeout, socket_path=socket_path)


# Example usage
if __name__ == "__main__":
    async def test_socket_client():
        """Test the socket client."""
        client = KSISocketClient()
        
        # Check health
        print("Checking daemon health...")
        if not client.check_health():
            print("Daemon not healthy!")
            return
        
        print("✓ Daemon is healthy")
        
        # Get recent events
        print("\nRecent events:")
        events = await client.get_events(limit=5)
        for event in events:
            print(f"  {event.get('timestamp', 0)}: {event.get('event_name', 'unknown')}")
        
        # List agents
        print("\nActive agents:")
        agents = await client.get_agent_list()
        for agent in agents:
            print(f"  {agent['agent_id']} ({agent.get('profile', 'unknown')})")
        
        # Test batch processing
        print("\nTesting batch operations...")
        async with BatchProcessor() as batch:
            batch.add_entity("test_1", "test_entity", {"value": 1})
            batch.add_entity("test_2", "test_entity", {"value": 2})
            batch.add_relationship("test_1", "test_2", "related_to")
            
            results = await batch.execute()
            print(f"Batch results: {len(results)} operations completed")
        
        # Test event streaming
        print("\nStreaming events for 5 seconds...")
        async with EventStream(patterns=["agent:*", "state:*"]) as stream:
            async def print_events():
                async for event in stream:
                    print(f"  Stream: {event.get('event_name', 'unknown')}")
            
            # Run for 5 seconds
            try:
                await asyncio.wait_for(print_events(), timeout=5.0)
            except asyncio.TimeoutError:
                print("Stream test complete")
    
    # Run test
    asyncio.run(test_socket_client())