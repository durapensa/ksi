#!/usr/bin/env python3
"""
Analyze event patterns in KSI using existing observation capabilities.
Demonstrates pattern mining, frequency analysis, and sequence detection.
"""

import asyncio
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import EventClient

async def analyze_patterns():
    """Analyze event patterns using observation history."""
    
    async with EventClient() as client:
        print("=== KSI Event Pattern Analysis ===\n")
        
        # 1. Query recent observation history
        print("1. Querying observation history...")
        
        # Get last hour of observations
        history = await client.send_single("observation:query_history", {
            "limit": 1000,
            "include_data": True
        })
        
        observations = history.get("observations", [])
        print(f"✓ Found {len(observations)} observations")
        
        if not observations:
            print("\n⚠️  No observations found. Run test_agent_network.py first to generate data.")
            return
        
        # 2. Analyze event frequency
        print("\n2. Event Frequency Analysis...")
        
        event_counts = Counter()
        originator_events = defaultdict(list)
        
        for obs in observations:
            event_name = obs.get("event_name", "")
            originator = obs.get("originator_id", "unknown")
            
            event_counts[event_name] += 1
            originator_events[originator].append(event_name)
        
        print("\nTop 10 Most Frequent Events:")
        for event, count in event_counts.most_common(10):
            print(f"  {event:40} {count:5} times")
        
        # 3. Analyze event sequences (n-grams)
        print("\n3. Event Sequence Analysis...")
        
        # Build sequences per originator
        bigrams = Counter()
        trigrams = Counter()
        
        for originator, events in originator_events.items():
            # Bigrams
            for i in range(len(events) - 1):
                bigram = (events[i], events[i + 1])
                bigrams[bigram] += 1
            
            # Trigrams
            for i in range(len(events) - 2):
                trigram = (events[i], events[i + 1], events[i + 2])
                trigrams[trigram] += 1
        
        print("\nTop 5 Event Bigrams (sequences of 2):")
        for bigram, count in bigrams.most_common(5):
            print(f"  {' → '.join(bigram):60} {count:3} times")
        
        print("\nTop 5 Event Trigrams (sequences of 3):")
        for trigram, count in trigrams.most_common(5):
            print(f"  {' → '.join(trigram):80} {count:3} times")
        
        # 4. Analyze timing patterns
        print("\n4. Timing Pattern Analysis...")
        
        # Group by hour
        hourly_events = defaultdict(int)
        
        for obs in observations:
            timestamp = obs.get("timestamp", 0)
            if timestamp:
                hour = datetime.fromtimestamp(timestamp).hour
                hourly_events[hour] += 1
        
        if hourly_events:
            print("\nEvents by Hour:")
            for hour in sorted(hourly_events.keys()):
                bar = "█" * (hourly_events[hour] // 5)
                print(f"  {hour:02d}:00  {bar} {hourly_events[hour]}")
        
        # 5. Analyze performance patterns
        print("\n5. Performance Pattern Analysis...")
        
        # Look for paired begin/end events
        performance_pairs = []
        begin_events = {}
        
        for obs in observations:
            event_name = obs.get("event_name", "")
            originator = obs.get("originator_id", "")
            timestamp = obs.get("timestamp", 0)
            
            if event_name == "observe:begin":
                key = originator
                begin_events[key] = timestamp
                
            elif event_name == "observe:end" and originator in begin_events:
                duration = timestamp - begin_events[originator]
                performance_pairs.append({
                    "originator": originator,
                    "duration": duration
                })
                del begin_events[originator]
        
        if performance_pairs:
            durations = [p["duration"] for p in performance_pairs]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            
            print(f"\nTask Completion Times:")
            print(f"  Average: {avg_duration:.2f}s")
            print(f"  Min:     {min_duration:.2f}s")
            print(f"  Max:     {max_duration:.2f}s")
        
        # 6. Error pattern analysis
        print("\n6. Error Pattern Analysis...")
        
        error_events = [obs for obs in observations if "error" in obs.get("event_name", "").lower()]
        
        if error_events:
            error_types = Counter()
            for obs in error_events:
                error_type = obs.get("data", {}).get("error_type", "unknown")
                error_types[error_type] += 1
            
            print(f"\nTotal Errors: {len(error_events)}")
            print("Error Types:")
            for error_type, count in error_types.most_common():
                print(f"  {error_type:30} {count:3} times")
        else:
            print("\n✓ No errors found!")
        
        # 7. Agent collaboration patterns
        print("\n7. Agent Collaboration Patterns...")
        
        # Look for message passing between agents
        agent_interactions = defaultdict(lambda: defaultdict(int))
        
        for obs in observations:
            if obs.get("event_name") == "message:publish":
                data = obs.get("data", {})
                from_agent = obs.get("originator_id", "")
                to_topic = data.get("topic", "")
                agent_interactions[from_agent][to_topic] += 1
        
        if agent_interactions:
            print("\nAgent Message Publishing:")
            for agent, topics in agent_interactions.items():
                print(f"\n  Agent: {agent}")
                for topic, count in topics.items():
                    print(f"    → {topic}: {count} messages")
        
        # 8. Summary statistics
        print("\n=== Analysis Summary ===")
        print(f"• Total observations analyzed: {len(observations)}")
        print(f"• Unique event types: {len(event_counts)}")
        print(f"• Active originators: {len(originator_events)}")
        print(f"• Event sequences found: {len(bigrams)} bigrams, {len(trigrams)} trigrams")
        print(f"• Performance measurements: {len(performance_pairs)}")
        print(f"• Error rate: {len(error_events) / len(observations) * 100:.1f}%")
        
        # 9. Recommendations
        print("\n=== Pattern-Based Recommendations ===")
        
        # Check for optimization opportunities
        if event_counts.get("completion:retry", 0) > 5:
            print("• High retry rate detected - consider timeout adjustments")
        
        common_sequences = [seq for seq, count in bigrams.most_common(3) if count > 5]
        if common_sequences:
            print(f"• Common sequences detected - could optimize with workflows")
        
        if error_events:
            print("• Errors detected - implement error recovery patterns")
        
        if max_duration > avg_duration * 3:
            print("• High variance in completion times - investigate outliers")

if __name__ == "__main__":
    # Ensure daemon is running
    print("Checking daemon status...")
    try:
        asyncio.run(analyze_patterns())
    except ConnectionError:
        print("\n❌ Error: KSI daemon is not running")
        print("Start it with: ./daemon_control.py start")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)