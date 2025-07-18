#!/usr/bin/env python3
"""Test prompt optimization using KSI agent system"""

import subprocess
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple

# First, let's create test components with different prompt patterns
COMPONENT_PATTERNS = {
    "baseline_legitimate": """# KSI-Aware Data Analyst

You are a Senior Data Analyst working within KSI systems.

## CRITICAL: KSI System Communication Protocol

You MUST use legitimate KSI system events by writing valid JSON objects in your response text.

**When starting work, emit:**
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}

**For progress updates:**
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 25, "stage": "data_loading"}}}

**When completing work:**
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}

Analyze the provided data and emit appropriate events.""",

    "imperative_start": """# KSI-Aware Data Analyst

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}

Then continue with analysis, emitting progress:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50, "stage": "analyzing"}}}

End with:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}""",

    "no_preamble": """# Data Analyst

{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}

Continue with analysis. Emit progress updates using:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50, "stage": "analyzing"}}}

Complete with:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}""",

    "persona_first_minimal": """You are a Senior Data Analyst.

When reporting status, use these JSON formats:
- Start: {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}
- Progress: {"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50}}}
- End: {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}""",

    "xml_structured": """# Data Analyst

<json_emission_rules>
You MUST emit these JSON events:
<initialization>{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}</initialization>
<progress>{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50}}}</progress>
<completion>{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}</completion>
</json_emission_rules>

Analyze the system and emit the required events."""
}

