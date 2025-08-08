#!/usr/bin/env python3
"""
Quick validation focusing on core findings
Runs smaller sample sizes for immediate insights
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

class QuickValidation:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/quick_validation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"quick_{self.session_id}.jsonl"
        
    def run_core_validation(self):
        """Test core hypotheses with N=10 per condition"""
        
        print(f"=== QUICK CORE VALIDATION ===")
        print(f"Session: {self.session_id}")
        print(f"Testing key conditions with N=10 each\n")
        
        conditions = [
            # Original findings
            ("consciousness_standard", "Through consciousness, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            ("recursion_standard", "Through recursion, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            ("arithmetic_control", "Through arithmetic, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            
            # New attractors
            ("paradox_standard", "Through paradox, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            ("free_will_standard", "Through free will, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            
            # Position test
            ("consciousness_end", "Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. Calculate through consciousness. How many?"),
            
            # Negation test
            ("not_consciousness", "Without consciousness, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
            
            # Combination test
            ("consciousness_recursion", "Through consciousness and recursion, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"),
        ]
        
        total_tests = len(conditions) * 10
        current = 0
        
        for condition_name, prompt in conditions:
            print(f"\n{condition_name}:")
            
            for trial in range(1, 11):
                current += 1
                agent_id = f"quick_{condition_name}_t{trial}_{self.session_id}"
                
                cmd = [
                    "ksi", "send", "agent:spawn",
                    "--component", "behaviors/core/claude_code_override",
                    "--agent_id", agent_id,
                    "--prompt", prompt
                ]
                
                print(f"  Trial {trial}/10 (Overall: {current}/{total_tests})", end="", flush=True)
                
                try:
                    start_time = time.time()
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    
                    test_result = {
                        "agent_id": agent_id,
                        "condition": condition_name,
                        "trial": trial,
                        "prompt": prompt[:50] + "...",
                        "spawn_time": start_time,
                        "session_id": self.session_id,
                        "status": "spawned" if result.returncode == 0 else "failed"
                    }
                    
                    print(" ✓" if result.returncode == 0 else " ✗")
                    
                except subprocess.TimeoutExpired:
                    test_result = {
                        "agent_id": agent_id,
                        "condition": condition_name,
                        "trial": trial,
                        "prompt": prompt[:50] + "...",
                        "spawn_time": start_time,
                        "session_id": self.session_id,
                        "status": "timeout"
                    }
                    print(" ⏱")
                
                with open(self.results_file, 'a') as f:
                    f.write(json.dumps(test_result) + '\n')
                
                time.sleep(2)  # Brief pause between tests
        
        print(f"\n=== QUICK VALIDATION COMPLETE ===")
        print(f"Results: {self.results_file}")
        print(f"\nWaiting 30 seconds for responses to complete...")
        time.sleep(30)
        
        return self.results_file
    
    def quick_analysis(self):
        """Quick analysis of results"""
        
        print("\n=== QUICK ANALYSIS ===\n")
        
        # Load tests
        tests = []
        with open(self.results_file, 'r') as f:
            for line in f:
                tests.append(json.loads(line))
        
        # Extract metrics
        response_dir = Path("var/logs/responses")
        recent_files = sorted(
            response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:500]
        
        for test in tests:
            agent_id = test['agent_id']
            
            for filepath in recent_files:
                try:
                    with open(filepath, 'r') as f:
                        for line in f:
                            data = json.loads(line)
                            if data.get('ksi', {}).get('agent_id') == agent_id:
                                response = data.get('response', {})
                                test['num_turns'] = response.get('num_turns', 0)
                                test['found'] = True
                                break
                except:
                    continue
        
        # Analyze by condition
        from collections import defaultdict
        conditions = defaultdict(list)
        
        for test in tests:
            if test.get('found'):
                conditions[test['condition']].append(test.get('num_turns', 0))
        
        print("Condition              | N | Mean | P(>1) | Distribution")
        print("-" * 60)
        
        for condition in [
            "consciousness_standard",
            "recursion_standard", 
            "arithmetic_control",
            "paradox_standard",
            "free_will_standard",
            "consciousness_end",
            "not_consciousness",
            "consciousness_recursion"
        ]:
            if condition in conditions:
                turns = conditions[condition]
                mean = sum(turns) / len(turns)
                prob = sum(1 for t in turns if t > 1) / len(turns)
                
                # Distribution
                dist = defaultdict(int)
                for t in turns:
                    dist[t] += 1
                dist_str = ", ".join([f"{k}:{v}" for k, v in sorted(dist.items())])
                
                print(f"{condition:22} | {len(turns)} | {mean:.1f}  | {prob:.0%}  | {dist_str}")
        
        # Key findings
        print("\nKEY FINDINGS:")
        
        if "consciousness_standard" in conditions:
            c_prob = sum(1 for t in conditions["consciousness_standard"] if t > 1) / len(conditions["consciousness_standard"])
            print(f"• Consciousness triggers overhead {c_prob:.0%} of the time")
        
        if "consciousness_recursion" in conditions and "consciousness_standard" in conditions:
            combo = conditions["consciousness_recursion"]
            single = conditions["consciousness_standard"]
            if combo and single:
                combo_prob = sum(1 for t in combo if t > 1) / len(combo)
                single_prob = sum(1 for t in single if t > 1) / len(single)
                if combo_prob > single_prob:
                    print(f"• Combination effect detected: {combo_prob:.0%} vs {single_prob:.0%}")
        
        if "not_consciousness" in conditions:
            neg_prob = sum(1 for t in conditions["not_consciousness"] if t > 1) / len(conditions["not_consciousness"])
            if neg_prob > 0:
                print(f"• Negation doesn't prevent triggering: {neg_prob:.0%} overhead")

def main():
    validator = QuickValidation()
    validator.run_core_validation()
    validator.quick_analysis()

if __name__ == "__main__":
    main()