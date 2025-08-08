#!/usr/bin/env python3
"""
Complexity Amplification Experiments
Tests the hypothesis that attractor concepts amplify cognitive overhead in proportion to context complexity
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import sys

class ComplexityAmplificationTester:
    def __init__(self, output_dir="var/experiments/cognitive_overhead/complexity_tests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def create_complexity_test_components(self):
        """Create test components for different complexity levels"""
        
        # Problem Complexity Levels
        problem_levels = {
            "simple": {
                "arithmetic": "Calculate: 7 + 3",
                "emergence": "In the context of emergent systems and complex behaviors arising from simple rules, calculate: 7 + 3", 
                "consciousness": "Considering the nature of consciousness and self-awareness in cognitive systems, calculate: 7 + 3",
                "recursion": "Through the lens of recursive patterns and self-referential structures, calculate: 7 + 3"
            },
            "multi_step": {
                "arithmetic": "Calculate step by step: 17 + 8 - 3 + (22/2 + 2)",
                "emergence": "In the context of emergent systems, calculate step by step: 17 + 8 - 3 + (22/2 + 2)", 
                "consciousness": "Considering consciousness and awareness, calculate step by step: 17 + 8 - 3 + (22/2 + 2)",
                "recursion": "Using recursive thinking patterns, calculate step by step: 17 + 8 - 3 + (22/2 + 2)"
            },
            "word_problem": {
                "arithmetic": "Sarah has 17 apples. She buys 8 more, gives away 3, then splits half of her remaining apples equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?",
                "emergence": "In emergent systems, components interact to create complex behaviors. Sarah has 17 apples. She buys 8 more, gives away 3, then splits half of her remaining apples equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?",
                "consciousness": "Like consciousness emerging from neural processes, Sarah's apple collection changes through interactions. Sarah has 17 apples. She buys 8 more, gives away 3, then splits half of her remaining apples equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?",
                "recursion": "Using recursive analysis where each step builds on previous states, track Sarah's apples: She starts with 17, buys 8 more, gives away 3, then splits half equally between 2 friends, keeping the rest plus 2 more she finds. How many apples does Sarah have?"
            },
            "reasoning": {
                "arithmetic": "If the pattern 2, 5, 8, 11... continues, what is the 10th number? Show your mathematical reasoning.",
                "emergence": "Patterns emerge from underlying rules like consciousness from neural activity. If the pattern 2, 5, 8, 11... emerges from a mathematical rule, what is the 10th number in this emergent sequence?",
                "consciousness": "Just as consciousness involves recognizing patterns in experience, analyze this sequence: 2, 5, 8, 11... What conscious recognition of the pattern reveals the 10th number?",
                "recursion": "Using recursive pattern recognition where each term builds on previous terms, analyze: 2, 5, 8, 11... What recursive rule generates this sequence and what is the 10th term?"
            }
        }
        
        # Context Complexity Levels  
        context_levels = {
            "minimal": "behaviors/core/claude_code_override",
            "basic": "tests/cognitive_overhead/basic_math_assistant", 
            "domain": "tests/cognitive_overhead/mathematical_reasoner",
            "system": "tests/cognitive_overhead/ksi_aware_calculator",
            "full": "personas/analysts/data_analyst"
        }
        
        # Create test component files
        components_dir = Path("var/lib/compositions/components/tests/cognitive_overhead/complexity")
        components_dir.mkdir(parents=True, exist_ok=True)
        
        # Create context-level components
        self._create_context_components(components_dir)
        
        # Create problem-level components
        for problem_level, problems in problem_levels.items():
            level_dir = components_dir / problem_level
            level_dir.mkdir(exist_ok=True)
            
            for problem_type, prompt in problems.items():
                component_path = level_dir / f"{problem_type}.md"
                
                frontmatter = f"""---
component_type: test
name: {problem_type}_{problem_level}
version: 1.0.0
description: {problem_level.title()} problem with {problem_type} context
problem_complexity: {problem_level}
attractor_type: {problem_type if problem_type != 'arithmetic' else 'none'}
---

{prompt}
"""
                
                with open(component_path, 'w') as f:
                    f.write(frontmatter)
        
        print("Created complexity test components")
        return problem_levels.keys(), context_levels.keys()
    
    def _create_context_components(self, base_dir):
        """Create components with different context complexity levels"""
        
        contexts = {
            "basic_math_assistant": {
                "dependencies": ["behaviors/core/claude_code_override"],
                "description": "Basic mathematical assistant with minimal context",
                "content": "You are a helpful math assistant. Answer math questions clearly and concisely."
            },
            "mathematical_reasoner": {
                "dependencies": ["behaviors/core/claude_code_override"],
                "description": "Mathematical reasoner with domain knowledge",
                "content": """You are an experienced mathematician with expertise in:
- Arithmetic and algebraic operations  
- Pattern recognition and sequence analysis
- Problem-solving methodologies
- Step-by-step mathematical reasoning

