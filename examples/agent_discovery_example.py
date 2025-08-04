#!/usr/bin/env python3
"""Example of how agents use the dual-path discovery system."""

import asyncio
import json
from ksi_common.sync_client import send_event_sync


def demonstrate_agent_discovery():
    """Show how agents interact with the discovery system."""
    
    print("=== Agent Discovery Example ===\n")
    
    # 1. Create a test component that uses discovery
    print("1. Creating agent component that uses discovery...")
    result = send_event_sync("composition:create_component", {
        "name": "discovery_user_agent",
        "content": """---
component_type: core
name: discovery_user_agent
---
You are an agent that helps users discover KSI capabilities.

When asked about available events or namespaces, use the ksi_tool_use pattern:

{
  "type": "ksi_tool_use",
  "id": "ksiu_discover_001",
  "name": "system:discover",
  "input": {
    "namespace": "agent",
    "level": "namespace"
  }
}

The response will be in ksi_tool_use format with discovery results.
"""
    })
    print(f"Created component: {result.get('status')}\n")
    
    # 2. Spawn agent with discovery capability
    print("2. Spawning agent with base capability (includes discovery)...")
    spawn_result = send_event_sync("agent:spawn", {
        "component": "discovery_user_agent",
        "capabilities": ["base", "state_read"]  # base includes system:discover
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Spawned agent: {agent_id}")
    print(f"Allowed events: {json.dumps(spawn_result.get('config', {}).get('allowed_events', []), indent=2)}\n")
    
    # 3. Ask agent to discover
    print("3. Asking agent to discover agent namespace events...")
    completion_result = send_event_sync("completion:async", {
        "agent_id": agent_id,
        "prompt": "Please discover what events are available in the 'agent' namespace using the system:discover event."
    })
    request_id = completion_result.get("request_id")
    print(f"Request queued: {request_id}\n")
    
    # 4. Wait and get result
    print("4. Waiting for agent response...")
    import time
    time.sleep(3)
    
    response = send_event_sync("completion:get", {
        "request_id": request_id
    })
    
    if response.get("status") == "completed":
        print("Agent response:")
        print(response.get("result", "No result"))
    else:
        print(f"Status: {response.get('status')}")
        print("Note: Agent would receive ksi_tool_use format internally")
    
    # 5. Clean up
    print("\n5. Cleaning up...")
    send_event_sync("agent:terminate", {"agent_id": agent_id})
    print("Agent terminated")


if __name__ == "__main__":
    print("Dual-Path JSON Discovery Integration Example")
    print("=" * 50)
    print("\nThis example shows how agents interact with the discovery system.")
    print("Agents receive ksi_tool_use format while CLI tools get standard format.\n")
    
    demonstrate_agent_discovery()
    
    print("\n" + "=" * 50)
    print("Example complete!")