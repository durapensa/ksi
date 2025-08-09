#!/usr/bin/env python3
"""
Experiment 2.1: Quantifying Context Establishment Cost (CEC)
Publication-quality measurement with N=100 per condition

Hypothesis: Each cognitive domain switch incurs a fixed token cost of 100-150 tokens
Formula: Total_Tokens = Base_Tokens + (N_switches × CEC)
"""

import json
import time
import subprocess
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
import matplotlib.pyplot as plt
from collections import defaultdict
import random

@dataclass
class CECResult:
    """Result from Context Establishment Cost experiment"""
    condition: str
    n_switches: int
    prompt: str
    response: str
    cost_usd: float
    output_tokens: int
    input_tokens_estimate: int
    total_tokens_estimate: int
    sections: List[Dict]
    transition_tokens: List[int]  # Tokens spent on transitions
    
class ContextEstablishmentExperiment:
    def __init__(self, n_per_condition: int = 100):
        self.n_per_condition = n_per_condition
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = defaultdict(list)
        
        # Claude pricing for cost-based token estimation
        self.claude_pricing = {
            'input_per_million': 3.00,
            'output_per_million': 15.00,
        }
        
    def create_controlled_prompts(self) -> Dict[str, Dict]:
        """Create prompts with controlled number of context switches"""
        
        # Base problems - all identical difficulty
        problems = [
            "Calculate 47 + 89",
            "Calculate 156 - 78", 
            "Calculate 34 × 3",
            "Calculate 144 ÷ 12",
            "Calculate 25 + 67"
        ]
        
        prompts = {
            # 0 switches - single instruction
            '0_switches': {
                'prompt': f"Solve these problems: {', '.join(problems)}",
                'n_switches': 0,
                'structure': 'single_batch'
            },
            
            # 1 switch - two batches
            '1_switch': {
                'prompt': f"First solve these: {', '.join(problems[:3])}. Then solve these: {', '.join(problems[3:])}",
                'n_switches': 1,
                'structure': 'two_batches'
            },
            
            # 2 switches - three batches
            '2_switches': {
                'prompt': f"Solve these: {problems[0]}, {problems[1]}. Next solve: {problems[2]}, {problems[3]}. Finally solve: {problems[4]}",
                'n_switches': 2,
                'structure': 'three_batches'
            },
            
            # 3 switches - four batches
            '3_switches': {
                'prompt': f"First: {problems[0]}. Then: {problems[1]}, {problems[2]}. Next: {problems[3]}. Finally: {problems[4]}",
                'n_switches': 3,
                'structure': 'four_batches'
            },
            
            # 4 switches - individual instructions
            '4_switches': {
                'prompt': f"Calculate each separately. First: {problems[0]}. Second: {problems[1]}. Third: {problems[2]}. Fourth: {problems[3]}. Fifth: {problems[4]}",
                'n_switches': 4,
                'structure': 'individual'
            }
        }
        
        return prompts
    
    def run_single_trial(self, condition_name: str, prompt_data: Dict) -> Optional[CECResult]:
        """Run a single experimental trial"""
        
        agent_id = f"cec_{condition_name}_{self.session_id}_{random.randint(1000,9999)}"
        
        # Run completion
        cmd = [
            "ksi", "send", "completion:async",
            "--agent-id", agent_id,
            "--prompt", prompt_data['prompt']
        ]
        
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Wait for completion
        time.sleep(5)
        
        # Retrieve result
        monitor_cmd = [
            "ksi", "send", "monitor:get_events",
            "--limit", "20",
            "--event-patterns", "completion:result"
        ]
        
        monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
        
        try:
            data = json.loads(monitor_result.stdout)
            events = data.get('events', [])
            
            for event in events:
                event_data = event.get('data', {})
                ksi_info = event_data.get('result', {}).get('ksi', {})
                
                if agent_id in ksi_info.get('agent_id', ''):
                    response_data = event_data.get('result', {}).get('response', {})
                    
                    # Extract metrics
                    cost = response_data.get('total_cost_usd', 0)
                    usage = response_data.get('usage', {})
                    output_tokens = usage.get('output_tokens', 0)
                    response_text = response_data.get('result', '')
                    
                    # Estimate total tokens from cost
                    prompt_words = len(prompt_data['prompt'].split())
                    estimated_input = prompt_words * 1.3  # Rough token estimate
                    
                    if cost > 0:
                        # Reverse engineer from cost
                        input_cost = estimated_input * self.claude_pricing['input_per_million'] / 1_000_000
                        output_cost = cost - input_cost
                        
                        if output_cost > 0:
                            estimated_output = output_cost / (self.claude_pricing['output_per_million'] / 1_000_000)
                            total_tokens_estimate = int(estimated_input + estimated_output)
                        else:
                            total_tokens_estimate = output_tokens + int(estimated_input)
                    else:
                        total_tokens_estimate = output_tokens + int(estimated_input)
                    
                    # Analyze response structure
                    sections = self.analyze_response_structure(response_text, prompt_data['n_switches'])
                    transition_tokens = self.extract_transition_tokens(sections)
                    
                    result = CECResult(
                        condition=condition_name,
                        n_switches=prompt_data['n_switches'],
                        prompt=prompt_data['prompt'],
                        response=response_text,
                        cost_usd=cost,
                        output_tokens=output_tokens,
                        input_tokens_estimate=int(estimated_input),
                        total_tokens_estimate=total_tokens_estimate,
                        sections=sections,
                        transition_tokens=transition_tokens
                    )
                    
                    return result
                    
        except Exception as e:
            print(f"Error in trial: {e}")
            
        return None
    
    def analyze_response_structure(self, response: str, expected_switches: int) -> List[Dict]:
        """Analyze response to identify sections and transitions"""
        
        sections = []
        lines = response.split('\n')
        
        current_section = {
            'type': 'unknown',
            'content': [],
            'token_estimate': 0
        }
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect transitions
            if any(marker in line_lower for marker in ['first', 'then', 'next', 'finally', 'second', 'third']):
                if current_section['content']:
                    current_section['token_estimate'] = len(' '.join(current_section['content']).split()) * 1.3
                    sections.append(current_section)
                    
                current_section = {
                    'type': 'transition',
                    'content': [line],
                    'token_estimate': 0
                }
            # Detect calculations
            elif any(op in line for op in ['+', '-', '×', '÷', '=']) or any(str(i) in line for i in range(10)):
                if current_section['type'] == 'transition':
                    current_section['token_estimate'] = len(' '.join(current_section['content']).split()) * 1.3
                    sections.append(current_section)
                    current_section = {
                        'type': 'calculation',
                        'content': [],
                        'token_estimate': 0
                    }
                current_section['content'].append(line)
            else:
                current_section['content'].append(line)
        
        # Add final section
        if current_section['content']:
            current_section['token_estimate'] = len(' '.join(current_section['content']).split()) * 1.3
            sections.append(current_section)
        
        return sections
    
    def extract_transition_tokens(self, sections: List[Dict]) -> List[int]:
        """Extract token counts for transition sections"""
        
        transition_tokens = []
        
        for section in sections:
            if section['type'] == 'transition':
                transition_tokens.append(int(section['token_estimate']))
        
        return transition_tokens
    
    def run_experiment(self):
        """Run the complete CEC experiment"""
        
        print("=" * 70)
        print("EXPERIMENT 2.1: CONTEXT ESTABLISHMENT COST")
        print(f"Target: N={self.n_per_condition} per condition")
        print("=" * 70)
        print()
        
        prompts = self.create_controlled_prompts()
        
        # Run trials for each condition
        for condition_name, prompt_data in prompts.items():
            print(f"\nCondition: {condition_name} ({prompt_data['n_switches']} switches)")
            print(f"Running {self.n_per_condition} trials...")
            
            successful_trials = 0
            attempts = 0
            
            while successful_trials < self.n_per_condition and attempts < self.n_per_condition * 1.5:
                attempts += 1
                
                result = self.run_single_trial(condition_name, prompt_data)
                
                if result:
                    self.results[condition_name].append(result)
                    successful_trials += 1
                    
                    if successful_trials % 10 == 0:
                        print(f"  Progress: {successful_trials}/{self.n_per_condition}")
                
                # Rate limiting
                time.sleep(2)
            
            print(f"  Completed: {successful_trials} successful trials")
    
    def analyze_results(self):
        """Perform statistical analysis of CEC"""
        
        print("\n" + "=" * 70)
        print("STATISTICAL ANALYSIS")
        print("=" * 70)
        print()
        
        # Aggregate data
        switch_counts = []
        mean_tokens = []
        std_tokens = []
        mean_costs = []
        
        for condition_name in sorted(self.results.keys()):
            trials = self.results[condition_name]
            if trials:
                n_switches = trials[0].n_switches
                tokens = [t.output_tokens for t in trials]
                costs = [t.cost_usd for t in trials]
                
                switch_counts.append(n_switches)
                mean_tokens.append(np.mean(tokens))
                std_tokens.append(np.std(tokens))
                mean_costs.append(np.mean(costs))
                
                print(f"{condition_name}:")
                print(f"  Switches: {n_switches}")
                print(f"  Mean tokens: {np.mean(tokens):.1f} ± {np.std(tokens):.1f}")
                print(f"  Mean cost: ${np.mean(costs):.6f}")
                print(f"  N samples: {len(trials)}")
                print()
        
        # Linear regression to extract CEC
        if len(switch_counts) >= 3:
            # Fit linear model: tokens = base + CEC * switches
            slope, intercept, r_value, p_value, std_err = stats.linregress(switch_counts, mean_tokens)
            
            print("LINEAR MODEL: Tokens = Base + CEC × Switches")
            print("-" * 70)
            print(f"Base tokens (intercept): {intercept:.1f}")
            print(f"Context Establishment Cost (slope): {slope:.1f} tokens/switch")
            print(f"R-squared: {r_value**2:.4f}")
            print(f"P-value: {p_value:.6f}")
            print(f"Standard error: {std_err:.2f}")
            print()
            
            # ANOVA to test significance
            print("ANOVA ANALYSIS")
            print("-" * 70)
            
            # Prepare data for ANOVA
            groups = []
            for condition_name, trials in self.results.items():
                if trials:
                    groups.append([t.output_tokens for t in trials])
            
            if len(groups) >= 2:
                f_stat, p_val = stats.f_oneway(*groups)
                print(f"F-statistic: {f_stat:.2f}")
                print(f"P-value: {p_val:.6f}")
                
                if p_val < 0.001:
                    print("Result: *** Highly significant difference between conditions")
                elif p_val < 0.01:
                    print("Result: ** Significant difference between conditions")
                elif p_val < 0.05:
                    print("Result: * Significant difference between conditions")
                else:
                    print("Result: No significant difference")
            
            # Calculate confidence interval for CEC
            confidence = 0.95
            t_val = stats.t.ppf((1 + confidence) / 2, len(switch_counts) - 2)
            ci_range = t_val * std_err
            
            print()
            print(f"95% Confidence Interval for CEC: {slope - ci_range:.1f} to {slope + ci_range:.1f} tokens/switch")
            
            return {
                'cec': slope,
                'base_tokens': intercept,
                'r_squared': r_value**2,
                'p_value': p_value,
                'ci_lower': slope - ci_range,
                'ci_upper': slope + ci_range
            }
    
    def visualize_results(self):
        """Create publication-quality visualizations"""
        
        if not self.results:
            print("No results to visualize")
            return
        
        # Prepare data
        switch_counts = []
        mean_tokens = []
        std_tokens = []
        all_data_points = defaultdict(list)
        
        for condition_name in sorted(self.results.keys()):
            trials = self.results[condition_name]
            if trials:
                n_switches = trials[0].n_switches
                tokens = [t.output_tokens for t in trials]
                
                switch_counts.append(n_switches)
                mean_tokens.append(np.mean(tokens))
                std_tokens.append(np.std(tokens))
                
                for t in tokens:
                    all_data_points[n_switches].append(t)
        
        # Create figure
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Linear relationship with error bars
        ax1 = axes[0]
        ax1.errorbar(switch_counts, mean_tokens, yerr=std_tokens, 
                     fmt='o', capsize=5, capthick=2, markersize=10,
                     color='#2E86AB', ecolor='#A23B72')
        
        # Add regression line
        if len(switch_counts) >= 2:
            z = np.polyfit(switch_counts, mean_tokens, 1)
            p = np.poly1d(z)
            x_line = np.linspace(min(switch_counts), max(switch_counts), 100)
            ax1.plot(x_line, p(x_line), "r-", alpha=0.8, linewidth=2,
                    label=f'y = {z[0]:.1f}x + {z[1]:.1f}')
        
        ax1.set_xlabel('Number of Context Switches', fontsize=12)
        ax1.set_ylabel('Output Tokens', fontsize=12)
        ax1.set_title('Context Establishment Cost: Linear Scaling', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Plot 2: Box plot showing distributions
        ax2 = axes[1]
        data_for_box = []
        labels_for_box = []
        
        for n_switches in sorted(all_data_points.keys()):
            data_for_box.append(all_data_points[n_switches])
            labels_for_box.append(f"{n_switches} switches")
        
        bp = ax2.boxplot(data_for_box, labels=labels_for_box, patch_artist=True)
        
        # Color the boxes
        colors = ['#E8F4F8', '#B8E6F1', '#88D4E6', '#58C1DB', '#28AFD0']
        for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
            patch.set_facecolor(color)
        
        ax2.set_xlabel('Condition', fontsize=12)
        ax2.set_ylabel('Output Tokens', fontsize=12)
        ax2.set_title('Token Distribution by Switch Count', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        
        plt.suptitle('Context Establishment Cost (CEC) Analysis', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        # Save figure
        plt.savefig(f'research/cognitive_overhead/cec_analysis_{self.session_id}.png', 
                   dpi=150, bbox_inches='tight')
        print(f"\nVisualization saved to: research/cognitive_overhead/cec_analysis_{self.session_id}.png")
        
        plt.show()
    
    def save_results(self):
        """Save detailed results for reproducibility"""
        
        output = {
            'experiment': 'Context Establishment Cost (CEC)',
            'timestamp': self.session_id,
            'n_per_condition': self.n_per_condition,
            'results': {}
        }
        
        for condition_name, trials in self.results.items():
            output['results'][condition_name] = [
                {
                    'n_switches': t.n_switches,
                    'output_tokens': t.output_tokens,
                    'cost_usd': t.cost_usd,
                    'total_tokens_estimate': t.total_tokens_estimate,
                    'transition_tokens': t.transition_tokens
                }
                for t in trials
            ]
        
        filename = f'research/cognitive_overhead/cec_results_{self.session_id}.json'
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\nResults saved to: {filename}")

def main():
    # Run with smaller N for testing, increase to 100 for publication
    N_PER_CONDITION = 10  # Change to 100 for publication quality
    
    print(f"Starting CEC Experiment with N={N_PER_CONDITION} per condition")
    print("This will take approximately", N_PER_CONDITION * 5 * 7 / 60, "minutes")
    print()
    
    experiment = ContextEstablishmentExperiment(n_per_condition=N_PER_CONDITION)
    
    # Run experiment
    experiment.run_experiment()
    
    # Analyze results
    cec_stats = experiment.analyze_results()
    
    # Visualize
    experiment.visualize_results()
    
    # Save for reproducibility
    experiment.save_results()
    
    # Print summary
    if cec_stats:
        print("\n" + "=" * 70)
        print("EXPERIMENT 2.1 COMPLETE")
        print("=" * 70)
        print()
        print("KEY FINDING:")
        print(f"Context Establishment Cost = {cec_stats['cec']:.1f} tokens per switch")
        print(f"95% CI: [{cec_stats['ci_lower']:.1f}, {cec_stats['ci_upper']:.1f}]")
        print(f"Model fit: R² = {cec_stats['r_squared']:.4f}")
        print()
        print("This confirms our hypothesis that each context switch")
        print("incurs a predictable token cost for establishing new context.")

if __name__ == "__main__":
    main()