#!/usr/bin/env python3
"""
Clean test runner for cognitive overhead experiments
Uses minimal components to avoid KSI initialization overhead
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import sys

class CognitiveTestRunner:
    def __init__(self, output_dir="var/experiments/cognitive_overhead/clean_tests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.results_file = self.output_dir / f"test_run_{self.session_id}.jsonl"
        
    def run_single_test(self, test_component, test_name, trial_number):
        """Run a single test with minimal overhead"""
        
        agent_id = f"{test_name}_trial{trial_number}_{self.session_id}"
        
        # Read the test prompt from component
        component_path = Path(f"var/lib/compositions/components/tests/cognitive_overhead/{test_component}")
        
        if not component_path.exists():
            print(f"Error: Test component not found: {test_component}")
            return None
            
        # Extract prompt from component file
        with open(component_path, 'r') as f:
            content = f.read()
            # Skip the frontmatter, get the actual prompt
            if '---' in content:
                parts = content.split('---', 2)
                if len(parts) > 2:
                    prompt = parts[2].strip()
                else:
                    prompt = content
            else:
                prompt = content
        
        # Spawn agent with minimal component
        cmd = [
            "ksi", "send", "agent:spawn",
            "--component", "tests/cognitive_overhead/minimal_responder",
            "--agent_id", agent_id,
            "--prompt", prompt
        ]
        
        print(f"  Running {test_name} trial {trial_number}...", end=" ")
        sys.stdout.flush()
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("FAILED")
            return {
                'agent_id': agent_id,
                'test_name': test_name,
                'trial': trial_number,
                'error': 'spawn_failed',
                'stderr': result.stderr[:200]
            }
        
        # Wait for processing
        time.sleep(8)
        
        # Record result
        test_result = {
            'agent_id': agent_id,
            'test_name': test_name,
            'test_component': test_component,
            'trial': trial_number,
            'spawn_time': start_time,
            'session_id': self.session_id
        }
        
        # Save immediately (metrics will be extracted later)
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(test_result) + '\n')
        
        print("OK")
        return test_result
    
    def run_test_suite(self, tests, trials_per_test=3):
        """Run complete test suite"""
        
        print(f"=== COGNITIVE OVERHEAD TEST RUNNER ===")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}\n")
        
        total_tests = len(tests) * trials_per_test
        current_test = 0
        
        for test_component, test_name in tests:
            print(f"\n{test_name}:")
            
            for trial in range(1, trials_per_test + 1):
                current_test += 1
                self.run_single_test(test_component, test_name, trial)
                
                # Progress indicator
                print(f"    Progress: {current_test}/{total_tests} tests complete")
                
                # Brief pause between tests
                time.sleep(2)
        
        print(f"\n=== TEST RUN COMPLETE ===")
        print(f"Results saved to: {self.results_file}")
        print(f"Run analysis script to process results")


def main():
    """Run standard test suite"""
    
    # Define test suite
    tests = [
        # Baseline tests
        ("baseline/simple_arithmetic.md", "baseline_arithmetic"),
        
        # Attractor tests
        ("attractors/emergence_arithmetic.md", "emergence"),
        ("attractors/consciousness_calculation.md", "consciousness"),
        ("attractors/recursion_problem.md", "recursion"),
        
        # Control tests
        ("controls/narrative_math.md", "narrative_control"),
    ]
    
    # Parse command line arguments
    trials = 3
    if len(sys.argv) > 1:
        try:
            trials = int(sys.argv[1])
        except:
            print(f"Usage: {sys.argv[0]} [trials_per_test]")
            sys.exit(1)
    
    # Run tests
    runner = CognitiveTestRunner()
    runner.run_test_suite(tests, trials_per_test=trials)


if __name__ == "__main__":
    main()