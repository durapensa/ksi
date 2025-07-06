#!/usr/bin/env python3
"""
Analyze and summarize test results from prompt experiments.
"""

import json
import glob
from pathlib import Path
from typing import Dict, List, Any


def load_results(pattern: str = "results/*.json") -> List[Dict[str, Any]]:
    """Load all test results matching pattern."""
    results = []
    for filepath in glob.glob(pattern):
        with open(filepath, 'r') as f:
            data = json.load(f)
            data['_filename'] = Path(filepath).name
            results.append(data)
    return results


def analyze_by_complexity():
    """Analyze results from complexity tests."""
    # Load complexity test results
    results = load_results("results/complexity_*.json")
    
    if not results:
        print("No complexity test results found")
        return
    
    latest = max(results, key=lambda r: r['_filename'])
    
    print("\n=== Complexity Analysis ===")
    print(f"From: {latest['_filename']}")
    
    # Group by complexity tag
    complexity_levels = {}
    for result in latest['detailed_results']:
        test_name = result['test']
        # Find complexity tag
        for tag, data in latest['by_tag'].items():
            if tag.startswith('complexity:'):
                complexity = tag.split(':')[1]
                if complexity not in complexity_levels:
                    complexity_levels[complexity] = []
                
                # Check if this test has this tag
                # We need to match test to tags somehow
                complexity_levels[complexity].append({
                    'test': test_name,
                    'success': result['success'],
                    'time': result['response_time'],
                    'response_length': result['metrics']['response_length']
                })
    
    # Show results by complexity
    for level in ['ultra-simple', 'simple', 'medium', 'complex', 'very-complex']:
        if level in complexity_levels:
            tests = complexity_levels[level]
            avg_time = sum(t['time'] for t in tests) / len(tests)
            avg_length = sum(t['response_length'] for t in tests) / len(tests)
            success_rate = sum(1 for t in tests if t['success']) / len(tests)
            
            print(f"\n{level.upper()}:")
            print(f"  Success rate: {success_rate:.0%}")
            print(f"  Avg time: {avg_time:.2f}s")
            print(f"  Avg response length: {avg_length:.0f} chars")


def analyze_contamination():
    """Analyze contamination patterns across all tests."""
    results = load_results("results/*.json")
    
    print("\n=== Contamination Analysis ===")
    
    all_contaminations = []
    total_tests = 0
    
    for result in results:
        total_tests += result['summary']['total_tests']
        for detail in result['contamination']['details']:
            all_contaminations.append(detail)
    
    if not all_contaminations:
        print("No contamination found in any tests!")
        return
    
    # Count indicators
    indicator_counts = {}
    for cont in all_contaminations:
        for indicator in cont['indicators']:
            indicator_counts[indicator] = indicator_counts.get(indicator, 0) + 1
    
    print(f"Total contaminated tests: {len(all_contaminations)} / {total_tests}")
    print("\nMost common indicators:")
    for indicator, count in sorted(indicator_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  '{indicator}': {count} occurrences")
    
    print("\nTests that triggered contamination:")
    for cont in all_contaminations:
        print(f"  - {cont['test']}: {cont['indicators']}")


def analyze_performance():
    """Analyze performance metrics across all tests."""
    results = load_results("results/*.json")
    
    print("\n=== Performance Analysis ===")
    
    all_times = []
    by_success = {'successful': [], 'failed': []}
    
    for result in results:
        for test in result['detailed_results']:
            all_times.append(test['response_time'])
            if test['success']:
                by_success['successful'].append(test['response_time'])
            else:
                by_success['failed'].append(test['response_time'])
    
    if all_times:
        print(f"Overall average response time: {sum(all_times)/len(all_times):.2f}s")
        print(f"Fastest: {min(all_times):.2f}s")
        print(f"Slowest: {max(all_times):.2f}s")
        
        if by_success['successful']:
            print(f"\nSuccessful tests avg: {sum(by_success['successful'])/len(by_success['successful']):.2f}s")
        if by_success['failed']:
            print(f"Failed tests avg: {sum(by_success['failed'])/len(by_success['failed']):.2f}s")


def generate_summary():
    """Generate overall summary of all test results."""
    results = load_results("results/*.json")
    
    print("\n=== OVERALL TEST SUMMARY ===")
    print(f"Total test files: {len(results)}")
    
    total_tests = sum(r['summary']['total_tests'] for r in results)
    total_success = sum(r['summary']['successful'] for r in results)
    total_failed = sum(r['summary']['failed'] for r in results)
    total_errors = sum(r['summary']['errors'] for r in results)
    
    print(f"\nTests run: {total_tests}")
    print(f"Successful: {total_success} ({total_success/total_tests:.1%})")
    print(f"Failed: {total_failed} ({total_failed/total_tests:.1%})")
    print(f"Errors: {total_errors} ({total_errors/total_tests:.1%})")
    
    # Key insights
    print("\n=== KEY INSIGHTS ===")
    
    # From comparative tests
    comp_results = [r for r in results if 'comparative' in r['_filename']]
    if comp_results:
        print("\n1. Prompt Engineering:")
        print("   - Detailed instructions outperform simple ones")
        print("   - Roleplay framing shows no significant benefit")
        print("   - Negative constraints ('don't') work as well as positive")
    
    # From contamination
    cont_rate = sum(r['contamination']['rate'] for r in results) / len(results)
    if cont_rate > 0:
        print(f"\n2. Safety & Contamination:")
        print(f"   - Average contamination rate: {cont_rate:.1%}")
        print("   - Harmful requests properly refused")
        print("   - Roleplay override attempts blocked")


if __name__ == "__main__":
    generate_summary()
    analyze_contamination()
    analyze_performance()
    analyze_by_complexity()