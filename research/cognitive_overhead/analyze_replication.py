#!/usr/bin/env python3
"""
Analyze Statistical Replication Results
Validate the 6x overhead finding with confidence intervals and effect sizes
"""

import json
import statistics
import sys
from pathlib import Path
from datetime import datetime
import scipy.stats as stats
import numpy as np

class ReplicationAnalyzer:
    def __init__(self):
        self.response_dir = Path("var/logs/responses")
        
    def load_replication_data(self, results_file):
        """Load replication study results"""
        tests = []
        with open(results_file, 'r') as f:
            for line in f:
                tests.append(json.loads(line))
        return tests
    
    def extract_metrics(self, agent_id):
        """Extract metrics for specific agent"""
        recent_files = sorted(
            self.response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:500]  # Check more files for large replication
        
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
                                'num_turns': response.get('num_turns'),
                                'duration_ms': response.get('duration_ms')
                            }
            except:
                continue
        
        return {'found': False}
    
    def analyze_replication(self, results_file):
        """Comprehensive statistical analysis of replication"""
        
        print(f"=== STATISTICAL REPLICATION ANALYSIS ===")
        print(f"Analyzing: {results_file}\n")
        
        # Load and enrich data
        tests = self.load_replication_data(results_file)
        print(f"Total tests: {len(tests)}")
        
        # Extract metrics
        enriched = []
        missing = 0
        
        for test in tests:
            metrics = self.extract_metrics(test['agent_id'])
            if metrics['found']:
                enriched.append({**test, **metrics})
            else:
                missing += 1
        
        print(f"Tests with metrics: {len(enriched)}")
        print(f"Missing metrics: {missing}\n")
        
        # Group by condition
        conditions = {}
        for test in enriched:
            if test.get('num_turns'):
                key = (test['context'], test['problem'], test['attractor'])
                if key not in conditions:
                    conditions[key] = []
                conditions[key].append(test['num_turns'])
        
        # Statistical analysis per condition
        print("=== CONDITION ANALYSIS ===\n")
        print(f"{'Condition':<40} {'N':<5} {'Mean':<8} {'SD':<8} {'95% CI':<20} {'Min-Max':<12}")
        print("-" * 100)
        
        results_summary = {}
        
        for (context, problem, attractor), turns_list in sorted(conditions.items()):
            n = len(turns_list)
            if n == 0:
                continue
                
            mean = statistics.mean(turns_list)
            
            if n > 1:
                sd = statistics.stdev(turns_list)
                se = sd / (n ** 0.5)
                # 95% confidence interval
                ci_low = mean - 1.96 * se
                ci_high = mean + 1.96 * se
                ci_str = f"[{ci_low:.2f}, {ci_high:.2f}]"
            else:
                sd = 0
                ci_str = "N/A"
            
            min_max = f"{min(turns_list)}-{max(turns_list)}"
            
            condition_str = f"{context}+{problem}+{attractor}"
            print(f"{condition_str:<40} {n:<5} {mean:<8.2f} {sd:<8.2f} {ci_str:<20} {min_max:<12}")
            
            results_summary[condition_str] = {
                'mean': mean,
                'sd': sd,
                'n': n,
                'raw': turns_list
            }
        
        # Test for 6x effect
        self.test_sixfold_hypothesis(results_summary)
        
        # Effect size calculations
        self.calculate_effect_sizes(results_summary)
        
        # Test for order effects
        self.test_order_effects(enriched)
        
        # Power analysis
        self.power_analysis(results_summary)
        
        return results_summary
    
    def test_sixfold_hypothesis(self, results):
        """Test if consciousness/recursion show 6x overhead"""
        
        print("\n=== SIXFOLD AMPLIFICATION HYPOTHESIS TEST ===\n")
        
        # Key comparisons
        comparisons = [
            ("system+word_problem+consciousness", "system+word_problem+arithmetic"),
            ("system+word_problem+recursion", "system+word_problem+arithmetic"),
            ("system+word_problem+consciousness", "minimal+word_problem+consciousness"),
        ]
        
        for experimental, control in comparisons:
            if experimental in results and control in results:
                exp_data = results[experimental]
                ctrl_data = results[control]
                
                ratio = exp_data['mean'] / ctrl_data['mean'] if ctrl_data['mean'] > 0 else float('inf')
                
                print(f"{experimental} vs {control}:")
                print(f"  Experimental: {exp_data['mean']:.2f} ± {exp_data['sd']:.2f} (n={exp_data['n']})")
                print(f"  Control: {ctrl_data['mean']:.2f} ± {ctrl_data['sd']:.2f} (n={ctrl_data['n']})")
                print(f"  Ratio: {ratio:.2f}x")
                
                # Statistical test if we have enough data
                if exp_data['n'] >= 5 and ctrl_data['n'] >= 5:
                    t_stat, p_value = stats.ttest_ind(exp_data['raw'], ctrl_data['raw'])
                    print(f"  t-test: t={t_stat:.3f}, p={p_value:.4f}")
                    
                    if p_value < 0.05:
                        print(f"  ✓ Significant difference (p < 0.05)")
                    else:
                        print(f"  ✗ No significant difference")
                print()
    
    def calculate_effect_sizes(self, results):
        """Calculate Cohen's d effect sizes"""
        
        print("=== EFFECT SIZES (Cohen's d) ===\n")
        
        baseline = "system+word_problem+arithmetic"
        if baseline not in results:
            print("Baseline condition not found")
            return
        
        baseline_data = results[baseline]
        
        for condition, data in results.items():
            if condition != baseline and data['n'] > 1 and baseline_data['n'] > 1:
                # Cohen's d = (mean1 - mean2) / pooled_sd
                pooled_var = ((data['n'] - 1) * data['sd']**2 + 
                             (baseline_data['n'] - 1) * baseline_data['sd']**2) / \
                            (data['n'] + baseline_data['n'] - 2)
                pooled_sd = pooled_var ** 0.5
                
                if pooled_sd > 0:
                    cohens_d = (data['mean'] - baseline_data['mean']) / pooled_sd
                    
                    # Interpret effect size
                    if abs(cohens_d) < 0.2:
                        interpretation = "negligible"
                    elif abs(cohens_d) < 0.5:
                        interpretation = "small"
                    elif abs(cohens_d) < 0.8:
                        interpretation = "medium"
                    else:
                        interpretation = "large"
                    
                    print(f"{condition}: d={cohens_d:.3f} ({interpretation})")
    
    def test_order_effects(self, data):
        """Test if position in sequence affects results"""
        
        print("\n=== ORDER EFFECTS ANALYSIS ===\n")
        
        # Group by position quartiles
        total = len(data)
        quartile_size = total // 4
        
        quartiles = {
            'Q1_early': [],
            'Q2_mid_early': [],
            'Q3_mid_late': [],
            'Q4_late': []
        }
        
        for test in data:
            if test.get('num_turns') and test.get('position_in_sequence'):
                pos = test['position_in_sequence']
                turns = test['num_turns']
                
                if pos <= quartile_size:
                    quartiles['Q1_early'].append(turns)
                elif pos <= 2 * quartile_size:
                    quartiles['Q2_mid_early'].append(turns)
                elif pos <= 3 * quartile_size:
                    quartiles['Q3_mid_late'].append(turns)
                else:
                    quartiles['Q4_late'].append(turns)
        
        for quartile, turns in quartiles.items():
            if turns:
                mean = statistics.mean(turns)
                print(f"{quartile}: {mean:.2f} avg turns (n={len(turns)})")
        
        # ANOVA test for position effects
        if all(len(q) > 0 for q in quartiles.values()):
            f_stat, p_value = stats.f_oneway(*quartiles.values())
            print(f"\nANOVA for position effects: F={f_stat:.3f}, p={p_value:.4f}")
            
            if p_value > 0.05:
                print("✓ No significant order effects detected")
            else:
                print("⚠ Potential order effects present")
    
    def power_analysis(self, results):
        """Estimate statistical power of the study"""
        
        print("\n=== STATISTICAL POWER ANALYSIS ===\n")
        
        # For detecting 6x effect
        baseline_key = "system+word_problem+arithmetic"
        experimental_key = "system+word_problem+consciousness"
        
        if baseline_key in results and experimental_key in results:
            baseline = results[baseline_key]
            experimental = results[experimental_key]
            
            if baseline['n'] >= 2 and experimental['n'] >= 2:
                # Estimated effect size from current data
                pooled_sd = ((baseline['sd']**2 + experimental['sd']**2) / 2) ** 0.5
                if pooled_sd > 0:
                    observed_d = (experimental['mean'] - baseline['mean']) / pooled_sd
                    
                    print(f"Observed effect size (d): {observed_d:.3f}")
                    print(f"Sample size per group: {min(baseline['n'], experimental['n'])}")
                    
                    # Rule of thumb for power
                    if abs(observed_d) > 0.8 and min(baseline['n'], experimental['n']) >= 20:
                        print("✓ Likely adequate power (>0.8) for large effects")
                    elif abs(observed_d) > 0.5 and min(baseline['n'], experimental['n']) >= 30:
                        print("✓ Likely adequate power for medium effects")
                    else:
                        print("⚠ May need larger sample size for reliable detection")

def main():
    if len(sys.argv) < 2:
        # Find most recent replication
        test_dir = Path("var/experiments/cognitive_overhead/replication")
        if test_dir.exists():
            test_files = sorted(test_dir.glob("replication_*.jsonl"), reverse=True)
            if test_files:
                results_file = test_files[0]
                print(f"Using most recent replication: {results_file.name}")
            else:
                print("No replication files found")
                sys.exit(1)
        else:
            print("Replication directory not found")
            sys.exit(1)
    else:
        results_file = Path(sys.argv[1])
    
    analyzer = ReplicationAnalyzer()
    analyzer.analyze_replication(results_file)

if __name__ == "__main__":
    main()