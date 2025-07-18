#!/usr/bin/env python3
"""Validate imperative pattern findings for JSON emission"""

import subprocess
import json
import time

# Test variations of the successful pattern
VALIDATION_PATTERNS = {
    "imperative_original": """# KSI-Aware Data Analyst

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Analyze the system.""",

    "imperative_without_mandatory": """# KSI-Aware Data Analyst

Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Analyze the system.""",

    "imperative_with_must": """# KSI-Aware Data Analyst

You MUST start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Analyze the system.""",

    "conditional_when": """# KSI-Aware Data Analyst

When starting work, emit this JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Analyze the system.""",

    "direct_json_first": """{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

# KSI-Aware Data Analyst
Analyze the system."""
}

def test_pattern(name: str, content: str) -> dict:
    """Test a single pattern and return results."""
    print(f"\nTesting: {name}")
    
    # Create component
    cmd = [
        'ksi', 'send', 'composition:create_component',
        '--name', f'components/validation/{name}',
        '--content', content
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if json.loads(result.stdout).get('status') != 'success':
        return {"error": "Failed to create component"}
    
    # Spawn agent
    cmd = [
        'ksi', 'send', 'agent:spawn_from_component',
        '--component', f'components/validation/{name}',
        '--prompt', 'Begin your analysis.'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    response = json.loads(result.stdout)
    if response.get('status') != 'success':
        return {"error": "Failed to spawn agent"}
    
    agent_id = response.get('agent_id')
    print(f"  Agent: {agent_id}")
    
    # Wait briefly for processing
    time.sleep(15)
    
    # Check for events
    cmd = [
        'ksi', 'send', 'monitor:get_events',
        '--event-patterns', 'agent:status',
        '--limit', '10'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    response = json.loads(result.stdout)
    
    # Find events from this agent
    agent_events = [
        e for e in response.get('events', [])
        if e.get('data', {}).get('agent_id') == agent_id
    ]
    
    return {
        "agent_id": agent_id,
        "events_found": len(agent_events) > 0,
        "event_count": len(agent_events),
        "events": agent_events
    }

def main():
    print("=== Imperative Pattern Validation ===")
    
    results = {}
    for name, content in VALIDATION_PATTERNS.items():
        results[name] = test_pattern(name, content)
        print(f"  Result: {'✓' if results[name].get('events_found') else '✗'}")
    
    print("\n=== Summary ===")
    successful = [name for name, r in results.items() if r.get('events_found')]
    print(f"Successful patterns: {len(successful)}/{len(results)}")
    if successful:
        print(f"Working patterns: {', '.join(successful)}")
    
    # Save results
    with open('imperative_validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to imperative_validation_results.json")

if __name__ == "__main__":
    main()