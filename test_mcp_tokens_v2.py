#!/usr/bin/env python3
"""Test token usage logging for MCP handshakes - Version 2."""

import json
import asyncio
from ksi_client import EventClient

async def test_token_usage():
    client = EventClient()
    await client.connect()
    
    print("=== Test 1: Completion without MCP (direct) ===")
    # First request without MCP
    response1 = await client.send_event("completion:async", {
        "prompt": "Say hello",
        "model": "claude-cli/sonnet",
        "temperature": 0.0
    })
    print(f"Request ID: {response1['request_id']}")
    
    # Wait for completion
    await asyncio.sleep(5)
    
    print("\n=== Test 2: Agent completion with MCP (should do full handshake) ===")
    # Create an agent with MCP enabled (system will create MCP config)
    agent_response = await client.send_event("agent:spawn", {
        "agent_id": "test_mcp_agent",
        "profile": "system_admin"
    })
    print(f"Agent spawned: {agent_response}")
    
    # Send completion through agent (this should use MCP)
    response2 = await client.send_event("agent:send_message", {
        "agent_id": "test_mcp_agent",
        "message": {
            "type": "completion",
            "prompt": "Say hello with MCP",
            "request_id": "test_mcp_1"
        }
    })
    print(f"Message sent to agent: {response2}")
    
    # Wait for completion
    await asyncio.sleep(8)
    
    print("\n=== Test 3: Agent completion with MCP (should do thin handshake) ===")
    # Another completion with same agent (should reuse MCP session)
    response3 = await client.send_event("agent:send_message", {
        "agent_id": "test_mcp_agent",
        "message": {
            "type": "completion",
            "prompt": "Say hello again with MCP",
            "request_id": "test_mcp_2"
        }
    })
    print(f"Message sent to agent: {response3}")
    
    # Wait for completion
    await asyncio.sleep(8)
    
    # Check agent status
    status = await client.send_event("agent:status", {"agent_id": "test_mcp_agent"})
    print(f"\nAgent status: {status}")
    
    # Clean up agent
    await client.send_event("agent:terminate", {"agent_id": "test_mcp_agent"})
    
    print("\n=== Check daemon logs for token usage comparison ===")
    print("Look for:")
    print("  - 'Completion token usage' log entries with has_mcp=True/False")
    print("  - 'Full handshake' vs 'Thin handshake' logs from MCP server")
    print("  - Token counts showing difference between full and thin")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_token_usage())