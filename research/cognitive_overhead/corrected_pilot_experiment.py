#!/usr/bin/env python3
"""
CORRECTED Pilot Experiment - Measures actual LLM processing time
Fixes critical flaw in original pilot that only measured request submission
"""

import json
import time
import subprocess
import numpy as np
from datetime import datetime
from pathlib import Path
from scipy import stats
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class ProperMeasurement:
    """Measurement with actual LLM processing time"""
    condition: str
    prompt: str
    request_id: str
    submission_time: float
    completion_time: float
    duration_ms: float  # From completion:result event
    response_length: int
    overhead_ratio: float

class CorrectedExperiment:
    def __init__(self):
        self.results_dir = Path("var/experiments/cognitive_overhead/corrected_pilot")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.measurements = []
        
        # Same conditions as before but now we'll measure properly
        self.conditions = {
            'baseline': "Calculate: 45 + 23 - 11",
            'length_control': "Calculate carefully and precisely: 45 + 23 - 11",
            'consciousness': "While contemplating consciousness, calculate: 45 + 23 - 11",
            'multi_neutral': "Complete these tasks: (1) Calculate 45 + 23, (2) Calculate 23 - 11",
            'multi_consciousness': "Complete these tasks: (1) Calculate 45 + 23, (2) Reflect on consciousness, (3) Calculate 23 - 11"
        }
        
    def wait_for_completion(self, request_id: str, timeout: int = 30) -> Optional[Dict]:
        """Wait for completion and extract actual duration"""
        
        start_wait = time.time()
        
        while time.time() - start_wait < timeout:
            # Check monitor for completion event
            result = subprocess.run([
                "ksi", "send", "monitor:get_events",
                "--limit", "10",
                "--event-patterns", "completion:result"
            ], capture_output=True, text=True, timeout=5)
            
            try:
                data = json.loads(result.stdout)
                events = data.get('events', [])
                
                # Look for our specific completion
                for event in events:
                    event_data = event.get('data', {})
                    if event_data.get('request_id') == request_id:
                        result_data = event_data.get('result', {})
                        ksi_info = result_data.get('ksi', {})
                        response_info = result_data.get('response', {})
                        
                        return {
                            'duration_ms': ksi_info.get('duration_ms', 0),
                            'response': response_info.get('result', ''),
                            'timestamp': ksi_info.get('timestamp', ''),
                            'found': True
                        }
                        
            except Exception as e:
                print(f"    Error parsing monitor: {e}")
            
            # Wait before checking again
            time.sleep(0.5)
        
        return None
    
    def run_single_measurement(self, condition: str, trial: int) -> Optional[ProperMeasurement]:
        """Run a single test with proper measurement"""
        
        prompt = self.conditions[condition]
        request_id = f"corrected_{condition}_{trial}_{self.session_id}"
        agent_id = f"agent_{request_id}"
        
        print(f"  Trial {trial} - {condition}:")
        print(f"    Submitting...", end="")
        
        # Submit async request
        submission_time = time.perf_counter()
        
        cmd = [
            "ksi", "send", "completion:async",
            "--agent-id", agent_id,
            "--prompt", prompt,
            "--request-id", request_id
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f" ERROR: {result.stderr}")
            return None
        
        print(" waiting for completion...", end="")
        
        # Wait for actual completion
        completion_data = self.wait_for_completion(request_id)
        completion_time = time.perf_counter()
        
        if not completion_data:
            print(" TIMEOUT")
            return None
        
        duration_ms = completion_data['duration_ms']
        response_length = len(completion_data.get('response', ''))
        
        print(f" {duration_ms:.0f}ms")
        
        # Calculate overhead (will set baseline later)
        overhead = 1.0
        
        return ProperMeasurement(
            condition=condition,
            prompt=prompt,
            request_id=request_id,
            submission_time=submission_time,
            completion_time=completion_time,
            duration_ms=duration_ms,
            response_length=response_length,
            overhead_ratio=overhead
        )
    
    def run_corrected_pilot(self, n_samples: int = 5):
        """Run pilot with proper measurements"""
        
        print("\n=== CORRECTED PILOT EXPERIMENT ===")
        print(f"Session: {self.session_id}")
        print(f"Samples per condition: {n_samples}")
        print("Measuring ACTUAL LLM processing time via completion events\n")
        
        # Run tests
        for condition in self.conditions:
            print(f"\nCondition: {condition}")
            
            for trial in range(1, n_samples + 1):
                measurement = self.run_single_measurement(condition, trial)
                
                if measurement:
                    self.measurements.append(measurement)
                
                # Delay between tests
                time.sleep(2)
        
        print(f"\n\nCollected {len(self.measurements)} measurements with actual durations")
        
        # Calculate overhead ratios
        baseline_times = [m.duration_ms for m in self.measurements if m.condition == 'baseline']
        if baseline_times:
            baseline_mean = np.mean(baseline_times)
            for m in self.measurements:
                m.overhead_ratio = m.duration_ms / baseline_mean
        
        return self.measurements
    
    def analyze_results(self):
        """Analyze with proper statistical tests"""
        
        print("\n=== ANALYSIS OF ACTUAL LLM PROCESSING TIMES ===\n")
        
        if not self.measurements:
            print("No measurements collected")
            return
        
        # Group by condition
        by_condition = {}
        for m in self.measurements:
            if m.condition not in by_condition:
                by_condition[m.condition] = []
            by_condition[m.condition].append(m.duration_ms)
        
        # Calculate statistics
        print("ACTUAL PROCESSING TIMES (not request latency):")
        print("-" * 70)
        print(f"{'Condition':<25} {'N':<5} {'Mean (ms)':<12} {'Std':<10} {'Overhead':<10}")
        print("-" * 70)
        
        baseline_mean = np.mean(by_condition.get('baseline', [1]))
        
        results_summary = {}
        for condition in self.conditions:
            if condition in by_condition:
                times = by_condition[condition]
                mean_time = np.mean(times)
                std_time = np.std(times)
                overhead = mean_time / baseline_mean
                
                results_summary[condition] = {
                    'mean': mean_time,
                    'std': std_time,
                    'overhead': overhead,
                    'data': times
                }
                
                print(f"{condition:<25} {len(times):<5} {mean_time:<12.1f} {std_time:<10.1f} {overhead:<10.2f}x")
        
        # Statistical tests
        print("\n\nSTATISTICAL SIGNIFICANCE:")
        print("-" * 70)
        
        if 'baseline' in by_condition and len(by_condition['baseline']) > 1:
            baseline_data = by_condition['baseline']
            
            for condition in ['consciousness', 'multi_consciousness', 'length_control']:
                if condition in by_condition and len(by_condition[condition]) > 1:
                    test_data = by_condition[condition]
                    
                    # Welch's t-test
                    t_stat, p_value = stats.ttest_ind(baseline_data, test_data, equal_var=False)
                    
                    # Effect size
                    mean_diff = np.mean(test_data) - np.mean(baseline_data)
                    pooled_std = np.sqrt((np.var(test_data) + np.var(baseline_data)) / 2)
                    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
                    
                    sig = '***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else ''
                    
                    print(f"\n{condition} vs baseline:")
                    print(f"  Mean difference: {mean_diff:.1f}ms")
                    print(f"  p-value: {p_value:.4f} {sig}")
                    print(f"  Cohen's d: {cohens_d:.3f}")
        
        return results_summary
    
    def save_results(self):
        """Save corrected results"""
        
        output_file = self.results_dir / f"corrected_{self.session_id}.json"
        
        data = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'methodology': 'Proper measurement via completion:result events',
            'measurements': [
                {
                    'condition': m.condition,
                    'duration_ms': m.duration_ms,
                    'overhead_ratio': m.overhead_ratio,
                    'response_length': m.response_length
                }
                for m in self.measurements
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")

def main():
    print("=" * 70)
    print("CORRECTED EXPERIMENT - MEASURING ACTUAL LLM PROCESSING")
    print("=" * 70)
    
    experiment = CorrectedExperiment()
    
    # Run with fewer samples since each takes longer
    experiment.run_corrected_pilot(n_samples=5)
    
    # Analyze
    results = experiment.analyze_results()
    
    # Save
    experiment.save_results()
    
    # Verdict
    print("\n" + "=" * 70)
    print("CORRECTED PILOT VERDICT:")
    print("=" * 70)
    
    if results:
        consciousness_overhead = results.get('consciousness', {}).get('overhead', 1.0)
        multi_overhead = results.get('multi_consciousness', {}).get('overhead', 1.0)
        
        print(f"Consciousness overhead: {consciousness_overhead:.2f}x")
        print(f"Multi-consciousness overhead: {multi_overhead:.2f}x")
        
        if consciousness_overhead > 1.5 or multi_overhead > 2.0:
            print("\n✅ EFFECT POTENTIALLY CONFIRMED with proper measurement")
        else:
            print("\n❌ NO SIGNIFICANT EFFECT even with correct methodology")

if __name__ == "__main__":
    main()