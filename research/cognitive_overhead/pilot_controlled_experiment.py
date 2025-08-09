#!/usr/bin/env python3
"""
Controlled Pilot Experiment for Cognitive Overhead Validation
Tests 3x overhead finding with proper controls for confounding variables
"""

import json
import time
import random
import numpy as np
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from scipy import stats
from sklearn.utils import resample

@dataclass
class ExperimentResult:
    """Single experiment measurement"""
    experiment_id: str
    timestamp: str
    condition: str
    prompt: str
    word_count: int
    token_count: int
    model: str
    latency_ms: float
    response: str
    session_state: str
    trial_number: int
    
class ControlledPilotExperiment:
    def __init__(self):
        self.results_dir = Path("var/experiments/cognitive_overhead/controlled_pilot")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = []
        
        # Experimental conditions with proper controls
        self.conditions = {
            # BASELINE - Simple arithmetic
            'baseline': {
                'prompt': "Calculate: 45 + 23 - 11",
                'word_count': 5,
                'category': 'baseline'
            },
            
            # LENGTH CONTROL - Same length as consciousness, neutral content
            'length_control': {
                'prompt': "Calculate carefully and precisely: 45 + 23 - 11",
                'word_count': 8,
                'category': 'control'
            },
            
            # COMPLEXITY CONTROL - Complex instructions, no consciousness
            'complexity_control': {
                'prompt': "Following standard mathematical order of operations, calculate: 45 + 23 - 11",
                'word_count': 10,
                'category': 'control'  
            },
            
            # CONSCIOUSNESS - Target condition
            'consciousness': {
                'prompt': "While contemplating consciousness, calculate: 45 + 23 - 11",
                'word_count': 8,
                'category': 'consciousness'
            },
            
            # MULTI-TASK NEUTRAL - Multiple tasks without consciousness
            'multi_neutral': {
                'prompt': "Complete these tasks: (1) Calculate 45 + 23, (2) Calculate 23 - 11",
                'word_count': 13,
                'category': 'multi_task'
            },
            
            # MULTI-TASK CONSCIOUSNESS - Multiple tasks with consciousness
            'multi_consciousness': {
                'prompt': "Complete these tasks: (1) Calculate 45 + 23, (2) Reflect on consciousness, (3) Calculate 23 - 11",
                'word_count': 17,
                'category': 'multi_consciousness'
            },
            
            # DOMAIN SWAP - Replace consciousness with temperature
            'domain_temperature': {
                'prompt': "While contemplating temperature dynamics, calculate: 45 + 23 - 11",
                'word_count': 9,
                'category': 'domain_swap'
            },
            
            # DOMAIN SWAP - Replace consciousness with market
            'domain_market': {
                'prompt': "While contemplating market fluctuations, calculate: 45 + 23 - 11",
                'word_count': 9,
                'category': 'domain_swap'
            }
        }
        
    def run_single_test(self, condition_name: str, model: str, trial_number: int, 
                       session_state: str = "fresh") -> ExperimentResult:
        """Run a single test with timing"""
        
        condition = self.conditions[condition_name]
        prompt = condition['prompt']
        
        # Create unique agent ID for fresh sessions
        agent_id = f"pilot_{condition_name}_{trial_number}_{self.session_id}"
        
        print(f"  Trial {trial_number}: {condition_name} ({session_state} session)...", end="")
        
        # Measure latency
        start_time = time.perf_counter()
        
        # Run through KSI
        cmd = [
            "ksi", "send", "completion:async",
            "--agent-id", agent_id,
            "--prompt", prompt
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            
            # Parse response
            response_data = json.loads(result.stdout) if result.stdout else {}
            response_text = str(response_data.get('result', {}).get('response', 'No response'))
            
            print(f" {latency_ms:.0f}ms")
            
            # Approximate token count (rough estimate)
            token_count = len(prompt.split()) * 1.3
            
            return ExperimentResult(
                experiment_id=f"{self.session_id}_{trial_number}",
                timestamp=datetime.now().isoformat(),
                condition=condition_name,
                prompt=prompt,
                word_count=condition['word_count'],
                token_count=int(token_count),
                model=model,
                latency_ms=latency_ms,
                response=response_text[:100],  # Truncate response
                session_state=session_state,
                trial_number=trial_number
            )
            
        except subprocess.TimeoutExpired:
            print(" TIMEOUT")
            return None
        except Exception as e:
            print(f" ERROR: {e}")
            return None
    
    def run_pilot_experiment(self, n_samples: int = 10):
        """Run the pilot experiment with N samples per condition"""
        
        print(f"\n=== CONTROLLED PILOT EXPERIMENT ===")
        print(f"Session: {self.session_id}")
        print(f"Samples per condition: {n_samples}")
        print(f"Total conditions: {len(self.conditions)}")
        print(f"Expected measurements: {len(self.conditions) * n_samples}\n")
        
        models = ["claude-cli/claude-sonnet-4-20250514"]  # Start with one model
        
        for model in models:
            print(f"\nTesting model: {model}")
            
            for condition_name in self.conditions:
                print(f"\nCondition: {condition_name}")
                
                for trial in range(1, n_samples + 1):
                    # Always use fresh sessions for controlled experiment
                    result = self.run_single_test(
                        condition_name, 
                        model, 
                        trial,
                        session_state="fresh"
                    )
                    
                    if result:
                        self.results.append(result)
                    
                    # Small delay between tests
                    time.sleep(1)
        
        print(f"\nCollected {len(self.results)} successful measurements")
        return self.results
    
    def analyze_results(self):
        """Statistical analysis of results"""
        
        print("\n=== STATISTICAL ANALYSIS ===\n")
        
        if not self.results:
            print("No results to analyze")
            return
        
        # Group results by condition
        conditions_data = {}
        for result in self.results:
            if result.condition not in conditions_data:
                conditions_data[result.condition] = []
            conditions_data[result.condition].append(result.latency_ms)
        
        # Calculate statistics for each condition
        print("DESCRIPTIVE STATISTICS:")
        print("-" * 60)
        print(f"{'Condition':<25} {'N':<5} {'Mean (ms)':<12} {'Std':<10} {'Overhead':<10}")
        print("-" * 60)
        
        baseline_mean = np.mean(conditions_data.get('baseline', [0]))
        
        stats_summary = {}
        for condition, latencies in conditions_data.items():
            if latencies:
                mean_latency = np.mean(latencies)
                std_latency = np.std(latencies)
                overhead = mean_latency / baseline_mean if baseline_mean > 0 else 1.0
                
                stats_summary[condition] = {
                    'mean': mean_latency,
                    'std': std_latency,
                    'overhead': overhead,
                    'n': len(latencies),
                    'data': latencies
                }
                
                print(f"{condition:<25} {len(latencies):<5} {mean_latency:<12.1f} {std_latency:<10.1f} {overhead:<10.2f}x")
        
        print("\n" + "=" * 60)
        
        # Statistical significance tests
        print("\nSTATISTICAL SIGNIFICANCE TESTS:")
        print("-" * 60)
        
        if 'baseline' in conditions_data and len(conditions_data['baseline']) > 1:
            baseline_data = conditions_data['baseline']
            
            for condition in ['consciousness', 'multi_consciousness', 'length_control', 'complexity_control']:
                if condition in conditions_data and len(conditions_data[condition]) > 1:
                    # Welch's t-test (unequal variances)
                    t_stat, p_value = stats.ttest_ind(
                        baseline_data,
                        conditions_data[condition],
                        equal_var=False
                    )
                    
                    # Cohen's d effect size
                    mean_diff = np.mean(conditions_data[condition]) - np.mean(baseline_data)
                    pooled_std = np.sqrt((np.var(conditions_data[condition]) + np.var(baseline_data)) / 2)
                    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
                    
                    print(f"\n{condition} vs baseline:")
                    print(f"  t-statistic: {t_stat:.3f}")
                    print(f"  p-value: {p_value:.4f} {'***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else ''}")
                    print(f"  Cohen's d: {cohens_d:.3f} ({'large' if abs(cohens_d) > 0.8 else 'medium' if abs(cohens_d) > 0.5 else 'small'})")
        
        # Bootstrap confidence intervals
        print("\nBOOTSTRAP CONFIDENCE INTERVALS (95%):")
        print("-" * 60)
        
        n_bootstrap = 1000
        for condition in ['baseline', 'consciousness', 'multi_consciousness']:
            if condition in conditions_data and len(conditions_data[condition]) > 2:
                data = conditions_data[condition]
                bootstrap_means = []
                
                for _ in range(n_bootstrap):
                    sample = resample(data, n_samples=len(data))
                    bootstrap_means.append(np.mean(sample))
                
                ci_lower = np.percentile(bootstrap_means, 2.5)
                ci_upper = np.percentile(bootstrap_means, 97.5)
                
                print(f"{condition}: [{ci_lower:.1f}, {ci_upper:.1f}] ms")
        
        return stats_summary
    
    def test_confounds(self):
        """Test for specific confounding variables"""
        
        print("\n=== CONFOUND ANALYSIS ===\n")
        
        if not self.results:
            print("No results to analyze")
            return
        
        # Test 1: Word count correlation
        word_counts = [r.word_count for r in self.results]
        latencies = [r.latency_ms for r in self.results]
        
        if len(set(word_counts)) > 1:  # Only if we have variation
            correlation, p_value = stats.pearsonr(word_counts, latencies)
            print(f"Word count correlation with latency: r={correlation:.3f}, p={p_value:.4f}")
            
            if abs(correlation) > 0.5 and p_value < 0.05:
                print("  ⚠️ WARNING: Strong correlation with word count suggests length confound")
        
        # Test 2: Compare consciousness vs domain swaps
        consciousness_latencies = [r.latency_ms for r in self.results if r.condition == 'consciousness']
        temperature_latencies = [r.latency_ms for r in self.results if r.condition == 'domain_temperature']
        market_latencies = [r.latency_ms for r in self.results if r.condition == 'domain_market']
        
        domain_swap_latencies = temperature_latencies + market_latencies
        
        if consciousness_latencies and domain_swap_latencies:
            t_stat, p_value = stats.ttest_ind(consciousness_latencies, domain_swap_latencies, equal_var=False)
            print(f"\nConsciousness vs Domain Swaps:")
            print(f"  Consciousness mean: {np.mean(consciousness_latencies):.1f}ms")
            print(f"  Domain swaps mean: {np.mean(domain_swap_latencies):.1f}ms")
            print(f"  p-value: {p_value:.4f}")
            
            if p_value > 0.05:
                print("  ✓ No significant difference - suggests general complexity effect, not consciousness-specific")
            else:
                print("  ⚠️ Significant difference - consciousness may have specific effect")
        
        # Test 3: Multi-task effect decomposition
        multi_neutral = [r.latency_ms for r in self.results if r.condition == 'multi_neutral']
        multi_consciousness = [r.latency_ms for r in self.results if r.condition == 'multi_consciousness']
        
        if multi_neutral and multi_consciousness:
            t_stat, p_value = stats.ttest_ind(multi_neutral, multi_consciousness, equal_var=False)
            print(f"\nMulti-task decomposition:")
            print(f"  Multi-neutral mean: {np.mean(multi_neutral):.1f}ms")
            print(f"  Multi-consciousness mean: {np.mean(multi_consciousness):.1f}ms")
            print(f"  p-value: {p_value:.4f}")
            
            if p_value > 0.05:
                print("  ✓ Multi-task structure drives overhead, not consciousness content")
            else:
                print("  ⚠️ Consciousness adds overhead even in multi-task context")
    
    def save_results(self):
        """Save results to file"""
        
        output_file = self.results_dir / f"pilot_{self.session_id}.json"
        
        data = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'n_samples_per_condition': 10,
            'conditions': self.conditions,
            'results': [asdict(r) for r in self.results],
            'summary': {
                'total_measurements': len(self.results),
                'conditions_tested': list(set(r.condition for r in self.results))
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        return output_file

def main():
    """Run the controlled pilot experiment"""
    
    experiment = ControlledPilotExperiment()
    
    # Run pilot with N=10 per condition
    experiment.run_pilot_experiment(n_samples=10)
    
    # Analyze results
    stats_summary = experiment.analyze_results()
    
    # Test for confounds
    experiment.test_confounds()
    
    # Save results
    output_file = experiment.save_results()
    
    # Final verdict
    print("\n" + "=" * 60)
    print("PILOT EXPERIMENT VERDICT:")
    print("=" * 60)
    
    if stats_summary:
        consciousness_overhead = stats_summary.get('consciousness', {}).get('overhead', 1.0)
        multi_overhead = stats_summary.get('multi_consciousness', {}).get('overhead', 1.0)
        length_overhead = stats_summary.get('length_control', {}).get('overhead', 1.0)
        
        if consciousness_overhead > 2.0 and length_overhead < 1.5:
            print("✅ EFFECT CONFIRMED: Consciousness content causes overhead beyond length effects")
        elif multi_overhead > 2.5:
            print("⚠️ PARTIAL CONFIRMATION: Multi-task with consciousness shows overhead")
        else:
            print("❌ EFFECT NOT CONFIRMED: No significant overhead detected in pilot")
        
        print(f"\nKey findings:")
        print(f"  Consciousness overhead: {consciousness_overhead:.2f}x")
        print(f"  Multi-consciousness overhead: {multi_overhead:.2f}x")
        print(f"  Length control overhead: {length_overhead:.2f}x")

if __name__ == "__main__":
    main()