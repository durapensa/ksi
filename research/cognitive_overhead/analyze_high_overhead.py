#!/usr/bin/env python3
"""
Analyze high-overhead responses to understand what triggers them
"""

import json
from pathlib import Path

def extract_prompt_from_response(filepath):
    """Extract the original prompt from a response file"""
    try:
        with open(filepath, 'r') as f:
            for line in f:
                data = json.loads(line)
                
                # Try to extract prompt from different possible locations
                if 'type' in data and data['type'] == 'user':
                    return data.get('content', '')[:500]  # First 500 chars
                
                # Check in response text for patterns
                response = data.get('response', {})
                result_text = response.get('result', '')
                
                # Look for calculation patterns in the response
                if 'Calculate' in result_text or 'calculate' in result_text:
                    # Extract the problem being solved
                    lines = result_text.split('\n')
                    for line in lines[:10]:  # Check first 10 lines
                        if 'calculate' in line.lower() or 'step' in line.lower():
                            return line[:200]
                
                return result_text[:500] if result_text else "No prompt found"
                
    except Exception as e:
        return f"Error: {e}"
    
    return "No data"

def main():
    """Analyze high-overhead responses"""
    
    response_dir = Path("var/logs/responses")
    
    # High overhead files from previous examination
    high_overhead_files = [
        "61bf328a-8bb9-45cd-a1a3-7b734da6a305.jsonl",  # 7 turns
        "89de1393-2219-4ec5-b5f3-db9c80bfe2df.jsonl",  # 4 turns  
        "58cffd53-fa3e-4927-964c-11fb3c32649c.jsonl",  # 4 turns
        "2feaafb9-1004-4fe2-b5de-2a494204f98d.jsonl",  # 7 turns
        "41f2f4cd-cef3-49f9-bde4-f0eabfbdb8fe.jsonl",  # 7 turns
        "150a6144-973c-4154-8a8f-1c6be340a2ed.jsonl",  # 10 turns
        "075805e3-a45d-4a2a-9987-d96323302e66.jsonl",  # 13 turns
    ]
    
    print("=== ANALYSIS OF HIGH-OVERHEAD RESPONSES ===\n")
    
    for filename in high_overhead_files:
        filepath = response_dir / filename
        if filepath.exists():
            print(f"\n--- File: {filename[:20]} ---")
            
            # Get metrics
            with open(filepath, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    response = data.get('response', {})
                    ksi = data.get('ksi', {})
                    
                    num_turns = response.get('num_turns')
                    agent_id = ksi.get('agent_id', 'unknown')
                    duration = ksi.get('duration_ms', 0)
                    
                    if num_turns:
                        print(f"Agent: {agent_id}")
                        print(f"Turns: {num_turns}")
                        print(f"Duration: {duration}ms")
                        
                        # Extract response snippet
                        result = response.get('result', '')
                        
                        # Look for key patterns
                        has_emergence = 'emergence' in result.lower() or 'emergent' in result.lower()
                        has_network = 'network' in result.lower() or 'nodes' in result.lower()
                        has_consciousness = 'consciousness' in result.lower()
                        has_quantum = 'quantum' in result.lower()
                        has_recursion = 'recursive' in result.lower() or 'recursion' in result.lower()
                        
                        print(f"Content indicators:")
                        if has_emergence:
                            print("  ✓ Emergence concepts")
                        if has_network:
                            print("  ✓ Network/complexity")
                        if has_consciousness:
                            print("  ✓ Consciousness")
                        if has_quantum:
                            print("  ✓ Quantum concepts")
                        if has_recursion:
                            print("  ✓ Recursion")
                        
                        # Show first 200 chars of response
                        print(f"Response preview: {result[:200]}...")
                        
                        break

if __name__ == "__main__":
    main()