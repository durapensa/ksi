#!/usr/bin/env python3
"""Test native WebSocket transport connectivity."""

import asyncio
import json
import websockets

async def test_native_websocket():
    """Test connecting to native WebSocket transport."""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to {uri}")
            
            # Wait for connection confirmation
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Received: {data}")
            
            # Send system health request
            health_msg = {
                "event": "system:health",
                "data": {}
            }
            await websocket.send(json.dumps(health_msg))
            print(f"→ Sent: {health_msg}")
            
            # Receive response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Health response: {json.dumps(data, indent=2)}")
            
            # Subscribe to monitor events
            subscribe_msg = {
                "event": "monitor:subscribe",
                "data": {
                    "client_id": "test-native-ws",
                    "event_patterns": ["agent:*"]
                }
            }
            await websocket.send(json.dumps(subscribe_msg))
            print(f"→ Sent: {subscribe_msg}")
            
            # Receive subscription response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Subscribe response: {data}")
            
            # Request agent list
            agent_list_msg = {
                "event": "agent:list",
                "data": {}
            }
            await websocket.send(json.dumps(agent_list_msg))
            print(f"→ Sent: {agent_list_msg}")
            
            # Receive agent list
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✓ Agent list: {json.dumps(data, indent=2)}")
            
            print("\n✓ Native WebSocket transport is working correctly!")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_native_websocket())