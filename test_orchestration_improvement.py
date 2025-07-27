#\!/usr/bin/env python3
"""
Test orchestration-based component improvement workflow.
"""

import json
import subprocess
import time

def run_ksi_command(event, data):
    """Run a KSI command and return the result."""
    cmd = ["ksi", "send", event]
    for key, value in data.items():
        if isinstance(value, dict) or isinstance(value, list):
            cmd.extend([f"--{key}", json.dumps(value)])
        else:
            cmd.extend([f"--{key}", str(value)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return {}
    
    try:
        return json.loads(result.stdout)
    except:
        return {"raw": result.stdout}

def main():
    print("Testing orchestration-based component improvement...")
    
    # The verbose component to improve
    verbose_component = '''---
component_type: agent
name: verbose_greeting_agent
version: 1.0.0
description: An overly verbose greeting agent that needs optimization
---

# Professional Greeting Specialist Agent

You are a highly trained professional greeting specialist with extensive experience.

## Your Role and Responsibilities

As a greeting specialist, your primary responsibility is to provide warm, welcoming, 
and professionally appropriate greetings to all users who interact with you.

## Greeting Guidelines

When a user greets you, respond with an appropriate greeting that:
1. Acknowledges their greeting
2. Is warm and welcoming
3. Is professionally appropriate
4. May include a brief pleasantry

Your goal is to make every user feel welcomed and valued.'''
    
    # Start the orchestration
    print("\n1. Starting component improvement orchestration...")
    result = run_ksi_command("orchestration:start", {
        "pattern": "orchestrations/component_improvement_orchestration",
        "vars": json.dumps({
            "component_content": verbose_component,
            "output_component_name": "agents/concise_greeting_agent"
        })
    })
    
    orchestration_id = result.get("orchestration_id")
    print(f"✓ Orchestration started: {orchestration_id}")
    
    # Wait for completion
    print("\n2. Waiting for orchestration to complete...")
    max_wait = 120
    elapsed = 0
    check_interval = 10
    
    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        
        status = run_ksi_command("orchestration:status", {
            "orchestration_id": orchestration_id
        })
        
        print(f"  Status: {status.get('status')} ({elapsed}s elapsed)")
        
        if status.get("status") in ["completed", "failed", "terminated"]:
            break
    
    # Check for created component
    print("\n3. Checking for improved component...")
    component = run_ksi_command("composition:get_component", {
        "name": "agents/concise_greeting_agent"
    })
    
    if component.get("name"):
        print("✓ Component created successfully\!")
        print("\nImproved component content:")
        print("-" * 50)
        print(component.get("content", ""))
        print("-" * 50)
    else:
        print("✗ Component not found")
    
    # Cleanup
    print("\n4. Cleaning up...")
    run_ksi_command("orchestration:stop", {
        "orchestration_id": orchestration_id,
        "force": True
    })
    print("✓ Orchestration stopped")
    
    return bool(component.get("name"))

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n✅ Orchestration-based improvement workflow PASSED\!")
    else:
        print("\n❌ Orchestration-based improvement workflow FAILED\!")
        print("\nTroubleshooting:")
        print("1. Check orchestration logs: ksi send orchestration:status --orchestration-id [id]")
        print("2. Check daemon logs: tail -f var/logs/daemon/daemon.log.jsonl | jq")
