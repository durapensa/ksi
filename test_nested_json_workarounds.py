#!/usr/bin/env python3
"""Test different workarounds for nested JSON in composition:create_component events."""

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

def run_ksi_command(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a KSI command and return the result."""
    cmd = ["ksi", "send", event]
    for key, value in data.items():
        if isinstance(value, str):
            cmd.extend([f"--{key}", value])
        else:
            cmd.extend([f"--{key}", json.dumps(value)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": result.stderr}
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON response: {result.stdout}"}
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out"}
    except Exception as e:
        return {"error": str(e)}

def test_workaround_1_base64():
    """Test Base64 encoding for content with nested JSON."""
    print("\n=== Test 1: Base64 Encoding ===")
    
    # Encode content as base64
    encoded_content = base64.b64encode(SAMPLE_CONTENT.encode()).decode()
    
    # Create component with base64 content
    result = run_ksi_command("composition:create_component", {
        "name": "test/workaround_base64",
        "content": f"BASE64:{encoded_content}",  # Use a marker to indicate encoding
        "type": "persona",
        "overwrite": "true"
    })
    
    print(f"Create result: {json.dumps(result, indent=2)}")
    
    # Try to get the component back
    time.sleep(1)
    get_result = run_ksi_command("composition:get_component", {
        "name": "test/workaround_base64"
    })
    
    if "content" in get_result:
        print(f"Retrieved content starts with: {get_result['content'][:100]}...")
    
    return result

def test_workaround_2_escape_sequences():
    """Test escape sequences for nested JSON."""
    print("\n=== Test 2: Escape Sequences ===")
    
    # Escape the nested JSON
    escaped_content = SAMPLE_CONTENT.replace('"', '\\"').replace('\n', '\\n')
    
    result = run_ksi_command("composition:create_component", {
        "name": "test/workaround_escaped",
        "content": escaped_content,
        "type": "persona",
        "overwrite": "true"
    })
    
    print(f"Create result: {json.dumps(result, indent=2)}")
    
    # Try to get the component back
    time.sleep(1)
    get_result = run_ksi_command("composition:get_component", {
        "name": "test/workaround_escaped"
    })
    
    if "content" in get_result:
        print(f"Retrieved content starts with: {get_result['content'][:100]}...")
    
    return result

def test_workaround_3_alternative_delimiters():
    """Test using alternative delimiters for JSON."""
    print("\n=== Test 3: Alternative Delimiters ===")
    
    # Replace JSON delimiters with alternatives
    modified_content = SAMPLE_CONTENT.replace('{"event"', '<<event:').replace('"}', '>>')
    modified_content = modified_content.replace('{"', '<<').replace('"}', '>>')
    modified_content = modified_content.replace(': "', ': ~').replace('", ', '~, ')
    
    result = run_ksi_command("composition:create_component", {
        "name": "test/workaround_delimiters",
        "content": modified_content,
        "type": "persona",
        "overwrite": "true"
    })
    
    print(f"Create result: {json.dumps(result, indent=2)}")
    
    # Document the delimiter mapping for reconstruction
    delimiter_map = {
        "<<event:": '{"event"',
        ">>": '"}',
        "<<": '{"',
        ": ~": ': "',
        "~, ": '", '
    }
    print(f"Delimiter map for reconstruction: {delimiter_map}")
    
    return result

def test_workaround_4_split_approach():
    """Test splitting content into metadata and body."""
    print("\n=== Test 4: Split Content Approach ===")
    
    # Split content into frontmatter and body
    parts = SAMPLE_CONTENT.split('\n---\n', 1)
    if len(parts) == 2:
        frontmatter = parts[0].strip('---\n')
        body = parts[1]
    else:
        frontmatter = ""
        body = SAMPLE_CONTENT
    
    # Create with metadata separate from content
    result = run_ksi_command("composition:create_component", {
        "name": "test/workaround_split",
        "content": body,  # Just the body without JSON examples
        "type": "persona",
        "metadata": {
            "frontmatter": frontmatter,
            "json_examples": [
                {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}},
                {"event": "data:processed", "data": {"result": "your_analysis"}}
            ]
        },
        "overwrite": "true"
    })
    
    print(f"Create result: {json.dumps(result, indent=2)}")
    
    return result

def test_workaround_5_json_string_in_data():
    """Test putting JSON as a string in a data field."""
    print("\n=== Test 5: JSON String in Data Field ===")
    
    # Extract JSON examples from content
    json_examples = [
        '{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}',
        '{"event": "data:processed", "data": {"result": "your_analysis"}}'
    ]
    
    # Remove JSON from content and add placeholders
    modified_content = SAMPLE_CONTENT
    for i, example in enumerate(json_examples):
        modified_content = modified_content.replace(example, f"{{{{JSON_EXAMPLE_{i}}}}}")
    
    result = run_ksi_command("composition:create_component", {
        "name": "test/workaround_json_string",
        "content": modified_content,
        "type": "persona",
        "metadata": {
            "json_examples": json_examples,
            "json_placeholders": {
                "JSON_EXAMPLE_0": json_examples[0],
                "JSON_EXAMPLE_1": json_examples[1]
            }
        },
        "overwrite": "true"
    })
    
    print(f"Create result: {json.dumps(result, indent=2)}")
    
    return result

def test_direct_approach():
    """Test the direct approach to see the actual error."""
    print("\n=== Test 0: Direct Approach (Expected to Fail) ===")
    
    result = run_ksi_command("composition:create_component", {
        "name": "test/direct_json",
        "content": SAMPLE_CONTENT,
        "type": "persona",
        "overwrite": "true"
    })
    
    print(f"Result: {json.dumps(result, indent=2)}")
    
    return result

def main():
    """Run all tests."""
    print("Testing workarounds for nested JSON in composition:create_component")
    print("=" * 70)
    
    # Test direct approach first to see the error
    test_direct_approach()
    
    # Test each workaround
    results = {
        "base64": test_workaround_1_base64(),
        "escape": test_workaround_2_escape_sequences(),
        "delimiters": test_workaround_3_alternative_delimiters(),
        "split": test_workaround_4_split_approach(),
        "json_string": test_workaround_5_json_string_in_data()
    }
    
    # Summary
    print("\n=== Summary ===")
    for name, result in results.items():
        status = "SUCCESS" if result.get("status") == "success" else "FAILED"
        print(f"{name}: {status}")
        if "error" in result:
            print(f"  Error: {result['error']}")

if __name__ == "__main__":
    main()