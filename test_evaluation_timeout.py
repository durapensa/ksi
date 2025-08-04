#!/usr/bin/env python3
"""
Test evaluation with extended timeout.
"""
import asyncio
import json
from ksi_client.client import EventClient

async def test_evaluation_with_timeout():
    """Test evaluation with proper timeout."""
    client = EventClient()
    await client.connect()
    
    print("Testing evaluation with 6-minute timeout...")
    
    try:
        # Use a longer timeout that matches the evaluation handler timeout
        result = await client.send_event("evaluation:run", {
            "component_path": "behaviors/optimization/strict_instruction_following",
            "test_suite": "ksi_tool_use_validation", 
            "model": "claude-sonnet-4"
        }, timeout=360.0)  # 6 minutes to be safe
        
        print(f"✅ Evaluation succeeded: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        print(f"❌ Evaluation failed: {type(e).__name__}: {e}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_evaluation_with_timeout())