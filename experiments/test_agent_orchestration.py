#!/usr/bin/env python3
"""
Test Agent Orchestration
========================

Minimal test to verify agent-directed orchestration works end-to-end.
"""

import time
import json
from ksi_common.sync_client import MinimalSyncClient


def test_agent_spawning_agent():
    """Test that an agent can spawn another agent."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: Agent Spawning Agent ===")
    
    # Create parent agent with researcher profile (has spawn_agents capability)
    print("\n1. Creating parent agent with spawn capability...")
    result = client.send_event("agent:spawn", {
        "agent_id": "parent_agent",
        "component": "components/core/base_agent", 
        "permission_profile": "researcher",
        "task": "Spawn a child agent",
        "prompt": """You are a parent agent. Your task is to spawn a child agent.

Use the KSI tool use pattern to spawn an agent:
{
  "type": "ksi_tool_use",
  "id": "spawn_child",
  "name": "agent:spawn",
  "input": {
    "agent_id": "child_agent",
    "component": "components/core/base_agent",
    "task": "Be a helpful child agent",
    "prompt": "You are a child agent. Say 'Hello from child!'"
  }
}

After spawning, emit a state:set event to confirm:
{
  "type": "ksi_tool_use",
  "id": "confirm_spawn",
  "name": "state:set",
  "input": {
    "key": "spawn_test_result",
    "value": "child_spawned"
  }
}"""
    })
    
    if result.get("status") == "created":
        print(f"✓ Parent agent created")
    else:
        print(f"✗ Failed: {result}")
        return False
    
    # Wait a bit for the parent to spawn child
    print("\n2. Waiting for parent to spawn child...")
    time.sleep(5)
    
    # Check if child was spawned
    agents = client.send_event("agent:list", {})
    child_exists = any(a["agent_id"] == "child_agent" for a in agents.get("agents", []))
    
    if child_exists:
        print("✓ Child agent successfully spawned by parent!")
    else:
        print("✗ Child agent not found")
    
    # Check state confirmation
    state_result = client.send_event("state:get", {
        "key": "spawn_test_result"
    })
    
    if state_result.get("value") == "child_spawned":
        print("✓ Parent confirmed spawn via state:set")
    else:
        print("✗ No confirmation in state")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "parent_agent"})
    client.send_event("agent:terminate", {"agent_id": "child_agent"})
    client.send_event("state:delete", {"key": "spawn_test_result"})
    
    return child_exists


def test_agent_communication():
    """Test agents communicating via completion:async."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: Agent-to-Agent Communication ===")
    
    # Create sender agent
    print("\n1. Creating sender agent...")
    client.send_event("agent:spawn", {
        "agent_id": "sender",
        "component": "components/core/base_agent",
        "task": "Send messages",
        "prompt": """You are a sender agent. Send a message to the receiver.

Use KSI tool use to send a message via completion:async:
{
  "type": "ksi_tool_use",
  "id": "send_msg",
  "name": "completion:async",
  "input": {
    "agent_id": "receiver",
    "prompt": "Message from sender: Please acknowledge by setting state key 'message_received' to 'yes'"
  }
}

Then confirm you sent it:
{
  "type": "ksi_tool_use",
  "id": "confirm_sent",
  "name": "state:set",
  "input": {
    "key": "message_sent",
    "value": "yes"
  }
}"""
    })
    
    # Create receiver agent
    print("2. Creating receiver agent...")
    client.send_event("agent:spawn", {
        "agent_id": "receiver",
        "component": "components/core/base_agent",
        "task": "Receive messages",
        "prompt": """You are a receiver agent. When you receive a message, acknowledge it.

If asked to acknowledge, use:
{
  "type": "ksi_tool_use",
  "id": "acknowledge",
  "name": "state:set",
  "input": {
    "key": "message_received",
    "value": "yes"
  }
}"""
    })
    
    print("\n3. Waiting for communication...")
    time.sleep(5)
    
    # Check results
    sent = client.send_event("state:get", {"key": "message_sent"})
    received = client.send_event("state:get", {"key": "message_received"})
    
    if sent.get("value") == "yes":
        print("✓ Sender confirmed message sent")
    else:
        print("✗ Sender didn't confirm")
    
    if received.get("value") == "yes":
        print("✓ Receiver acknowledged message!")
    else:
        print("✗ Receiver didn't acknowledge")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "sender"})
    client.send_event("agent:terminate", {"agent_id": "receiver"})
    client.send_event("state:delete", {"key": "message_sent"})
    client.send_event("state:delete", {"key": "message_received"})
    
    return received.get("value") == "yes"


