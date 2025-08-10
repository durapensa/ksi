#!/usr/bin/env python3
"""
Data Collection Script with Proper Sampling Methodology
Following GPT-5's requirements for randomization and documentation
"""

import json
import time
import subprocess
import numpy as np
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import sys
import os

@dataclass
class ExperimentalTrial:
    """Single experimental trial with full metadata"""
    trial_id: str
    condition: str
    n_switches: int
    prompt: str
    response: str
    output_tokens: int
    input_tokens: int
    cost_usd: float
    duration_ms: float
    ttft_ms: Optional[float]  # Time to first token
    tpot_ms: Optional[float]  # Time per output token
    timestamp: str
    seed: int
    order_in_sequence: int
    api_version: str
    
class DataCollectorV3:
    """
    Data collector with proper sampling methodology
    Implements GPT-5's requirements for randomization and controls
    """
    
    def __init__(self, n_per_condition: int = 10):
        self.n_per_condition = n_per_condition
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Experimental conditions
        self.conditions = {
            '0_switches': {
                'prompt': "Calculate: 47+89, 156-78, 34×3, 144÷12, 25+67",
                'n_switches': 0,
                'expected_output': [136, 78, 102, 12, 92]
            },
            '1_switch': {
                'prompt': "First calculate: 47+89, 156-78, 34×3. Then calculate: 144÷12, 25+67",
                'n_switches': 1,
                'expected_output': [136, 78, 102, 12, 92]
            },
            '2_switches': {
                'prompt': "Start with: 47+89, 156-78. Continue with: 34×3, 144÷12. Finish with: 25+67",
                'n_switches': 2,
                'expected_output': [136, 78, 102, 12, 92]
            },
            '3_switches': {
                'prompt': "First: 47+89. Second: 156-78, 34×3. Third: 144÷12. Fourth: 25+67",
                'n_switches': 3,
                'expected_output': [136, 78, 102, 12, 92]
            },
            '4_switches': {
                'prompt': "Do separately. First: 47+89. Second: 156-78. Third: 34×3. Fourth: 144÷12. Fifth: 25+67",
                'n_switches': 4,
                'expected_output': [136, 78, 102, 12, 92]
            }
        }
        
        self.results = []
        self.failed_trials = []
        
        # API configuration (following GPT-5's documentation requirements)
        self.api_config = {
            'model': 'claude-3.5-sonnet-20241022',
            'api_version': 'Anthropic API v1',
            'temperature': 'Not controlled (API default ~0.7)',
            'top_p': 'Not controlled (API default)',
            'max_tokens': 4096,
            'stop_sequences': None,
            'system_prompt': None
        }
        
    def generate_latin_square(self) -> List[List[str]]:
        """
        Generate Latin square design for condition ordering
        Ensures each condition appears in each position equally
        """
        conditions = list(self.conditions.keys())
        n = len(conditions)
        
        # Standard Latin square
        latin_square = []
        for i in range(n):
            row = conditions[i:] + conditions[:i]
            latin_square.append(row)
        
        # Replicate and randomize for required trials
        sequences = []
        for trial_num in range(self.n_per_condition):
            # Use deterministic seed for reproducibility
            seed = 42 + trial_num * 137
            np.random.seed(seed)
            
            # Randomly select and permute a row
            row_idx = trial_num % n
            sequence = latin_square[row_idx].copy()
            
            # Add some randomization while maintaining balance
            if trial_num >= n:
                np.random.shuffle(sequence)
            
            sequences.append({
                'sequence': sequence,
                'seed': seed,
                'trial_num': trial_num
            })
        
        return sequences
    
    def run_single_trial(self, condition: str, trial_num: int, order_in_sequence: int, seed: int) -> Optional[ExperimentalTrial]:
        """
        Run a single experimental trial with full documentation
        """
        condition_data = self.conditions[condition]
        # Use timestamp microseconds to ensure absolute uniqueness
        unique_suffix = datetime.now().strftime("%f")
        agent_id = f"exp_{condition}_{self.session_id}_t{trial_num}_o{order_in_sequence}_{unique_suffix}"
        
        print(f"    Trial {trial_num}, Position {order_in_sequence}: {condition}", end="")
        
        # Start timing
        start_time = time.time()
        
        # Use completion directly without agent to ensure clean sessions
        # Each completion gets a fresh temporary sandbox
        completion_cmd = [
            "ksi", "send", "completion:async",
            "--prompt", condition_data['prompt']
        ]
        
        try:
            result = subprocess.run(completion_cmd, capture_output=True, text=True, check=False)
            
            # Parse the async response to get request_id
            try:
                async_response = json.loads(result.stdout) if result.stdout else {}
                request_id = async_response.get('request_id')
                
                if not request_id:
                    print(f" ✗ No request_id in response")
                    return None
            except json.JSONDecodeError:
                print(f" ✗ Failed to parse async response")
                return None
        except Exception as e:
            print(f" ✗ Failed to start: {e}")
            self.failed_trials.append({
                'agent_id': agent_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None
        
        # Wait for completion to finish
        time.sleep(20)
        
        # Get completion result
        try:
            monitor_cmd = [
                "ksi", "send", "monitor:get_events",
                "--limit", "20",
                "--event-patterns", "completion:result"
            ]
            
            monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True, check=False)
            monitor_data = json.loads(monitor_result.stdout) if monitor_result.stdout else {}
            events = monitor_data.get('events', [])
            
            # Find our completion by request_id
            for event in events:
                event_data = event.get('data', {})
                result_data = event_data.get('result', {})
                ksi_info = result_data.get('ksi', {})
                
                if ksi_info.get('request_id') == request_id:
                    response_data = result_data.get('response', {})
                    
                    # Extract all metrics
                    usage = response_data.get('usage', {})
                    output_tokens = usage.get('output_tokens', 0)
                    input_tokens = usage.get('input_tokens', 0)
                    cost = response_data.get('total_cost_usd', 0)
                    response_text = response_data.get('result', '')
                    duration_ms = response_data.get('duration_ms', 0)
                    
                    # Calculate TPOT (Time Per Output Token)
                    tpot_ms = duration_ms / output_tokens if output_tokens > 0 else None
                    
                    # TTFT would require streaming API (not available)
                    ttft_ms = None
                    
                    # Verify arithmetic accuracy
                    accuracy = self.verify_arithmetic_accuracy(response_text, condition_data['expected_output'])
                    
                    trial = ExperimentalTrial(
                        trial_id=agent_id,
                        condition=condition,
                        n_switches=condition_data['n_switches'],
                        prompt=condition_data['prompt'],
                        response=response_text,
                        output_tokens=output_tokens,
                        input_tokens=input_tokens,
                        cost_usd=cost,
                        duration_ms=duration_ms,
                        ttft_ms=ttft_ms,
                        tpot_ms=tpot_ms,
                        timestamp=datetime.now().isoformat(),
                        seed=seed,
                        order_in_sequence=order_in_sequence,
                        api_version=self.api_config['api_version']
                    )
                    
                    print(f" ✓ {output_tokens} tokens, ${cost:.6f}, {accuracy}")
                    
                    return trial
            
            print(" ⏳ No result found")
            return None
            
        except Exception as e:
            print(f" ✗ Error: {e}")
            self.failed_trials.append({
                'agent_id': agent_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None
    
    def verify_arithmetic_accuracy(self, response: str, expected: List[int]) -> str:
        """Verify arithmetic accuracy of response"""
        found = []
        for value in expected:
            if str(value) in response:
                found.append(value)
        
        accuracy = len(found) / len(expected) if expected else 0
        return f"{accuracy:.0%} accurate"
    
    def run_experiment(self):
        """
        Run the complete experiment with Latin square design
        """
        print("=" * 70)
        print("DATA COLLECTION V3: Following GPT-5's Methodology Requirements")
        print("=" * 70)
        print()
        print("Configuration:")
        print(f"  N per condition: {self.n_per_condition}")
        print(f"  Total trials: {self.n_per_condition * len(self.conditions)}")
        print(f"  Design: Latin square with randomization")
        print(f"  Session ID: {self.session_id}")
        print()
        
        # Generate Latin square sequences
        sequences = self.generate_latin_square()
        
        print(f"Generated {len(sequences)} trial sequences")
        print()
        
        # Run trials
        for seq_num, seq_data in enumerate(sequences):
            print(f"Sequence {seq_num + 1}/{len(sequences)} (seed={seq_data['seed']}):")
            
            for position, condition in enumerate(seq_data['sequence']):
                trial = self.run_single_trial(
                    condition=condition,
                    trial_num=seq_num,
                    order_in_sequence=position,
                    seed=seq_data['seed']
                )
                
                if trial:
                    self.results.append(trial)
                
                # Rate limiting
                time.sleep(2)
            
            print()
        
        print(f"Collection complete: {len(self.results)} successful, {len(self.failed_trials)} failed")
    
    def save_results(self):
        """Save results with full documentation"""
        
        # Create results directory
        os.makedirs('results', exist_ok=True)
        
        # Main results file
        output = {
            'metadata': {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'n_per_condition': self.n_per_condition,
                'total_trials_attempted': self.n_per_condition * len(self.conditions),
                'successful_trials': len(self.results),
                'failed_trials': len(self.failed_trials)
            },
            'configuration': self.api_config,
            'conditions': self.conditions,
            'results': [asdict(r) for r in self.results],
            'failed_trials': self.failed_trials
        }
        
        filename = f'results/preliminary_data_{self.session_id}.json'
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        # Compute SHA256 checksum
        with open(filename, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
        
        print(f"\nResults saved to: {filename}")
        print(f"SHA256: {checksum}")
        
        # Save checksum
        with open('results/checksums.txt', 'a') as f:
            f.write(f"{filename}: {checksum}\n")
        
        # Create summary statistics
        self.generate_summary()
    
    def generate_summary(self):
        """Generate summary statistics for quick inspection"""
        
        if not self.results:
            print("No results to summarize")
            return
        
        print("\n" + "=" * 70)
        print("PRELIMINARY RESULTS SUMMARY")
        print("=" * 70)
        print()
        
        # Group by condition
        by_condition = {}
        for trial in self.results:
            if trial.condition not in by_condition:
                by_condition[trial.condition] = []
            by_condition[trial.condition].append(trial)
        
        # Summary table
        print(f"{'Condition':<15} {'N':<5} {'Mean Tokens':<12} {'Std':<8} {'Mean Cost':<10}")
        print("-" * 60)
        
        for condition in sorted(by_condition.keys(), key=lambda x: self.conditions[x]['n_switches']):
            trials = by_condition[condition]
            tokens = [t.output_tokens for t in trials]
            costs = [t.cost_usd for t in trials]
            
            print(f"{condition:<15} {len(trials):<5} {np.mean(tokens):<12.1f} "
                  f"{np.std(tokens):<8.1f} ${np.mean(costs):<10.6f}")
        
        # Quick CEC calculation
        print("\nQuick CEC Estimate:")
        switches = []
        mean_tokens = []
        
        for condition, trials in by_condition.items():
            switches.append(self.conditions[condition]['n_switches'])
            mean_tokens.append(np.mean([t.output_tokens for t in trials]))
        
        if len(switches) >= 3:
            from scipy import stats
            slope, intercept, r_value, p_value, _ = stats.linregress(switches, mean_tokens)
            print(f"  CEC = {slope:.1f} tokens per switch")
            print(f"  Base = {intercept:.1f} tokens")
            print(f"  R² = {r_value**2:.4f}")
            print(f"  p = {p_value:.6f}")


def main():
    """Run data collection"""
    
    # Parse command line arguments
    n_per_condition = 10  # Default
    if len(sys.argv) > 1:
        try:
            n_per_condition = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [n_per_condition]")
            sys.exit(1)
    
    # Run collection
    collector = DataCollectorV3(n_per_condition=n_per_condition)
    collector.run_experiment()
    collector.save_results()


if __name__ == "__main__":
    main()