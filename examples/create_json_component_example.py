#!/usr/bin/env python3
"""Example of creating components with nested JSON using the safe utilities."""

import asyncio
from ksi_common.json_component_utils import (
    prepare_component_with_json,
    decode_json_content,
    create_json_aware_component_content
)
from ksi_client import KSIClient


async def create_json_emitter_example():
    """Example of creating a component that emits JSON events."""
    
    # Define the component content with JSON examples
    content = """---
component_type: persona
name: smart_json_emitter
version: 1.0.0
description: An agent that emits structured JSON events
---
# Smart JSON Emitter

You are an intelligent agent that communicates using JSON events.

## Required Behavior

1. **Always start** your response with this status event:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "active", "timestamp": "{{timestamp}}"}}

2. **For analysis tasks**, emit:
{"event": "analysis:result", "data": {"findings": [...], "confidence": 0.0-1.0, "next_steps": [...]}}

3. **When complete**, emit:
{"event": "task:complete", "data": {"success": true, "summary": "...", "metrics": {...}}}

## Example Interaction

User: Analyze this data: [1, 2, 3, 4, 5]

Response:
{"event": "agent:status", "data": {"agent_id": "smart_json_123", "status": "active", "timestamp": "2024-01-27T10:30:00Z"}}

I'll analyze this numerical sequence.

{"event": "analysis:result", "data": {"findings": ["Sequential integers from 1-5", "Mean: 3.0", "Pattern: +1 increment"], "confidence": 0.95, "next_steps": ["Check for extended pattern", "Calculate statistical properties"]}}

The data shows a simple arithmetic sequence with a common difference of 1.

{"event": "task:complete", "data": {"success": true, "summary": "Analyzed 5-element integer sequence", "metrics": {"mean": 3.0, "min": 1, "max": 5, "count": 5}}}
"""
    
    # Initialize KSI client
    client = KSIClient()
    
    # Method 1: Using base64 encoding (most reliable)
    print("=== Method 1: Base64 Encoding ===")
    request_data = prepare_component_with_json(
        name="personas/json_emitters/smart_emitter_base64",
        content=content,
        component_type="persona",
        encoding_method="base64",
        overwrite=True
    )
    
    # Send the request
    response = await client.send_event("composition:create_component", request_data)
    print(f"Creation result: {response.get('status')}")
    
    # Method 2: Using placeholder approach
    print("\n=== Method 2: Placeholder Approach ===")
    request_data = prepare_component_with_json(
        name="personas/json_emitters/smart_emitter_placeholders",
        content=content,
        component_type="persona",
        encoding_method="placeholder",
        overwrite=True
    )
    
    response = await client.send_event("composition:create_component", request_data)
    print(f"Creation result: {response.get('status')}")
    
    # Retrieve and decode
    print("\n=== Retrieving and Decoding ===")
    response = await client.send_event("composition:get_component", {
        "name": "personas/json_emitters/smart_emitter_base64"
    })
    
    if response.get("status") == "success":
        decoded_content = decode_json_content(
            response.get("content", ""),
            response.get("metadata")
        )
        print("Successfully decoded content!")
        print(f"Content preview: {decoded_content[:100]}...")
        
        # Verify JSON is intact
        if '{"event": "agent:status"' in decoded_content:
            print("✓ JSON examples preserved correctly!")
    
    await client.close()


async def create_with_yaml_instructions():
    """Example using YAML frontmatter for JSON instructions."""
    
    # Base content without inline JSON
    base_content = """---
component_type: behavior
name: structured_responder
version: 1.0.0
---
# Structured Response Behavior

This behavior ensures agents respond with structured JSON events.

## Response Pattern

1. Start with status event (see json_instructions[0])
2. Provide main response with appropriate event type
3. End with completion event (see json_instructions[2])

The exact JSON formats are defined in the component metadata.
"""
    
    # JSON instructions to add
    json_instructions = [
        {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "ready"}},
        {"event": "response:data", "data": {"content": "{{response}}", "metadata": {}}},
        {"event": "response:complete", "data": {"tokens_used": 0, "success": True}}
    ]
    
    # Create content with JSON in YAML frontmatter
    content_with_json = create_json_aware_component_content(
        base_content,
        json_instructions,
        instruction_format="yaml"
    )
    
    print("\n=== Method 3: YAML Frontmatter Approach ===")
    print("Generated content structure:")
    print(content_with_json[:200] + "...")
    
    # This content can now be saved without JSON parsing issues
    client = KSIClient()
    response = await client.send_event("composition:create_component", {
        "name": "behaviors/structured_responder",
        "content": content_with_json,
        "type": "behavior",
        "overwrite": True
    })
    
    print(f"\nCreation result: {response.get('status')}")
    await client.close()


async def main():
    """Run all examples."""
    print("Examples of Creating Components with Nested JSON\n")
    
    await create_json_emitter_example()
    await create_with_yaml_instructions()
    
    print("\n=== Summary ===")
    print("✓ Use base64 encoding for maximum reliability")
    print("✓ Use placeholders when you need readable intermediate format")
    print("✓ Use YAML frontmatter to separate JSON from content")
    print("✓ Always decode when retrieving for use")


if __name__ == "__main__":
    asyncio.run(main())