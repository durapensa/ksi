#!/usr/bin/env python3
"""
Simple test of completion system to verify claude-cli provider is working.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.ksi_socket_utils import KSISocketClient

def test_simple_completion():
    """Test a simple completion."""
    client = KSISocketClient()
    
    # Test basic completion
    result = client.send_command({
        "event": "completion:async",
        "data": {
            "prompt": "Say 'OK' if you can hear me.",
            "model": "claude-cli/sonnet"
        }
    })
    
    print(f"Result: {result}")
    
    if result.get('data', {}).get('request_id'):
        print(f"✓ Got request_id: {result['data']['request_id']}")
    else:
        print(f"✗ No request_id in response")

if __name__ == "__main__":
    test_simple_completion()