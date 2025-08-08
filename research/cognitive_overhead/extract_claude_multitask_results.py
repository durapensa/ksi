#!/usr/bin/env python3
"""
Extract and analyze Claude multi-task experiment results from daemon logs
Focus on the 10-round experiment including multi-task rounds 7-9
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import re

class ClaudeMultiTaskAnalyzer:
    def __init__(self):
        self.daemon_log = Path("var/logs/daemon/daemon.log.jsonl")
        self.results = []
        
    def extract_experiment_data(self):
        """Extract Claude 10-round experiment data from logs"""
        
        print("=== CLAUDE MULTI-TASK EXPERIMENT RESULTS ===")
        print(f"Analysis time: {datetime.now().isoformat()}\n")
        
        # Track completions and their durations
        completions = []
        session_tracking = {}
        
        with open(self.daemon_log) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    timestamp = data.get('timestamp', '')
                    
                    # Track completion starts
                    if 'Starting Claude CLI completion' in data.get('event', ''):
                        session_id = data.get('session_id')
                        if session_id:
                            session_tracking[session_id] = {
                                'start': datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                                'session_id': session_id
                            }
                    
                    # Track completion ends with duration
                    if 'LiteLLM completion successful' in data.get('msg', ''):
                        duration_match = re.search(r'duration=(\d+\.?\d*)s', data.get('msg', ''))
                        if duration_match:
                            duration = float(duration_match.group(1))
                            provider = 'claude-cli' if 'claude-cli' in data.get('msg', '') else 'unknown'
                            completions.append({
                                'timestamp': timestamp,
                                'duration': duration,
                                'provider': provider
                            })
                    
                    # Look for multi-task prompts
                    if 'MULTI-TASK' in str(data.get('first_msg', {}).get('content', '')):
                        print(f"Found MULTI-TASK prompt at {timestamp}")
                        # Find the next completion after this
                        for comp in completions:
                            comp_time = datetime.fromisoformat(comp['timestamp'].replace('Z', '+00:00'))
                            prompt_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            if comp_time > prompt_time:
                                print(f"  Duration: {comp['duration']}s")
                                break
                    
                    # Extract prompts with round numbers
                    prompt_preview = data.get('prompt_preview', '')
                    if prompt_preview and 'Round' in prompt_preview:
                        round_match = re.search(r'Round (\d+):', prompt_preview)
                        if round_match:
                            round_num = int(round_match.group(1))
                            
                            # Categorize prompt type
                            prompt_type = 'BASELINE'
                            if 'MULTI-TASK' in prompt_preview:
                                prompt_type = 'MULTI-TASK'
                            elif 'consciousness' in prompt_preview.lower():
                                prompt_type = 'CONSCIOUSNESS'
                            elif round_num == 10:
                                prompt_type = 'SYNTHESIS'
                            
                            self.results.append({
                                'round': round_num,
                                'prompt_type': prompt_type,
                                'timestamp': timestamp,
                                'prompt_preview': prompt_preview[:100]
                            })
                            
                except Exception as e:
                    continue
        
        # Match completions to rounds
        print("\n=== ROUND-BY-ROUND ANALYSIS ===\n")
        for result in sorted(self.results, key=lambda x: x['round']):
            print(f"Round {result['round']} ({result['prompt_type']})")
            print(f"  Prompt: {result['prompt_preview']}...")
            
            # Find associated completion
            result_time = datetime.fromisoformat(result['timestamp'].replace('Z', '+00:00'))
            for comp in completions:
                comp_time = datetime.fromisoformat(comp['timestamp'].replace('Z', '+00:00'))
                if comp_time > result_time and (comp_time - result_time).total_seconds() < 300:  # Within 5 minutes
                    print(f"  Duration: {comp['duration']:.1f}s")
                    result['duration'] = comp['duration']
                    break
            print()
        
        return self.results
    
    def analyze_overhead(self):
        """Analyze cognitive overhead patterns"""
        
        print("\n=== COGNITIVE OVERHEAD ANALYSIS ===\n")
        
        # Group by phase
        baseline_rounds = [r for r in self.results if r['round'] in [1, 2, 3] and 'duration' in r]
        consciousness_rounds = [r for r in self.results if r['round'] in [4, 5, 6] and 'duration' in r]
        multitask_rounds = [r for r in self.results if r['round'] in [7, 8, 9] and 'duration' in r]
        
        if baseline_rounds:
            baseline_avg = sum(r['duration'] for r in baseline_rounds) / len(baseline_rounds)
            print(f"Baseline (Rounds 1-3): {baseline_avg:.1f}s average")
        
        if consciousness_rounds:
            conscious_avg = sum(r['duration'] for r in consciousness_rounds) / len(consciousness_rounds)
            print(f"Consciousness (Rounds 4-6): {conscious_avg:.1f}s average")
            if baseline_rounds:
                print(f"  Overhead: {conscious_avg/baseline_avg:.1f}x baseline")
        
        if multitask_rounds:
            multi_avg = sum(r['duration'] for r in multitask_rounds) / len(multitask_rounds)
            print(f"Multi-task (Rounds 7-9): {multi_avg:.1f}s average")
            if baseline_rounds:
                print(f"  Overhead: {multi_avg/baseline_avg:.1f}x baseline")
        
        # Check for extreme overhead
        print("\n=== EXTREME OVERHEAD DETECTION ===\n")
        for result in self.results:
            if 'duration' in result and result['duration'] > 60:
                print(f"⚠️ Round {result['round']}: {result['duration']:.1f}s ({result['duration']/60:.1f} minutes)")
                print(f"   Type: {result['prompt_type']}")
    
    def search_for_multitask_completion(self):
        """Search specifically for the long-running multi-task experiment"""
        
        print("\n=== SEARCHING FOR LONG-RUNNING MULTI-TASK ===\n")
        
        # Known start time from logs
        multitask_start = datetime.fromisoformat('2025-08-08T19:28:58.349729Z'.replace('Z', '+00:00'))
        print(f"Multi-task Round 7 started at: {multitask_start.isoformat()}")
        
        # Look for completions after this time
        found_completion = False
        with open(self.daemon_log) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    timestamp_str = data.get('timestamp', '')
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        if timestamp > multitask_start:
                            # Look for completion events
                            if 'LiteLLM completion successful' in data.get('msg', ''):
                                duration_match = re.search(r'duration=(\d+\.?\d*)s', data.get('msg', ''))
                                if duration_match:
                                    duration = float(duration_match.group(1))
                                    elapsed = (timestamp - multitask_start).total_seconds()
                                    
                                    # Check if this could be our multi-task completion
                                    if duration > 30 or elapsed < 120:  # Long duration or happened soon after
                                        print(f"Potential completion at {timestamp.isoformat()}")
                                        print(f"  Duration: {duration:.1f}s")
                                        print(f"  Time since multi-task start: {elapsed:.1f}s")
                                        
                                        if duration > 100:  # Likely our extreme overhead case
                                            found_completion = True
                                            print(f"  ⚠️ EXTREME OVERHEAD DETECTED: {duration/60:.1f} minutes!")
                                            return duration
                                            
                except:
                    continue
        
        if not found_completion:
            # Calculate how long it's been running
            now = datetime.utcnow().replace(tzinfo=multitask_start.tzinfo)
            elapsed = (now - multitask_start).total_seconds()
            print(f"\n⏱️ Multi-task still running after {elapsed:.0f}s ({elapsed/60:.1f} minutes)")
            return None

def main():
    analyzer = ClaudeMultiTaskAnalyzer()
    analyzer.extract_experiment_data()
    analyzer.analyze_overhead()
    duration = analyzer.search_for_multitask_completion()
    
    if duration:
        print(f"\n=== FINAL RESULT ===")
        print(f"Claude Multi-task Round 7 completed with {duration/60:.1f} minutes processing time")
        print(f"This represents approximately {duration/30:.0f}x overhead compared to baseline")

if __name__ == "__main__":
    main()