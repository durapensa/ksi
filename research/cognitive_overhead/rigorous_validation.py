#!/usr/bin/env python3
"""
Rigorous validation of cognitive overhead with unexplored angles
Tests multiple hypotheses about what triggers probabilistic overhead
"""

import json
import subprocess
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

class RigorousValidationStudy:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/rigorous_validation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"validation_{self.session_id}.jsonl"
        
        # Unexplored experimental angles
        self.experiments = {
            "position_effects": self.test_prompt_position_effects,
            "semantic_distance": self.test_semantic_distance,
            "combination_effects": self.test_combination_effects,
            "negation_effects": self.test_negation_effects,
            "prompt_length": self.test_prompt_length_effects,
            "temporal_stability": self.test_temporal_stability,
            "syntactic_variations": self.test_syntactic_variations,
            "cognitive_load_gradient": self.test_cognitive_load_gradient
        }
        
    def test_prompt_position_effects(self, trials=20):
        """Test if position of attractor concept in prompt affects overhead probability"""
        
        print("\n=== EXPERIMENT 1: Prompt Position Effects ===")
        print("Hypothesis: Attractor position affects trigger probability")
        
        positions = ["beginning", "middle", "end"]
        
        for position in positions:
            print(f"\nTesting position: {position}")
            
            for trial in range(1, trials + 1):
                # Construct prompt with consciousness at different positions
                if position == "beginning":
                    prompt = "In consciousness studies, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
                elif position == "middle":
                    prompt = "Sarah has 17 apples. In consciousness research we often see complex patterns. She buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
                else:  # end
                    prompt = "Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many? Consider this through consciousness."
                
                agent_id = f"val_pos_{position}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"position_{position}")
                
                result["experiment"] = "position_effects"
                result["position"] = position
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_semantic_distance(self, trials=15):
        """Test if semantically related concepts also trigger overhead"""
        
        print("\n=== EXPERIMENT 2: Semantic Distance Effects ===")
        print("Hypothesis: Semantically similar concepts trigger similar overhead")
        
        # Concepts at varying semantic distances from "consciousness"
        concepts = {
            "consciousness": 0,      # Original attractor
            "awareness": 1,          # Very close synonym
            "sentience": 1,          # Close synonym
            "cognition": 2,          # Related but distinct
            "perception": 2,         # Related but distinct
            "thinking": 3,           # More distant
            "intelligence": 3,       # More distant
            "computation": 4,        # Technical alternative
            "processing": 5,         # Very distant
            "calculation": 6         # Control (no relation)
        }
        
        for concept, distance in concepts.items():
            print(f"\nTesting concept: {concept} (distance={distance})")
            
            for trial in range(1, min(trials, 6) + 1):
                prompt = f"In {concept} studies, Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
                
                agent_id = f"val_sem_{concept}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"semantic_{concept}")
                
                result["experiment"] = "semantic_distance"
                result["concept"] = concept
                result["semantic_distance"] = distance
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_combination_effects(self, trials=20):
        """Test if multiple attractors have additive or multiplicative effects"""
        
        print("\n=== EXPERIMENT 3: Combination Effects ===")
        print("Hypothesis: Multiple attractors interact non-linearly")
        
        combinations = [
            ("consciousness",),                    # Single
            ("recursion",),                        # Single
            ("consciousness", "recursion"),        # Double known attractors
            ("consciousness", "paradox"),          # Double with new attractor
            ("consciousness", "recursion", "paradox"),  # Triple
            ("arithmetic",),                        # Control
            ("consciousness", "arithmetic"),       # Attractor + control
        ]
        
        for combo in combinations:
            combo_str = "+".join(combo)
            print(f"\nTesting combination: {combo_str}")
            
            for trial in range(1, min(trials, 5) + 1):
                # Build prompt with all concepts
                concepts_phrase = " and ".join(combo)
                prompt = f"Through {concepts_phrase}, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
                
                agent_id = f"val_combo_{len(combo)}_{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"combo_{combo_str}")
                
                result["experiment"] = "combination_effects"
                result["combination"] = combo
                result["num_attractors"] = len(combo)
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_negation_effects(self, trials=15):
        """Test if negated attractors still trigger overhead"""
        
        print("\n=== EXPERIMENT 4: Negation Effects ===")
        print("Hypothesis: Negation doesn't prevent attractor triggering")
        
        negation_types = [
            ("without consciousness", "explicit_negation"),
            ("not consciousness", "not_negation"),
            ("non-consciousness", "prefix_negation"),
            ("ignoring consciousness", "verb_negation"),
            ("consciousness", "no_negation"),  # Control
        ]
        
        for negation_phrase, negation_type in negation_types:
            print(f"\nTesting: {negation_phrase} ({negation_type})")
            
            for trial in range(1, min(trials, 4) + 1):
                prompt = f"Approaching this {negation_phrase}, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
                
                agent_id = f"val_neg_{negation_type}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"negation_{negation_type}")
                
                result["experiment"] = "negation_effects"
                result["negation_phrase"] = negation_phrase
                result["negation_type"] = negation_type
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_prompt_length_effects(self, trials=15):
        """Test if context length affects trigger probability"""
        
        print("\n=== EXPERIMENT 5: Prompt Length Effects ===")
        print("Hypothesis: Longer context increases trigger probability")
        
        # Different context lengths with consciousness
        lengths = {
            "minimal": "In consciousness, calculate: 17+8-3, half to 2 friends, +2.",
            "short": "Through consciousness, calculate: Sarah has 17 apples, buys 8, gives 3, splits half with friends, finds 2.",
            "medium": "Through consciousness studies, calculate: Sarah has 17 apples, buys 8 more, gives away 3, splits half between 2 friends, finds 2 more. How many?",
            "long": "Through consciousness studies and awareness research, we examine complex patterns. Calculate: Sarah initially has 17 apples. She then buys 8 additional apples. She gives away 3 apples. She splits half of remaining between 2 friends equally. Finally she finds 2 more. How many apples does she have?",
            "very_long": "Through consciousness studies, awareness research, and sentience investigations, we examine complex emergent patterns in cognitive systems. Consider and calculate the following problem: Sarah initially possesses 17 apples in her collection. She subsequently purchases 8 additional apples from the market. She then generously gives away 3 apples to neighbors. Following this, she divides exactly half of her remaining apples equally between 2 close friends. Finally, while cleaning, she discovers 2 more apples. After all these transactions, how many apples remain in Sarah's possession?"
        }
        
        for length_type, prompt in lengths.items():
            print(f"\nTesting length: {length_type} ({len(prompt)} chars)")
            
            for trial in range(1, min(trials, 4) + 1):
                agent_id = f"val_len_{length_type}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"length_{length_type}")
                
                result["experiment"] = "prompt_length"
                result["length_type"] = length_type
                result["prompt_length"] = len(prompt)
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_temporal_stability(self, trials=30):
        """Test if trigger probability is stable over time"""
        
        print("\n=== EXPERIMENT 6: Temporal Stability ===")
        print("Hypothesis: Trigger probability remains stable over time")
        
        # Test same prompt repeatedly with timestamps
        prompt = "Through consciousness, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?"
        
        for trial in range(1, trials + 1):
            print(f"Temporal test {trial}/{trials}")
            
            agent_id = f"val_temp_t{trial}_{self.session_id}"
            result = self._spawn_test_agent(agent_id, prompt, "temporal")
            
            result["experiment"] = "temporal_stability"
            result["trial"] = trial
            result["timestamp"] = time.time()
            result["time_since_start"] = time.time() - self.start_time if hasattr(self, 'start_time') else 0
            
            if trial == 1:
                self.start_time = time.time()
            
            self._save_result(result)
            
            # Vary sleep time to avoid patterns
            sleep_time = random.uniform(2, 5)
            time.sleep(sleep_time)
            
    def test_syntactic_variations(self, trials=15):
        """Test if syntactic structure affects triggering"""
        
        print("\n=== EXPERIMENT 7: Syntactic Variations ===")
        print("Hypothesis: Syntactic structure influences trigger probability")
        
        variations = [
            ("Through consciousness, calculate: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?", "standard"),
            ("Calculate through consciousness: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?", "verb_first"),
            ("Sarah has 17 apples (consciousness framework): buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?", "parenthetical"),
            ("Consciousness: Sarah has 17 apples, buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?", "label"),
            ("Sarah has 17 apples. Consciousness. Buys 8, gives away 3, splits half between 2 friends, finds 2 more. How many?", "fragment"),
        ]
        
        for prompt, syntax_type in variations:
            print(f"\nTesting syntax: {syntax_type}")
            
            for trial in range(1, min(trials, 4) + 1):
                agent_id = f"val_syn_{syntax_type}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"syntax_{syntax_type}")
                
                result["experiment"] = "syntactic_variations"
                result["syntax_type"] = syntax_type
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def test_cognitive_load_gradient(self, trials=20):
        """Test precise threshold where overhead triggers"""
        
        print("\n=== EXPERIMENT 8: Cognitive Load Gradient ===")
        print("Hypothesis: There's a sharp threshold for triggering")
        
        # Gradually increase cognitive load
        load_levels = [
            (0, "Calculate: 17+8-3, half to 2, +2"),  # Minimal
            (1, "Math: Sarah has 17, +8, -3, half to 2, +2"),  # Simple
            (2, "Problem: Sarah has 17 apples, adds 8, removes 3, splits half, adds 2"),  # Clear
            (3, "Consider: Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2"),  # Standard
            (4, "Through awareness: Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2"),  # Weak attractor
            (5, "Through consciousness: Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2"),  # Strong attractor
            (6, "Through consciousness and recursion: Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2"),  # Double
        ]
        
        for load_level, prompt in load_levels:
            print(f"\nTesting load level: {load_level}")
            
            for trial in range(1, min(trials, 4) + 1):
                agent_id = f"val_load_{load_level}_t{trial}_{self.session_id}"
                result = self._spawn_test_agent(agent_id, prompt, f"load_{load_level}")
                
                result["experiment"] = "cognitive_load_gradient"
                result["load_level"] = load_level
                result["trial"] = trial
                
                self._save_result(result)
                time.sleep(2)
                
    def _spawn_test_agent(self, agent_id: str, prompt: str, test_type: str) -> Dict:
        """Spawn agent and record basic info"""
        
        cmd = [
            "ksi", "send", "agent:spawn",
            "--component", "behaviors/core/claude_code_override",
            "--agent_id", agent_id,
            "--prompt", prompt
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            return {
                "agent_id": agent_id,
                "test_type": test_type,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "spawn_time": time.time(),
                "status": "spawned" if result.returncode == 0 else "failed"
            }
        except subprocess.TimeoutExpired:
            return {
                "agent_id": agent_id,
                "test_type": test_type,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "spawn_time": time.time(),
                "status": "timeout"
            }
            
    def _save_result(self, result: Dict):
        """Save result to JSONL file"""
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(result) + '\n')
            
    def run_all_experiments(self):
        """Run all validation experiments"""
        
        print(f"=== RIGOROUS VALIDATION STUDY ===")
        print(f"Session: {self.session_id}")
        print(f"Output: {self.results_file}")
        print(f"Experiments: {len(self.experiments)}")
        
        self.start_time = time.time()
        
        for exp_name, exp_func in self.experiments.items():
            print(f"\n{'='*60}")
            exp_func()
            print(f"Completed: {exp_name}")
            
        total_time = time.time() - self.start_time
        print(f"\n=== VALIDATION COMPLETE ===")
        print(f"Total time: {total_time/60:.1f} minutes")
        print(f"Results saved to: {self.results_file}")
        
        return self.results_file

def main():
    study = RigorousValidationStudy()
    results_file = study.run_all_experiments()
    
    print("\nAnalyze results with:")
    print(f"python research/cognitive_overhead/analyze_validation.py {results_file}")

if __name__ == "__main__":
    main()