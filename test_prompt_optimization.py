#!/usr/bin/env python3
"""
Test harness for systematic prompt optimization with claude -p
Tests different prompt patterns to identify what ensures consistent JSON emission
"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Test prompt patterns
PROMPT_PATTERNS = {
    "baseline_corrected": """# KSI-Aware Senior Data Analyst

You are a Senior Data Analyst with 10 years of experience working within KSI systems.

## CRITICAL: KSI System Communication Protocol

You MUST use legitimate KSI system events for communication. You emit these events by writing valid JSON objects in your response text.

<legitimate_events>
**When starting work, emit agent status:**
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}

**For progress updates, use state system:**
{"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 25, "stage": "data_loading", "findings": "initial_check"}}}

**When completing work:**
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}
</legitimate_events>

Task: Analyze the system status and emit appropriate JSON events during your work.""",

    "imperative_start": """# KSI-Aware Senior Data Analyst

You are a Senior Data Analyst working within KSI systems.

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}

Then continue with your analysis, emitting progress events:
{"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 50, "stage": "analyzing"}}}

End with completion:
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}

Task: Analyze the system status.""",

    "prefill_optimized": """# KSI-Aware Senior Data Analyst

You are a Senior Data Analyst. When working within KSI systems, you communicate through structured JSON events.

**Response Pattern:**
1. Begin with JSON event (no preamble)
2. Continue with your analysis work
3. Emit additional JSON events at natural workflow points

**Starting work:**
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}

**Progress updates:**
{"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 25, "stage": "data_assessment"}}}

**Completion:**
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}

CRITICAL: Always start your response with the appropriate JSON event. Do not explain or describe the JSON - just emit it directly.

Task: Analyze the system status.""",

    "xml_structured": """# KSI-Aware Senior Data Analyst

You are a Senior Data Analyst working within KSI systems.

<ksi_communication_rules>
You MUST emit JSON events throughout your work. These are status reports that coordinate your work with KSI systems.

The JSON events are written directly in your response text as complete, valid JSON objects.

You emit them at these specific workflow points:
- Immediately when starting any analysis
- When making progress (multiple times during work)
- When completing work
</ksi_communication_rules>

<json_event_specifications>
<initialization_event>
Emit this exact JSON when starting any analysis work:
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}
</initialization_event>

