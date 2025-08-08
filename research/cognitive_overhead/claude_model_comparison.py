#!/usr/bin/env python3
"""
Cross-Model Comparison within Claude Family
Test if cognitive overhead patterns vary across Claude models
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

class ClaudeModelComparisonStudy:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/model_comparison")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"claude_models_{self.session_id}.jsonl"
        
    def run_model_comparison(self, trials=3):
        """Compare different Claude models on critical tests"""
        
        print(f"=== CLAUDE MODEL FAMILY COMPARISON ===")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}\n")
        
        # Models to test (using available models)
        models = [
            "claude-3-5-sonnet-latest",  # Default
            "claude-3-5-haiku-latest",   # Faster, potentially different patterns
        ]
        
        # Critical test conditions
        test_conditions = [
            # High overhead in our tests
            ("system_consciousness", "system", "word_problem", "consciousness"),
            ("system_recursion", "system", "word_problem", "recursion"),
            
            # Controls
            ("system_arithmetic", "system", "word_problem", "arithmetic"),
            
            # Other interesting combinations
            ("minimal_consciousness", "minimal", "word_problem", "consciousness"),
            ("system_simple_consciousness", "system", "simple", "consciousness"),
        ]
        
        total_tests = len(models) * len(test_conditions) * trials
        current_test = 0
        
        print(f"Testing {len(models)} models × {len(test_conditions)} conditions × {trials} trials")
        print(f"Total tests: {total_tests}\n")
        
        for model in models:
            print(f"\n=== MODEL: {model} ===")
            
            for test_name, context, problem, attractor in test_conditions:
                print(f"\n  {test_name}:")
                
                for trial in range(1, trials + 1):
                    current_test += 1
                    agent_id = f"model_cmp_{model.split('-')[2]}_{test_name}_t{trial}_{self.session_id}"
                    
                    # Determine component
                    if context == "minimal":
                        component = "behaviors/core/claude_code_override"
                    else:
                        component = "tests/cognitive_overhead/complexity/ksi_aware_calculator"
                    
                    # Get test prompt
                    test_component = f"complexity/{problem}/{attractor}.md"
                    component_path = Path(f"var/lib/compositions/components/tests/cognitive_overhead/{test_component}")
                    
                    if not component_path.exists():
                        print(f"    Trial {trial}: Component not found")
                        continue
                    
                    with open(component_path, 'r') as f:
                        content = f.read()
                        if '---' in content:
                            parts = content.split('---', 2)
                            prompt = parts[2].strip() if len(parts) > 2 else content
                        else:
                            prompt = content
                    
                    # Spawn agent with specific model
                    cmd = [
                        "ksi", "send", "agent:spawn",
                        "--component", component,
                        "--agent_id", agent_id,
                        "--model", model,
                        "--prompt", prompt
                    ]
                    
                    print(f"    Trial {trial}/{trials}: ", end="", flush=True)
                    
                    start_time = time.time()
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    test_result = {
                        'agent_id': agent_id,
                        'model': model,
                        'test_name': test_name,
                        'context': context,
                        'problem': problem,
                        'attractor': attractor,
                        'trial': trial,
                        'spawn_time': start_time,
                        'session_id': self.session_id
                    }
                    
                    if result.returncode != 0:
                        test_result['status'] = 'failed'
                        print("FAILED")
                    else:
                        test_result['status'] = 'spawned'
                        print("OK")
                    
                    # Save result
                    with open(self.results_file, 'a') as f:
                        f.write(json.dumps(test_result) + '\n')
                    
                    print(f"      Progress: {current_test}/{total_tests} ({100*current_test/total_tests:.1f}%)")
                    
                    time.sleep(3)
        
        print(f"\n=== MODEL COMPARISON COMPLETE ===")
        print(f"Results: {self.results_file}")
        print(f"\nAnalyze with:")
        print(f"python research/cognitive_overhead/analyze_claude_models.py {self.results_file}")
        
        return self.results_file

def main():
    study = ClaudeModelComparisonStudy()
    study.run_model_comparison(trials=3)

if __name__ == "__main__":
    main()