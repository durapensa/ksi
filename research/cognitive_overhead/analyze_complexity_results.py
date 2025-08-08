#!/usr/bin/env python3
"""
Analyze complexity amplification experiment results
Tests for multiplicative vs additive interaction effects
"""

import json
import statistics
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import itertools

class ComplexityAnalyzer:
    def __init__(self):
        self.response_dir = Path("var/logs/responses")
        
    def load_complexity_results(self, results_file):
        """Load complexity matrix results"""
        
        tests = []
        with open(results_file, 'r') as f:
            for line in f:
                tests.append(json.loads(line))
        
        return tests
    
    def extract_metrics(self, agent_id):
        """Extract metrics for specific agent from response logs"""
        
        # Search recent response files 
        recent_files = sorted(
            self.response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:200]  # Check more files for complex experiments
        
        for filepath in recent_files:
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        ksi = data.get('ksi', {})
                        
                        if ksi.get('agent_id') == agent_id:
                            response = data.get('response', {})
                            usage = response.get('usage', {})
                            
                            return {
                                'found': True,
                                'num_turns': response.get('num_turns'),
                                'duration_ms': response.get('duration_ms'),
                                'total_cost_usd': response.get('total_cost_usd'),
                                'input_tokens': usage.get('input_tokens'),
                                'output_tokens': usage.get('output_tokens'),
                                'total_tokens': sum([
                                    usage.get('input_tokens', 0),
                                    usage.get('output_tokens', 0),
                                    usage.get('cache_creation_input_tokens', 0),
                                    usage.get('cache_read_input_tokens', 0)
                                ])
                            }
            except:
                continue
        
        return {'found': False}
    
    def analyze_complexity_matrix(self, results_file):
        """Analyze complete complexity amplification matrix"""
        
        print(f"=== COMPLEXITY AMPLIFICATION ANALYSIS ===")
        print(f"Analyzing: {results_file}\n")
        
        # Load results
        tests = self.load_complexity_results(results_file)
        
        if not tests:
            print("No test results found")
            return
        
        print(f"Total test combinations: {len(tests)}")
        
        # Extract metrics for each test
        enriched_results = []
        missing = 0
        
        for test in tests:
            agent_id = test['agent_id']
            metrics = self.extract_metrics(agent_id)
            
            if metrics['found']:
                result = {**test, **metrics}
                enriched_results.append(result)
                turns = metrics.get('num_turns', '?')
                trial = test.get('trial', 1)
                print(f"✓ {test['context_level']}_{test['problem_level']}_{test['problem_type']}_t{trial}: {turns} turns")
            else:
                missing += 1
                print(f"✗ {agent_id}: metrics not found")
        
        if missing > 0:
            print(f"\nWarning: {missing} tests missing metrics")
        
        # Analyze interaction patterns
        self.analyze_interaction_effects(enriched_results)
        
        # Statistical analysis
        self.complexity_statistical_analysis(enriched_results)
        
        # Save enriched results
        self.save_complexity_analysis(enriched_results, results_file)
    
    def analyze_interaction_effects(self, results):
        """Analyze multiplicative vs additive interaction effects"""
        
        print(f"\n=== INTERACTION EFFECTS ANALYSIS ===\n")
        
        # Group results by dimensions
        grouped = {}
        for r in results:
            if not r.get('num_turns'):
                continue
                
            key = (r['context_level'], r['problem_level'], r['problem_type'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r['num_turns'])
        
        # Calculate averages for each combination
        matrix = {}
        for (context, problem, ptype), turns_list in grouped.items():
            avg_turns = statistics.mean(turns_list)
            if context not in matrix:
                matrix[context] = {}
            if problem not in matrix[context]:
                matrix[context][problem] = {}
            matrix[context][problem][ptype] = avg_turns
        
        # Find baseline (minimal context, simple problem, arithmetic)
        try:
            baseline = matrix['minimal']['simple']['arithmetic']
            print(f"Baseline (minimal/simple/arithmetic): {baseline:.1f} turns\n")
        except KeyError:
            baseline = 1.0
            print("Warning: Baseline not found, using 1.0\n")
        
        # Display interaction matrix
        context_levels = sorted(matrix.keys())
        problem_levels = ['simple', 'multi_step', 'word_problem', 'reasoning']
        problem_types = ['arithmetic', 'emergence', 'consciousness', 'recursion']
        
        print("=== OVERHEAD MATRIX (turns relative to baseline) ===\n")
        
        for context in context_levels:
            print(f"CONTEXT LEVEL: {context.upper()}")
            print(f"{'Problem/Type':<15} {'Arithmetic':<12} {'Emergence':<12} {'Consciousness':<12} {'Recursion':<12} {'Attractor Avg':<12}")
            print("-" * 90)
            
            for problem in problem_levels:
                if context in matrix and problem in matrix[context]:
                    row_data = []
                    attractor_overheads = []
                    
                    for ptype in problem_types:
                        if ptype in matrix[context][problem]:
                            turns = matrix[context][problem][ptype]
                            overhead = turns / baseline
                            row_data.append(f"{overhead:.1f}x")
                            
                            if ptype != 'arithmetic':  # Exclude arithmetic from attractor analysis
                                attractor_overheads.append(overhead)
                        else:
                            row_data.append("N/A")
                    
                    # Calculate average attractor overhead
                    if attractor_overheads:
                        avg_attractor = statistics.mean(attractor_overheads)
                        attractor_avg = f"{avg_attractor:.1f}x"
                    else:
                        attractor_avg = "N/A"
                    
                    print(f"{problem:<15} {row_data[0]:<12} {row_data[1]:<12} {row_data[2]:<12} {row_data[3]:<12} {attractor_avg:<12}")
            
            print()
        
        # Test for interaction patterns
        self.test_interaction_patterns(matrix, baseline)
    
    def test_interaction_patterns(self, matrix, baseline):
        """Test for multiplicative vs additive patterns"""
        
        print("=== INTERACTION PATTERN ANALYSIS ===\n")
        
        # Collect data points for pattern analysis
        data_points = []
        
        for context in matrix:
            for problem in matrix[context]:
                for ptype in matrix[context][problem]:
                    turns = matrix[context][problem][ptype]
                    overhead = turns / baseline
                    
                    # Assign complexity scores
                    context_complexity = {
                        'minimal': 1, 'basic': 2, 'domain': 3, 'system': 4, 'full': 5
                    }.get(context, 1)
                    
                    problem_complexity = {
                        'simple': 1, 'multi_step': 2, 'word_problem': 3, 'reasoning': 4
                    }.get(problem, 1)
                    
                    attractor_factor = 1 if ptype == 'arithmetic' else 2  # Simple binary for now
                    
                    data_points.append({
                        'context_complexity': context_complexity,
                        'problem_complexity': problem_complexity, 
                        'attractor_factor': attractor_factor,
                        'observed_overhead': overhead,
                        'context': context,
                        'problem': problem,
                        'type': ptype
                    })
        
        if len(data_points) < 5:
            print("Insufficient data for pattern analysis")
            return
        
        # Test different interaction models
        self.test_multiplicative_model(data_points)
        self.test_additive_model(data_points)
        self.analyze_attractor_amplification(data_points)
    
    def test_multiplicative_model(self, data_points):
        """Test if overhead follows multiplicative pattern: Context × Problem × Attractor"""
        
        print("MULTIPLICATIVE MODEL TEST:")
        print(f"{'Observed':<12} {'Predicted':<12} {'Ratio':<12} {'Context':<10} {'Problem':<12} {'Type':<12}")
        print("-" * 80)
        
        predictions = []
        for point in data_points:
            # Simple multiplicative model
            predicted = point['context_complexity'] * point['problem_complexity'] * point['attractor_factor'] / 4  # Normalize
            actual = point['observed_overhead']
            ratio = actual / predicted if predicted > 0 else float('inf')
            
            predictions.append((actual, predicted, ratio))
            
            print(f"{actual:<12.1f} {predicted:<12.1f} {ratio:<12.1f} {point['context']:<10} {point['problem']:<12} {point['type']:<12}")
        
        # Calculate model fit
        ratios = [r for _, _, r in predictions if r != float('inf')]
        if ratios:
            avg_ratio = statistics.mean(ratios)
            std_ratio = statistics.stdev(ratios) if len(ratios) > 1 else 0
            print(f"\nModel fit - Mean ratio: {avg_ratio:.2f}, Std dev: {std_ratio:.2f}")
            print(f"Good fit if mean ≈ 1.0 and std dev is low\n")
    
    def test_additive_model(self, data_points):
        """Test if overhead follows additive pattern: Context + Problem + Attractor"""
        
        print("ADDITIVE MODEL TEST:")
        print(f"{'Observed':<12} {'Predicted':<12} {'Difference':<12} {'Context':<10} {'Problem':<12} {'Type':<12}")
        print("-" * 80)
        
        predictions = []
        for point in data_points:
            # Simple additive model
            predicted = (point['context_complexity'] + point['problem_complexity'] + point['attractor_factor']) / 3
            actual = point['observed_overhead'] 
            diff = abs(actual - predicted)
            
            predictions.append((actual, predicted, diff))
            
            print(f"{actual:<12.1f} {predicted:<12.1f} {diff:<12.1f} {point['context']:<10} {point['problem']:<12} {point['type']:<12}")
        
        # Calculate model fit
        differences = [d for _, _, d in predictions]
        if differences:
            avg_diff = statistics.mean(differences)
            std_diff = statistics.stdev(differences) if len(differences) > 1 else 0
            print(f"\nModel fit - Mean difference: {avg_diff:.2f}, Std dev: {std_diff:.2f}")
            print(f"Good fit if mean difference is low\n")
    
    def analyze_attractor_amplification(self, data_points):
        """Analyze how attractors amplify complexity"""
        
        print("ATTRACTOR AMPLIFICATION ANALYSIS:")
        
        # Compare arithmetic vs attractor types for same context/problem combinations
        attractor_effects = []
        
        # Group by context and problem
        groups = {}
        for point in data_points:
            key = (point['context'], point['problem'])
            if key not in groups:
                groups[key] = {}
            groups[key][point['type']] = point['observed_overhead']
        
        print(f"{'Context':<10} {'Problem':<12} {'Arithmetic':<12} {'Emergence':<12} {'Conscious':<12} {'Recursion':<12} {'Amplification':<12}")
        print("-" * 95)
        
        for (context, problem), types in groups.items():
            if 'arithmetic' in types:
                baseline_overhead = types['arithmetic']
                attractor_overheads = [types[t] for t in ['emergence', 'consciousness', 'recursion'] if t in types]
                
                if attractor_overheads:
                    avg_attractor = statistics.mean(attractor_overheads)
                    amplification = avg_attractor / baseline_overhead if baseline_overhead > 0 else float('inf')
                    attractor_effects.append(amplification)
                    
                    # Display row
                    emergence = f"{types.get('emergence', 0):.1f}" if 'emergence' in types else "N/A"
                    consciousness = f"{types.get('consciousness', 0):.1f}" if 'consciousness' in types else "N/A" 
                    recursion = f"{types.get('recursion', 0):.1f}" if 'recursion' in types else "N/A"
                    
                    print(f"{context:<10} {problem:<12} {baseline_overhead:<12.1f} {emergence:<12} {consciousness:<12} {recursion:<12} {amplification:<12.1f}")
        
        if attractor_effects:
            print(f"\nOverall attractor amplification:")
            print(f"  Mean: {statistics.mean(attractor_effects):.2f}x")
            print(f"  Range: {min(attractor_effects):.2f}x - {max(attractor_effects):.2f}x")
            if len(attractor_effects) > 1:
                print(f"  Std dev: {statistics.stdev(attractor_effects):.2f}")
    
    def complexity_statistical_analysis(self, results):
        """Statistical analysis of complexity results"""
        
        print(f"\n=== STATISTICAL SUMMARY ===\n")
        
        all_turns = [r['num_turns'] for r in results if r.get('num_turns')]
        
        if not all_turns:
            print("No turn data available")
            return
        
        print(f"Total samples: {len(all_turns)}")
        print(f"Turn count range: {min(all_turns)} - {max(all_turns)}")
        print(f"Mean turns: {statistics.mean(all_turns):.2f}")
        print(f"Median turns: {statistics.median(all_turns):.1f}")
        
        if len(all_turns) > 1:
            print(f"Standard deviation: {statistics.stdev(all_turns):.2f}")
        
        # Group by major categories
        by_context = {}
        by_problem = {}
        by_type = {}
        
        for r in results:
            if not r.get('num_turns'):
                continue
            
            turns = r['num_turns']
            
            # By context
            context = r['context_level']
            if context not in by_context:
                by_context[context] = []
            by_context[context].append(turns)
            
            # By problem complexity
            problem = r['problem_level']
            if problem not in by_problem:
                by_problem[problem] = []
            by_problem[problem].append(turns)
            
            # By attractor type
            ptype = r['problem_type']
            if ptype not in by_type:
                by_type[ptype] = []
            by_type[ptype].append(turns)
        
        # Display category summaries
        self._display_category_summary("Context Complexity", by_context)
        self._display_category_summary("Problem Complexity", by_problem)  
        self._display_category_summary("Attractor Type", by_type)
    
    def _display_category_summary(self, category_name, groups):
        """Display summary statistics for a category"""
        
        print(f"\n{category_name} Effects:")
        for name in sorted(groups.keys()):
            turns = groups[name]
            mean_turns = statistics.mean(turns)
            print(f"  {name}: {mean_turns:.1f} avg turns (n={len(turns)})")
    
    def save_complexity_analysis(self, results, original_file):
        """Save complexity analysis results"""
        
        analysis_file = Path(original_file).parent / f"{Path(original_file).stem}_complexity_analysis.json"
        
        analysis = {
            'original_file': str(original_file),
            'analysis_timestamp': datetime.now().isoformat(),
            'total_tests': len(results),
            'tests_with_metrics': len([r for r in results if r.get('found')]),
            'results': results
        }
        
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\nComplexity analysis saved to: {analysis_file}")


def main():
    if len(sys.argv) < 2:
        # Find most recent complexity test
        test_dir = Path("var/experiments/cognitive_overhead/complexity_tests")
        if test_dir.exists():
            test_files = sorted(test_dir.glob("complexity_matrix_*.jsonl"), reverse=True)
            if test_files:
                results_file = test_files[0]
                print(f"Using most recent complexity test: {results_file.name}")
            else:
                print("No complexity test files found")
                sys.exit(1)
        else:
            print("Complexity test directory not found")
            sys.exit(1)
    else:
        results_file = sys.argv[1]
    
    analyzer = ComplexityAnalyzer()
    analyzer.analyze_complexity_matrix(results_file)


if __name__ == "__main__":
    main()