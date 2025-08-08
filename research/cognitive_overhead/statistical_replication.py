#!/usr/bin/env python3
"""
Statistical Replication Study
Validate the 6x overhead finding with N=20 trials per condition
Focus on the critical system + word_problem + consciousness/recursion effect
"""

import json
import subprocess
import time
import statistics
from pathlib import Path
from datetime import datetime
import random

class StatisticalReplicationStudy:
    def __init__(self, trials_per_condition=20):
        self.trials = trials_per_condition
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/replication")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"replication_{self.session_id}.jsonl"
        
    def run_replication_study(self):
        """Run focused replication on the 6x overhead finding"""
        
        print(f"=== STATISTICAL REPLICATION STUDY ===")
        print(f"N = {self.trials} per condition")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}\n")
        
        # Critical conditions to replicate
        conditions = [
            # Original 6x findings
            ("system", "word_problem", "consciousness", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            ("system", "word_problem", "recursion", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            
            # Controls
            ("system", "word_problem", "arithmetic", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            ("system", "word_problem", "emergence", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            
            # Verify no effect in other combinations
            ("system", "simple", "consciousness", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            ("system", "reasoning", "consciousness", "tests/cognitive_overhead/complexity/ksi_aware_calculator"),
            
            # Baseline minimal context for comparison
            ("minimal", "word_problem", "consciousness", "behaviors/core/claude_code_override"),
            ("minimal", "word_problem", "recursion", "behaviors/core/claude_code_override"),
        ]
        
        total_tests = len(conditions) * self.trials
        current_test = 0
        
        # Randomize trial order to avoid position effects
        trial_order = []
        for condition in conditions:
            for trial in range(1, self.trials + 1):
                trial_order.append((*condition, trial))
        
        random.shuffle(trial_order)
        
        print("Running randomized trials to avoid order effects...\n")
        
        for context, problem, attractor, component in conditions:
            print(f"\n{context} + {problem} + {attractor}:")
            condition_results = []
            
            # Get trials for this condition from randomized order
            condition_trials = [t for t in trial_order if t[:3] == (context, problem, attractor)]
            
            for _, _, _, _, trial_num in condition_trials:
                current_test += 1
                agent_id = f"rep_{context}_{problem}_{attractor}_t{trial_num}_{self.session_id}"
                
                # Get test prompt
                test_component = f"complexity/{problem}/{attractor}.md"
                component_path = Path(f"var/lib/compositions/components/tests/cognitive_overhead/{test_component}")
                
                if not component_path.exists():
                    print(f"  Trial {trial_num}: Component not found")
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
                
                print(f"  Trial {trial_num}/{self.trials}: ", end="", flush=True)
                
                start_time = time.time()
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                test_result = {
                    'agent_id': agent_id,
                    'context': context,
                    'problem': problem,
                    'attractor': attractor,
                    'component': component,
                    'trial': trial_num,
                    'spawn_time': start_time,
                    'session_id': self.session_id,
                    'position_in_sequence': current_test,
                    'total_tests': total_tests
                }
                
                if result.returncode != 0:
                    test_result['status'] = 'failed'
                    print("FAILED")
                else:
                    test_result['status'] = 'spawned'
                    print("OK")
                
                # Save immediately
                with open(self.results_file, 'a') as f:
                    f.write(json.dumps(test_result) + '\n')
                
                # Brief pause between tests
                time.sleep(2)
            
            print(f"  Progress: {current_test}/{total_tests} ({100*current_test/total_tests:.1f}%)")
        
        print(f"\n=== REPLICATION STUDY COMPLETE ===")
        print(f"Results: {self.results_file}")
        print(f"\nWait 60 seconds for processing, then analyze with:")
        print(f"python research/cognitive_overhead/analyze_replication.py {self.results_file}")
        
        return self.results_file

def main():
    study = StatisticalReplicationStudy(trials_per_condition=20)
    study.run_replication_study()

if __name__ == "__main__":
    main()