#!/usr/bin/env python3
"""Direct test of JSON extraction with both valid and malformed patterns."""

import asyncio
from ksi_client import EventClient
import json
import time


async def test_direct_json():
    async with EventClient() as client:
        print("=== Direct JSON Extraction Test ===")
        
        # Spawn agent with very direct instructions
        spawn_result = await client.send_single("agent:spawn", {
            "profile": "base_single_agent",
            "initial_prompt": """DIRECTLY include these 4 JSON objects in your response:

{"event": "orchestration:track", "data": {"test": "valid1"}}

{'event': 'orchestration:track', 'data': {'test': 'single_quotes'}}

{"event": "orchestration:track", "data": {"test": "trailing_comma",}}

{"event": "orchestration:track", "data": {"test": "valid2"}}

Just include them in your response text. Say nothing else except: "JSON test patterns included above."""
        })
        
        agent_id = spawn_result.get('agent_id')
        print(f"Spawned test agent: {agent_id}")
        
        # Wait for completion
        print("Waiting for agent response...")
        await asyncio.sleep(15)
        
        # Check for extracted valid events
        print("\n=== Checking Extracted Events ===")
        events = await client.send_all("monitor:get_events", {
            "event_patterns": ["orchestration:track"],
            "since": time.time() - 60,
            "limit": 10
        })
        
        valid_count = 0
        for event_data in events:
            if 'events' in event_data:
                for evt in event_data['events']:
                    if evt['data'].get('_agent_id') == agent_id:
                        print(f"✓ Extracted: {evt['data']}")
                        valid_count += 1
        
        print(f"\nValid events extracted: {valid_count}")
        
        # Check for feedback
        print("\n=== Checking Feedback ===")
        feedback_events = await client.send_all("monitor:get_events", {
            "event_patterns": ["completion:async"],
            "since": time.time() - 60,
            "limit": 20
        })
        
        feedback_found = False
        for event_data in feedback_events:
            if 'events' in event_data:
                for evt in event_data['events']:
                    data = evt.get('data', {})
                    if (data.get('is_feedback') and 
                        data.get('agent_id') == agent_id):
                        content = data['messages'][0]['content']
                        print(f"📨 Feedback received:")
                        print(content[:300] + "..." if len(content) > 300 else content)
                        feedback_found = True
        
        if not feedback_found:
            print("❌ No feedback found")
        
        # Get response logs
        print("\n=== Checking Response Log ===")
        completion_events = await client.send_all("monitor:get_events", {
            "event_patterns": ["completion:result"],
            "since": time.time() - 60,
            "limit": 5
        })
        
        for event_data in completion_events:
            if 'events' in event_data:
                for evt in event_data['events']:
                    if evt['data']['request_id'].startswith(agent_id):
                        session_id = evt['data']['result']['response']['session_id']
                        result_text = evt['data']['result']['response']['result']
                        print(f"📄 Agent response (session {session_id}):")
                        print(result_text[:200] + "..." if len(result_text) > 200 else result_text)
        
        # Cleanup
        await client.send_single("agent:terminate", {"agent_id": agent_id})
        print(f"\n🗑️ Terminated agent: {agent_id}")
        
        # Summary
        print(f"\n=== Test Summary ===")
        print(f"Expected: 2 valid JSON extractions + feedback for 2 malformed")
        print(f"Actual: {valid_count} valid extractions + {'feedback' if feedback_found else 'no feedback'}")
        
        success = valid_count == 2 and feedback_found
        print(f"Test Result: {'✅ PASS' if success else '❌ FAIL'}")
        
        return success


if __name__ == "__main__":
    result = asyncio.run(test_direct_json())
    exit(0 if result else 1)