#!/usr/bin/env python3
"""Test JSON extraction feedback with both valid and malformed JSON."""

import asyncio
from ksi_client import EventClient
import json


async def test_json_feedback():
    async with EventClient() as client:
        # Spawn a simple agent to test JSON extraction
        spawn_result = await client.send_single("agent:spawn", {
            "profile": "base_single_agent",
            "initial_prompt": """Test JSON extraction by including these in your response:

1. Valid JSON: {"event": "state:set", "data": {"key": "test1", "value": "valid"}}

2. Single quotes (malformed): {'event': 'state:set', 'data': {'key': 'test2', 'value': 'single_quotes'}}

3. Trailing comma (malformed): {"event": "state:set", "data": {"key": "test3",}}

Include all three exactly as shown above."""
        })
        
        agent_id = spawn_result.get('agent_id')
        print(f"Spawned agent: {agent_id}")
        
        # Wait for completion and feedback
        print("\nWaiting for agent response and feedback...")
        await asyncio.sleep(30)
        
        # Check for feedback events
        events = await client.send_all("monitor:get_events", {
            "event_patterns": ["completion:async"],
            "limit": 20
        })
        
        # Find feedback messages
        feedback_found = False
        for event_data in events:
            if 'events' in event_data:
                for evt in event_data['events']:
                    data = evt.get('data', {})
                    if (data.get('is_feedback') and 
                        data.get('agent_id') == agent_id):
                        print("\n=== FEEDBACK RECEIVED ===")
                        content = data['messages'][0]['content']
                        print(content)
                        feedback_found = True
        
        if not feedback_found:
            print("\nNo feedback found. Checking extracted events...")
            
            # Check what events were extracted
            events = await client.send_all("monitor:get_events", {
                "event_patterns": ["state:set"],
                "limit": 10
            })
            
            for event_data in events:
                if 'events' in event_data:
                    for evt in event_data['events']:
                        if evt['data'].get('_agent_id') == agent_id:
                            print(f"\nExtracted event: {evt['event_name']}")
                            print(f"Data: {evt['data']}")
        
        # Terminate agent
        await client.send_single("agent:terminate", {"agent_id": agent_id})
        print(f"\nTerminated agent: {agent_id}")


if __name__ == "__main__":
    asyncio.run(test_json_feedback())