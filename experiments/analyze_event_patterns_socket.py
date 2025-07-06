#!/usr/bin/env python3
"""
Analyze event patterns in KSI using direct socket communication.
Demonstrates pattern mining, frequency analysis, and sequence detection.
"""

import json
import socket
import time
from datetime import datetime
from collections import Counter, defaultdict

def send_command(cmd):
    """Send command via Unix socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("var/run/daemon.sock")
    sock.sendall(json.dumps(cmd).encode() + b'\n')
    
    # Read response
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
        # Check if we have a complete JSON response
        try:
            json.loads(response.decode())
            break
        except:
            continue
    
    sock.close()
    return json.loads(response.decode())

def analyze_patterns():
    """Analyze event patterns using monitor:get_events."""
    
    print("=== KSI Event Pattern Analysis (Socket Version) ===\n")
    
    # 1. Query recent events
    print("1. Querying recent events...")
    
    # Get last hour of events
    since_timestamp = time.time() - 3600  # 1 hour ago
    
    result = send_command({
        "event": "monitor:get_events",
        "data": {
            "event_patterns": None,  # Get all events
            "since": since_timestamp,
            "limit": 1000,
            "reverse": True
        }
    })
    
    events = result.get("data", {}).get("events", [])
    print(f"✓ Found {len(events)} events in the last hour")
    
    if not events:
        print("\n⚠️  No events found. Generate some activity first.")
        return
    
    # 2. Analyze event frequency
    print("\n2. Event Frequency Analysis...")
    
    event_counts = Counter()
    originator_events = defaultdict(list)
    
    for event in events:
        event_name = event.get("event_name", "")
        originator = event.get("originator_id", "unknown")
        
        event_counts[event_name] += 1
        originator_events[originator].append(event_name)
    
    print("\nTop 10 Most Frequent Events:")
    for event_name, count in event_counts.most_common(10):
        print(f"  {event_name:40} {count:5} times")
    
    # 3. Analyze event sequences (n-grams)
    print("\n3. Event Sequence Analysis...")
    
    # Build sequences per originator
    bigrams = Counter()
    trigrams = Counter()
    
    for originator, events_list in originator_events.items():
        # Bigrams
        for i in range(len(events_list) - 1):
            bigram = (events_list[i], events_list[i + 1])
            bigrams[bigram] += 1
        
        # Trigrams
        for i in range(len(events_list) - 2):
            trigram = (events_list[i], events_list[i + 1], events_list[i + 2])
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
    
    for event in events:
        timestamp = event.get("timestamp", 0)
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
    
    # Look for completion events
    completion_events = []
    
    for event in events:
        event_name = event.get("event_name", "")
        if "completion" in event_name:
            completion_events.append(event)
    
    if completion_events:
        print(f"\nCompletion Events: {len(completion_events)}")
        completion_types = Counter()
        for event in completion_events:
            completion_types[event.get("event_name", "")] += 1
        
        for event_type, count in completion_types.most_common():
            print(f"  {event_type:30} {count:3} times")
    
    # 6. Error pattern analysis
    print("\n6. Error Pattern Analysis...")
    
    error_events = [e for e in events if "error" in e.get("event_name", "").lower()]
    
    if error_events:
        error_types = Counter()
        for event in error_events:
            error_types[event.get("event_name", "")] += 1
        
        print(f"\nTotal Errors: {len(error_events)}")
        print("Error Types:")
        for error_type, count in error_types.most_common():
            print(f"  {error_type:30} {count:3} times")
    else:
        print("\n✓ No errors found!")
    
    # 7. Agent activity patterns
    print("\n7. Agent Activity Patterns...")
    
    # Check current agents
    agent_result = send_command({"event": "agent:list", "data": {}})
    agents = agent_result.get("data", {}).get("agents", [])
    
    if agents:
        print(f"\nActive Agents: {len(agents)}")
        for agent in agents[:5]:  # Show first 5
            print(f"  • {agent['agent_id']} ({agent.get('profile', 'unknown')})")
    
    # Look for agent-related events
    agent_events = [e for e in events if "agent:" in e.get("event_name", "")]
    
    if agent_events:
        agent_event_types = Counter()
        for event in agent_events:
            agent_event_types[event.get("event_name", "")] += 1
        
        print(f"\nAgent Events: {len(agent_events)}")
        for event_type, count in agent_event_types.most_common(5):
            print(f"  {event_type:30} {count:3} times")
    
    # 8. Summary statistics
    print("\n=== Analysis Summary ===")
    print(f"• Total events analyzed: {len(events)}")
    print(f"• Unique event types: {len(event_counts)}")
    print(f"• Active originators: {len(originator_events)}")
    print(f"• Event sequences found: {len(bigrams)} bigrams, {len(trigrams)} trigrams")
    print(f"• Error rate: {len(error_events) / len(events) * 100:.1f}%")
    print(f"• Active agents: {len(agents)}")
    
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
    
    if len(originator_events) > 10:
        print("• High originator count - consider consolidation")

if __name__ == "__main__":
    # Ensure daemon is running
    print("Checking daemon status...")
    try:
        # Test connection
        result = send_command({"event": "system:health", "data": {}})
        if result.get("event") == "system:health":
            print("✓ Daemon is healthy\n")
            analyze_patterns()
        else:
            print("❌ Unexpected response from daemon")
    except ConnectionError:
        print("\n❌ Error: KSI daemon is not running")
        print("Start it with: ./daemon_control.py start")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()