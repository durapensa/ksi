#!/usr/bin/env python3
"""Test script for dual-path JSON discovery system."""

import asyncio
import json
from ksi_daemon.core.discovery import handle_discover, handle_help, is_agent_context
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("test_dual_path_discovery")


async def test_cli_context():
    """Test discovery with CLI context (should return standard format)."""
    print("\n=== Testing CLI Context ===")
    
    # Test system:discover with CLI context
    cli_context = {"_client_id": "ksi-cli"}
    result = await handle_discover(
        {"namespace": "agent", "level": "namespace"},
        cli_context
    )
    
    print(f"CLI Discovery response keys: {list(result.keys())}")
    assert "events" in result or "namespaces" in result
    assert "type" not in result  # Should NOT be ksi_tool_use format
    print("✅ CLI context returns standard format")


async def test_agent_context():
    """Test discovery with agent context (should return ksi_tool_use format)."""
    print("\n=== Testing Agent Context ===")
    
    # Test system:discover with agent context
    agent_context = {"_agent_id": "test_agent_123", "_client_id": "claude-cli"}
    result = await handle_discover(
        {"namespace": "agent", "level": "namespace"},
        agent_context
    )
    
    print(f"Agent Discovery response keys: {list(result.keys())}")
    print(f"Response: {json.dumps(result, indent=2)}")
    
    # Check for ksi_tool_use format
    if "type" in result and result["type"] == "ksi_tool_use":
        print("✅ Agent context returns ksi_tool_use format")
        assert "id" in result
        assert "name" in result
        assert result["name"] == "discovery:results"
        assert "input" in result
    else:
        print("❌ Agent context did NOT return ksi_tool_use format")


async def test_help_dual_path():
    """Test help endpoint with both contexts."""
    print("\n=== Testing Help Dual Path ===")
    
    # CLI context
    cli_result = await handle_help(
        {"event": "system:discover"},
        {"_client_id": "ksi-cli"}
    )
    print(f"CLI Help response has 'type': {'type' in cli_result}")
    assert "type" not in cli_result or cli_result.get("type") != "ksi_tool_use"
    
    # Agent context
    agent_result = await handle_help(
        {"event": "system:discover"},
        {"_agent_id": "test_agent", "_client_id": "claude-cli"}
    )
    print(f"Agent Help response: {json.dumps(agent_result, indent=2)}")
    
    if "type" in agent_result and agent_result["type"] == "ksi_tool_use":
        print("✅ Help endpoint returns ksi_tool_use for agents")
    else:
        print("❌ Help endpoint did NOT return ksi_tool_use for agents")


async def test_error_cases():
    """Test that errors remain in standard format even for agents."""
    print("\n=== Testing Error Cases ===")
    
    # Test non-existent event with agent context
    error_result = await handle_help(
        {"event": "nonexistent:event"},
        {"_agent_id": "test_agent", "_client_id": "claude-cli"}
    )
    
    print(f"Error response: {json.dumps(error_result, indent=2)}")
    
    # Errors should remain in standard format for proper handling
    if error_result.get("status") == "failed" and "error" in error_result:
        print("✅ Errors remain in standard format (not ksi_tool_use)")
    else:
        print("❌ Unexpected error format")


async def test_context_detection():
    """Test the is_agent_context function."""
    print("\n=== Testing Context Detection ===")
    
    test_cases = [
        ({"_client_id": "ksi-cli"}, False, "ksi-cli"),
        ({"_client_id": "web-ui"}, False, "web-ui"),
        ({"_agent_id": "agent_123"}, True, "agent with ID"),
        ({"_agent_id": "agent_123", "_client_id": "ksi-cli"}, True, "agent overrides CLI"),
        ({"_client_id": "claude-code"}, True, "claude-code coordination"),
        ({}, False, "empty context"),
        (None, False, "None context"),
    ]
    
    for context, expected, description in test_cases:
        result = is_agent_context(context)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description}: {result} (expected {expected})")


async def main():
    """Run all tests."""
    print("Testing Dual-Path JSON Discovery System")
    print("=" * 50)
    
    await test_context_detection()
    await test_cli_context()
    await test_agent_context()
    await test_help_dual_path()
    await test_error_cases()
    
    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(main())