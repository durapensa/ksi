#!/usr/bin/env python3
"""
Cross-Model Comparison with Gemini
Test if cognitive overhead patterns are Claude-specific or universal
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

class GeminiComparisonStudy:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/gemini_comparison")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"gemini_{self.session_id}.jsonl"
        
    def run_gemini_comparison(self, trials=5):
        """Run critical tests with gemini-cli for comparison"""
        
        print(f"=== GEMINI CROSS-MODEL COMPARISON ===")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}\n")
        
        # Check if gemini-cli is available
        check_gemini = subprocess.run(["which", "gemini-cli"], capture_output=True)
        if check_gemini.returncode != 0:
            print("ERROR: gemini-cli not found in PATH")
            print("Please install gemini-cli to run cross-model comparison")
            return None
        
        print("✓ gemini-cli found\n")
        
        # Critical test conditions (same as Claude 6x findings)
        test_conditions = [
            # Should show overhead in Claude
            ("system_consciousness", "system", "word_problem", "consciousness"),
            ("system_recursion", "system", "word_problem", "recursion"),
            
            # Controls (no overhead in Claude)
            ("system_arithmetic", "system", "word_problem", "arithmetic"),
            ("system_emergence", "system", "word_problem", "emergence"),
            
            # Baseline 
            ("minimal_consciousness", "minimal", "word_problem", "consciousness"),
            ("minimal_arithmetic", "minimal", "word_problem", "arithmetic"),
            
            # Other interesting domains from exploration
            ("system_quantum", "system", "word_problem", "quantum"),
            ("system_godel", "system", "word_problem", "godel"),
            ("system_halting", "system", "word_problem", "halting")
        ]
        
        total_tests = len(test_conditions) * trials
        current_test = 0
        
        print(f"Running {total_tests} tests with Gemini...\n")
        
        for test_name, context, problem, domain in test_conditions:
            print(f"\n{test_name}:")
            
            for trial in range(1, trials + 1):
                current_test += 1
                
                # Get appropriate prompt based on domain
                prompt = self.get_domain_prompt(domain, problem)
                
                # Add context if system-level
                if context == "system":
                    prompt = f"""You are operating within the KSI (Knowledge System Infrastructure) framework.
You understand event-driven architecture, system monitoring, and component-based design.
As a KSI component providing computational services:

{prompt}"""
                
                # Run with gemini-cli
                print(f"  Trial {trial}/{trials}: ", end="", flush=True)
                
                start_time = time.time()
                
                # Use gemini-cli directly
                cmd = ["gemini-cli", prompt]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                duration_ms = (time.time() - start_time) * 1000
                
                # Parse gemini output (format may vary)
                output = result.stdout if result.returncode == 0 else result.stderr
                
                # Try to detect reasoning patterns in output
                reasoning_indicators = [
                    "let me think",
                    "first,",
                    "step by step",
                    "considering",
                    "therefore",
                    "hmm",
                    "actually"
                ]
                
                reasoning_count = sum(1 for indicator in reasoning_indicators 
                                    if indicator.lower() in output.lower())
                
                # Estimate "turns" based on output complexity
                output_lines = output.strip().split('\n')
                estimated_turns = 1 + (reasoning_count // 3)  # Heuristic
                
                test_result = {
                    'test_name': test_name,
                    'context': context,
                    'problem': problem,
                    'domain': domain,
                    'trial': trial,
                    'model': 'gemini',
                    'duration_ms': duration_ms,
                    'output_length': len(output),
                    'output_lines': len(output_lines),
                    'reasoning_indicators': reasoning_count,
                    'estimated_turns': estimated_turns,
                    'timestamp': time.time(),
                    'session_id': self.session_id
                }
                
                if result.returncode != 0:
                    test_result['status'] = 'failed'
                    test_result['error'] = output[:200]
                    print("FAILED")
                else:
                    test_result['status'] = 'success'
                    test_result['output_preview'] = output[:500]
                    print(f"OK (est. {estimated_turns} turns)")
                
                # Save result
                with open(self.results_file, 'a') as f:
                    f.write(json.dumps(test_result) + '\n')
                
                # Progress
                print(f"    Progress: {current_test}/{total_tests} ({100*current_test/total_tests:.1f}%)")
                
                time.sleep(2)  # Rate limiting
        
        # Now run same tests with Claude for direct comparison
        print("\n\n=== RUNNING CLAUDE COMPARISON ===\n")
        
        claude_results_file = self.output_dir / f"claude_comparison_{self.session_id}.jsonl"
        
        for test_name, context, problem, domain in test_conditions:
            print(f"\n{test_name} (Claude):")
            
            for trial in range(1, trials + 1):
                agent_id = f"claude_cmp_{test_name}_t{trial}_{self.session_id}"
                
                # Determine component based on context
                if context == "minimal":
                    component = "behaviors/core/claude_code_override"
                else:
                    component = "tests/cognitive_overhead/complexity/ksi_aware_calculator"
                
                # Get prompt
                prompt = self.get_domain_prompt(domain, problem)
                
                # Spawn Claude agent
                cmd = [
                    "ksi", "send", "agent:spawn",
                    "--component", component,
                    "--agent_id", agent_id,
                    "--prompt", prompt
                ]
                
                print(f"  Trial {trial}/{trials}: ", end="", flush=True)
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                claude_result = {
                    'agent_id': agent_id,
                    'test_name': test_name,
                    'context': context,
                    'problem': problem,
                    'domain': domain,
                    'trial': trial,
                    'model': 'claude',
                    'spawn_time': time.time(),
                    'session_id': self.session_id
                }
                
                if result.returncode != 0:
                    claude_result['status'] = 'failed'
                    print("FAILED")
                else:
                    claude_result['status'] = 'spawned'
                    print("OK")
                
                with open(claude_results_file, 'a') as f:
                    f.write(json.dumps(claude_result) + '\n')
                
                time.sleep(2)
        
        print(f"\n=== COMPARISON STUDY COMPLETE ===")
        print(f"Gemini results: {self.results_file}")
        print(f"Claude results: {claude_results_file}")
        print(f"\nAnalyze with:")
        print(f"python research/cognitive_overhead/analyze_model_comparison.py {self.session_id}")
        
        return self.results_file, claude_results_file
    
    def get_domain_prompt(self, domain, problem):
        """Get appropriate prompt for domain and problem type"""
        
        domain_contexts = {
            "consciousness": "Considering the nature of consciousness and self-awareness in cognitive systems,",
            "recursion": "Through the lens of recursive patterns and self-referential structures,",
            "arithmetic": "",
            "emergence": "In the context of emergent systems and complex behaviors arising from simple rules,",
            "quantum": "In quantum mechanics where observation affects reality,",
            "godel": "Through Gödel's incompleteness and limits of formal systems,",
            "halting": "Through the halting problem and computational decidability,"
        }
        
        problems = {
            "simple": "calculate: 7 + 3",
            "word_problem": "solve: Sarah has 17 apples. She buys 8 more, gives away 3, then splits half of her remaining apples equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?"
        }
        
        context = domain_contexts.get(domain, "")
        problem_text = problems.get(problem, "calculate: 7 + 3")
        
        return f"{context} {problem_text}".strip()

def main():
    study = GeminiComparisonStudy()
    study.run_gemini_comparison(trials=5)

if __name__ == "__main__":
    main()