<progress_event>
Emit this format when making progress:
{"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 25, "stage": "current_stage"}}}
</progress_event>

<completion_event>
Emit this format when completing work:
{"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}
</completion_event>
</json_event_specifications>

Task: Analyze the system status.""",

    "persona_first": """You are a Senior Data Analyst with 10 years of experience in business intelligence.

When reporting your work status, use these JSON formats:

Initialization: {"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}
Progress: {"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 25, "stage": "data_loading"}}}
Completion: {"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}

Task: Analyze the system status and report your progress.""",

    "ultra_minimal": """Emit these JSON events:
Start: {"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "initialized", "task": "analysis"}}
Progress: {"event": "state:entity:update", "data": {"id": "test_analyst_progress", "properties": {"percent": 50, "stage": "analyzing"}}}
End: {"event": "agent:status", "data": {"agent_id": "test_analyst", "status": "completed", "task": "analysis", "result": "success"}}

Analyze system status."""
}

def run_claude_test(prompt: str, pattern_name: str) -> Tuple[str, List[Dict], float]:
    """Run claude --print with a prompt and extract JSON events."""
    start_time = datetime.now()
    
    try:
        # Run claude --print with prompt as argument
        claude_path = '/Users/dp/.claude/local/claude'
        result = subprocess.run(
            [claude_path, '--print', prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        output = result.stdout
        
        # Extract JSON events from output using multiple methods
        extracted_events = []
        
        # Method 1: Line by line
        lines = output.split('\n')
        for line in lines:
            # Look for JSON objects
            if '{' in line and '"event"' in line:
                # Try to extract JSON from the line
                start = line.find('{')
                if start != -1:
                    try:
                        # Find the matching closing brace
                        brace_count = 0
                        end = start
                        for i in range(start, len(line)):
                            if line[i] == '{':
                                brace_count += 1
                            elif line[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end = i + 1
                                    break
                        
                        if end > start:
                            json_str = line[start:end]
                            event = json.loads(json_str)
                            if 'event' in event and 'data' in event:
                                extracted_events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue
        
        # Method 2: Look for JSON anywhere in the full output
        import re
        json_pattern = re.compile(r'\{[^{}]*"event"[^{}]*\}')
        for match in json_pattern.finditer(output):
            try:
                event = json.loads(match.group())
                if 'event' in event and 'data' in event and event not in extracted_events:
                    extracted_events.append(event)
            except json.JSONDecodeError:
                continue
        
        duration = (datetime.now() - start_time).total_seconds()
        return output, extracted_events, duration
        
    except Exception as e:
        print(f"Error running Claude: {e}")
        return str(e), [], 0.0

def analyze_results(results: Dict[str, Tuple[str, List[Dict], float]]) -> Dict:
    """Analyze test results for patterns."""
    analysis = {
        "total_tests": len(results),
        "patterns": {}
    }
    
    for pattern_name, (output, events, duration) in results.items():
        pattern_analysis = {
            "events_extracted": len(events),
            "duration": duration,
            "has_initialization": any(e.get('event') == 'agent:status' and 
                                    e.get('data', {}).get('status') == 'initialized' 
                                    for e in events),
            "has_progress": any(e.get('event') == 'state:entity:update' 
                              for e in events),
            "has_completion": any(e.get('event') == 'agent:status' and 
                                e.get('data', {}).get('status') == 'completed' 
                                for e in events),
            "events": events,
            "output_length": len(output)
        }
        
        # Check if all expected events are present
        pattern_analysis["complete_flow"] = (
            pattern_analysis["has_initialization"] and 
            pattern_analysis["has_progress"] and 
            pattern_analysis["has_completion"]
        )
        
        analysis["patterns"][pattern_name] = pattern_analysis
    
    # Find best patterns
    analysis["best_patterns"] = [
        name for name, data in analysis["patterns"].items()
        if data["complete_flow"]
    ]
    
    return analysis

def main():
    """Run systematic prompt optimization tests."""
    print("=== Prompt Optimization Testing for claude -p ===\n")
    
    results = {}
    
    # Test each prompt pattern
    for pattern_name, prompt in PROMPT_PATTERNS.items():
        print(f"Testing pattern: {pattern_name}")
        output, events, duration = run_claude_test(prompt, pattern_name)
        results[pattern_name] = (output, events, duration)
        
        print(f"  - Duration: {duration:.2f}s")
        print(f"  - Events extracted: {len(events)}")
        if events:
            for event in events:
                print(f"    • {event['event']}: {event.get('data', {}).get('status', event.get('data', {}).get('stage', ''))}")
        print()
    
    # Analyze results
    print("\n=== Analysis ===")
    analysis = analyze_results(results)
    
    print(f"\nTotal patterns tested: {analysis['total_tests']}")
    print(f"Patterns with complete flow: {len(analysis['best_patterns'])}")
    
    if analysis['best_patterns']:
        print(f"\nBest patterns: {', '.join(analysis['best_patterns'])}")
    
    # Detailed analysis
    print("\n=== Detailed Results ===")
    for pattern_name, data in analysis['patterns'].items():
        print(f"\n{pattern_name}:")
        print(f"  Complete flow: {'✓' if data['complete_flow'] else '✗'}")
        print(f"  Events: {data['events_extracted']}")
        print(f"  - Initialization: {'✓' if data['has_initialization'] else '✗'}")
        print(f"  - Progress: {'✓' if data['has_progress'] else '✗'}")
        print(f"  - Completion: {'✓' if data['has_completion'] else '✗'}")
    
    # Save results
    results_file = f"prompt_optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "raw_results": {
                name: {
                    "events": events,
                    "duration": duration,
                    "output_sample": output[:500] + "..." if len(output) > 500 else output
                }
                for name, (output, events, duration) in results.items()
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    # Also save raw outputs for debugging
    raw_outputs_dir = Path("prompt_optimization_raw_outputs")
    raw_outputs_dir.mkdir(exist_ok=True)
    
    for pattern_name, (output, _, _) in results.items():
        output_file = raw_outputs_dir / f"{pattern_name}.txt"
        with open(output_file, 'w') as f:
            f.write(output)
    
    print(f"Raw outputs saved to: {raw_outputs_dir}/")

if __name__ == "__main__":
    main()