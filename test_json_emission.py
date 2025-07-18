#!/usr/bin/env python3
"""Focused test for JSON emission patterns with Claude"""

import subprocess
import json
from datetime import datetime

# Simpler, focused test prompts
TEST_PROMPTS = {
    "direct_json": 'Emit this JSON: {"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}',
    
    "simple_instruction": 'Start by emitting {"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}. Then say hello.',
    
    "analyst_persona": """You are a data analyst. When starting work, emit:
{"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}

Analyze: Sales increased 20% this quarter.""",
    
    "critical_instruction": """CRITICAL: You MUST start with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}

Then analyze the system.""",
    
    "no_preamble": """{"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}

Continue with analysis of system performance.""",
    
    "multi_event": """Emit these events during your work:
1. Start: {"event": "agent:status", "data": {"agent_id": "test", "status": "initialized"}}
2. Progress: {"event": "state:entity:update", "data": {"id": "test_progress", "properties": {"percent": 50}}}
3. End: {"event": "agent:status", "data": {"agent_id": "test", "status": "completed"}}

Analyze system status."""
}

def test_prompt(name: str, prompt: str):
    """Test a single prompt and analyze results."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    try:
        # Run Claude with the prompt
        result = subprocess.run(
            ['/Users/dp/.claude/local/claude', '--print', prompt],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout.strip()
        print(f"Output length: {len(output)} chars")
        
        # Try to extract JSON events
        events = []
        lines = output.split('\n')
        for i, line in enumerate(lines):
            if '{' in line and '"event"' in line:
                # Try to extract JSON
                try:
                    # Find JSON boundaries
                    start = line.find('{')
                    if start != -1:
                        # Simple extraction for single-line JSON
                        end = line.rfind('}') + 1
                        if end > start:
                            json_str = line[start:end]
                            event = json.loads(json_str)
                            if 'event' in event:
                                events.append({
                                    'line': i + 1,
                                    'event': event
                                })
                                print(f"✓ Found event on line {i+1}: {event['event']}")
                except json.JSONDecodeError as e:
                    print(f"✗ JSON parse error on line {i+1}: {e}")
        
        if not events:
            print("✗ No JSON events found")
            print(f"First 200 chars of output:\n{output[:200]}")
        else:
            print(f"\n✓ Total events found: {len(events)}")
        
        # Save raw output for analysis
        with open(f"json_test_{name}.txt", 'w') as f:
            f.write(output)
            
    except subprocess.TimeoutExpired:
        print("✗ Timeout expired")
    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    print("JSON Emission Testing with Claude\n")
    
    # Test each prompt
    for name, prompt in TEST_PROMPTS.items():
        test_prompt(name, prompt)
    
    print(f"\n{'='*60}")
    print("Testing complete. Raw outputs saved as json_test_*.txt")

if __name__ == "__main__":
    main()