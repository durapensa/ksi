#!/usr/bin/env python3
"""
Monitor long-running orchestrations with patient polling and subprocess tracking.
"""
import asyncio
import json
import subprocess
import time
from datetime import datetime
from ksi_client import EventClient


async def monitor_orchestration(orchestration_id: str, timeout: int = 1200):
    """Monitor an orchestration with subprocess tracking.
    
    Args:
        orchestration_id: The orchestration ID to monitor
        timeout: Maximum time to wait in seconds (default: 20 minutes)
    """
    start_time = time.time()
    poll_interval = 5  # Start with 5 second polls
    
    async with EventClient() as client:
        print(f"Monitoring orchestration: {orchestration_id}")
        print(f"Timeout: {timeout}s ({timeout/60:.1f} minutes)")
        print("-" * 60)
        
        while time.time() - start_time < timeout:
            # Check for Claude subprocesses
            try:
                ps_output = subprocess.check_output(
                    ["ps", "aux"], 
                    text=True
                )
                claude_procs = [
                    line for line in ps_output.split('\n') 
                    if 'claude' in line and '??' in line and 'grep' not in line
                ]
                
                if claude_procs:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Active Claude processes:")
                    for proc in claude_procs:
                        parts = proc.split()
                        if len(parts) > 10:
                            pid = parts[1]
                            cpu = parts[2]
                            cmd = ' '.join(parts[10:])
                            print(f"  PID {pid} (CPU: {cpu}%): {cmd[:80]}...")
                
            except Exception as e:
                print(f"Process check error: {e}")
            
            # Check orchestration events
            try:
                # Get recent events
                events = await client.send_all("monitor:get_events", {
                    "event_patterns": ["orchestration:track", "completion:result", "agent:spawn"],
                    "limit": 10,
                    "since": start_time
                })
                
                # Filter for our orchestration
                our_events = []
                for event_data in events:
                    if 'events' in event_data:
                        for evt in event_data['events']:
                            data = evt.get('data', {})
                            # Check various ID fields
                            if (orchestration_id in str(data.get('orchestration_id', '')) or
                                orchestration_id in str(data.get('agent_id', '')) or
                                orchestration_id in str(data.get('request_id', '')) or
                                orchestration_id in str(data.get('_agent_id', ''))):
                                our_events.append(evt)
                
                # Display new events
                for evt in our_events[-3:]:  # Show last 3 relevant events
                    timestamp = datetime.fromtimestamp(evt['timestamp']).strftime('%H:%M:%S')
                    event_name = evt['event_name']
                    data_summary = str(evt.get('data', {}))[:100]
                    print(f"[{timestamp}] {event_name}: {data_summary}...")
                
                # Check for completion
                for evt in our_events:
                    if evt['event_name'] == 'orchestration:track':
                        data = evt.get('data', {})
                        if data.get('stage') == 'complete' or data.get('phase') == 'complete':
                            print(f"\n✓ Orchestration completed!")
                            print(f"Result: {json.dumps(data, indent=2)}")
                            return data
                    
                    if evt['event_name'] == 'completion:result':
                        data = evt.get('data', {})
                        if 'result' in data:
                            result = data['result']
                            if isinstance(result, dict) and result.get('response', {}).get('result'):
                                print(f"\n✓ Agent completed response")
                                print(f"Result preview: {result['response']['result'][:200]}...")
                
            except Exception as e:
                print(f"Event check error: {e}")
            
            # Adaptive polling - slow down after first minute
            if time.time() - start_time > 60:
                poll_interval = min(poll_interval + 5, 30)  # Max 30s polls
            
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Waiting... (poll interval: {poll_interval}s)", end='', flush=True)
            await asyncio.sleep(poll_interval)
        
        print(f"\n\n⏱️  Timeout reached after {timeout}s")
        return None


async def start_and_monitor(pattern: str, vars: dict = None, timeout: int = 600):
    """Start an orchestration and monitor it."""
    async with EventClient() as client:
        # Start orchestration
        start_data = {"pattern": pattern}
        if vars:
            start_data["vars"] = vars
            
        result = await client.send_single("orchestration:start", start_data)
        orchestration_id = result.get('orchestration_id')
        
        if not orchestration_id:
            print(f"Failed to start orchestration: {result}")
            return None
        
        print(f"Started orchestration: {orchestration_id}")
        print(f"Pattern: {pattern}")
        print(f"Agents: {result.get('agents', [])}")
        
        # Monitor it
        return await monitor_orchestration(orchestration_id, timeout)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python monitor_orchestration.py <orchestration_id>")
        print("   or: python monitor_orchestration.py start <pattern> [timeout_seconds]")
        sys.exit(1)
    
    if sys.argv[1] == "start" and len(sys.argv) >= 3:
        pattern = sys.argv[2]
        timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 600
        asyncio.run(start_and_monitor(pattern, timeout=timeout))
    else:
        orchestration_id = sys.argv[1]
        timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
        asyncio.run(monitor_orchestration(orchestration_id, timeout))