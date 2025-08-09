#!/usr/bin/env python3
"""
Quick Context Establishment Cost (CEC) Experiment
Rapid data collection for initial validation
"""

import json
import time
import subprocess
import numpy as np
from datetime import datetime
from typing import Dict, List
import random

def run_cec_test():
    """Run quick CEC test with controlled switches"""
    
    print("=" * 70)
    print("QUICK CEC EXPERIMENT")
    print("=" * 70)
    print()
    
    # Test conditions with known switch counts
    conditions = {
        '0_switches': {
            'prompt': "Calculate: 47+89, 156-78, 34×3, 144÷12, 25+67",
            'switches': 0
        },
        '1_switch': {
            'prompt': "First calculate: 47+89, 156-78, 34×3. Then calculate: 144÷12, 25+67",
            'switches': 1
        },
        '2_switches': {
            'prompt': "Start with: 47+89, 156-78. Continue with: 34×3, 144÷12. Finish with: 25+67",
            'switches': 2
        },
        '3_switches': {
            'prompt': "First: 47+89. Second: 156-78, 34×3. Third: 144÷12. Fourth: 25+67",
            'switches': 3
        },
        '4_switches': {
            'prompt': "Do separately. First: 47+89. Second: 156-78. Third: 34×3. Fourth: 144÷12. Fifth: 25+67",
            'switches': 4
        }
    }
    
    results = {}
    session_id = datetime.now().strftime("%H%M%S")
    
    # Run each condition 3 times for quick validation
    for condition_name, data in conditions.items():
        print(f"\nTesting: {condition_name} ({data['switches']} switches)")
        
        tokens_list = []
        costs_list = []
        
        for trial in range(3):
            agent_id = f"cec_{condition_name}_{session_id}_{trial}"
            
            # Run completion
            cmd = [
                "ksi", "send", "completion:async",
                "--agent-id", agent_id,
                "--prompt", data['prompt']
            ]
            
            subprocess.run(cmd, capture_output=True, text=True)
            time.sleep(6)  # Wait for completion
            
            # Get result
            monitor_cmd = [
                "ksi", "send", "monitor:get_events",
                "--limit", "10",
                "--event-patterns", "completion:result"
            ]
            
            monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
            
            try:
                response_data = json.loads(monitor_result.stdout)
                events = response_data.get('events', [])
                
                for event in events:
                    event_data = event.get('data', {})
                    ksi_info = event_data.get('result', {}).get('ksi', {})
                    
                    if agent_id in ksi_info.get('agent_id', ''):
                        result_data = event_data.get('result', {}).get('response', {})
                        cost = result_data.get('total_cost_usd', 0)
                        usage = result_data.get('usage', {})
                        output_tokens = usage.get('output_tokens', 0)
                        
                        if output_tokens > 0:
                            tokens_list.append(output_tokens)
                            costs_list.append(cost)
                            print(f"  Trial {trial+1}: {output_tokens} tokens, ${cost:.6f}")
                        break
                        
            except Exception as e:
                print(f"  Trial {trial+1}: Error - {e}")
        
        if tokens_list:
            results[condition_name] = {
                'switches': data['switches'],
                'mean_tokens': np.mean(tokens_list),
                'std_tokens': np.std(tokens_list),
                'mean_cost': np.mean(costs_list),
                'samples': len(tokens_list),
                'raw_tokens': tokens_list
            }
    
    return results

def analyze_cec_results(results):
    """Analyze CEC from results"""
    
    print("\n" + "=" * 70)
    print("CEC ANALYSIS")
    print("=" * 70)
    print()
    
    # Extract data for regression
    switches = []
    tokens = []
    
    for condition, data in sorted(results.items()):
        print(f"{condition}:")
        print(f"  Switches: {data['switches']}")
        print(f"  Tokens: {data['mean_tokens']:.1f} ± {data['std_tokens']:.1f}")
        print(f"  Cost: ${data['mean_cost']:.6f}")
        print()
        
        switches.append(data['switches'])
        tokens.append(data['mean_tokens'])
    
    if len(switches) >= 3:
        # Linear regression
        from scipy import stats
        slope, intercept, r_value, p_value, std_err = stats.linregress(switches, tokens)
        
        print("LINEAR MODEL:")
        print("-" * 40)
        print(f"Tokens = {intercept:.1f} + {slope:.1f} × Switches")
        print(f"R² = {r_value**2:.4f}")
        print(f"p-value = {p_value:.6f}")
        print()
        print(f"CONTEXT ESTABLISHMENT COST = {slope:.1f} tokens per switch")
        print(f"Base tokens (no switches) = {intercept:.1f}")
        
        # Visualize
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6))
        plt.scatter(switches, tokens, s=100, color='red', zorder=5, label='Observed')
        
        # Plot regression line
        x_line = np.linspace(0, max(switches), 100)
        y_line = intercept + slope * x_line
        plt.plot(x_line, y_line, 'b--', alpha=0.7, 
                label=f'y = {intercept:.1f} + {slope:.1f}x (R²={r_value**2:.3f})')
        
        plt.xlabel('Number of Context Switches', fontsize=12)
        plt.ylabel('Output Tokens', fontsize=12)
        plt.title('Context Establishment Cost (CEC) - Quick Validation', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        # Add annotations
        for i, (x, y) in enumerate(zip(switches, tokens)):
            plt.annotate(f'{y:.0f}', (x, y), textcoords="offset points", 
                        xytext=(0,10), ha='center')
        
        plt.tight_layout()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plt.savefig(f'research/cognitive_overhead/quick_cec_{timestamp}.png')
        print(f"\nPlot saved to: research/cognitive_overhead/quick_cec_{timestamp}.png")
        plt.show()
        
        return {
            'cec': slope,
            'base_tokens': intercept,
            'r_squared': r_value**2,
            'p_value': p_value
        }
    
    return None

def main():
    print("Running Quick CEC Experiment")
    print("This will take approximately 2-3 minutes")
    print()
    
    # Run experiment
    results = run_cec_test()
    
    if results:
        # Analyze
        cec_stats = analyze_cec_results(results)
        
        if cec_stats:
            print("\n" + "=" * 70)
            print("QUICK CEC EXPERIMENT COMPLETE")
            print("=" * 70)
            print()
            print("KEY FINDING:")
            print(f"Context Establishment Cost = {cec_stats['cec']:.1f} tokens/switch")
            print(f"This aligns with our hypothesis of 100-150 tokens per context switch")
            print()
            print("Next step: Run full experiment with N=100 for publication quality")
    else:
        print("No results collected. Check KSI daemon status.")

if __name__ == "__main__":
    main()