#!/usr/bin/env python3
"""Test that agents can dynamically select compositions"""

import asyncio
import json
import subprocess
import time
import os


async def test_dynamic_selection():
    """Test that agents select appropriate compositions based on their profiles"""
    print("=== Testing Dynamic Composition Selection in Agents ===\n")
    
    # Ensure daemon is running
    print("1. Checking daemon status...")
    proc = subprocess.run(['python3', 'daemon_control.sh', 'status'], 
                         capture_output=True, text=True)
    if 'not running' in proc.stdout:
        print("   Starting daemon...")
        subprocess.run(['python3', 'daemon_control.sh', 'start'], check=True)
        time.sleep(2)
    
    # Test different agent profiles
    test_cases = [
        {
            'profile': 'researcher',
            'task': 'Research the latest developments in quantum computing',
            'expected_compositions': ['autonomous_researcher', 'claude_agent_default']
        },
        {
            'profile': 'coder',
            'task': 'Write a Python function to calculate fibonacci numbers',
            'expected_compositions': ['claude_agent_default', 'autonomous_researcher']
        },
        {
            'profile': 'analyst',
            'task': 'Analyze the performance metrics and identify trends',
            'expected_compositions': ['claude_agent_default', 'autonomous_researcher']
        }
    ]
    
    for i, test_case in enumerate(test_cases, 2):
        print(f"\n{i}. Testing {test_case['profile']} agent...")
        
        # Create a simple test script that spawns an agent
        test_script = f"""
import asyncio
import json
import sys
sys.path.insert(0, '.')
from daemon_client import DaemonClient

async def main():
    client = DaemonClient()
    
    # Spawn agent with specific profile
    result = await client.spawn_agent(
        profile_name='{test_case['profile']}',
        task='{test_case['task']}',
        context='Test dynamic composition selection',
        agent_id='test_{test_case['profile']}_agent'
    )
    
    print(json.dumps(result, indent=2))

asyncio.run(main())
"""
        
        # Run the test
        with open('temp_test_agent.py', 'w') as f:
            f.write(test_script)
        
        try:
            proc = subprocess.run(['python3', 'temp_test_agent.py'], 
                                capture_output=True, text=True, timeout=10)
            
            if proc.returncode == 0:
                print(f"   ✓ Agent spawned successfully")
                # Check logs for composition selection
                if os.path.exists('logs/daemon.log'):
                    with open('logs/daemon.log', 'r') as f:
                        recent_logs = f.read()[-2000:]  # Last 2000 chars
                        if 'Selected composition' in recent_logs:
                            # Extract selection info
                            import re
                            matches = re.findall(r"Selected composition '(\w+)' \(score: ([\d.]+)\)", recent_logs)
                            if matches:
                                comp_name, score = matches[-1]
                                print(f"   Selected: {comp_name} (score: {score})")
                                if comp_name in test_case['expected_compositions']:
                                    print(f"   ✓ Expected composition selected")
                                else:
                                    print(f"   ⚠ Unexpected composition (expected one of: {test_case['expected_compositions']})")
            else:
                print(f"   ✗ Failed to spawn agent: {proc.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"   ✗ Test timed out")
        finally:
            if os.path.exists('temp_test_agent.py'):
                os.remove('temp_test_agent.py')
    
    print("\n=== Test completed ===")
    print("\nNote: Check logs/daemon.log for detailed composition selection information")


if __name__ == '__main__':
    asyncio.run(test_dynamic_selection())