def test_simple_prisoners_dilemma():
    """Test a simple 1-round Prisoners Dilemma with agent orchestration."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: Simple Agent-Orchestrated Prisoners Dilemma ===")
    
    # Create game master
    print("\n1. Creating game master...")
    client.send_event("agent:spawn", {
        "agent_id": "game_master",
        "component": "components/core/base_agent",
        "permission_profile": "researcher",
        "task": "Run Prisoners Dilemma",
        "prompt": """You are the game master. Run a 1-round Prisoners Dilemma.

Step 1: Spawn player 1 (always cooperates):
{
  "type": "ksi_tool_use",
  "id": "spawn_p1",
  "name": "agent:spawn",
  "input": {
    "agent_id": "player_1",
    "component": "components/strategies/always_cooperate",
    "task": "Play Prisoners Dilemma"
  }
}

Step 2: Spawn player 2 (always defects):
{
  "type": "ksi_tool_use",
  "id": "spawn_p2",
  "name": "agent:spawn",
  "input": {
    "agent_id": "player_2",
    "component": "components/core/base_agent",
    "task": "Play Prisoners Dilemma",
    "prompt": "Always choose DEFECT"
  }
}

Step 3: Get decisions (use completion:async):
{
  "type": "ksi_tool_use",
  "id": "ask_p1",
  "name": "completion:async",
  "input": {
    "agent_id": "player_1",
    "prompt": "Choose: COOPERATE or DEFECT"
  }
}

{
  "type": "ksi_tool_use",
  "id": "ask_p2",
  "name": "completion:async",
  "input": {
    "agent_id": "player_2",
    "prompt": "Choose: COOPERATE or DEFECT"
  }
}

Step 4: Record that game started:
{
  "type": "ksi_tool_use",
  "id": "record",
  "name": "state:set",
  "input": {
    "key": "pd_game_status",
    "value": "started"
  }
}"""
    })
    
    print("\n2. Waiting for game to run...")
    time.sleep(8)
    
    # Check results
    agents = client.send_event("agent:list", {})
    player1_exists = any(a["agent_id"] == "player_1" for a in agents.get("agents", []))
    player2_exists = any(a["agent_id"] == "player_2" for a in agents.get("agents", []))
    
    game_status = client.send_event("state:get", {"key": "pd_game_status"})
    
    print("\n3. Results:")
    if player1_exists:
        print("✓ Player 1 spawned")
    else:
        print("✗ Player 1 not spawned")
        
    if player2_exists:
        print("✓ Player 2 spawned")
    else:
        print("✗ Player 2 not spawned")
    
    if game_status.get("value") == "started":
        print("✓ Game master confirmed game started")
    else:
        print("✗ Game not started")
    
    # Cleanup
    for agent_id in ["game_master", "player_1", "player_2"]:
        client.send_event("agent:terminate", {"agent_id": agent_id})
    client.send_event("state:delete", {"key": "pd_game_status"})
    
    return player1_exists and player2_exists


if __name__ == "__main__":
    print("\n" + "="*80)
    print("AGENT ORCHESTRATION VALIDATION TESTS")
    print("="*80)
    
    # Run tests
    test1 = test_agent_spawning_agent()
    test2 = test_agent_communication()
    test3 = test_simple_prisoners_dilemma()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Agent spawning agent: {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Agent communication: {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"Simple PD orchestration: {'✓ PASS' if test3 else '✗ FAIL'}")
    
    if test1 and test2 and test3:
        print("\n🎉 ALL TESTS PASSED - Agent orchestration is working!")
    else:
        print("\n⚠️ Some tests failed - debugging needed")