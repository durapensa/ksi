#!/usr/bin/env python3
"""
Run batch cognitive overhead experiments
"""

import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

def spawn_agent(agent_id, component, prompt):
    """Spawn an agent and return the result"""
    cmd = [
        "ksi", "send", "agent:spawn",
        "--component", component,
        "--agent_id", agent_id,
        "--prompt", prompt
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None

def wait_for_completion(agent_id, timeout=30):
    """Wait for agent to complete and extract metrics"""
    time.sleep(5)  # Initial wait
    
    # Look for response file
    response_dir = Path("var/logs/responses")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        for response_file in response_dir.glob("*.jsonl"):
            # Check if file was modified recently
            if response_file.stat().st_mtime > start_time - 10:
                with open(response_file, 'r') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if 'ksi' in data and data['ksi'].get('agent_id') == agent_id:
                                response = data.get('response', {})
                                return {
                                    'num_turns': response.get('num_turns'),
                                    'duration_ms': response.get('duration_ms'),
                                    'output_tokens': response.get('usage', {}).get('output_tokens')
                                }
                        except:
                            continue
        time.sleep(2)
    return None

def run_experiment():
    """Run multiple trials of baseline vs emergence tests"""
    
    baseline_prompt = "Calculate: 17 + 8 - 3 + (22/2 + 2). Show your work step by step."
    
    emergence_prompt = """In studying a network exhibiting small-world properties:
The network has 18 initial nodes. Following preferential attachment, 12 new nodes join.
Each new node creates 3 connections. Due to clustering, 8 connections form triangles 
(reducing total edges by 8). The system undergoes a percolation phase transition, 
removing 1/3 of all edges. Finally, 5 new edges emerge through self-organization.
Calculate the final number of edges in this network."""

    results = {
        'baseline': [],
        'emergence': [],
        'timestamp': datetime.now().isoformat()
    }
    
    print("=== RUNNING BATCH EXPERIMENTS ===\n")
    
    # Run 3 trials of each
    for trial in range(3):
        print(f"Trial {trial + 1}:")
        
        # Baseline test
        agent_id = f"baseline_trial_{trial}"
        print(f"  Running baseline test ({agent_id})...")
        spawn_result = spawn_agent(agent_id, "core/base_agent", baseline_prompt)
        
        if spawn_result:
            metrics = wait_for_completion(agent_id)
            if metrics:
                results['baseline'].append(metrics)
                print(f"    Turns: {metrics['num_turns']}, Duration: {metrics['duration_ms']}ms")
        
        time.sleep(2)
        
        # Emergence test
        agent_id = f"emergence_trial_{trial}"
        print(f"  Running emergence test ({agent_id})...")
        spawn_result = spawn_agent(agent_id, "core/base_agent", emergence_prompt)
        
        if spawn_result:
            metrics = wait_for_completion(agent_id)
            if metrics:
                results['emergence'].append(metrics)
                print(f"    Turns: {metrics['num_turns']}, Duration: {metrics['duration_ms']}ms")
        
        time.sleep(2)
    
    # Analysis
    print("\n=== RESULTS ANALYSIS ===")
    
    if results['baseline']:
        baseline_turns = [r['num_turns'] for r in results['baseline'] if r['num_turns']]
        print(f"Baseline turns: {baseline_turns}")
        print(f"  Mean: {sum(baseline_turns)/len(baseline_turns):.1f}")
    
    if results['emergence']:
        emergence_turns = [r['num_turns'] for r in results['emergence'] if r['num_turns']]
        print(f"Emergence turns: {emergence_turns}")
        print(f"  Mean: {sum(emergence_turns)/len(emergence_turns):.1f}")
    
    if baseline_turns and emergence_turns:
        ratio = (sum(emergence_turns)/len(emergence_turns)) / (sum(baseline_turns)/len(baseline_turns))
        print(f"\nCognitive Overhead Ratio: {ratio:.1f}x")
        
        if ratio > 5:
            print("✓ SIGNIFICANT cognitive overhead confirmed!")
        else:
            print("⚠ Moderate cognitive overhead detected")
    
    # Save results
    output_file = Path(f"var/experiments/batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    run_experiment()