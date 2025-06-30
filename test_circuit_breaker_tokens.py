#!/usr/bin/env python3
"""
Test circuit breaker token estimation improvements.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_daemon.plugins.injection.circuit_breakers import estimate_tokens, get_circuit_breaker_status

def test_token_estimation():
    """Test improved token estimation function."""
    
    print("Testing token estimation improvements...")
    
    test_cases = [
        ("", 1),  # Empty string should return 1
        ("   ", 1),  # Whitespace should return 1
        ("Hello", 1),  # Single word
        ("Hello world", 2),  # Two words
        ("This is a test sentence with multiple words.", 10),  # Longer text
        ("A" * 100, 25),  # 100 characters should be ~25 tokens
        ("Word " * 50, 65),  # 50 words should be ~65 tokens
    ]
    
    all_passed = True
    
    for text, expected_min in test_cases:
        result = estimate_tokens(text)
        
        print(f"Text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        print(f"  Length: {len(text)} chars, {len(text.split())} words")
        print(f"  Estimated tokens: {result}")
        print(f"  Expected minimum: {expected_min}")
        
        if result >= expected_min and result > 0:
            print("  ✓ PASS")
        else:
            print(f"  ✗ FAIL: Expected >= {expected_min}, got {result}")
            all_passed = False
        print()
    
    return all_passed

def test_circuit_breaker_status():
    """Test that circuit breaker status returns non-zero tokens."""
    
    print("Testing circuit breaker status...")
    
    # Test with no parent (should return default values)
    status = get_circuit_breaker_status(None)
    
    print("Default status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Verify tokens_used is 0 initially (which is correct)
    if status['tokens_used'] == 0 and status['token_budget'] > 0:
        print("  ✓ PASS: Default status has correct token values")
        return True
    else:
        print("  ✗ FAIL: Unexpected token values in status")
        return False

if __name__ == "__main__":
    print("Circuit Breaker Token Estimation Test")
    print("=" * 50)
    
    test1_passed = test_token_estimation()
    test2_passed = test_circuit_breaker_status()
    
    print("=" * 50)
    if test1_passed and test2_passed:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)