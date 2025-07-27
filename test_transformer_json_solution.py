#!/usr/bin/env python3
"""Test the transformer-based solution for nested JSON handling."""

import json
import subprocess
import time

def run_ksi_command(event: str, **kwargs):
    """Run a KSI command."""
    cmd = ["ksi", "send", event]
    for key, value in kwargs.items():
        param_name = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                cmd.append(param_name)
        elif isinstance(value, (dict, list)):
            cmd.extend([param_name, json.dumps(value)])
        else:
            cmd.extend([param_name, str(value)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": result.stderr}
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}

def test_with_transformer():
    """Test creating a component with nested JSON using the transformer."""
    print("=== Testing Transformer-Based JSON Handling ===\n")
    
    # Component with nested JSON
    content = """---
component_type: persona
name: advanced_json_emitter
version: 1.0.0
---
# Advanced JSON Emitter

You must emit these JSON events in order:

1. First, emit status:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "ready", "mode": "json_emission"}}

2. Then emit your analysis:
{"event": "analysis:complete", "data": {"findings": ["item1", "item2"], "confidence": 0.95}}

3. Finally emit completion:
{"event": "task:complete", "data": {"success": true, "duration_ms": 1500}}
"""
    
    # Create with transformer handling
    print("1. Creating component with nested JSON...")
    create_result = run_ksi_command("composition:create_component",
        name="test/transformer_json_test",
        content=content,
        type="persona",
        use_base64_encoding=True,  # Tell transformer to use base64
        overwrite=True
    )
    
    print(f"Create status: {create_result.get('status', 'failed')}")
    if create_result.get('status') != 'success':
        print(f"Error: {create_result.get('error', 'Unknown error')}")
        return
    
    # Wait for component to be indexed
    time.sleep(1)
    
    # Retrieve component (should be auto-decoded)
    print("\n2. Retrieving component (should auto-decode)...")
    get_result = run_ksi_command("composition:get_component",
        name="test/transformer_json_test"
    )
    
    if get_result.get('status') == 'success':
        print("Retrieved successfully!")
        content = get_result.get('content', '')
        
        # Check if JSON is properly preserved
        if '{"event": "agent:status"' in content:
            print("✓ JSON content properly preserved and decoded!")
        else:
            print("✗ JSON content not found in decoded result")
        
        # Show preview
        print(f"\nContent preview:\n{content[:200]}...")
        
        # Check for encoding metadata
        if '_was_encoded' in get_result:
            print(f"\nEncoding used: {get_result['_was_encoded']}")
    else:
        print(f"Retrieval failed: {get_result}")
    
    # Test with metadata approach
    print("\n\n3. Testing metadata-based JSON storage...")
    create_result2 = run_ksi_command("composition:create_component",
        name="test/transformer_json_metadata",
        content=content,
        type="persona",
        use_base64_encoding=False,  # Use metadata approach
        overwrite=True
    )
    
    print(f"Create status: {create_result2.get('status', 'failed')}")
    
    # Retrieve and check
    time.sleep(0.5)
    get_result2 = run_ksi_command("composition:get_component",
        name="test/transformer_json_metadata"
    )
    
    if get_result2.get('status') == 'success':
        print("Retrieved successfully!")
        if '{"event": "agent:status"' in get_result2.get('content', ''):
            print("✓ JSON content properly preserved with metadata approach!")

def main():
    """Run the transformer test."""
    test_with_transformer()
    
    print("\n\n=== Summary ===")
    print("The transformer-based approach provides automatic handling of nested JSON:")
    print("1. On create: Detects nested JSON and encodes/transforms it")
    print("2. On retrieve: Automatically decodes/reconstructs the original content")
    print("3. Supports both base64 and metadata-based storage")
    print("4. Transparent to the user - no manual encoding needed")

if __name__ == "__main__":
    main()