#!/usr/bin/env python3
"""
Phase 1: Test two-agent communication.
Identifies technical issues with agent-to-agent messaging.
"""

import json
import time
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("two_agent_test")


def test_two_agent_communication():
    """Test basic agent-to-agent communication patterns."""
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    test_id = f"comm_test_{uuid.uuid4().hex[:6]}"
    
    print("\n" + "="*60)
    print("🧪 PHASE 1: Two-Agent Communication Test")
    print("="*60)
    print(f"Test ID: {test_id}\n")
    
    # Create simple communicator component if not exists
    print("1️⃣ Creating simple communicator component...")
    client.send_event("composition:create_component", {
        "name": "experiments/simple_communicator",
        "content": """---
component_type: agent
name: simple_communicator  
version: 1.0.0
description: Simple agent for communication testing
dependencies:
  - core/base_agent
---

# Simple Communicator Agent

You are agent {{agent_id}}. Your role is to test communication.

## Communication Protocol:
1. When you receive a message from another agent, acknowledge it
2. If asked to send a message, use completion:async to send it
3. Keep responses brief and clear

## Response Format:
When sending messages to other agents, structure your message clearly:
"MESSAGE TO [agent_name]: [your message]"

Remember: You are testing agent-to-agent communication."""
    })
    print("   ✅ Component created/updated")
    
    # Spawn two agents
    print("\n2️⃣ Spawning test agents...")
    agents = []
    for name in ["alice", "bob"]:
        agent_id = f"{name}_{test_id}"
        result = client.send_event("agent:spawn", {
            "agent_id": agent_id,
            "component": "experiments/simple_communicator",
            "capabilities": ["base", "state_write", "completion", "agent_messaging"]
        })
        
        if "error" not in str(result):
            agents.append(agent_id)
            print(f"   ✅ Spawned {agent_id}")
            # Get allowed events for verification
            allowed = len(result.get('config', {}).get('allowed_events', []))
            print(f"      Allowed events: {allowed}")
        else:
            print(f"   ❌ Failed to spawn {agent_id}: {result}")
            return
    
    if len(agents) != 2:
        print("   ❌ Failed to spawn both agents")
        return
    
    alice_id, bob_id = agents
    
    # Set up monitoring for communication
    print("\n3️⃣ Setting up interaction monitoring...")
    client.send_event("routing:add_rule", {
        "rule_id": f"{test_id}_monitor",
        "source_pattern": "completion:*",
        "target": "monitor:log",
        "condition": f"agent_id in ['{alice_id}', '{bob_id}']",
        "mapping": {
            "test_id": test_id,
            "interaction": "agent_communication",
            "from_agent": "{{agent_id}}",
            "event_type": "{{_event_name}}"
        },
        "ttl": 300
    })
    print("   ✅ Monitoring configured")
    
    # Test 1: Direct message from Alice to Bob
    print("\n4️⃣ Test 1: Direct agent-to-agent message...")
    print(f"   Alice ({alice_id}) → Bob ({bob_id})")
    
    msg_result = client.send_event("completion:async", {
        "agent_id": alice_id,
        "prompt": f"Send a greeting message to Bob. Use completion:async to send to agent_id '{bob_id}' with your greeting."
    })
    print(f"   Request sent: {msg_result.get('status')}")
    
    # Wait for processing
    print("   Waiting for message delivery...")
    time.sleep(5)
    
    # Check if Bob received anything
    print("\n5️⃣ Checking Bob's queue for messages...")
    bob_status = client.send_event("completion:status", {})
    
    # Look for completion events
    events = client.send_event("monitor:get_events", {
        "limit": 20,
        "event_patterns": ["completion:*"]
    })
    
    # Analyze communication patterns
    print("\n6️⃣ Analyzing communication patterns...")
    alice_events = []
    bob_events = []
    
    for event in events.get('events', []):
        data = event.get('data', {})
        if data.get('agent_id') == alice_id:
            alice_events.append(event)
        elif data.get('agent_id') == bob_id:
            bob_events.append(event)
    
    print(f"   Alice events: {len(alice_events)}")
    print(f"   Bob events: {len(bob_events)}")
    
    # Test 2: Bidirectional communication
    print("\n7️⃣ Test 2: Bidirectional communication...")
    
    # Bob responds to Alice
    client.send_event("completion:async", {
        "agent_id": bob_id,
        "prompt": f"Send a response back to Alice. Use completion:async to send to agent_id '{alice_id}' thanking her for the greeting."
    })
    
    time.sleep(5)
    
    # Test 3: Check if agents can emit JSON events
    print("\n8️⃣ Test 3: JSON event emission...")
    
    json_test = client.send_event("completion:async", {
        "agent_id": alice_id,
        "prompt": 'Emit this exact JSON event: {"event": "agent:status", "data": {"agent_id": "' + alice_id + '", "status": "communicating"}}'
    })
    
    time.sleep(3)
    
    # Check for agent:status events
    status_events = client.send_event("monitor:get_events", {
        "limit": 10,
        "event_patterns": ["agent:status"]
    })
    
    found_json = False
    for event in status_events.get('events', []):
        if event.get('data', {}).get('agent_id') == alice_id:
            found_json = True
            print(f"   ✅ Agent successfully emitted JSON event")
            break
    
    if not found_json:
        print(f"   ⚠️ JSON event not found (Issue #12 - JSON extraction)")
    
    # Identify technical issues
    print("\n9️⃣ Technical Issues Identified:")
    issues = []
    
    # Check message delivery
    if len(bob_events) == 0:
        issues.append({
            "title": "Agent-to-agent message delivery failure",
            "severity": "HIGH",
            "impact": "Blocks multi-agent coordination",
            "details": "Messages sent via completion:async not reaching target agent"
        })
    
    # Check JSON emission
    if not found_json:
        issues.append({
            "title": "JSON event extraction unreliable",
            "severity": "MEDIUM", 
            "impact": "Complicates agent coordination",
            "details": "Agents describe JSON instead of emitting it (Issue #12)"
        })
    
    # Check completion queue processing
    if msg_result.get('status') == 'queued' and len(alice_events) < 2:
        issues.append({
            "title": "Completion queue processing delays",
            "severity": "LOW",
            "impact": "Slows down experiments",
            "details": "Queued completions taking longer than expected"
        })
    
    # Cleanup
    print("\n🧹 Cleanup...")
    for agent in agents:
        client.send_event("agent:terminate", {"agent_id": agent})
    client.send_event("routing:remove_rule", {"rule_id": f"{test_id}_monitor"})
    print("   ✅ Cleanup complete")
    
    # Results
    print("\n" + "="*60)
    print("📊 COMMUNICATION TEST RESULTS")
    print("="*60)
    
    if len(issues) == 0:
        print("✅ All communication tests passed!")
    else:
        print(f"⚠️ {len(issues)} technical issue(s) found:\n")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue['title']}")
            print(f"   Severity: {issue['severity']}")
            print(f"   Impact: {issue['impact']}")
            print(f"   Details: {issue['details']}\n")
    
    return {
        "test_id": test_id,
        "agents_spawned": len(agents),
        "alice_events": len(alice_events),
        "bob_events": len(bob_events),
        "json_emission_works": found_json,
        "issues": issues
    }


if __name__ == "__main__":
    # Check daemon
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    try:
        result = client.send_event("system:health", {})
        if result.get("status") != "healthy":
            print("❌ Daemon not healthy")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to daemon: {e}")
        sys.exit(1)
    
    # Run test
    results = test_two_agent_communication()
    
    # Triage recommendations
    if results.get("issues"):
        print("\n" + "="*60)
        print("🔧 TRIAGE RECOMMENDATIONS")
        print("="*60)
        
        for issue in results["issues"]:
            if issue["severity"] == "HIGH":
                print(f"\n🔴 {issue['title']}")
                print("   Action: Investigate immediately")
                print("   Time estimate: 2-4 hours")
                print("   Priority: BLOCKS EXPERIMENTS")
            elif issue["severity"] == "MEDIUM":
                print(f"\n🟡 {issue['title']}")
                print("   Action: Document workaround, fix later")
                print("   Time estimate: 4-8 hours")
                print("   Priority: Impacts efficiency")
            else:
                print(f"\n🟢 {issue['title']}")
                print("   Action: Monitor, fix if time permits")
                print("   Time estimate: 1-2 hours")
                print("   Priority: Nice to have")