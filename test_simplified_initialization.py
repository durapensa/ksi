#!/usr/bin/env python3
"""Test simplified agent initialization with direct prompt field"""

import asyncio
import json
from ksi_client import KSIClient

async def test_simplified_initialization():
    """Test that agents receive prompts through direct prompt field only"""
    
    client = KSIClient()
    
    # Clear monitor
    await client.send_event("monitor:clear", {})
    
    # Spawn agent with direct prompt field
    print("Testing agent with direct prompt field...")
    response = await client.send_event("agent:spawn_from_component", {
        "component": "components/core/base_agent",
        "agent_id": "test_direct_prompt",
        "vars": {
            "prompt": "You should receive this prompt directly"
        }
    })
    print(f"Spawn response: {json.dumps(response, indent=2)}")
    
    # Wait for agent to initialize
    await asyncio.sleep(2)
    
    # Send test message
    await client.send_event("completion:async", {
        "agent_id": "test_direct_prompt",
        "prompt": "Did you receive the initial prompt? What was it?"
    })
    
    # Wait for response
    await asyncio.sleep(5)
    
    # Check monitor events
    events = await client.send_event("monitor:get_events", {
        "event_patterns": ["agent:status", "completion:*"],
        "extracted": True,
        "limit": 20
    })
    
    print("\nExtracted events:")
    for event in events.get('events', []):
        if event['event_name'] in ['agent:status', 'completion:result']:
            print(f"- {event['event_name']}: {event.get('data', {})}")
    
    # Cleanup
    await client.send_event("agent:kill", {"agent_id": "test_direct_prompt"})
    
if __name__ == "__main__":
    asyncio.run(test_simplified_initialization())