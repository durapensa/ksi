#!/usr/bin/env python3
"""Test token usage logging for MCP handshakes."""

import json
import asyncio
from ksi_client import EventClient

async def test_token_usage():
    client = EventClient()
    await client.connect()
    
    print("=== Test 1: Completion without MCP ===")
    # First request without MCP
    response1 = await client.send_event("completion:async", {
        "prompt": "Say hello",
        "model": "claude-cli/sonnet",
        "temperature": 0.0
    })
    print(f"Request ID: {response1['request_id']}")
    
    # Wait for completion
    await asyncio.sleep(5)
    
    print("\n=== Test 2: Completion with MCP (first request - full handshake) ===")
    # Create an agent with MCP enabled
    agent_response = await client.send_event("agent:spawn", {
        "agent_id": "test_mcp_agent",
        "profile": "system_admin",
        "mcp_enabled": True
    })
    print(f"Agent spawned: {agent_response}")
    
    # Completion with MCP (should do full handshake)
    response2 = await client.send_event("completion:async", {
        "prompt": "Say hello with MCP",
        "model": "claude-cli/sonnet",
        "agent_id": "test_mcp_agent",
        "conversation_id": "test_conv_1",
        "temperature": 0.0
    })
    print(f"Request ID: {response2['request_id']}")
    
    # Wait for completion
    await asyncio.sleep(5)
    
    print("\n=== Test 3: Completion with MCP (subsequent request - thin handshake) ===")
    # Another completion with same agent/conversation (should do thin handshake)
    response3 = await client.send_event("completion:async", {
        "prompt": "Say hello again with MCP",
        "model": "claude-cli/sonnet",
        "agent_id": "test_mcp_agent",
        "conversation_id": "test_conv_1",
        "temperature": 0.0
    })
    print(f"Request ID: {response3['request_id']}")
    
    # Wait for completion
    await asyncio.sleep(5)
    
    # Clean up agent
    await client.send_event("agent:terminate", {"agent_id": "test_mcp_agent"})
    
    print("\n=== Check daemon logs for token usage comparison ===")
    print("Look for 'Completion token usage' log entries with has_mcp=True/False")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_token_usage())