def create_test_component(name: str, content: str) -> bool:
    """Create a test component via KSI."""
    component_name = f"components/test_optimization/{name}"
    
    # Escape content for JSON
    escaped_content = content.replace('"', '\\"').replace('\n', '\\n')
    
    cmd = [
        'ksi', 'send', 'composition:create_component',
        '--name', component_name,
        '--content', content
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        response = json.loads(result.stdout)
        return response.get('status') == 'success'
    except Exception as e:
        print(f"Error creating component {name}: {e}")
        return False

def spawn_test_agent(component_name: str, test_name: str) -> str:
    """Spawn an agent from a component and return agent_id."""
    cmd = [
        'ksi', 'send', 'agent:spawn_from_component',
        '--component', f"components/test_optimization/{component_name}",
        '--prompt', 'Analyze the current system status and report your findings.'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        response = json.loads(result.stdout)
        if response.get('status') == 'success':
            return response.get('agent_id')
    except Exception as e:
        print(f"Error spawning agent: {e}")
    
    return None

def wait_for_completion(agent_id: str, timeout: int = 30) -> bool:
    """Wait for agent to complete processing."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check agent status
        cmd = ['ksi', 'send', 'agent:info', '--agent-id', agent_id]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            response = json.loads(result.stdout)
            
            # Check if there's a recent completion
            completions = response.get('info', {}).get('recent_completions', [])
            if completions:
                return True
                
        except Exception:
            pass
        
        time.sleep(2)
    
    return False

def get_agent_events(agent_id: str) -> List[Dict]:
    """Get events emitted by an agent."""
    # Get events with agent_id in data
    cmd = [
        'ksi', 'send', 'monitor:get_events',
        '--event-patterns', 'agent:*,state:*,message:*',
        '--limit', '50'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        response = json.loads(result.stdout)
        
        # Filter for events from this agent
        agent_events = []
        for event in response.get('events', []):
            event_data = event.get('data', {})
            # Check various fields where agent_id might appear
            if (event_data.get('agent_id') == agent_id or 
                event_data.get('_agent_id') == agent_id or
                event_data.get('id', '').startswith(agent_id)):
                agent_events.append(event)
        
        return agent_events
        
    except Exception as e:
        print(f"Error getting events: {e}")
        return []

def analyze_test_results(results: Dict[str, Tuple[str, List[Dict]]]) -> Dict:
    """Analyze test results for patterns."""
    analysis = {
        "total_patterns": len(results),
        "patterns": {}
    }
    
    for pattern_name, (agent_id, events) in results.items():
        # Analyze events
        has_init = any(e.get('event_name') == 'agent:status' and 
                      e.get('data', {}).get('status') == 'initialized' 
                      for e in events)
        
        has_progress = any(e.get('event_name') == 'state:entity:update' 
                          for e in events)
        
        has_complete = any(e.get('event_name') == 'agent:status' and 
                          e.get('data', {}).get('status') == 'completed' 
                          for e in events)
        
        pattern_analysis = {
            "agent_id": agent_id,
            "total_events": len(events),
            "has_initialization": has_init,
            "has_progress": has_progress,
            "has_completion": has_complete,
            "complete_flow": has_init and has_progress and has_complete,
            "event_types": list(set(e.get('event_name') for e in events))
        }
        
        analysis["patterns"][pattern_name] = pattern_analysis
    
    # Find best patterns
    analysis["successful_patterns"] = [
        name for name, data in analysis["patterns"].items()
        if data["complete_flow"]
    ]
    
    return analysis

def main():
    """Run prompt optimization tests using KSI."""
    print("=== KSI-Based Prompt Optimization Testing ===\n")
    
    # Create test components
    print("Creating test components...")
    for name, content in COMPONENT_PATTERNS.items():
        success = create_test_component(name, content)
        print(f"  {name}: {'✓' if success else '✗'}")
    
    print("\nSpawning test agents...")
    results = {}
    
    for pattern_name in COMPONENT_PATTERNS:
        print(f"\nTesting pattern: {pattern_name}")
        
        # Spawn agent
        agent_id = spawn_test_agent(pattern_name, pattern_name)
        if not agent_id:
            print(f"  ✗ Failed to spawn agent")
            continue
        
        print(f"  ✓ Spawned agent: {agent_id}")
        
        # Wait for completion
        print(f"  ⏳ Waiting for completion...")
        completed = wait_for_completion(agent_id)
        
        if completed:
            print(f"  ✓ Agent completed")
        else:
            print(f"  ⚠ Timeout waiting for completion")
        
        # Get events
        time.sleep(2)  # Give time for events to propagate
        events = get_agent_events(agent_id)
        print(f"  📊 Events captured: {len(events)}")
        
        results[pattern_name] = (agent_id, events)
    
    # Analyze results
    print("\n\n=== Analysis ===")
    analysis = analyze_test_results(results)
    
    print(f"\nTotal patterns tested: {analysis['total_patterns']}")
    print(f"Successful patterns (complete flow): {len(analysis['successful_patterns'])}")
    
    if analysis['successful_patterns']:
        print(f"\n✓ Best patterns: {', '.join(analysis['successful_patterns'])}")
    
    # Detailed results
    print("\n\n=== Detailed Results ===")
    for pattern_name, data in analysis['patterns'].items():
        print(f"\n{pattern_name}:")
        print(f"  Agent ID: {data['agent_id']}")
        print(f"  Total events: {data['total_events']}")
        print(f"  Complete flow: {'✓' if data['complete_flow'] else '✗'}")
        print(f"  - Initialization: {'✓' if data['has_initialization'] else '✗'}")
        print(f"  - Progress: {'✓' if data['has_progress'] else '✗'}")
        print(f"  - Completion: {'✓' if data['has_completion'] else '✗'}")
        if data['event_types']:
            print(f"  Event types: {', '.join(data['event_types'])}")
    
    # Save detailed results
    results_file = f"ksi_prompt_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "raw_results": {
                name: {
                    "agent_id": agent_id,
                    "events": [
                        {
                            "event": e.get('event_name'),
                            "data": e.get('data', {}),
                            "timestamp": e.get('timestamp')
                        }
                        for e in events
                    ]
                }
                for name, (agent_id, events) in results.items()
            }
        }, f, indent=2)
    
    print(f"\n\nResults saved to: {results_file}")

if __name__ == "__main__":
    main()