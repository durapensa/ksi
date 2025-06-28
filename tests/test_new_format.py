#!/usr/bin/env python3
"""
Test the new standardized completion format
"""

import asyncio
import json
from ksi_client.event_client import EventChatClient

async def test_completion():
    """Test completion with new standardized format"""
    
    async with EventChatClient("test_client") as client:
        print("Testing completion with new standardized format...")
        
        # Send a simple prompt
        response_text, session_id = await client.send_prompt("Say hello and respond with just 'Hello from Claude!'")
        
        print(f"Response text: {response_text}")
        print(f"Session ID: {session_id}")
        
        # Check if response directory has the session file
        from ksi_common import config
        session_file = config.responses_dir / f"{session_id}.jsonl"
        print(f"Session file: {session_file}")
        print(f"Session file exists: {session_file.exists()}")
        
        if session_file.exists():
            print("Latest entry in session file:")
            with open(session_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    latest = json.loads(lines[-1])
                    print(json.dumps(latest, indent=2))

if __name__ == "__main__":
    asyncio.run(test_completion())