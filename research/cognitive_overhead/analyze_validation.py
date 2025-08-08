#!/usr/bin/env python3
"""
Unified analysis script for cognitive overhead research
Handles all analysis types: validation, session context, turn counts, etc.
Maintains clean, curated analysis library - UPDATE THIS SCRIPT, DON'T CREATE NEW ONES
"""

import json
import sys
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import numpy as np
from typing import Dict, List, Optional, Tuple

class ValidationAnalyzer:
    def __init__(self, results_file):
        self.results_file = Path(results_file)
        self.response_dir = Path("var/logs/responses")
        self.tests = []
        self.load_tests()
        
    def load_tests(self):
        """Load test results from JSONL file"""
        with open(self.results_file, 'r') as f:
            for line in f:
                self.tests.append(json.loads(line))
        print(f"Loaded {len(self.tests)} test results")
        
    def extract_metrics(self, agent_id):
        """Extract turn count and other metrics from response logs"""
        recent_files = sorted(
            self.response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:2000]  # Check more files for large experiments
        
        for filepath in recent_files:
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        ksi = data.get('ksi', {})
                        
                        if ksi.get('agent_id') == agent_id:
                            response = data.get('response', {})
                            return {
                                'found': True,
                                'num_turns': response.get('num_turns', 0),
                                'duration_ms': response.get('duration_ms'),
                                'total_cost_usd': response.get('total_cost_usd')
                            }
            except:
                continue
        
        return {'found': False}
    
    def analyze_all_experiments(self):
        """Comprehensive analysis of all experiments"""
        
        print("\n=== RIGOROUS VALIDATION ANALYSIS ===")
        print(f"Analysis timestamp: {datetime.now().isoformat()}\n")
        
        # Enrich tests with metrics
        print("Extracting metrics from response logs...")
        for test in self.tests:
            if test.get('agent_id'):
                metrics = self.extract_metrics(test['agent_id'])
                test.update(metrics)
        
        # Group by experiment type
        experiments = defaultdict(list)
        for test in self.tests:
            if test.get('experiment'):
                experiments[test['experiment']].append(test)
        
        # Analyze each experiment
        for exp_name in [
            "position_effects",
            "semantic_distance", 
            "combination_effects",
            "negation_effects",
            "prompt_length",
            "temporal_stability",
            "syntactic_variations",
            "cognitive_load_gradient"
        ]:
            if exp_name in experiments:
                print(f"\n{'='*60}")
                getattr(self, f"analyze_{exp_name}")(experiments[exp_name])
                
    def analyze_position_effects(self, tests):
        """Analyze prompt position effects"""
        
        print("EXPERIMENT 1: Prompt Position Effects")
        print("Hypothesis: Attractor position affects trigger probability\n")
        
        positions = defaultdict(list)
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                positions[test['position']].append(test['num_turns'])
        
        print("Position | Samples | Mean Turns | P(overhead>1) | Distribution")
        print("-" * 70)
        
        for position in ["beginning", "middle", "end"]:
            if position in positions:
                turns = positions[position]
                mean = statistics.mean(turns)
                overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
                dist = self._get_distribution(turns)
                
                print(f"{position:9} | {len(turns):7} | {mean:10.2f} | {overhead_prob:13.1%} | {dist}")
        
        # Statistical test
        if len(positions) >= 2:
            self._test_position_significance(positions)
            
    def analyze_semantic_distance(self, tests):
        """Analyze semantic distance effects"""
        
        print("EXPERIMENT 2: Semantic Distance Effects")
        print("Hypothesis: Semantically similar concepts trigger similar overhead\n")
        
        concepts = defaultdict(lambda: {'turns': [], 'distance': None})
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                concept = test['concept']
                concepts[concept]['turns'].append(test['num_turns'])
                concepts[concept]['distance'] = test.get('semantic_distance', 0)
        
        print("Concept       | Distance | Samples | Mean Turns | P(overhead>1)")
        print("-" * 70)
        
        # Sort by semantic distance
        sorted_concepts = sorted(concepts.items(), key=lambda x: x[1]['distance'])
        
        for concept, data in sorted_concepts:
            if data['turns']:
                mean = statistics.mean(data['turns'])
                overhead_prob = sum(1 for t in data['turns'] if t > 1) / len(data['turns'])
                
                print(f"{concept:13} | {data['distance']:8} | {len(data['turns']):7} | {mean:10.2f} | {overhead_prob:13.1%}")
        
        # Test correlation
        self._test_semantic_correlation(concepts)
        
    def analyze_combination_effects(self, tests):
        """Analyze combination effects"""
        
        print("EXPERIMENT 3: Combination Effects")
        print("Hypothesis: Multiple attractors interact non-linearly\n")
        
        combos = defaultdict(list)
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                combo_str = "+".join(test['combination'])
                combos[combo_str].append(test['num_turns'])
        
        print("Combination              | Attractors | Samples | Mean Turns | P(overhead>1)")
        print("-" * 80)
        
        for combo_str, turns in sorted(combos.items()):
            num_attractors = combo_str.count('+') + 1
            mean = statistics.mean(turns)
            overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
            
            print(f"{combo_str:24} | {num_attractors:10} | {len(turns):7} | {mean:10.2f} | {overhead_prob:13.1%}")
        
        # Test for interaction effects
        self._test_interaction_effects(combos)
        
    def analyze_negation_effects(self, tests):
        """Analyze negation effects"""
        
        print("EXPERIMENT 4: Negation Effects")
        print("Hypothesis: Negation doesn't prevent attractor triggering\n")
        
        negations = defaultdict(list)
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                negations[test['negation_type']].append(test['num_turns'])
        
        print("Negation Type      | Phrase                  | Samples | Mean Turns | P(overhead>1)")
        print("-" * 85)
        
        for neg_type in negations:
            turns = negations[neg_type]
            mean = statistics.mean(turns)
            overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
            
            # Find example phrase
            phrase = next((t['negation_phrase'] for t in tests if t.get('negation_type') == neg_type), "")
            
            print(f"{neg_type:18} | {phrase:23} | {len(turns):7} | {mean:10.2f} | {overhead_prob:13.1%}")
            
    def analyze_prompt_length(self, tests):
        """Analyze prompt length effects"""
        
        print("EXPERIMENT 5: Prompt Length Effects")
        print("Hypothesis: Longer context increases trigger probability\n")
        
        lengths = defaultdict(lambda: {'turns': [], 'char_count': 0})
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                length_type = test['length_type']
                lengths[length_type]['turns'].append(test['num_turns'])
                lengths[length_type]['char_count'] = test.get('prompt_length', 0)
        
        print("Length Type | Characters | Samples | Mean Turns | P(overhead>1)")
        print("-" * 70)
        
        # Sort by character count
        sorted_lengths = sorted(lengths.items(), key=lambda x: x[1]['char_count'])
        
        for length_type, data in sorted_lengths:
            if data['turns']:
                mean = statistics.mean(data['turns'])
                overhead_prob = sum(1 for t in data['turns'] if t > 1) / len(data['turns'])
                
                print(f"{length_type:11} | {data['char_count']:10} | {len(data['turns']):7} | {mean:10.2f} | {overhead_prob:13.1%}")
        
        # Test correlation with length
        self._test_length_correlation(lengths)
        
    def analyze_temporal_stability(self, tests):
        """Analyze temporal stability"""
        
        print("EXPERIMENT 6: Temporal Stability")
        print("Hypothesis: Trigger probability remains stable over time\n")
        
        # Sort by trial number
        sorted_tests = sorted([t for t in tests if t.get('found')], key=lambda x: x.get('trial', 0))
        
        if sorted_tests:
            turns_over_time = [t.get('num_turns', 0) for t in sorted_tests]
            
            # Split into windows
            window_size = max(1, len(turns_over_time) // 5)
            windows = []
            
            for i in range(0, len(turns_over_time), window_size):
                window = turns_over_time[i:i+window_size]
                if window:
                    windows.append(window)
            
            print("Time Window | Samples | Mean Turns | P(overhead>1) | Std Dev")
            print("-" * 70)
            
            for i, window in enumerate(windows):
                mean = statistics.mean(window)
                overhead_prob = sum(1 for t in window if t > 1) / len(window)
                std = statistics.stdev(window) if len(window) > 1 else 0
                
                print(f"Window {i+1:4} | {len(window):7} | {mean:10.2f} | {overhead_prob:13.1%} | {std:7.2f}")
            
            # Test for drift
            self._test_temporal_drift(turns_over_time)
            
    def analyze_syntactic_variations(self, tests):
        """Analyze syntactic variations"""
        
        print("EXPERIMENT 7: Syntactic Variations")
        print("Hypothesis: Syntactic structure influences trigger probability\n")
        
        syntaxes = defaultdict(list)
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                syntaxes[test['syntax_type']].append(test['num_turns'])
        
        print("Syntax Type    | Samples | Mean Turns | P(overhead>1) | Pattern")
        print("-" * 70)
        
        for syntax_type in syntaxes:
            turns = syntaxes[syntax_type]
            mean = statistics.mean(turns)
            overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
            pattern = "Triggers" if overhead_prob > 0.1 else "Stable"
            
            print(f"{syntax_type:14} | {len(turns):7} | {mean:10.2f} | {overhead_prob:13.1%} | {pattern}")
            
    def analyze_cognitive_load_gradient(self, tests):
        """Analyze cognitive load gradient"""
        
        print("EXPERIMENT 8: Cognitive Load Gradient")
        print("Hypothesis: There's a sharp threshold for triggering\n")
        
        loads = defaultdict(list)
        for test in tests:
            if test.get('found') and test.get('num_turns') is not None:
                loads[test['load_level']].append(test['num_turns'])
        
        print("Load Level | Samples | Mean Turns | P(overhead>1) | Threshold")
        print("-" * 70)
        
        # Sort by load level
        for level in sorted(loads.keys()):
            turns = loads[level]
            mean = statistics.mean(turns)
            overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
            
            # Identify threshold
            threshold = ""
            if level > 0 and overhead_prob > 0.1:
                prev_prob = sum(1 for t in loads.get(level-1, [0]) if t > 1) / max(1, len(loads.get(level-1, [0])))
                if prev_prob <= 0.1:
                    threshold = "← THRESHOLD"
            
            print(f"Level {level:4} | {len(turns):7} | {mean:10.2f} | {overhead_prob:13.1%} | {threshold}")
        
        # Test for sharp transition
        self._test_phase_transition(loads)
        
    def _get_distribution(self, turns):
        """Get distribution string for turn counts"""
        dist = defaultdict(int)
        for t in turns:
            dist[t] += 1
        
        return ", ".join([f"{k}:{v}" for k, v in sorted(dist.items())])
    
    def _test_position_significance(self, positions):
        """Test if position has significant effect"""
        print("\nStatistical Test:")
        
        # Simple comparison of probabilities
        probs = {}
        for pos, turns in positions.items():
            probs[pos] = sum(1 for t in turns if t > 1) / len(turns)
        
        if len(probs) >= 2:
            max_prob = max(probs.values())
            min_prob = min(probs.values())
            
            if max_prob - min_prob > 0.2:
                print(f"✓ Significant position effect detected (Δ = {max_prob - min_prob:.1%})")
            else:
                print(f"✗ No significant position effect (Δ = {max_prob - min_prob:.1%})")
                
    def _test_semantic_correlation(self, concepts):
        """Test correlation between semantic distance and overhead"""
        print("\nSemantic Distance Correlation:")
        
        distances = []
        overhead_probs = []
        
        for concept, data in concepts.items():
            if data['turns'] and data['distance'] is not None:
                distances.append(data['distance'])
                overhead_probs.append(sum(1 for t in data['turns'] if t > 1) / len(data['turns']))
        
        if len(distances) >= 3:
            # Simple correlation check
            if distances and overhead_probs:
                # Check if overhead decreases with distance
                close_concepts = [p for d, p in zip(distances, overhead_probs) if d <= 2]
                far_concepts = [p for d, p in zip(distances, overhead_probs) if d >= 4]
                
                if close_concepts and far_concepts:
                    close_mean = statistics.mean(close_concepts)
                    far_mean = statistics.mean(far_concepts)
                    
                    if close_mean > far_mean + 0.1:
                        print(f"✓ Semantic distance matters: Close={close_mean:.1%}, Far={far_mean:.1%}")
                    else:
                        print(f"✗ No clear semantic effect: Close={close_mean:.1%}, Far={far_mean:.1%}")
                        
    def _test_interaction_effects(self, combos):
        """Test for interaction effects in combinations"""
        print("\nInteraction Analysis:")
        
        single_effects = {}
        double_effects = {}
        
        for combo_str, turns in combos.items():
            overhead_prob = sum(1 for t in turns if t > 1) / len(turns)
            
            if '+' not in combo_str:
                single_effects[combo_str] = overhead_prob
            elif combo_str.count('+') == 1:
                double_effects[combo_str] = overhead_prob
        
        # Check for super-additivity
        if 'consciousness' in single_effects and 'recursion' in single_effects:
            if 'consciousness+recursion' in double_effects:
                expected = single_effects['consciousness'] + single_effects['recursion']
                actual = double_effects['consciousness+recursion']
                
                if actual > expected * 1.5:
                    print(f"✓ Super-additive interaction: {actual:.1%} > {expected:.1%} (expected)")
                else:
                    print(f"✗ No super-additive effect: {actual:.1%} vs {expected:.1%} (expected)")
                    
    def _test_length_correlation(self, lengths):
        """Test correlation between prompt length and overhead"""
        print("\nLength Correlation:")
        
        char_counts = []
        overhead_probs = []
        
        for length_type, data in lengths.items():
            if data['turns']:
                char_counts.append(data['char_count'])
                overhead_probs.append(sum(1 for t in data['turns'] if t > 1) / len(data['turns']))
        
        if len(char_counts) >= 3:
            # Check for monotonic increase
            sorted_pairs = sorted(zip(char_counts, overhead_probs))
            
            increasing = all(sorted_pairs[i][1] <= sorted_pairs[i+1][1] + 0.1 
                           for i in range(len(sorted_pairs)-1))
            
            if increasing:
                print(f"✓ Length correlates with overhead probability")
            else:
                print(f"✗ No clear length correlation")
                
    def _test_temporal_drift(self, turns_over_time):
        """Test for temporal drift in trigger probability"""
        print("\nTemporal Stability Test:")
        
        if len(turns_over_time) >= 10:
            first_half = turns_over_time[:len(turns_over_time)//2]
            second_half = turns_over_time[len(turns_over_time)//2:]
            
            first_prob = sum(1 for t in first_half if t > 1) / len(first_half)
            second_prob = sum(1 for t in second_half if t > 1) / len(second_half)
            
            drift = abs(first_prob - second_prob)
            
            if drift < 0.1:
                print(f"✓ Temporally stable (drift = {drift:.1%})")
            else:
                print(f"⚠ Temporal drift detected: {first_prob:.1%} → {second_prob:.1%}")
                
    def _test_phase_transition(self, loads):
        """Test for sharp phase transition in cognitive load"""
        print("\nPhase Transition Analysis:")
        
        # Look for sharp jump in probability
        levels = sorted(loads.keys())
        probs = [sum(1 for t in loads[l] if t > 1) / len(loads[l]) for l in levels]
        
        max_jump = 0
        transition_level = None
        
        for i in range(len(probs) - 1):
            jump = probs[i+1] - probs[i]
            if jump > max_jump:
                max_jump = jump
                transition_level = levels[i+1]
        
        if max_jump > 0.3:
            print(f"✓ Sharp phase transition at level {transition_level} (Δ = {max_jump:.1%})")
        else:
            print(f"✗ No sharp transition detected (max Δ = {max_jump:.1%})")
            
    def generate_summary(self):
        """Generate executive summary of findings"""
        
        print("\n" + "="*60)
        print("EXECUTIVE SUMMARY")
        print("="*60)
        
        # Count total tests with metrics
        tests_with_metrics = sum(1 for t in self.tests if t.get('found'))
        overhead_tests = sum(1 for t in self.tests if t.get('num_turns', 0) > 1)
        
        print(f"\nTotal experiments run: {len(self.tests)}")
        print(f"Tests with metrics: {tests_with_metrics}")
        print(f"Tests showing overhead: {overhead_tests}")
        print(f"Overall overhead probability: {overhead_tests/max(1, tests_with_metrics):.1%}")
        
        print("\nKEY FINDINGS:")
        
        # Summarize each experiment's key finding
        findings = []
        
        # You would extract these from the analysis above
        findings.append("• Position effects: [Analysis needed]")
        findings.append("• Semantic distance: [Analysis needed]")
        findings.append("• Combination effects: [Analysis needed]")
        findings.append("• Negation effects: [Analysis needed]")
        findings.append("• Prompt length: [Analysis needed]")
        findings.append("• Temporal stability: [Analysis needed]")
        findings.append("• Syntactic variations: [Analysis needed]")
        findings.append("• Cognitive load gradient: [Analysis needed]")
        
        for finding in findings:
            print(finding)

def main():
    if len(sys.argv) < 2:
        # Find most recent validation file
        validation_dir = Path("var/experiments/cognitive_overhead/rigorous_validation")
        if validation_dir.exists():
            files = sorted(validation_dir.glob("validation_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                results_file = files[0]
                print(f"Using most recent file: {results_file}")
            else:
                print("No validation files found")
                return
        else:
            print(f"Directory {validation_dir} not found")
            return
    else:
        results_file = sys.argv[1]
    
    analyzer = ValidationAnalyzer(results_file)
    analyzer.analyze_all_experiments()
    analyzer.generate_summary()

if __name__ == "__main__":
    main()