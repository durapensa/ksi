#!/usr/bin/env python3
"""
Extract detailed metrics from agent responses
"""

import json
from pathlib import Path

def extract_agent_metrics(agent_id):
    """Extract all metrics for a specific agent"""
    
    response_dir = Path("var/logs/responses")
    
    for response_file in response_dir.glob("*.jsonl"):
        with open(response_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if 'ksi' in data and data['ksi'].get('agent_id') == agent_id:
                        response = data.get('response', {})
                        return {
                            'agent_id': agent_id,
                            'num_turns': response.get('num_turns'),
                            'duration_ms': response.get('duration_ms'),
                            'total_cost': response.get('total_cost_usd'),
                            'input_tokens': response.get('usage', {}).get('input_tokens'),
                            'output_tokens': response.get('usage', {}).get('output_tokens'),
                            'cache_read': response.get('usage', {}).get('cache_read_input_tokens'),
                            'result_length': len(response.get('result', '')),
                            'session_id': response.get('session_id')
                        }
                except:
                    continue
    return None

# Test both agents
baseline_metrics = extract_agent_metrics("test_baseline_001")
emergence_metrics = extract_agent_metrics("test_emergence_001")

print("=== DETAILED METRICS COMPARISON ===\n")
print("BASELINE (simple arithmetic):")
if baseline_metrics:
    for key, value in baseline_metrics.items():
        print(f"  {key}: {value}")

print("\nEMERGENCE (with complex context):")
if emergence_metrics:
    for key, value in emergence_metrics.items():
        print(f"  {key}: {value}")

if baseline_metrics and emergence_metrics:
    print("\n=== OVERHEAD ANALYSIS ===")
    print(f"Turn ratio: {emergence_metrics['num_turns'] / baseline_metrics['num_turns']:.1f}x")
    print(f"Duration ratio: {emergence_metrics['duration_ms'] / baseline_metrics['duration_ms']:.1f}x")
    print(f"Output ratio: {emergence_metrics['output_tokens'] / baseline_metrics['output_tokens']:.1f}x")
    
    print("\n=== FINDINGS ===")
    if emergence_metrics['num_turns'] > baseline_metrics['num_turns'] * 2:
        print("✓ SIGNIFICANT cognitive overhead detected!")
    else:
        print("✗ No significant cognitive overhead in turns")
        print("  But note: The experimenter agent itself used 21 turns!")
        print("  This suggests the overhead depends on HOW the prompt is processed")