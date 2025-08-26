#!/usr/bin/env python3
"""Test different workarounds for nested JSON in composition:create_component events - V2."""

import json
import base64
import subprocess
import time
from typing import Dict, Any

# Sample component content with nested JSON
SAMPLE_CONTENT = """---
component_type: persona
name: json_emitter
version: 1.0.0
---
# JSON Emitter Persona

You are a data processor that must emit JSON events.

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Then process the request and emit:
{"event": "data:processed", "data": {"result": "your_analysis"}}
"""

def run_ksi_command(event: str, **kwargs) -> Dict[str, Any]:
    """Run a KSI command with proper parameter handling."""
    cmd = ["ksi", "send", event]
    
    # Build parameters properly
    for key, value in kwargs.items():
        if key.startswith('_'):  # Skip internal params
            continue
        # Use double dash for all parameters
        param_name = f"--{key.replace('_', '-')}"
        
        if isinstance(value, bool):
            # For boolean flags, only add if True
            if value:
                cmd.append(param_name)
        elif isinstance(value, (dict, list)):
            # JSON serialize complex types
            cmd.extend([param_name, json.dumps(value)])
        else:
            # String values
            cmd.extend([param_name, str(value)])
    
    print(f"Running: {' '.join(cmd[:4])}...")  # Show command without full content
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": result.stderr, "stdout": result.stdout}
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON response: {result.stdout}"}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out"}
    except Exception as e:
        return {"error": str(e)}

def test_base64_encoding():
    """Test Base64 encoding with proper decoding on retrieval."""
    print("\n=== Test: Base64 Encoding (Complete Flow) ===")
    
    # Encode content as base64
    encoded_content = base64.b64encode(SAMPLE_CONTENT.encode()).decode()
    
    # Create component with base64 content
    result = run_ksi_command("composition:create_component",
        name="test/base64_json_emitter",
        content=f"BASE64:{encoded_content}",
        type="persona",
        overwrite=True
    )
    
    print(f"Create result: {result.get('status', 'failed')}")
    if "error" in result:
        print(f"Error: {result['error']}")
        return result
    
    # Try to get the component back
    time.sleep(0.5)
    get_result = run_ksi_command("composition:get_component",
        name="test/base64_json_emitter"
    )
    
    if get_result.get("status") == "success" and "content" in get_result:
        content = get_result["content"]
        # Check if it needs decoding
        if content.startswith("BASE64:"):
            decoded = base64.b64decode(content[7:]).decode()
            print("Retrieved and decoded content successfully!")
            print(f"Content preview: {decoded[:100]}...")
        else:
            print(f"Retrieved raw content: {content[:100]}...")
    else:
        print(f"Get failed: {get_result}")
    
    return result

def test_split_content_approach():
    """Test splitting content and metadata."""
    print("\n=== Test: Split Content Approach (Complete Flow) ===")
    
    # Split into body only (no frontmatter with JSON)
    parts = SAMPLE_CONTENT.split('\n---\n', 1)
    body = parts[1] if len(parts) == 2 else SAMPLE_CONTENT
    
    # Remove JSON examples from body
    clean_body = body.replace('{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}', 
                              'JSON_INSTRUCTION_1')
    clean_body = clean_body.replace('{"event": "data:processed", "data": {"result": "your_analysis"}}',
                                    'JSON_INSTRUCTION_2')
    
    result = run_ksi_command("composition:create_component",
        name="test/split_json_emitter",
        content=clean_body,
        type="persona",
        metadata={
            "component_type": "persona",
            "version": "1.0.0",
            "json_instructions": {
                "JSON_INSTRUCTION_1": {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}},
                "JSON_INSTRUCTION_2": {"event": "data:processed", "data": {"result": "your_analysis"}}
            }
        },
        overwrite=True
    )
    
    print(f"Create result: {result.get('status', 'failed')}")
    if "error" in result:
        print(f"Error: {result['error']}")
        return result
    
    # Retrieve and check
    time.sleep(0.5)
    get_result = run_ksi_command("composition:get_component",
        name="test/split_json_emitter"
    )
    
    if get_result.get("status") == "success":
        print("Retrieved component successfully!")
        print(f"Content preview: {get_result.get('content', '')[:100]}...")
        if "metadata" in get_result:
            print(f"Metadata includes JSON instructions: {'json_instructions' in get_result['metadata']}")
    
    return result

