#!/usr/bin/env python3
"""
Simple test script to debug evaluation system.
"""
import asyncio
import json
from ksi_client.client import EventClient

async def test_evaluation():
    """Test evaluation with timeout and debugging."""
    client = EventClient()
    
    # Connect to daemon first
    await client.connect()
    
    print("Sending evaluation:run event...")
    
    try:
        result = await asyncio.wait_for(
            client.send_event("evaluation:run", {
                "component_path": "behaviors/optimization/strict_instruction_following",
                "test_suite": "ksi_tool_use_validation", 
                "model": "claude-sonnet-4"
            }),
            timeout=30.0  # 30 second timeout
        )
        
        print(f"Result: {json.dumps(result, indent=2)}")
        
    except asyncio.TimeoutError:
        print("ERROR: Evaluation timed out after 30 seconds")
        
        # Check recent logs
        print("\nChecking recent completion:result events...")
        monitor_result = await client.send_event("monitor:get_events", {
            "event_patterns": ["completion:result", "evaluation:*"],
            "limit": 5
        })
        
        events = monitor_result.get('data', {}).get('events', [])
        print(f"\nFound {len(events)} recent events:")
        for event in events:
            print(f"  - {event.get('timestamp')}: {event.get('event_name')}")
            
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_evaluation())