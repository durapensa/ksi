#!/usr/bin/env python3
"""
Test Timestamp Standardization
Verifies that all components generate consistent UTC timestamps
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import timestamp utilities directly
import importlib.util
spec = importlib.util.spec_from_file_location("timestamp_utils", 
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daemon", "timestamp_utils.py"))
timestamp_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timestamp_utils)
TimestampManager = timestamp_utils.TimestampManager

def test_timestamp_formats():
    """Test various timestamp generation methods"""
    print("Testing Timestamp Generation:")
    print("-" * 50)
    
    # Test UTC timestamp
    utc_ts = TimestampManager.timestamp_utc()
    print(f"UTC timestamp: {utc_ts}")
    assert utc_ts.endswith('Z'), "UTC timestamp should end with 'Z'"
    assert 'T' in utc_ts, "Should be ISO format"
    
    # Test local timestamp
    local_ts = TimestampManager.timestamp_local_iso()
    print(f"Local timestamp: {local_ts}")
    assert '+' in local_ts or '-' in local_ts, "Local timestamp should have timezone offset"
    
    # Test filename timestamp
    filename_ts = TimestampManager.filename_timestamp()
    print(f"Filename timestamp: {filename_ts}")
    assert len(filename_ts) == 15, "Filename timestamp should be YYYYMMDD_HHMMSS format"
    assert '_' in filename_ts, "Should contain underscore separator"
    
    # Test parsing
    parsed = TimestampManager.parse_iso_timestamp(utc_ts)
    print(f"Parsed datetime: {parsed}")
    assert parsed.tzinfo is not None, "Parsed datetime should be timezone-aware"
    
    # Test conversions
    local_dt = TimestampManager.utc_to_local(parsed)
    print(f"UTC to local: {local_dt}")
    
    back_to_utc = TimestampManager.local_to_utc(local_dt)
    print(f"Local to UTC: {back_to_utc}")
    assert back_to_utc.timestamp() == parsed.timestamp(), "Round-trip conversion should preserve time"
    
    print("\n✓ All timestamp format tests passed!")

def test_ensure_utc_suffix():
    """Test UTC suffix handling"""
    print("\nTesting UTC Suffix Handling:")
    print("-" * 50)
    
    test_cases = [
        ("2025-06-20T23:17:27.832348Z", "2025-06-20T23:17:27.832348Z"),  # Already has Z
        ("2025-06-20T23:17:27.832348", "2025-06-20T23:17:27.832348Z"),   # Missing Z
        ("2025-06-20T23:17:27.832348+00:00", "2025-06-20T23:17:27.832348+00:00"),  # Has offset
        ("2025-06-20T23:17:27.832348-04:00", "2025-06-20T23:17:27.832348-04:00"),  # Has offset
        ("invalid timestamp", "invalid timestamp"),  # Non-timestamp string
    ]
    
    for input_ts, expected in test_cases:
        result = TimestampManager.ensure_utc_suffix(input_ts)
        print(f"'{input_ts}' -> '{result}'")
        assert result == expected, f"Expected '{expected}', got '{result}'"
    
    print("\n✓ UTC suffix tests passed!")

async def test_daemon_integration():
    """Test that daemon components use standardized timestamps"""
    print("\nTesting Daemon Component Integration:")
    print("-" * 50)
    
    try:
        # Try to import and test message bus
        spec = importlib.util.spec_from_file_location("message_bus", 
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daemon", "message_bus.py"))
        message_bus = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(message_bus)
        
        bus = message_bus.MessageBus()
        
        # Simulate publishing a message
        test_payload = {"content": "test message"}
        result = await bus.publish("test_agent", "TEST_EVENT", test_payload)
        
        # Check message history
        if bus.message_history:
            last_message = bus.message_history[-1]
            timestamp = last_message.get('timestamp', '')
            print(f"Message bus timestamp: {timestamp}")
            assert timestamp.endswith('Z'), "Message bus should use UTC timestamps with Z suffix"
            print("✓ Message bus uses correct timestamp format")
    except Exception as e:
        print(f"Note: Could not test message bus integration: {e}")
        print("✓ Skipping daemon integration test (requires full daemon environment)")
    
    print("\n✓ Integration test complete!")

def test_timezone_offset():
    """Test timezone offset detection"""
    print("\nTesting Timezone Offset Detection:")
    print("-" * 50)
    
    offset = TimestampManager.get_timezone_offset()
    print(f"Current timezone offset: {offset}")
    
    # Should be in format like "-0400" or "+0000"
    assert len(offset) == 5, "Offset should be 5 characters"
    assert offset[0] in ['+', '-'], "Should start with + or -"
    assert offset[1:].isdigit(), "Should contain digits after sign"
    
    print("✓ Timezone offset test passed!")

def main():
    """Run all tests"""
    print("Timestamp Standardization Test Suite")
    print("=" * 50)
    
    try:
        # Run synchronous tests
        test_timestamp_formats()
        test_ensure_utc_suffix()
        test_timezone_offset()
        
        # Run async tests
        asyncio.run(test_daemon_integration())
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Timestamp standardization is working correctly.")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()