def test_heredoc_approach():
    """Test using a heredoc-style delimiter approach."""
    print("\n=== Test: Heredoc-Style Delimiters ===")
    
    # Use heredoc-style markers for JSON blocks
    modified_content = SAMPLE_CONTENT.replace(
        '{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}',
        '<<<JSON\n{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}\nJSON>>>'
    ).replace(
        '{"event": "data:processed", "data": {"result": "your_analysis"}}',
        '<<<JSON\n{"event": "data:processed", "data": {"result": "your_analysis"}}\nJSON>>>'
    )
    
    result = run_ksi_command("composition:create_component",
        name="test/heredoc_json_emitter",
        content=modified_content,
        type="persona",
        overwrite=True
    )
    
    print(f"Create result: {result.get('status', 'failed')}")
    if "error" in result:
        print(f"Error: {result['error']}")
    
    return result

def test_json_placeholder_approach():
    """Test using placeholders with separate JSON storage."""
    print("\n=== Test: JSON Placeholder Approach ===")
    
    # Create content with placeholders
    placeholder_content = """---
component_type: persona
name: json_emitter
version: 1.0.0
---
# JSON Emitter Persona

You are a data processor that must emit JSON events.

## MANDATORY: Start your response with this exact JSON:
${JSON_EXAMPLE_1}

Then process the request and emit:
${JSON_EXAMPLE_2}
"""
    
    # Store JSON separately
    json_examples = {
        "JSON_EXAMPLE_1": '{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}',
        "JSON_EXAMPLE_2": '{"event": "data:processed", "data": {"result": "your_analysis"}}'
    }
    
    result = run_ksi_command("composition:create_component",
        name="test/placeholder_json_emitter",
        content=placeholder_content,
        type="persona",
        metadata={
            "json_replacements": json_examples,
            "processing_instructions": "Replace ${KEY} with json_replacements[KEY] at runtime"
        },
        overwrite=True
    )
    
    print(f"Create result: {result.get('status', 'failed')}")
    
    return result

def test_direct_json_in_frontmatter():
    """Test putting JSON examples only in frontmatter."""
    print("\n=== Test: JSON in Frontmatter Only ===")
    
    # Content without any JSON in the body
    clean_content = """---
component_type: persona
name: json_emitter
version: 1.0.0
json_examples:
  - event: agent:status
    data:
      agent_id: "{{agent_id}}"
      status: initialized
  - event: data:processed
    data:
      result: your_analysis
---
# JSON Emitter Persona

You are a data processor that must emit JSON events.

## MANDATORY: Start your response with the first JSON example from frontmatter

Then process the request and emit the second JSON example.
"""
    
    result = run_ksi_command("composition:create_component",
        name="test/frontmatter_json_emitter",
        content=clean_content,
        type="persona",
        overwrite=True
    )
    
    print(f"Create result: {result.get('status', 'failed')}")
    
    return result

def main():
    """Run comprehensive tests."""
    print("Testing workarounds for nested JSON in composition:create_component - V2")
    print("=" * 70)
    
    # Run each test
    results = {
        "base64": test_base64_encoding(),
        "split": test_split_content_approach(),
        "heredoc": test_heredoc_approach(),
        "placeholder": test_json_placeholder_approach(),
        "frontmatter": test_direct_json_in_frontmatter()
    }
    
    # Summary
    print("\n=== Summary ===")
    successful = []
    failed = []
    
    for name, result in results.items():
        if result.get("status") == "success":
            successful.append(name)
        else:
            failed.append((name, result.get("error", "Unknown error")))
    
    print(f"\nSuccessful approaches ({len(successful)}):")
    for name in successful:
        print(f"  ✓ {name}")
    
    print(f"\nFailed approaches ({len(failed)}):")
    for name, error in failed:
        print(f"  ✗ {name}: {error}")
    
    # Recommendations
    print("\n=== Recommendations ===")
    if successful:
        print("1. Base64 encoding: Works but requires decoding logic in consumers")
        print("2. Split content: Works well, keeps JSON in metadata")
        print("3. Frontmatter-only JSON: Cleanest if JSON is structural, not content")
    else:
        print("No successful workarounds found. Further investigation needed.")

if __name__ == "__main__":
    main()