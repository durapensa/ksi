#!/usr/bin/env python3
"""
Simple test of component improvement using orchestration approach.
"""

import json
import subprocess
import time

def ksi(event, **kwargs):
    """Execute KSI command."""
    cmd = ["ksi", "send", event]
    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            cmd.extend([f"--{k}", json.dumps(v)])
        else:
            cmd.extend([f"--{k}", str(v)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return {}
    
    try:
        return json.loads(result.stdout)
    except:
        return {"raw": result.stdout}

def main():
    print("Simple component improvement test using orchestration approach")
    
    # Simple greeting component
    component = """---
component_type: agent
name: simple_greeting
version: 1.0.0
---
You are a greeting specialist who provides warm greetings."""
    
    # Step 1: Spawn analyzer
    print("\n1. Spawning analyzer agent...")
    result = ksi("agent:spawn",
        component="personas/optimizers/component_analyzer",
        agent_id="test_analyzer"
    )
    print(f"Analyzer: {result.get('status')}")
    
    # Step 2: Send component to analyzer
    print("\n2. Sending component to analyzer...")
    result = ksi("completion:async",
        agent_id="test_analyzer",
        prompt=f"Analyze this component for improvements:\n{component}"
    )
    request_id = result.get("request_id")
    print(f"Request ID: {request_id}")
    
    # Wait for completion
    print("Waiting for analysis...")
    time.sleep(15)
    
    # Step 3: Check the response
    print("\n3. Checking analyzer response...")
    # Get recent responses
    result = subprocess.run(
        ["ls", "-lat", "var/logs/responses/*.jsonl"], 
        capture_output=True, text=True, shell=True
    )
    print("Recent responses:", result.stdout.split('\n')[0])
    
    # Step 4: Spawn JSON orchestrator
    print("\n4. Spawning JSON orchestrator...")
    result = ksi("agent:spawn",
        component="core/json_orchestrator", 
        agent_id="test_json_emitter"
    )
    print(f"JSON orchestrator: {result.get('status')}")
    
    # Step 5: Send improved component to JSON orchestrator
    improved = """---
component_type: agent
name: simple_greeting
version: 2.0.0
---
Hello! How can I help you today?"""
    
    print("\n5. Sending improved component to JSON orchestrator...")
    result = ksi("completion:async",
        agent_id="test_json_emitter",
        prompt=f'''Extract this component and emit as JSON:

{improved}

Emit: {{"event": "composition:create_component", "data": {{"name": "agents/test_simple_improved", "content": "[component content]"}}}}'''
    )
    print(f"Request ID: {result.get('request_id')}")
    
    # Wait and check
    print("Waiting for JSON emission...")
    time.sleep(10)
    
    # Check if component was created
    print("\n6. Checking for created component...")
    result = ksi("composition:get_component",
        name="agents/test_simple_improved"
    )
    
    if result.get("name"):
        print("✓ Component created successfully!")
        print(f"Content: {result.get('content')}")
    else:
        print("✗ Component not created")
    
    # Cleanup
    print("\n7. Cleaning up...")
    ksi("agent:terminate", agent_id="test_analyzer", force=True)
    ksi("agent:terminate", agent_id="test_json_emitter", force=True)
    
    return bool(result.get("name"))

if __name__ == "__main__":
    success = main()
    print(f"\n{'✅ PASSED' if success else '❌ FAILED'}")