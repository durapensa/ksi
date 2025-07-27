#!/usr/bin/env python3
"""
Test the unified agent spawn with system_prompt extraction.
"""
import asyncio
import json
import socket
from datetime import datetime
import time

SOCKET_PATH = "/Users/dp/projects/ksi/var/run/daemon.sock"

async def send_event(event_name: str, data: dict):
    """Send event to daemon via Unix socket."""
    message = {"event": event_name, "data": data}
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        client.send(json.dumps(message).encode() + b'\n')
        
        response = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\n' in response:
                break
        
        client.close()
        
        if response:
            return json.loads(response.decode().strip())
        return {}
        
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


async def test_basic_spawn():
    """Test basic spawn without variables."""
    print("=== Test 1: Basic Spawn ===")
    
    agent_id = f"test_basic_{datetime.now().strftime('%H%M%S')}"
    
    result = await send_event("agent:spawn", {
        "agent_id": agent_id,
        "component": "components/core/base_agent"
    })
    
    print(f"Spawn result: {json.dumps(result, indent=2)}")
    
    if result.get("data", {}).get("status") == "created":
        print("✓ Basic spawn successful")
        
        # Terminate agent
        await send_event("agent:terminate", {"agent_id": agent_id})
        return True
    else:
        print("✗ Basic spawn failed")
        return False


async def test_spawn_with_variables():
    """Test spawn with variables."""
    print("\n=== Test 2: Spawn with Variables ===")
    
    agent_id = f"test_vars_{datetime.now().strftime('%H%M%S')}"
    
    result = await send_event("agent:spawn", {
        "agent_id": agent_id,
        "component": "components/agents/json_strict",
        "variables": {
            "role": "senior",
            "domain": "security"
        }
    })
    
    print(f"Spawn result: {json.dumps(result, indent=2)}")
    
    if result.get("data", {}).get("status") == "created":
        print("✓ Spawn with variables successful")
        
        # Test if agent received system prompt
        await asyncio.sleep(2)
        
        # Send test prompt
        completion_result = await send_event("completion:async", {
            "agent_id": agent_id,
            "prompt": "Please emit a status event."
        })
        
        print(f"Completion request: {completion_result}")
        
        # Terminate agent
        await send_event("agent:terminate", {"agent_id": agent_id})
        return True
    else:
        print("✗ Spawn with variables failed")
        return False


async def test_deprecated_spawn():
    """Test deprecated spawn_from_component (should still work with warning)."""
    print("\n=== Test 3: Deprecated spawn_from_component ===")
    
    agent_id = f"test_deprecated_{datetime.now().strftime('%H%M%S')}"
    
    result = await send_event("agent:spawn_from_component", {
        "agent_id": agent_id,
        "component": "components/core/base_agent",
        "variables": {"test": "value"}
    })
    
    print(f"Spawn result: {json.dumps(result, indent=2)}")
    
    status = result.get("data", {}).get("status")
    spawn_status = result.get("data", {}).get("spawn_status")
    
    if status in ["created", "success"] or spawn_status == "created":
        print("✓ Deprecated spawn still works (check logs for warning)")
        
        # Terminate agent
        await send_event("agent:terminate", {"agent_id": agent_id})
        return True
    else:
        print("✗ Deprecated spawn failed")
        return False


async def test_missing_component():
    """Test spawn without component (should fail)."""
    print("\n=== Test 4: Missing Component ===")
    
    agent_id = f"test_missing_{datetime.now().strftime('%H%M%S')}"
    
    result = await send_event("agent:spawn", {
        "agent_id": agent_id
        # No component specified
    })
    
    print(f"Spawn result: {json.dumps(result, indent=2)}")
    
    if "error" in result.get("data", {}) or result.get("data", {}).get("status") == "failed":
        print("✓ Correctly rejected spawn without component")
        return True
    else:
        print("✗ Should have failed without component")
        # Try to cleanup if somehow created
        await send_event("agent:terminate", {"agent_id": agent_id})
        return False


async def main():
    """Run all tests."""
    print("Testing Unified Agent Spawn")
    print("===========================\n")
    
    results = []
    
    # Run tests
    results.append(await test_basic_spawn())
    results.append(await test_spawn_with_variables())
    results.append(await test_deprecated_spawn())
    results.append(await test_missing_component())
    
    # Summary
    print("\n=== Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed")


if __name__ == "__main__":
    asyncio.run(main())