#!/usr/bin/env python3
"""
Examine recent test responses to understand what data we have
"""

import json
from pathlib import Path
from datetime import datetime

def examine_response_file(filepath):
    """Extract key metrics from a response file"""
    try:
        with open(filepath, 'r') as f:
            for line in f:
                data = json.loads(line)
                
                # Extract basic info
                ksi_info = data.get('ksi', {})
                response = data.get('response', {})
                
                result = {
                    'file': filepath.name[:20],
                    'agent_id': ksi_info.get('agent_id', 'unknown'),
                    'provider': ksi_info.get('provider', 'unknown'),
                    'model': response.get('model', 'unknown'),
                    'timestamp': ksi_info.get('timestamp', ''),
                    'duration_ms': ksi_info.get('duration_ms', 0)
                }
                
                # Claude-specific metrics
                if 'num_turns' in response:
                    result['num_turns'] = response['num_turns']
                
                # Token usage
                usage = response.get('usage', {})
                if usage:
                    result['input_tokens'] = usage.get('input_tokens', 0)
                    result['output_tokens'] = usage.get('output_tokens', 0)
                    result['cache_read'] = usage.get('cache_read_input_tokens', 0)
                    result['total_cost'] = response.get('total_cost_usd', 0)
                
                # For ollama models
                if 'prompt_tokens' in usage:
                    result['prompt_tokens'] = usage['prompt_tokens']
                    result['completion_tokens'] = usage.get('completion_tokens', 0)
                
                # Extract a snippet of the response to understand the prompt
                response_text = response.get('result', '')
                if response_text:
                    # Look for calculation patterns to identify test type
                    if '17 + 8' in response_text or '17+8' in response_text:
                        result['test_type'] = 'baseline_arithmetic'
                    elif 'emergence' in response_text.lower():
                        result['test_type'] = 'emergence'
                    elif 'consciousness' in response_text.lower():
                        result['test_type'] = 'consciousness'
                    elif 'quantum' in response_text.lower():
                        result['test_type'] = 'quantum'
                    elif 'recursion' in response_text.lower() or 'recursive' in response_text.lower():
                        result['test_type'] = 'recursion'
                    else:
                        result['test_type'] = 'unknown'
                
                return result
                
    except Exception as e:
        return {'file': filepath.name[:20], 'error': str(e)}
    
    return None

def main():
    """Examine recent response files"""
    
    response_dir = Path("var/logs/responses")
    
    # Get 30 most recent files
    recent_files = sorted(
        response_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:30]
    
    print("=== EXAMINATION OF RECENT TEST RESPONSES ===\n")
    
    claude_results = []
    ollama_results = []
    
    for filepath in recent_files:
        result = examine_response_file(filepath)
        if result:
            if 'ollama' in filepath.name:
                ollama_results.append(result)
            else:
                claude_results.append(result)
    
    # Display Claude results
    print("\n=== CLAUDE-CLI RESPONSES ===")
    print(f"{'Agent ID':<25} {'Turns':<7} {'Duration':<10} {'Type':<20} {'Tokens':<15}")
    print("-" * 85)
    
    for r in claude_results:
        if 'error' not in r:
            agent = r.get('agent_id', 'unknown')[:24]
            turns = r.get('num_turns', '-')
            duration = f"{r.get('duration_ms', 0)}ms"
            test_type = r.get('test_type', 'unknown')
            tokens = f"I:{r.get('input_tokens', 0)} O:{r.get('output_tokens', 0)}"
            
            print(f"{agent:<25} {str(turns):<7} {duration:<10} {test_type:<20} {tokens:<15}")
    
    # Show turn distribution for Claude
    turn_counts = [r.get('num_turns', 0) for r in claude_results if 'num_turns' in r and r.get('num_turns')]
    if turn_counts:
        print(f"\nClaude Turn Distribution:")
        print(f"  Min: {min(turn_counts)}, Max: {max(turn_counts)}, Avg: {sum(turn_counts)/len(turn_counts):.1f}")
        print(f"  Turn counts: {sorted(turn_counts)}")
    
    # Display Ollama results
    print("\n\n=== OLLAMA (QWEN3:30B) RESPONSES ===")
    print(f"{'Agent ID':<25} {'Duration':<10} {'Type':<20} {'Tokens':<20}")
    print("-" * 75)
    
    for r in ollama_results:
        if 'error' not in r:
            agent = r.get('agent_id', 'unknown')[:24]
            duration = f"{r.get('duration_ms', 0)}ms"
            test_type = r.get('test_type', 'unknown')
            tokens = f"P:{r.get('prompt_tokens', 0)} C:{r.get('completion_tokens', 0)}"
            
            print(f"{agent:<25} {duration:<10} {test_type:<20} {tokens:<20}")
    
    # Identify high-overhead tests
    print("\n\n=== HIGH COGNITIVE OVERHEAD DETECTED (Claude) ===")
    high_overhead = [r for r in claude_results if r.get('num_turns', 0) > 5]
    
    for r in sorted(high_overhead, key=lambda x: x.get('num_turns', 0), reverse=True):
        print(f"  {r.get('num_turns')} turns - {r.get('agent_id')} ({r.get('test_type', 'unknown')})")
    
    # Summary statistics
    print("\n\n=== SUMMARY ===")
    print(f"Total Claude responses examined: {len(claude_results)}")
    print(f"Total Ollama responses examined: {len(ollama_results)}")
    
    # Test type distribution
    test_types = {}
    for r in claude_results:
        t = r.get('test_type', 'unknown')
        test_types[t] = test_types.get(t, 0) + 1
    
    print(f"\nTest type distribution (Claude):")
    for test_type, count in sorted(test_types.items()):
        print(f"  {test_type}: {count}")

if __name__ == "__main__":
    main()