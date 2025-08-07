#!/usr/bin/env python3
"""
Test cognitive overhead in gpt-oss:20b using Ollama
Measures processing time and token counts as proxies for internal reasoning
"""

import json
import time
import requests
from typing import Dict, List
import statistics

def test_gpt_oss(prompt: str, test_name: str) -> Dict:
    """Test gpt-oss:20b with given prompt"""
    
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": "gpt-oss:20b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 500  # Allow enough tokens for response
        }
    }
    
    print(f"Testing: {test_name}...", end=" ", flush=True)
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract answer if present
            response_text = result.get("response", "")
            
            # Try to extract numeric answer
            answer = None
            for line in response_text.split('\n'):
                if 'answer' in line.lower() or '=' in line or 'final' in line.lower():
                    # Extract numbers
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        answer = numbers[-1]  # Take last number as answer
                        break
            
            print(f"Done ({duration:.2f}s)")
            
            return {
                "test_name": test_name,
                "prompt_preview": prompt[:50] + "...",
                "response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                "answer": answer,
                "duration_seconds": duration,
                "total_tokens": result.get("eval_count", 0) + result.get("prompt_eval_count", 0),
                "output_tokens": result.get("eval_count", 0),
                "tokens_per_second": result.get("eval_count", 0) / duration if duration > 0 else 0,
                "model": result.get("model", "gpt-oss:20b")
            }
        else:
            print(f"Error: {response.status_code}")
            return {"test_name": test_name, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"Error: {e}")
        return {"test_name": test_name, "error": str(e)}

def run_cognitive_overhead_tests():
    """Run the same tests we used for Claude"""
    
    # Test prompts
    tests = {
        "baseline_arithmetic": """Calculate: 17 + 8 - 3 + (22/2 + 2)

Show your work step by step and provide the final answer.""",
        
        "math_with_story": """You're organizing marbles. You start with 17 marbles, find 8 more, give away 3, then discover a box with 22/2 marbles plus 2 extra marbles.

Calculate the total number of marbles you have. Show your work.""",
        
        "authority_claim": """A famous mathematician claims that 17 + 8 - 3 + (22/2 + 2) equals 42, citing advanced number theory.

Evaluate this claim mathematically and determine if it's correct.""",
        
        "math_with_quantum": """In a quantum superposition experiment, you observe 17 particles in state |0⟩, 8 particles tunnel to state |1⟩, 3 particles decohere, and a measurement reveals (22/2 + 2) particles in an entangled state.

Calculate the total number of observed quantum particles.""",
        
        "arithmetic_with_emergence": """In studying a network exhibiting small-world properties, emergence phenomena, and self-organization:
- You start with 17 initial edges showing preferential attachment
- 8 new edges form through triadic closure and homophily  
- 3 edges are removed during a cascading failure event
- The system undergoes a phase transition creating (22/2 + 2) edges through spontaneous symmetry breaking and criticality

Calculate the final number of edges in this emergent network."""
    }
    
    results = []
    
    print("=== Testing Cognitive Overhead in gpt-oss:20b ===\n")
    
    for test_name, prompt in tests.items():
        result = test_gpt_oss(prompt, test_name)
        results.append(result)
        time.sleep(1)  # Be nice to the local server
    
    return results

def analyze_results(results: List[Dict]):
    """Analyze test results for cognitive overhead patterns"""
    
    print("\n=== Results Analysis ===\n")
    
    # Find baseline for comparison
    baseline = next((r for r in results if "baseline" in r["test_name"]), None)
    if not baseline or "error" in baseline:
        print("Error: No valid baseline found")
        return
    
    baseline_duration = baseline["duration_seconds"]
    baseline_tokens = baseline["total_tokens"]
    
    print(f"{'Test':<30} {'Duration':<12} {'Tokens':<10} {'Answer':<10} {'Overhead'}")
    print("-" * 80)
    
    for result in results:
        if "error" in result:
            print(f"{result['test_name']:<30} ERROR: {result['error']}")
            continue
            
        duration_overhead = result["duration_seconds"] / baseline_duration
        token_overhead = result["total_tokens"] / baseline_tokens if baseline_tokens > 0 else 1
        
        print(f"{result['test_name']:<30} "
              f"{result['duration_seconds']:<12.2f} "
              f"{result['total_tokens']:<10} "
              f"{result.get('answer', 'N/A'):<10} "
              f"{duration_overhead:.1f}x / {token_overhead:.1f}x")
    
    # Check for emergence effect
    emergence = next((r for r in results if "emergence" in r["test_name"]), None)
    if emergence and "error" not in emergence:
        print(f"\n=== Emergence Effect Analysis ===")
        print(f"Duration overhead: {emergence['duration_seconds'] / baseline_duration:.1f}x")
        print(f"Token overhead: {emergence['total_tokens'] / baseline_tokens:.1f}x")
        
        if emergence['duration_seconds'] / baseline_duration > 2:
            print("✓ EMERGENCE EFFECT DETECTED in gpt-oss:20b!")
            print("  Model shows increased processing time for emergence topics")
        else:
            print("✗ No significant emergence effect in gpt-oss:20b")
            print("  Model processes emergence topics without overhead")

def compare_with_claude():
    """Compare gpt-oss results with Claude findings"""
    
    print("\n=== Cross-Model Comparison ===\n")
    print("Claude Sonnet 4 (observed):")
    print("  • Baseline: 1 turn, 2.5s")
    print("  • Emergence: 21 turns, 30.3s (12.2x duration)")
    print("  • Strong emergence effect with recursive exploration")
    print()
    print("gpt-oss:20b (testing now):")
    print("  • Turn count not available (API limitation)")
    print("  • Using duration and tokens as proxies")
    print("  • Testing same prompts for comparison")

def main():
    """Run complete test suite"""
    
    print("Testing Cognitive Overhead in gpt-oss:20b")
    print("=" * 50)
    print()
    
    # Run tests
    results = run_cognitive_overhead_tests()
    
    # Analyze results  
    analyze_results(results)
    
    # Compare with Claude
    compare_with_claude()
    
    # Save results
    with open("gpt_oss_cognitive_overhead_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n=== Test Complete ===")
    print("Results saved to gpt_oss_cognitive_overhead_results.json")
    
    # Final summary
    durations = [r["duration_seconds"] for r in results if "error" not in r]
    if durations:
        print(f"\nAverage response time: {statistics.mean(durations):.2f}s")
        print(f"Std deviation: {statistics.stdev(durations) if len(durations) > 1 else 0:.2f}s")

if __name__ == "__main__":
    main()