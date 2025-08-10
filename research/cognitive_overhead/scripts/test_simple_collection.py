#!/usr/bin/env python3
"""
Simple test script to verify data collection pipeline
"""

import json
import time
import subprocess
import sys

def test_single_completion():
    """Test a single completion request"""
    
    print("Testing single completion...")
    
    # Send completion request
    cmd = ["ksi", "send", "completion:async", "--prompt", "Calculate: 5+3"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"Command output: {result.stdout}")
    
    # Parse response
    try:
        response = json.loads(result.stdout)
        request_id = response.get('request_id')
        print(f"Request ID: {request_id}")
    except Exception as e:
        print(f"Failed to parse: {e}")
        return False
    
    # Wait for completion
    print("Waiting 15 seconds for completion...")
    time.sleep(15)
    
    # Get result
    monitor_cmd = ["ksi", "send", "monitor:get_events", "--limit", "10", "--event-patterns", "completion:result"]
    monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
    
    try:
        events_data = json.loads(monitor_result.stdout)
        events = events_data.get('events', [])
        
        print(f"Found {len(events)} completion events")
        
        # Find our completion
        for event in events:
            event_data = event.get('data', {})
            result_data = event_data.get('result', {})
            ksi_info = result_data.get('ksi', {})
            
            if ksi_info.get('request_id') == request_id:
                response_data = result_data.get('response', {})
                response_text = response_data.get('result', '')
                tokens = response_data.get('usage', {}).get('output_tokens', 0)
                
                print(f"✓ Found our completion!")
                print(f"  Response: {response_text[:100]}")
                print(f"  Tokens: {tokens}")
                return True
        
        print("✗ Completion not found in events")
        return False
        
    except Exception as e:
        print(f"Failed to get events: {e}")
        return False

if __name__ == "__main__":
    success = test_single_completion()
    sys.exit(0 if success else 1)