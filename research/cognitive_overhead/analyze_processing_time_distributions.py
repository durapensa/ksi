#!/usr/bin/env python3
"""
Analyze processing time distributions as a metric for cognitive overhead
Processing latency may be more reliable than turn counts for measuring overhead
"""

import json
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

class ProcessingTimeAnalyzer:
    def __init__(self):
        self.daemon_log = Path("var/logs/daemon/daemon.log.jsonl")
        self.response_dir = Path("var/logs/responses")
        self.processing_times = defaultdict(list)
        self.prompt_types = {}
        self.completion_data = {}
        
    def extract_processing_times(self):
        """Extract processing times from daemon logs"""
        
        print("=== PROCESSING TIME DISTRIBUTION ANALYSIS ===")
        print(f"Analysis time: {datetime.now().isoformat()}\n")
        
        # Track completion lifecycle
        completion_starts = {}
        completion_ends = {}
        prompt_contents = {}
        
        # Parse daemon log for timing data
        with open(self.daemon_log) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                    
                    # Track completion starts
                    if 'Starting Claude CLI completion' in data.get('msg', ''):
                        request_id = data.get('request_id')
                        if request_id:
                            completion_starts[request_id] = timestamp
                    
                    # Track prompt content
                    if 'Writing' in data.get('event', '') and 'bytes to stdin' in data.get('event', ''):
                        preview = data.get('prompt_preview', '')
                        request_id = data.get('request_id')
                        if preview and request_id:
                            prompt_contents[request_id] = preview
                            
                            # Categorize prompt type
                            if 'MULTI-TASK' in preview:
                                self.prompt_types[request_id] = 'MULTI-TASK'
                            elif 'consciousness' in preview.lower():
                                self.prompt_types[request_id] = 'CONSCIOUSNESS'
                            elif 'recursion' in preview.lower() or 'recursive' in preview.lower():
                                self.prompt_types[request_id] = 'RECURSION'
                            else:
                                self.prompt_types[request_id] = 'BASELINE'
                    
                    # Track completion ends
                    if 'Process exited' in data.get('msg', ''):
                        request_id = data.get('request_id')
                        if request_id:
                            completion_ends[request_id] = timestamp
                            
                except:
                    continue
        
        # Calculate processing times
        for request_id, start_time in completion_starts.items():
            if request_id in completion_ends:
                duration = (completion_ends[request_id] - start_time).total_seconds()
                prompt_type = self.prompt_types.get(request_id, 'UNKNOWN')
                
                self.processing_times[prompt_type].append(duration)
                self.completion_data[request_id] = {
                    'duration': duration,
                    'type': prompt_type,
                    'prompt': prompt_contents.get(request_id, '')
                }
        
        return self.processing_times
    
    def analyze_distributions(self):
        """Analyze statistical distributions of processing times"""
        
        print("\n=== STATISTICAL DISTRIBUTION BY PROMPT TYPE ===\n")
        
        for prompt_type in ['BASELINE', 'CONSCIOUSNESS', 'RECURSION', 'MULTI-TASK']:
            times = self.processing_times.get(prompt_type, [])
            
            if times:
                print(f"{prompt_type}:")
                print(f"  N samples: {len(times)}")
                print(f"  Mean: {statistics.mean(times):.1f}s")
                print(f"  Median: {statistics.median(times):.1f}s")
                print(f"  Min: {min(times):.1f}s")
                print(f"  Max: {max(times):.1f}s")
                
                if len(times) > 1:
                    print(f"  Std Dev: {statistics.stdev(times):.1f}s")
                    
                    # Calculate percentiles
                    sorted_times = sorted(times)
                    p25 = sorted_times[len(sorted_times)//4] if len(sorted_times) >= 4 else sorted_times[0]
                    p75 = sorted_times[3*len(sorted_times)//4] if len(sorted_times) >= 4 else sorted_times[-1]
                    p95 = sorted_times[19*len(sorted_times)//20] if len(sorted_times) >= 20 else sorted_times[-1]
                    
                    print(f"  25th percentile: {p25:.1f}s")
                    print(f"  75th percentile: {p75:.1f}s")
                    print(f"  95th percentile: {p95:.1f}s")
                
                # Distribution shape
                if len(times) >= 3:
                    # Check for bimodal distribution (phase transitions)
                    sorted_times = sorted(times)
                    gaps = []
                    for i in range(1, len(sorted_times)):
                        gaps.append(sorted_times[i] - sorted_times[i-1])
                    
                    max_gap = max(gaps) if gaps else 0
                    avg_gap = statistics.mean(gaps) if gaps else 0
                    
                    if max_gap > 3 * avg_gap:
                        print(f"  ⚠️ Potential bimodal distribution detected (max gap: {max_gap:.1f}s)")
                
                print()
    
    def calculate_overhead_ratios(self):
        """Calculate overhead ratios compared to baseline"""
        
        print("\n=== COGNITIVE OVERHEAD RATIOS ===\n")
        
        baseline_times = self.processing_times.get('BASELINE', [])
        
        if baseline_times:
            baseline_mean = statistics.mean(baseline_times)
            baseline_median = statistics.median(baseline_times)
            
            print(f"Baseline reference:")
            print(f"  Mean: {baseline_mean:.1f}s")
            print(f"  Median: {baseline_median:.1f}s\n")
            
            for prompt_type in ['CONSCIOUSNESS', 'RECURSION', 'MULTI-TASK']:
                times = self.processing_times.get(prompt_type, [])
                
                if times:
                    mean_ratio = statistics.mean(times) / baseline_mean
                    median_ratio = statistics.median(times) / baseline_median
                    max_ratio = max(times) / baseline_mean
                    
                    print(f"{prompt_type} overhead:")
                    print(f"  Mean ratio: {mean_ratio:.1f}x")
                    print(f"  Median ratio: {median_ratio:.1f}x")
                    print(f"  Max ratio: {max_ratio:.1f}x")
                    
                    # Test for statistical significance
                    if len(times) >= 3 and len(baseline_times) >= 3:
                        # Simple t-test approximation
                        baseline_std = statistics.stdev(baseline_times) if len(baseline_times) > 1 else 0
                        test_std = statistics.stdev(times) if len(times) > 1 else 0
                        
                        if baseline_std > 0 and test_std > 0:
                            # Cohen's d effect size
                            pooled_std = ((baseline_std**2 + test_std**2) / 2) ** 0.5
                            cohens_d = (statistics.mean(times) - baseline_mean) / pooled_std
                            
                            effect_size = "negligible"
                            if abs(cohens_d) >= 0.2:
                                effect_size = "small"
                            if abs(cohens_d) >= 0.5:
                                effect_size = "medium"
                            if abs(cohens_d) >= 0.8:
                                effect_size = "large"
                            if abs(cohens_d) >= 1.2:
                                effect_size = "very large"
                            
                            print(f"  Cohen's d: {cohens_d:.2f} ({effect_size} effect)")
                    
                    print()
    
    def identify_phase_transitions(self):
        """Identify potential phase transitions in processing time"""
        
        print("\n=== PHASE TRANSITION DETECTION ===\n")
        
        # Look for discrete jumps in processing time
        all_times = []
        for prompt_type, times in self.processing_times.items():
            for t in times:
                all_times.append((t, prompt_type))
        
        all_times.sort()
        
        if len(all_times) >= 3:
            # Look for gaps in distribution
            gaps = []
            for i in range(1, len(all_times)):
                gap = all_times[i][0] - all_times[i-1][0]
                if gap > 10:  # More than 10 seconds gap
                    gaps.append((all_times[i-1], all_times[i], gap))
            
            if gaps:
                print("Detected processing time discontinuities:")
                for (t1, type1), (t2, type2), gap in gaps:
                    print(f"  {t1:.1f}s ({type1}) → {t2:.1f}s ({type2}): gap of {gap:.1f}s")
                print()
                
                # Check if gaps correlate with prompt type transitions
                type_transitions = defaultdict(list)
                for (t1, type1), (t2, type2), gap in gaps:
                    if type1 != type2:
                        type_transitions[f"{type1}→{type2}"].append(gap)
                
                if type_transitions:
                    print("Transitions associated with prompt type changes:")
                    for transition, gap_list in type_transitions.items():
                        avg_gap = statistics.mean(gap_list)
                        print(f"  {transition}: avg gap {avg_gap:.1f}s")
            else:
                print("No significant discontinuities detected")
    
    def generate_summary(self):
        """Generate executive summary of findings"""
        
        print("\n=== EXECUTIVE SUMMARY ===\n")
        
        total_completions = sum(len(times) for times in self.processing_times.values())
        
        print(f"Total completions analyzed: {total_completions}")
        
        if total_completions > 0:
            # Find extremes
            all_times_flat = []
            for times in self.processing_times.values():
                all_times_flat.extend(times)
            
            if all_times_flat:
                print(f"Processing time range: {min(all_times_flat):.1f}s - {max(all_times_flat):.1f}s")
                print(f"Overall mean: {statistics.mean(all_times_flat):.1f}s")
                print(f"Overall median: {statistics.median(all_times_flat):.1f}s")
                
                # Key findings
                print("\nKey Findings:")
                
                baseline_times = self.processing_times.get('BASELINE', [])
                multitask_times = self.processing_times.get('MULTI-TASK', [])
                
                if baseline_times and multitask_times:
                    baseline_mean = statistics.mean(baseline_times)
                    multitask_mean = statistics.mean(multitask_times)
                    
                    if multitask_mean > baseline_mean * 2:
                        print(f"✓ Multi-task prompts show {multitask_mean/baseline_mean:.1f}x processing overhead")
                
                consciousness_times = self.processing_times.get('CONSCIOUSNESS', [])
                if baseline_times and consciousness_times:
                    consciousness_mean = statistics.mean(consciousness_times)
                    
                    if consciousness_mean > baseline_mean * 1.5:
                        print(f"✓ Consciousness prompts show {consciousness_mean/baseline_mean:.1f}x processing overhead")
                
                # Check for evidence of dual-mode transitions
                if len(all_times_flat) >= 10:
                    sorted_times = sorted(all_times_flat)
                    
                    # Look for clustering
                    fast_cluster = [t for t in sorted_times if t < 60]
                    slow_cluster = [t for t in sorted_times if t >= 60]
                    
                    if fast_cluster and slow_cluster:
                        print(f"✓ Evidence of dual-mode processing:")
                        print(f"  - Fast mode: {len(fast_cluster)} completions < 60s")
                        print(f"  - Slow mode: {len(slow_cluster)} completions >= 60s")
                        
                        if slow_cluster:
                            slow_mean = statistics.mean(slow_cluster)
                            fast_mean = statistics.mean(fast_cluster) if fast_cluster else 1
                            print(f"  - Slow/Fast ratio: {slow_mean/fast_mean:.1f}x")

def main():
    analyzer = ProcessingTimeAnalyzer()
    analyzer.extract_processing_times()
    analyzer.analyze_distributions()
    analyzer.calculate_overhead_ratios()
    analyzer.identify_phase_transitions()
    analyzer.generate_summary()

if __name__ == "__main__":
    main()