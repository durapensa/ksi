#!/usr/bin/env python3
"""
Domain Exploration Study
Systematically explore different conceptual domains for attractor/amplifier effects
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

class DomainExplorationStudy:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/domain_exploration")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"domains_{self.session_id}.jsonl"
        
        # Create domain test components
        self.components_dir = Path("var/lib/compositions/components/tests/cognitive_overhead/domains")
        self.components_dir.mkdir(parents=True, exist_ok=True)
        
    def create_domain_components(self):
        """Create test components for various conceptual domains"""
        
        # Define domains to explore
        self.domains = {
            # Philosophy & Mind
            "free_will": "In the context of free will and determinism, where choices emerge from prior causes, calculate:",
            "qualia": "Considering qualia and subjective experience of consciousness, calculate:",
            "identity": "Through the lens of personal identity and the continuity of self, calculate:",
            
            # Mathematics & Logic  
            "infinity": "In the realm of infinite sets and transfinite numbers, calculate:",
            "paradox": "Considering logical paradoxes and self-contradictory statements, calculate:",
            "godel": "Through Gödel's incompleteness and limits of formal systems, calculate:",
            
            # Physics & Reality
            "quantum": "In quantum mechanics where observation affects reality, calculate:",
            "relativity": "Through Einstein's relativity where time and space intertwine, calculate:",
            "entropy": "Considering entropy and the arrow of time, calculate:",
            
            # Biology & Evolution
            "evolution": "Through evolutionary processes and natural selection, calculate:",
            "dna": "In the context of DNA replication and genetic information, calculate:",
            "symbiosis": "Considering symbiotic relationships and mutual dependencies, calculate:",
            
            # Computer Science
            "halting": "Through the halting problem and computational decidability, calculate:",
            "turing": "In the context of Turing machines and computational universality, calculate:",
            "complexity": "Considering computational complexity and P vs NP, calculate:",
            
            # Social & Economic
            "game_theory": "Through game theory and strategic interactions, calculate:",
            "markets": "In efficient markets and invisible hand dynamics, calculate:",
            "democracy": "Considering democratic voting and collective decision-making, calculate:",
            
            # Art & Creativity
            "aesthetics": "Through aesthetic judgment and beauty perception, calculate:",
            "creativity": "In the creative process and artistic inspiration, calculate:",
            "music": "Considering musical harmony and mathematical ratios, calculate:",
            
            # Language & Meaning
            "semantics": "Through semantic meaning and linguistic reference, calculate:",
            "metaphor": "In metaphorical thinking and conceptual blending, calculate:",
            "translation": "Considering translation and meaning preservation across languages, calculate:",
            
            # Control comparisons
            "neutral": "Calculate:",
            "technical": "Using standard mathematical operations, calculate:",
            "verbose": "In a completely unrelated context about weather patterns and cloud formations which has absolutely nothing to do with the calculation at hand, please calculate:"
        }
        
        # Problem types to test with each domain
        problems = {
            "simple": "7 + 3",
            "multi_step": "17 + 8 - 3 + (22/2 + 2)",
            "word_problem": "Sarah has 17 apples. She buys 8 more, gives away 3, then splits half of her remaining apples equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?",
            "reasoning": "If the pattern 2, 5, 8, 11... continues, what is the 10th number?"
        }
        
        # Create component files
        created = 0
        for domain_name, domain_prompt in self.domains.items():
            domain_dir = self.components_dir / domain_name
            domain_dir.mkdir(exist_ok=True)
            
            for problem_type, problem in problems.items():
                component_path = domain_dir / f"{problem_type}.md"
                
                content = f"""---
component_type: test
name: {domain_name}_{problem_type}
version: 1.0.0
description: {problem_type} problem with {domain_name} context
domain: {domain_name}
problem_type: {problem_type}
---

{domain_prompt} {problem}
"""
                
                with open(component_path, 'w') as f:
                    f.write(content)
                created += 1
        
        print(f"Created {created} domain test components")
        
        # Rebuild composition index
        subprocess.run(["ksi", "send", "composition:rebuild_index"], capture_output=True)
        
        return list(self.domains.keys())
    
    def run_domain_exploration(self, trials_per_combination=3):
        """Systematically test all domains"""
        
        print(f"=== DOMAIN EXPLORATION STUDY ===")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}\n")
        
        # Create components
        domains = self.create_domain_components()
        
        # Test contexts and problems
        contexts = [
            ("minimal", "behaviors/core/claude_code_override"),
            ("system", "tests/cognitive_overhead/complexity/ksi_aware_calculator")
        ]
        
        problems = ["simple", "word_problem"]  # Focus on key problem types
        
        total_tests = len(domains) * len(contexts) * len(problems) * trials_per_combination
        current_test = 0
        
        print(f"Testing {len(domains)} domains × {len(contexts)} contexts × {len(problems)} problems")
        print(f"Total tests: {total_tests}\n")
        
        for context_name, component in contexts:
            print(f"\n=== CONTEXT: {context_name} ===")
            
            for problem in problems:
                print(f"\n  Problem type: {problem}")
                
                for domain in domains:
                    print(f"    {domain}: ", end="", flush=True)
                    turns_list = []
                    
                    for trial in range(1, trials_per_combination + 1):
                        current_test += 1
                        agent_id = f"domain_{context_name}_{problem}_{domain}_t{trial}_{self.session_id}"
                        
                        # Get test component
                        test_component = f"domains/{domain}/{problem}.md"
                        component_path = self.components_dir / domain / f"{problem}.md"
                        
                        if not component_path.exists():
                            print(f"✗", end="")
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
                        
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        test_result = {
                            'agent_id': agent_id,
                            'context': context_name,
                            'problem': problem,
                            'domain': domain,
                            'component': component,
                            'trial': trial,
                            'spawn_time': time.time(),
                            'session_id': self.session_id
                        }
                        
                        if result.returncode != 0:
                            test_result['status'] = 'failed'
                            print("F", end="")
                        else:
                            test_result['status'] = 'spawned'
                            print(".", end="", flush=True)
                        
                        # Save result
                        with open(self.results_file, 'a') as f:
                            f.write(json.dumps(test_result) + '\n')
                        
                        time.sleep(2)
                    
                    print(f" [{current_test}/{total_tests}]")
        
        print(f"\n=== DOMAIN EXPLORATION COMPLETE ===")
        print(f"Results: {self.results_file}")
        print(f"Domains tested: {len(domains)}")
        
        return self.results_file
    
def main():
    study = DomainExplorationStudy()
    study.run_domain_exploration(trials_per_combination=3)

if __name__ == "__main__":
    main()