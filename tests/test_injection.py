#!/usr/bin/env python3
"""
Test runner for injection system with live daemon.

This script tests the injection system against a running daemon.
"""

import asyncio
import json
import subprocess
from pathlib import Path
import sys


async def send_socket_command(command: dict) -> dict:
    """Send command to daemon socket and get response."""
    socket_path = "var/run/daemon.sock"
    
    # Use echo and nc to send command
    cmd_json = json.dumps(command)
    result = subprocess.run(
        ["sh", "-c", f"echo '{cmd_json}' | nc -U {socket_path}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise Exception(f"Socket command failed: {result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response", "raw": result.stdout}


async def test_unified_injection_system():
    """Test the unified injection system."""
    print("Testing Unified Injection System")
    print("=" * 50)
    
    # Test 1: Direct mode injection with before_prompt position
    print("\n1. Testing DIRECT mode with BEFORE_PROMPT position...")
    result = await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "This is a test injection before the prompt.",
            "mode": "direct",
            "position": "before_prompt",
            "session_id": "test-direct-before",
            "metadata": {
                "test": True,
                "timestamp": "2025-06-30T09:00:00Z"
            }
        }
    })
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Test 2: Direct mode with system_reminder position
    print("\n2. Testing DIRECT mode with SYSTEM_REMINDER position...")
    result = await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "<system-reminder>This is an important system note.</system-reminder>",
            "mode": "direct",
            "position": "system_reminder",
            "session_id": "test-direct-reminder"
        }
    })
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Test 3: Next mode injection
    print("\n3. Testing NEXT mode injection (queued)...")
    result = await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "This injection will be used in the next completion.",
            "mode": "next",
            "position": "after_prompt",
            "session_id": "test-next-queue",
            "priority": "high"
        }
    })
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Test 4: Check injection queue status
    print("\n4. Checking injection queue status...")
    result = await send_socket_command({
        "event": "injection:status",
        "data": {
            "session_id": "test-next-queue"
        }
    })
    print(f"Queue status: {json.dumps(result, indent=2)}")
    
    # Test 5: Invalid request (next mode without session_id)
    print("\n5. Testing error handling (next mode without session_id)...")
    result = await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "This should fail",
            "mode": "next",
            "position": "before_prompt"
        }
    })
    print(f"Error result: {json.dumps(result, indent=2)}")
    
    # Test 6: Test completion with queued injection
    print("\n6. Testing completion with queued injection...")
    # First queue an injection
    await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "INJECTED: This message was injected before the user prompt.",
            "mode": "next",
            "position": "before_prompt",
            "session_id": "test-completion-inject",
            "priority": "high"
        }
    })
    
    # Now send a completion request with same session_id
    result = await send_socket_command({
        "event": "completion:async",
        "data": {
            "prompt": "What was injected before this message?",
            "session_id": "test-completion-inject",
            "model": "claude-cli/sonnet"
        }
    })
    print(f"Completion result: {json.dumps(result, indent=2)}")
    
    if "request_id" in result:
        print(f"\nCheck response at: var/logs/responses/{result.get('session_id', 'unknown')}.jsonl")
    
    # Test 7: Multiple injections in queue
    print("\n7. Testing multiple injections in queue...")
    session_id = "test-multi-inject"
    
    # Queue multiple injections
    for i in range(3):
        await send_socket_command({
            "event": "injection:inject",
            "data": {
                "content": f"Injection #{i+1}",
                "mode": "next",
                "position": "before_prompt" if i == 0 else "after_prompt",
                "session_id": session_id,
                "priority": "high" if i == 1 else "normal"
            }
        })
    
    # Check queue
    result = await send_socket_command({
        "event": "injection:status",
        "data": {
            "session_id": session_id
        }
    })
    print(f"Multi-injection queue: {json.dumps(result, indent=2)}")


async def test_injection_management():
    """Test injection management features."""
    print("\n\nTesting Injection Management")
    print("=" * 50)
    
    # Test 1: Clear injection queue
    print("\n1. Testing queue clear...")
    session_id = "test-clear-queue"
    
    # Add some injections
    await send_socket_command({
        "event": "injection:inject",
        "data": {
            "content": "This will be cleared",
            "mode": "next",
            "position": "before_prompt",
            "session_id": session_id
        }
    })
    
    # Clear queue
    result = await send_socket_command({
        "event": "injection:clear",
        "data": {
            "session_id": session_id
        }
    })
    print(f"Clear result: {json.dumps(result, indent=2)}")
    
    # Test 2: List all injection queues
    print("\n2. Listing all injection queues...")
    result = await send_socket_command({
        "event": "injection:list",
        "data": {}
    })
    print(f"All queues: {json.dumps(result, indent=2)}")


async def main():
    """Run all injection tests."""
    try:
        # Check if daemon is running
        result = await send_socket_command({"event": "system:health", "data": {}})
        if "status" not in result or result["status"] != "healthy":
            print("ERROR: Daemon is not healthy. Please start it first.")
            return
        
        print("Daemon is healthy, proceeding with tests...\n")
        
        # Run tests
        await test_unified_injection_system()
        await test_injection_management()
        
        print("\n\nAll tests completed!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())