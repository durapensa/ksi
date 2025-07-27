#!/usr/bin/env python3
"""
Demonstration of JSON event emission in KSI.

This test shows:
1. What happens when agents are asked to emit JSON
2. How the system actually works
3. Recommended patterns for JSON emission
"""

import json
import time
import subprocess
import uuid
import sys

def run_command(cmd):
    """Run command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def extract_json(text):
    """Extract JSON from text output."""
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
    except:
        pass
    return None

def demo_1_direct_request():
    """Demo 1: What happens with direct JSON request."""
    print("\n" + "="*70)
    print("DEMO 1: Direct JSON Request to Agent")
    print("="*70)
    
    agent_id = f"demo1_{uuid.uuid4().hex[:8]}"
    
    print(f"\nSpawning agent {agent_id} with instruction to emit JSON...")
    
    json_prompt = '{"event": "test:demo", "data": {"message": "hello"}}'
    cmd = f'''ksi send agent:spawn \
        --agent-id {agent_id} \
        --component core/base_agent \
        --prompt '{json_prompt}' \
        --task demo'''
    
    stdout, stderr, code = run_command(cmd)
    
    if code == 0:
        print("✅ Agent spawned successfully")
        
        # Wait and check what happened
        time.sleep(3)
        
        # Check agent's actual response
        cmd = f"ksi send monitor:get_events --event-patterns 'completion:complete' --limit 5"
        stdout, stderr, code = run_command(cmd)
        
        if code == 0:
            data = extract_json(stdout)
            if data and "events" in data.get("data", {}):
                events = data["data"]["events"]
                
                # Find our agent's completion
                for event in events:
                    if agent_id in str(event.get("data", {})):
                        completion = event.get("data", {}).get("completion", "")
                        print("\nAgent's actual response:")
                        print("-" * 50)
                        print(completion[:300] + "..." if len(completion) > 300 else completion)
                        print("-" * 50)
                        
                        if '{"event"' in completion:
                            print("\n✅ Agent included JSON in response")
                        else:
                            print("\n❌ Agent described what to do instead of emitting JSON")
                        break
    else:
        print(f"❌ Failed to spawn agent: {stderr}")

def demo_2_system_extraction():
    """Demo 2: How KSI extracts events from agent responses."""
    print("\n" + "="*70)
    print("DEMO 2: System Event Extraction")
    print("="*70)
    
    print("\nKSI can extract properly formatted JSON events from agent text.")
    print("When an agent includes valid KSI events in their response,")
    print("the system extracts and processes them.")
    
    # Check recent extracted events
    cmd = "ksi send monitor:get_events --limit 10"
    stdout, stderr, code = run_command(cmd)
    
    if code == 0:
        data = extract_json(stdout)
        if data and "events" in data.get("data", {}):
            events = data["data"]["events"]
            
            extracted = [e for e in events if e.get("data", {}).get("_extracted_from_response")]
            
            if extracted:
                print(f"\n✅ Found {len(extracted)} extracted events")
                print("\nExample extracted event:")
                print(json.dumps(extracted[0], indent=2))
            else:
                print("\n❌ No extracted events found in recent history")

def demo_3_orchestration_pattern():
    """Demo 3: Using orchestration for reliable JSON emission."""
    print("\n" + "="*70)
    print("DEMO 3: Orchestration Pattern (Recommended)")
    print("="*70)
    
    print("\nThe reliable way to emit JSON events is through orchestration:")
    print("1. Agent analyzes the request in natural language")
    print("2. JSON orchestrator translates to actual events")
    print("3. System processes the emitted events")
    
    print("\nExample orchestration pattern:")
    print("-" * 50)
    print("""agents:
  analyzer:
    component: "core/base_agent"
    vars:
      initial_prompt: |
        Analyze what needs to be done and describe it clearly.
  
  json_emitter:
    component: "core/json_orchestrator"
    vars:
      initial_prompt: |
        Based on the analyzer's output, emit the appropriate JSON events.
""")
    print("-" * 50)

def demo_4_working_example():
    """Demo 4: A working example using existing components."""
    print("\n" + "="*70)
    print("DEMO 4: Working Example - Hello/Goodbye Orchestration")
    print("="*70)
    
    print("\nStarting hello_goodbye orchestration...")
    
    cmd = 'ksi send orchestration:start --pattern orchestrations/hello_goodbye'
    stdout, stderr, code = run_command(cmd)
    
    if code == 0:
        data = extract_json(stdout)
        if data and "orchestration_id" in data:
            orch_id = data["orchestration_id"]
            print(f"✅ Orchestration started: {orch_id}")
            
            # Wait for it to complete
            time.sleep(5)
            
            # Check orchestration events
            cmd = f"ksi send monitor:get_events --event-patterns 'agent:*' --limit 10"
            stdout, stderr, code = run_command(cmd)
            
            if code == 0:
                data = extract_json(stdout)
                if data and "events" in data.get("data", {}):
                    events = data["data"]["events"]
                    
                    # Count agent events from this orchestration
                    orch_events = [e for e in events if orch_id in str(e.get("data", {}))]
                    
                    if orch_events:
                        print(f"\n✅ Orchestration generated {len(orch_events)} agent events")
                    else:
                        print("\n❌ No agent events from orchestration found")
    else:
        print(f"❌ Failed to start orchestration: {stderr}")

def main():
    print("\n" + "="*70)
    print("KSI JSON EVENT EMISSION DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how JSON event emission actually works in KSI.")
    
    # Run demos
    demo_1_direct_request()
    demo_2_system_extraction()
    demo_3_orchestration_pattern()
    demo_4_working_example()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
KEY FINDINGS:

1. AGENT BEHAVIOR: When asked to emit JSON, agents typically describe
   what they would do rather than actually emitting the JSON.

2. SYSTEM EXTRACTION: KSI can extract properly formatted JSON events
   from agent responses if they include them in their text.

3. ORCHESTRATION PATTERN: The most reliable approach is to use
   orchestration with dedicated JSON translator components.

4. DESIGN PHILOSOPHY: KSI is designed for natural language communication
   between agents. JSON emission is a special case best handled by
   specialized components.

RECOMMENDATION:
For reliable JSON event emission, use the three-layer orchestration pattern:
- Analysis Layer: Agents understand and analyze in natural language
- Translation Layer: JSON orchestrator converts to events  
- Execution Layer: System processes the JSON events
""")

if __name__ == "__main__":
    main()