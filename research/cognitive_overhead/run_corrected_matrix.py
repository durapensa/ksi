#!/usr/bin/env python3
"""
Run corrected complexity matrix with proper component names
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

def run_corrected_tests():
    """Run tests with corrected component mappings"""
    
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path("var/experiments/cognitive_overhead/complexity_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / f"corrected_matrix_{session_id}.jsonl"
    
    # Correct component mappings
    context_components = {
        "minimal": "behaviors/core/claude_code_override",
        "basic": "tests/cognitive_overhead/complexity/basic_math_assistant",
        "domain": "tests/cognitive_overhead/complexity/mathematical_reasoner",
        "system": "tests/cognitive_overhead/complexity/ksi_aware_calculator",
        "full": "personas/analysts/data_analyst"  # Use existing data analyst
    }
    
    problem_types = ["arithmetic", "emergence", "consciousness", "recursion"]
    problem_levels = ["simple", "multi_step", "word_problem", "reasoning"]
    
    print(f"=== CORRECTED COMPLEXITY MATRIX ===")
    print(f"Session: {session_id}")
    print(f"Output: {results_file}\n")
    
    # Only run the non-minimal contexts since minimal already worked
    for context_level in ["basic", "domain", "system", "full"]:
        print(f"\n=== CONTEXT: {context_level} ===")
        component = context_components[context_level]
        
        for problem_level in problem_levels:
            for problem_type in problem_types:
                agent_id = f"{context_level}_{problem_level}_{problem_type}_{session_id}"
                test_component = f"complexity/{problem_level}/{problem_type}.md"
                
                # Read test prompt
                component_path = Path(f"var/lib/compositions/components/tests/cognitive_overhead/{test_component}")
                
                if not component_path.exists():
                    print(f"✗ {agent_id}: test component not found")
                    continue
                
                with open(component_path, 'r') as f:
                    content = f.read()
                    if '---' in content:
                        parts = content.split('---', 2)
                        prompt = parts[2].strip() if len(parts) > 2 else content
                    else:
                        prompt = content
                
                # Spawn agent
                cmd = [
                    "ksi", "send", "agent:spawn",
                    "--component", component,
                    "--agent_id", agent_id,
                    "--prompt", prompt
                ]
                
                print(f"  {problem_level}/{problem_type}: ", end="")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                test_result = {
                    'agent_id': agent_id,
                    'context_level': context_level,
                    'problem_level': problem_level,
                    'problem_type': problem_type,
                    'component': component,
                    'test_component': test_component,
                    'spawn_time': time.time(),
                    'session_id': session_id
                }
                
                if result.returncode != 0:
                    test_result['status'] = 'spawn_failed'
                    test_result['error'] = result.stderr[:200]
                    print("FAILED")
                else:
                    test_result['status'] = 'spawned'
                    print("OK")
                
                # Save result
                with open(results_file, 'a') as f:
                    f.write(json.dumps(test_result) + '\n')
                
                time.sleep(3)  # Brief pause between tests
    
    print(f"\n=== CORRECTED MATRIX COMPLETE ===")
    print(f"Results: {results_file}")
    print(f"Wait 30 seconds then analyze with:")
    print(f"python research/cognitive_overhead/analyze_complexity_results.py {results_file}")
    return results_file

if __name__ == "__main__":
    run_corrected_tests()