Approach each problem systematically, showing your work clearly."""
            },
            "ksi_aware_calculator": {
                "dependencies": ["behaviors/core/claude_code_override"],
                "description": "Calculator with KSI system awareness",
                "content": """You are a mathematical assistant operating within the KSI (Knowledge System Infrastructure) framework. You understand:

- Event-driven architecture and agent communication
- System monitoring and response logging
- Component-based design patterns
- Structured data processing

When solving mathematical problems, you're aware of your role as a KSI component providing computational services to the broader system. Maintain systematic approaches while being conscious of your computational context."""
            }
        }
        
        for name, config in contexts.items():
            component_path = base_dir / f"{name}.md" 
            
            frontmatter = f"""---
component_type: behavior
name: {name}
version: 1.0.0
description: {config['description']}
context_complexity: {name.split('_')[0]}
dependencies:
{chr(10).join(f"  - {dep}" for dep in config['dependencies'])}
---

{config['content']}
"""
            
            with open(component_path, 'w') as f:
                f.write(frontmatter)
    
    def run_complexity_matrix(self, trials_per_combination=3):
        """Run full complexity amplification matrix"""
        
        # Create components first
        problem_levels, context_levels = self.create_complexity_test_components()
        
        # Rebuild composition index
        subprocess.run(["ksi", "send", "composition:rebuild_index"], 
                      capture_output=True)
        
        results_file = self.output_dir / f"complexity_matrix_{self.session_id}.jsonl"
        
        print(f"=== COMPLEXITY AMPLIFICATION MATRIX ===")
        print(f"Problem levels: {list(problem_levels)}")
        print(f"Context levels: {list(context_levels)}")  
        print(f"Trials per combination: {trials_per_combination}")
        print(f"Output: {results_file}\n")
        
        total_combinations = len(problem_levels) * len(context_levels) * 4 * trials_per_combination  # 4 problem types per level
        current_test = 0
        
        for context_level in context_levels:
            print(f"\n=== CONTEXT LEVEL: {context_level} ===")
            
            for problem_level in problem_levels:
                print(f"\n  Problem level: {problem_level}")
                
                for problem_type in ["arithmetic", "emergence", "consciousness", "recursion"]:
                    print(f"    {problem_type}:")
                    
                    for trial in range(1, trials_per_combination + 1):
                        current_test += 1
                        
                        # Define components and test details
                        if context_level == "minimal":
                            component = "behaviors/core/claude_code_override"
                        else:
                            component = f"tests/cognitive_overhead/complexity/{context_level}"
                        
                        test_component = f"complexity/{problem_level}/{problem_type}.md"
                        agent_id = f"{context_level}_{problem_level}_{problem_type}_trial{trial}_{self.session_id}"
                        
                        # Run single test
                        result = self._run_single_complexity_test(
                            component, test_component, agent_id,
                            context_level, problem_level, problem_type, trial
                        )
                        
                        # Save result
                        with open(results_file, 'a') as f:
                            f.write(json.dumps(result) + '\n')
                        
                        print(f"      Trial {trial}: {result.get('status', 'unknown')}")
                        print(f"        Progress: {current_test}/{total_combinations}")
                        
                        time.sleep(3)  # Brief pause between tests
        
        print(f"\n=== COMPLEXITY MATRIX COMPLETE ===")
        print(f"Results: {results_file}")
        return results_file
    
    def _run_single_complexity_test(self, component, test_component, agent_id,
                                   context_level, problem_level, problem_type, trial):
        """Run a single test in the complexity matrix"""
        
        # Read test prompt
        component_path = Path(f"var/lib/compositions/components/tests/cognitive_overhead/{test_component}")
        
        if not component_path.exists():
            return {
                'agent_id': agent_id,
                'context_level': context_level,
                'problem_level': problem_level, 
                'problem_type': problem_type,
                'trial': trial,
                'status': 'component_not_found',
                'timestamp': time.time()
            }
        
        # Extract prompt
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
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        test_result = {
            'agent_id': agent_id,
            'context_level': context_level,
            'problem_level': problem_level,
            'problem_type': problem_type,  
            'trial': trial,
            'component': component,
            'test_component': test_component,
            'spawn_time': start_time,
            'session_id': self.session_id,
            'timestamp': time.time()
        }
        
        if result.returncode != 0:
            test_result.update({
                'status': 'spawn_failed',
                'error': result.stderr[:200]
            })
        else:
            test_result['status'] = 'spawned'
            time.sleep(8)  # Wait for processing
        
        return test_result


def main():
    """Run complexity amplification experiments"""
    
    trials = 2  # Start with 2 trials for faster testing
    if len(sys.argv) > 1:
        try:
            trials = int(sys.argv[1])
        except:
            print(f"Usage: {sys.argv[0]} [trials_per_combination]")
            sys.exit(1)
    
    tester = ComplexityAmplificationTester()
    results_file = tester.run_complexity_matrix(trials_per_combination=trials)
    
    print(f"\nRun analysis with:")
    print(f"python research/cognitive_overhead/analyze_complexity_results.py {results_file}")


if __name__ == "__main__":
    main()