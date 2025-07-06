#!/usr/bin/env python3
"""
Safety utilities for KSI experiments.

Provides guardrails to prevent runaway agent spawning and resource exhaustion
during experimental work with multi-agent systems.
"""

import asyncio
import time
import json
import socket
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict

class ExperimentSafetyGuard:
    """
    Safety guard for KSI experiments with agent spawn and resource limits.
    
    Features:
    - Global agent count limits
    - Spawn depth tracking
    - Rate limiting for spawns
    - Agent timeout monitoring
    - Automatic cleanup of old agents
    """
    
    def __init__(self, 
                 max_agents: int = 10,
                 max_spawn_depth: int = 3,
                 max_children_per_agent: int = 5,
                 agent_timeout: int = 300,  # 5 minutes
                 spawn_cooldown: float = 1.0,  # seconds between spawns
                 socket_path: str = "var/run/daemon.sock"):
        
        self.max_agents = max_agents
        self.max_spawn_depth = max_spawn_depth
        self.max_children_per_agent = max_children_per_agent
        self.agent_timeout = agent_timeout
        self.spawn_cooldown = spawn_cooldown
        self.socket_path = socket_path
        
        # Tracking state
        self.agent_spawn_times: Dict[str, float] = {}
        self.agent_parents: Dict[str, Optional[str]] = {}
        self.agent_children: Dict[str, List[str]] = defaultdict(list)
        self.last_spawn_time: float = 0
        self.terminated_agents: set = set()
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Export safety limits as dict for agent metadata."""
        return {
            "max_agents": self.max_agents,
            "max_spawn_depth": self.max_spawn_depth,
            "max_children_per_agent": self.max_children_per_agent,
            "agent_timeout": self.agent_timeout,
            "spawn_cooldown": self.spawn_cooldown
        }
    
    def send_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Send command via Unix socket."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        sock.sendall(json.dumps(cmd).encode() + b'\n')
        
        # Read response
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            try:
                json.loads(response.decode())
                break
            except:
                continue
        
        sock.close()
        return json.loads(response.decode())
    
    async def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of active agents from daemon."""
        result = await asyncio.to_thread(
            self.send_command,
            {"event": "agent:list", "data": {}}
        )
        return result.get("data", {}).get("agents", [])
    
    async def terminate_agent(self, agent_id: str, reason: str = "Safety limit"):
        """Terminate an agent."""
        if agent_id in self.terminated_agents:
            return  # Already terminated
            
        print(f"[Safety] Terminating agent {agent_id}: {reason}")
        
        try:
            await asyncio.to_thread(
                self.send_command,
                {"event": "agent:terminate", "data": {"agent_id": agent_id}}
            )
            self.terminated_agents.add(agent_id)
            
            # Clean up tracking
            if agent_id in self.agent_spawn_times:
                del self.agent_spawn_times[agent_id]
            if agent_id in self.agent_parents:
                parent = self.agent_parents[agent_id]
                if parent and parent in self.agent_children:
                    self.agent_children[parent].remove(agent_id)
                del self.agent_parents[agent_id]
                
        except Exception as e:
            print(f"[Safety] Error terminating {agent_id}: {e}")
    
    async def calculate_spawn_depth(self, agent_id: str) -> int:
        """Calculate the spawn depth of an agent."""
        depth = 0
        current = agent_id
        
        while current in self.agent_parents:
            parent = self.agent_parents[current]
            if parent is None:
                break
            depth += 1
            current = parent
            
            # Prevent infinite loops
            if depth > 10:
                print(f"[Safety] Warning: Depth calculation exceeded 10 for {agent_id}")
                break
        
        return depth
    
    async def check_spawn_allowed(self, 
                                  parent_id: Optional[str] = None,
                                  profile: str = "unknown") -> Tuple[bool, str]:
        """
        Check if spawning a new agent is allowed.
        
        Returns:
            (allowed, reason) tuple
        """
        # Check rate limiting
        current_time = time.time()
        if current_time - self.last_spawn_time < self.spawn_cooldown:
            return False, f"Spawn cooldown active (wait {self.spawn_cooldown}s between spawns)"
        
        # Check total agent count
        agents = await self.get_agent_list()
        active_count = len([a for a in agents if a['agent_id'] not in self.terminated_agents])
        
        if active_count >= self.max_agents:
            return False, f"Max agent limit reached ({active_count}/{self.max_agents})"
        
        # Check spawn depth if parent provided
        if parent_id:
            depth = await self.calculate_spawn_depth(parent_id)
            if depth >= self.max_spawn_depth - 1:  # -1 because we're about to add one
                return False, f"Max spawn depth reached (current: {depth}, max: {self.max_spawn_depth})"
            
            # Check children per agent
            children_count = len(self.agent_children.get(parent_id, []))
            if children_count >= self.max_children_per_agent:
                return False, f"Max children per agent reached ({children_count}/{self.max_children_per_agent})"
        
        return True, "Spawn allowed"
    
    def record_spawn(self, agent_id: str, parent_id: Optional[str] = None):
        """Record that an agent was spawned."""
        current_time = time.time()
        self.agent_spawn_times[agent_id] = current_time
        self.last_spawn_time = current_time
        
        if parent_id:
            self.agent_parents[agent_id] = parent_id
            self.agent_children[parent_id].append(agent_id)
        else:
            self.agent_parents[agent_id] = None
    
    async def monitor_agents(self):
        """
        Background task to monitor and cleanup old agents.
        Runs every 30 seconds.
        """
        print("[Safety] Starting agent monitor")
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = time.time()
                agents = await self.get_agent_list()
                
                # Build set of active agent IDs
                active_ids = {a['agent_id'] for a in agents}
                
                # Check for timeout violations
                for agent in agents:
                    agent_id = agent['agent_id']
                    
                    # Skip if already terminated
                    if agent_id in self.terminated_agents:
                        continue
                    
                    # Check spawn time
                    if agent_id in self.agent_spawn_times:
                        age = current_time - self.agent_spawn_times[agent_id]
                        if age > self.agent_timeout:
                            await self.terminate_agent(agent_id, f"Timeout ({age:.0f}s > {self.agent_timeout}s)")
                    else:
                        # Agent not tracked, add it with current time
                        self.agent_spawn_times[agent_id] = current_time
                
                # Clean up tracking for agents that no longer exist
                tracked_ids = set(self.agent_spawn_times.keys())
                for agent_id in tracked_ids - active_ids:
                    if agent_id in self.agent_spawn_times:
                        del self.agent_spawn_times[agent_id]
                    if agent_id in self.agent_parents:
                        del self.agent_parents[agent_id]
                
                # Report status
                active_count = len(active_ids - self.terminated_agents)
                if active_count > 0:
                    print(f"[Safety] Monitor: {active_count} active agents")
                    
            except Exception as e:
                print(f"[Safety] Monitor error: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def start_monitoring(self):
        """Start the background monitoring task."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self.monitor_agents())
    
    async def stop_monitoring(self):
        """Stop the background monitoring task."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    async def cleanup_all_agents(self):
        """Terminate all tracked agents."""
        print("[Safety] Cleaning up all agents")
        
        agents = await self.get_agent_list()
        for agent in agents:
            agent_id = agent['agent_id']
            if agent_id not in self.terminated_agents:
                await self.terminate_agent(agent_id, "Experiment cleanup")
    
    def get_safety_report(self) -> Dict[str, Any]:
        """Get current safety status report."""
        return {
            "limits": self.to_dict(),
            "active_agents": len(self.agent_spawn_times) - len(self.terminated_agents),
            "terminated_agents": len(self.terminated_agents),
            "spawn_tree": self._build_spawn_tree(),
            "oldest_agent": self._get_oldest_agent()
        }
    
    def _build_spawn_tree(self) -> Dict[str, Any]:
        """Build a tree representation of agent relationships."""
        # Find root agents (no parent)
        roots = [aid for aid, parent in self.agent_parents.items() 
                 if parent is None and aid not in self.terminated_agents]
        
        def build_subtree(agent_id: str) -> Dict[str, Any]:
            children = self.agent_children.get(agent_id, [])
            active_children = [c for c in children if c not in self.terminated_agents]
            
            return {
                "id": agent_id,
                "children": [build_subtree(c) for c in active_children]
            }
        
        # Calculate max depth synchronously
        max_depth = 0
        for aid in self.agent_parents.keys():
            if aid not in self.terminated_agents:
                depth = 0
                current = aid
                while current in self.agent_parents and self.agent_parents[current]:
                    depth += 1
                    current = self.agent_parents[current]
                    if depth > 10:  # Prevent infinite loops
                        break
                max_depth = max(max_depth, depth)
        
        return {
            "roots": [build_subtree(r) for r in roots],
            "total_depth": max_depth
        }
    
    def _get_oldest_agent(self) -> Optional[Dict[str, Any]]:
        """Get the oldest active agent."""
        active_agents = [(aid, spawn_time) 
                        for aid, spawn_time in self.agent_spawn_times.items()
                        if aid not in self.terminated_agents]
        
        if not active_agents:
            return None
        
        oldest_id, oldest_time = min(active_agents, key=lambda x: x[1])
        age = time.time() - oldest_time
        
        return {
            "agent_id": oldest_id,
            "age_seconds": age,
            "age_formatted": f"{age/60:.1f} minutes"
        }


class SafeSpawnContext:
    """
    Context manager for safe agent spawning.
    
    Usage:
        safety = ExperimentSafetyGuard()
        
        async with SafeSpawnContext(safety) as ctx:
            # Spawning happens here
            agent = await ctx.spawn_agent(...)
    """
    
    def __init__(self, safety_guard: ExperimentSafetyGuard):
        self.safety = safety_guard
        self.spawned_agents: List[str] = []
    
    async def __aenter__(self):
        await self.safety.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup on exit
        if exc_type is not None:
            print(f"[Safety] Error in spawn context: {exc_type.__name__}: {exc_val}")
        
        await self.safety.stop_monitoring()
        
        # Optionally cleanup spawned agents
        if exc_type is not None:  # On error, cleanup
            for agent_id in self.spawned_agents:
                await self.safety.terminate_agent(agent_id, "Context error cleanup")
    
    async def spawn_agent(self, 
                         profile: str,
                         prompt: str,
                         parent_id: Optional[str] = None,
                         **kwargs) -> Dict[str, Any]:
        """Spawn an agent with safety checks."""
        # Check if allowed
        allowed, reason = await self.safety.check_spawn_allowed(parent_id, profile)
        if not allowed:
            raise RuntimeError(f"Spawn blocked: {reason}")
        
        # Inject safety metadata
        metadata = kwargs.get("metadata", {})
        metadata["safety_limits"] = self.safety.to_dict()
        metadata["spawn_time"] = time.time()
        metadata["parent_id"] = parent_id
        kwargs["metadata"] = metadata
        
        # Perform spawn
        result = await asyncio.to_thread(
            self.safety.send_command,
            {
                "event": "agent:spawn",
                "data": {
                    "profile": profile,
                    "prompt": prompt,
                    **kwargs
                }
            }
        )
        
        # Record spawn
        if "data" in result and "agent_id" in result["data"]:
            agent_id = result["data"]["agent_id"]
            self.safety.record_spawn(agent_id, parent_id)
            self.spawned_agents.append(agent_id)
            print(f"[Safety] Spawned agent {agent_id} (parent: {parent_id or 'root'})")
        
        return result


# Example usage
if __name__ == "__main__":
    async def test_safety():
        """Test the safety system."""
        safety = ExperimentSafetyGuard(
            max_agents=5,
            max_spawn_depth=2,
            agent_timeout=60  # 1 minute for testing
        )
        
        async with SafeSpawnContext(safety) as ctx:
            # Spawn root agent
            result = await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="You are a test agent. Say hello."
            )
            
            print(f"Spawned: {result}")
            
            # Get safety report
            report = safety.get_safety_report()
            print(f"\nSafety Report: {json.dumps(report, indent=2)}")
            
            # Wait a bit
            await asyncio.sleep(5)
            
            # Try to spawn too many
            try:
                for i in range(10):
                    await ctx.spawn_agent(
                        profile="base_single_agent",
                        prompt=f"Test agent {i}"
                    )
            except RuntimeError as e:
                print(f"\nExpected error: {e}")
            
            # Final report
            report = safety.get_safety_report()
            print(f"\nFinal Report: {json.dumps(report, indent=2)}")
    
    # Run test
    asyncio.run(test_safety())