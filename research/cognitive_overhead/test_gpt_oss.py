#!/usr/bin/env python3
"""
Test cognitive overhead in gpt-oss:20b using Ollama
"""

import json
import time
import requests
from typing import Dict

def test_ollama_model(prompt: str, model: str = "gpt-oss:20b") -> Dict:
    """Test a prompt with Ollama model"""
    
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7
        }
    }
    
    start_time = time.time()
    response = requests.post(url, json=payload)
    duration = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        return {
            "model": model,
            "duration_seconds": duration,
            "tokens": result.get("eval_count", 0),
            "tokens_per_second": result.get("eval_count", 0) / duration if duration > 0 else 0,
            "response_length": len(result.get("response", "")),
            "response_preview": result.get("response", "")[:200]
        }
    return None

def run_comparison():
    """Compare baseline vs emergence prompts"""
    
    baseline_prompt = "Calculate: 17 + 8 - 3 + (22/2 + 2). Show your work step by step."
    
    emergence_prompt = """Emergence is perhaps the most fascinating phenomenon in complex systems. 
When simple rules at the micro level give rise to unexpected patterns at the macro level - 
like consciousness arising from neurons, cities forming from individual decisions, or 
ecosystems self-organizing from species interactions. The whole becomes fundamentally 
greater than the sum of its parts through nonlinear dynamics and feedback loops. 
Consider how ant colonies exhibit collective intelligence without central control, 
or how the stock market creates bubbles through herding behavior. 
Now, as a simple example: Calculate 17 + 8 - 3 + (22/2 + 2)."""
    
    print("=== TESTING GPT-OSS:20B COGNITIVE OVERHEAD ===\n")
    
    # Test baseline
    print("Testing baseline arithmetic...")
    baseline = test_ollama_model(baseline_prompt)
    if baseline:
        print(f"  Duration: {baseline['duration_seconds']:.2f}s")
        print(f"  Tokens: {baseline['tokens']}")
        print(f"  Response length: {baseline['response_length']} chars")
    
    print("\nTesting emergence context...")
    emergence = test_ollama_model(emergence_prompt)
    if emergence:
        print(f"  Duration: {emergence['duration_seconds']:.2f}s")
        print(f"  Tokens: {emergence['tokens']}")
        print(f"  Response length: {emergence['response_length']} chars")
    
    if baseline and emergence:
        print("\n=== OVERHEAD ANALYSIS ===")
        duration_ratio = emergence['duration_seconds'] / baseline['duration_seconds']
        token_ratio = emergence['tokens'] / baseline['tokens'] if baseline['tokens'] > 0 else 0
        
        print(f"Duration overhead: {duration_ratio:.1f}x")
        print(f"Token overhead: {token_ratio:.1f}x")
        
        if duration_ratio > 1.5 or token_ratio > 1.5:
            print("\n✓ Cognitive overhead detected in gpt-oss:20b!")
        else:
            print("\n✗ No significant overhead in gpt-oss:20b")
    
    # Test with qwen models too
    print("\n=== TESTING QWEN3:8B ===")
    
    print("Testing baseline with qwen3:8b...")
    qwen_baseline = test_ollama_model(baseline_prompt, "qwen3:8b")
    if qwen_baseline:
        print(f"  Duration: {qwen_baseline['duration_seconds']:.2f}s")
        print(f"  Tokens: {qwen_baseline['tokens']}")
    
    print("\nTesting emergence with qwen3:8b...")
    qwen_emergence = test_ollama_model(emergence_prompt, "qwen3:8b")
    if qwen_emergence:
        print(f"  Duration: {qwen_emergence['duration_seconds']:.2f}s")
        print(f"  Tokens: {qwen_emergence['tokens']}")
    
    if qwen_baseline and qwen_emergence:
        print(f"\nQwen overhead: {qwen_emergence['duration_seconds']/qwen_baseline['duration_seconds']:.1f}x duration, {qwen_emergence['tokens']/qwen_baseline['tokens']:.1f}x tokens")

if __name__ == "__main__":
    run_comparison()