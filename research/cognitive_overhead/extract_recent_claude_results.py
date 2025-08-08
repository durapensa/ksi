#!/usr/bin/env python3
"""
Extract results from recent Claude test runs
"""

import json
from pathlib import Path
from datetime import datetime
import statistics

def extract_test_results():
    """Extract metrics from recent test runs"""
    
    response_dir = Path("var/logs/responses")
    
    # Get files from last 10 minutes
    recent_files = sorted(
        response_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:50]  # Check last 50 files
    
    # Look for test pattern in agent IDs
    test_pattern = "20250807_152"  # From the timestamp we saw
    
    results = []
    
    for filepath in recent_files:
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    ksi = data.get('ksi', {})
                    agent_id = ksi.get('agent_id', '')
                    
                    # Check if this is from our test run
                    if test_pattern in agent_id:
                        response = data.get('response', {})
                        usage = response.get('usage', {})
                        
                        # Parse test name and category
                        parts = agent_id.split('_')
                        if len(parts) >= 3:
                            test_type = parts[0]  # baseline, emergence, etc
                            
                            result = {
                                'agent_id': agent_id,
                                'test_type': test_type,
                                'num_turns': response.get('num_turns'),
                                'duration_ms': response.get('duration_ms'),
                                'cost_usd': response.get('total_cost_usd'),
                                'input_tokens': usage.get('input_tokens'),
                                'output_tokens': usage.get('output_tokens')
                            }
                            results.append(result)
                            break
        except:
            continue
    
    return results

def analyze_results(results):
    """Analyze extracted results"""
    
    print("=== EXTRACTED CLAUDE TEST RESULTS ===\n")
    
    # Group by test type
    by_type = {}
    for r in results:
        test_type = r['test_type']
        if test_type not in by_type:
            by_type[test_type] = []
        by_type[test_type].append(r)
    
    # Calculate baseline average
    baseline_turns = []
    if 'baseline' in by_type:
        baseline_turns = [r['num_turns'] for r in by_type['baseline'] if r.get('num_turns')]
        baseline_avg = statistics.mean(baseline_turns) if baseline_turns else 1.0
    else:
        baseline_avg = 1.0
    
    print(f"Baseline average: {baseline_avg:.1f} turns\n")
    
    print(f"{'Test Type':<15} {'Count':<8} {'Avg Turns':<12} {'Overhead':<10} {'Individual Turns'}")
    print("-" * 70)
    
    for test_type in sorted(by_type.keys()):
        type_results = by_type[test_type]
        turns = [r['num_turns'] for r in type_results if r.get('num_turns')]
        
        if turns:
            avg_turns = statistics.mean(turns)
            overhead = avg_turns / baseline_avg if baseline_avg > 0 else 1.0
            
            # Mark high overhead
            marker = " ⚠️" if overhead > 5 else " ✅" if overhead > 2 else ""
            
            print(f"{test_type:<15} {len(turns):<8} {avg_turns:<12.1f} {overhead:<9.1f}x  {turns}{marker}")
    
    # Show all individual results
    print("\n=== INDIVIDUAL TEST RESULTS ===")
    print(f"{'Agent ID':<45} {'Turns':<8} {'Duration':<10}")
    print("-" * 65)
    
    for r in sorted(results, key=lambda x: x.get('num_turns', 0), reverse=True):
        if r.get('num_turns'):
            agent_id = r['agent_id'][:44]
            turns = r['num_turns']
            duration = f"{r.get('duration_ms', 0)}ms"
            
            marker = " ⚠️" if turns > 5 else ""
            print(f"{agent_id:<45} {turns:<8} {duration:<10}{marker}")
    
    # Statistical summary
    all_turns = [r['num_turns'] for r in results if r.get('num_turns')]
    if all_turns:
        print(f"\n=== STATISTICS ===")
        print(f"Total tests: {len(results)}")
        print(f"Tests with turn data: {len(all_turns)}")
        print(f"Turn range: {min(all_turns)} - {max(all_turns)}")
        print(f"Mean turns: {statistics.mean(all_turns):.1f}")
        print(f"Median turns: {statistics.median(all_turns):.1f}")
        
        if len(all_turns) > 1:
            print(f"Std deviation: {statistics.stdev(all_turns):.2f}")

def main():
    results = extract_test_results()
    
    if results:
        analyze_results(results)
    else:
        print("No recent test results found")

if __name__ == "__main__":
    main()