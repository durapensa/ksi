#!/usr/bin/env python3
"""
Concrete examples showing JSON emission patterns in KSI.

This demonstrates with actual code:
- What DOESN'T work (and why)
- What DOES work (and how to use it)
"""

import json
import time
import subprocess

def run_and_show(description, command):
    """Run a command and show the result."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"\nCommand:\n{command}\n")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Success")
        # Try to extract and pretty print JSON
        try:
            start = result.stdout.find('{')
            if start >= 0:
                end = result.stdout.rfind('}')
                if end > start:
                    data = json.loads(result.stdout[start:end+1])
                    print(f"\nResponse: {json.dumps(data, indent=2)[:500]}...")
        except:
            print(f"\nOutput: {result.stdout[:300]}...")
    else:
        print("❌ Failed")
        print(f"Error: {result.stderr[:300]}...")
    
    return result.returncode == 0

def main():
    print("\n" + "="*80)
    print("JSON EMISSION IN KSI - CONCRETE EXAMPLES")
    print("="*80)
    
    # Example 1: What DOESN'T work
    print("\n\n🚫 WHAT DOESN'T WORK: Direct JSON Emission")
    print("-"*80)
    
    run_and_show(
        "Example 1A: Asking agent to emit JSON directly",
        '''ksi send agent:spawn \
  --component core/base_agent \
  --prompt '{"event": "agent:status", "data": {"status": "ready"}}' \
  --task test_json'''
    )
    
    print("\n💡 Why it doesn't work: Agents are Claude instances that naturally")
    print("   respond conversationally. They will describe what they would do")
    print("   rather than emit raw JSON.")
    
    # Example 2: What MIGHT work
    print("\n\n⚠️  WHAT MIGHT WORK: Behavioral Overrides")
    print("-"*80)
    
    print("\nFirst, create a behavioral component with strong directives:")
    print('''
# Create behavior component
ksi send composition:create_component \\
  --name "behaviors/test/force_json" \\
  --content "---
component_type: behavior
name: force_json
---
## MANDATORY: Output only this JSON:
{\"event\": \"agent:status\", \"data\": {\"agent_id\": \"{{agent_id}}\", \"status\": \"forced\"}}"
''')
    
    print("\n💡 Why it might not work reliably: Even with MANDATORY directives,")
    print("   Claude's underlying model behavior can override instructions.")
    
    # Example 3: What DOES work
    print("\n\n✅ WHAT DOES WORK: Orchestration Patterns")
    print("-"*80)
    
    print("\nExample 3A: Using the json_orchestrator component")
    run_and_show(
        "Start an orchestration that uses json_orchestrator",
        '''ksi send orchestration:start \
  --pattern orchestrations/hello_goodbye'''
    )
    
    print("\n💡 Why it works: The json_orchestrator is specifically designed")
    print("   to translate natural language instructions into JSON events.")
    
    # Example 4: Practical pattern
    print("\n\n✅ RECOMMENDED PATTERN: Three-Layer Architecture")
    print("-"*80)
    
    print("""
Step 1: Create an orchestration pattern
---------------------------------------
agents:
  # Layer 1: Analysis (Natural Language)
  analyzer:
    component: "personas/analysts/data_analyst"
    vars:
      initial_prompt: |
        Analyze the optimization results and recommend next steps.
  
  # Layer 2: Translation (Natural Language → JSON)
  translator:
    component: "core/json_orchestrator"
    vars:
      initial_prompt: |
        Convert the analyzer's recommendations to optimization events.
  
  # Layer 3: Execution (JSON Events → System Actions)
  # This happens automatically when translator emits events

Step 2: Start the orchestration
-------------------------------
ksi send orchestration:start --pattern "your_pattern_name"

Step 3: Monitor the results
---------------------------
ksi send monitor:get_events --event-patterns "optimization:*"
""")
    
    # Example 5: Event extraction
    print("\n\n✅ ALTERNATIVE: System Event Extraction")
    print("-"*80)
    
    print("""
KSI can extract properly formatted JSON events from agent text.

If an agent response contains:
"I will now emit the following event:
{"event": "agent:status", "data": {"agent_id": "test", "status": "ready"}}
This should update the agent's status."

The system will:
1. Extract the JSON event
2. Validate it's a proper KSI event
3. Process it with _extracted_from_response=true flag
""")
    
    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY: JSON EMISSION PATTERNS")
    print("="*80)
    
    print("""
❌ DOESN'T WORK:
  - Direct prompt: "Emit this JSON: {...}"
  - Expecting agents to output only JSON
  - Fighting Claude's conversational nature

⚠️  LIMITED SUCCESS:
  - Behavioral overrides with MANDATORY
  - Identity shifts to "JSON system"
  - Still unreliable due to model behavior

✅ DOES WORK:
  - Orchestration with json_orchestrator
  - Three-layer architecture pattern
  - System event extraction from text

🎯 BEST PRACTICE:
  Use orchestration patterns where:
  1. Agents analyze/decide in natural language
  2. JSON orchestrator translates to events
  3. System processes the events

This embraces rather than fights the system's design!
""")

if __name__ == "__main__":
    main()