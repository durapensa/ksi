#!/usr/bin/env python3
"""
Investigate why pilot results differ from original findings
Compare measurement methodologies
"""

import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

class MeasurementInvestigation:
    def __init__(self):
        self.results = []
        
    def test_ksi_async_timing(self):
        """Test what we're actually measuring with KSI async calls"""
        
        print("=== MEASUREMENT METHODOLOGY INVESTIGATION ===\n")
        
        # Test 1: KSI async (returns immediately)
        print("Test 1: KSI completion:async (returns immediately)")
        agent_id = f"test_async_{datetime.now().strftime('%H%M%S')}"
        
        start = time.perf_counter()
        result = subprocess.run([
            "ksi", "send", "completion:async",
            "--agent-id", agent_id,
            "--prompt", "Calculate: 45 + 23 - 11"
        ], capture_output=True, text=True)
        end = time.perf_counter()
        
        print(f"  Time: {(end-start)*1000:.1f}ms")
        print(f"  This measures: KSI infrastructure + request queuing")
        print(f"  NOT measuring: Actual LLM processing time\n")
        
        # Test 2: Check completion status (shows actual processing)
        print("Test 2: Check completion status after async call")
        time.sleep(2)  # Wait for processing
        
        status_result = subprocess.run([
            "ksi", "send", "completion:status",
            "--request-id", agent_id
        ], capture_output=True, text=True)
        
        print(f"  Status check shows if processing is complete")
        print(f"  Our original experiments likely used synchronous calls\n")
        
        # Test 3: Monitor events to see actual completion time
        print("Test 3: Check monitor for actual completion events")
        
        monitor_result = subprocess.run([
            "ksi", "send", "monitor:get_events",
            "--limit", "5",
            "--event-patterns", "completion:result"
        ], capture_output=True, text=True)
        
        try:
            events = json.loads(monitor_result.stdout)
            if events.get('events'):
                latest = events['events'][0]
                if 'duration_ms' in str(latest):
                    print(f"  Found completion with actual duration in monitor")
                    print(f"  This is what we should be measuring!\n")
        except:
            pass
        
        # Test 4: Direct Python measurement with proper completion waiting
        print("Test 4: Proper measurement methodology")
        print("  1. Send async request")
        print("  2. Poll for completion")
        print("  3. Extract duration_ms from result")
        print("  4. This gives actual LLM processing time\n")
        
        return self.analyze_original_methodology()
    
    def analyze_original_methodology(self):
        """Analyze what the original experiments were measuring"""
        
        print("=== ORIGINAL EXPERIMENT ANALYSIS ===\n")
        
        print("Original 10-round experiment results:")
        print("  Baseline (R1-3): 3.7s average")
        print("  Consciousness (R4-6): 7.4s average")
        print("  Multi-task (R7-9): 11.4s average\n")
        
        print("These times are 20-75x longer than our pilot results!")
        print("This suggests original measurements included:")
        print("  - Actual LLM processing time")
        print("  - Full response generation")
        print("  - Possibly synchronous completion\n")
        
        print("Our pilot measured:")
        print("  - Only KSI async request submission time (~150ms)")
        print("  - NOT actual processing time")
        print("  - Results are meaningless for cognitive overhead\n")
        
        print("CONCLUSION:")
        print("  ❌ Pilot methodology is wrong")
        print("  ❌ We're not measuring what we think we're measuring")
        print("  ✅ Need to extract duration_ms from completion:result events")
        print("  ✅ Or use synchronous calls that wait for completion")
        
        return True
    
    def find_actual_durations(self):
        """Extract actual processing durations from monitor events"""
        
        print("\n=== EXTRACTING ACTUAL DURATIONS ===\n")
        
        # Get recent completion events
        result = subprocess.run([
            "ksi", "send", "monitor:get_events",
            "--limit", "50",
            "--event-patterns", "completion:result",
            "--since", str(int(time.time() - 3600))  # Last hour
        ], capture_output=True, text=True)
        
        try:
            data = json.loads(result.stdout)
            events = data.get('events', [])
            
            durations = []
            for event in events:
                result_data = event.get('data', {}).get('result', {})
                ksi_data = result_data.get('ksi', {})
                duration_ms = ksi_data.get('duration_ms')
                
                if duration_ms:
                    agent_id = ksi_data.get('agent_id', 'unknown')
                    if 'pilot_' in agent_id:
                        condition = agent_id.split('_')[1]
                        durations.append({
                            'condition': condition,
                            'duration_ms': duration_ms,
                            'agent_id': agent_id
                        })
            
            if durations:
                print(f"Found {len(durations)} actual completion durations:")
                
                # Group by condition
                by_condition = {}
                for d in durations:
                    cond = d['condition']
                    if cond not in by_condition:
                        by_condition[cond] = []
                    by_condition[cond].append(d['duration_ms'])
                
                # Calculate averages
                baseline_avg = 0
                for condition, times in by_condition.items():
                    avg = sum(times) / len(times) if times else 0
                    if condition == 'baseline':
                        baseline_avg = avg
                    
                print(f"\nActual processing times by condition:")
                for condition, times in sorted(by_condition.items()):
                    if times:
                        avg = sum(times) / len(times)
                        overhead = avg / baseline_avg if baseline_avg > 0 else 1.0
                        print(f"  {condition}: {avg:.0f}ms ({overhead:.2f}x overhead)")
                
                print("\nThese are the REAL measurements we should analyze!")
            else:
                print("No pilot experiment durations found in monitor")
                print("The completion:async calls don't wait for results")
                
        except Exception as e:
            print(f"Error parsing monitor data: {e}")

def main():
    investigator = MeasurementInvestigation()
    investigator.test_ksi_async_timing()
    investigator.find_actual_durations()
    
    print("\n" + "=" * 60)
    print("CRITICAL FINDING:")
    print("=" * 60)
    print("Our pilot experiment methodology is fundamentally flawed!")
    print("We measured request submission time, not processing time.")
    print("Need to redesign experiment to measure actual LLM computation.")

if __name__ == "__main__":
    main()