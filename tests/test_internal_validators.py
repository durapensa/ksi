#!/usr/bin/env python3
"""
Internal Validator Test Suite
=============================

Comprehensive tests for Melting Pot validators using KSI's internal testing framework.
Tests movement, resource, and interaction validation through events.
"""

import json
import time
from ksi_common.sync_client import MinimalSyncClient

def run_comprehensive_test_suite():
    """Run full internal test suite for validators."""
    client = MinimalSyncClient()
    
    # Create test suite
    print("\n=== Creating Test Suite ===")
    suite_response = client.send_event("testing:suite:create", {
        "suite_name": "Comprehensive Validator Tests",
        "metadata": {
            "test_type": "internal",
            "framework": "melting_pot",
            "version": "1.0.0"
        }
    })
    suite_id = suite_response.get("suite_id")
    print(f"Created suite: {suite_id}")
    
    # Test cases with test framework
    test_cases = [
        # Movement validation tests
        {
            "test_name": "Movement - Valid Walk",
            "test_function": "validator:movement:validate",
            "test_args": {
                "from_x": 0.0,
                "from_y": 0.0,
                "to_x": 5.0,
                "to_y": 5.0,
                "movement_type": "walk",
                "entity_capacity": 10.0
            }
        },
        {
            "test_name": "Movement - Invalid Run Distance",
            "test_function": "validator:movement:validate",
            "test_args": {
                "from_x": 0.0,
                "from_y": 0.0,
                "to_x": 50.0,
                "to_y": 50.0,
                "movement_type": "run",
                "entity_capacity": 5.0
            }
        },
        # Resource validation tests
        {
            "test_name": "Resource - Setup Initial Ownership",
            "test_function": "validator:resource:update_ownership",
            "test_args": {
                "entity": "agent_1",
                "resource_type": "gold",
                "amount": 100.0
            }
        },
        {
            "test_name": "Resource - Valid Trade",
            "test_function": "validator:resource:validate",
            "test_args": {
                "from_entity": "agent_1",
                "to_entity": "agent_2",
                "resource_type": "gold",
                "amount": 25.0,
                "transfer_type": "trade"
            }
        },
        {
            "test_name": "Resource - Invalid Transfer (Insufficient)",
            "test_function": "validator:resource:validate",
            "test_args": {
                "from_entity": "agent_2",
                "to_entity": "agent_1",
                "resource_type": "gold",
                "amount": 200.0,
                "transfer_type": "trade"
            }
        },
        # Interaction validation tests
        {
            "test_name": "Interaction - Valid Cooperation",
            "test_function": "validator:interaction:validate",
            "test_args": {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "cooperate",
                "actor_x": 0.0,
                "actor_y": 0.0,
                "target_x": 1.0,
                "target_y": 1.0,
                "range_limit": 5.0,
                "capabilities": ["cooperate"]
            }
        },
        {
            "test_name": "Interaction - Invalid (Out of Range)",
            "test_function": "validator:interaction:validate",
            "test_args": {
                "actor_id": "agent_1",
                "target_id": "agent_3",
                "interaction_type": "cooperate",
                "actor_x": 0.0,
                "actor_y": 0.0,
                "target_x": 100.0,
                "target_y": 100.0,
                "range_limit": 5.0,
                "capabilities": ["cooperate"]
            }
        }
    ]
    
    # Run tests through testing framework
    print("\n=== Running Tests ===")
    for test_case in test_cases:
        print(f"\nRunning: {test_case['test_name']}")
        
        result = client.send_event("testing:run:test", {
            "test_name": test_case["test_name"],
            "test_function": test_case["test_function"],
            "test_args": test_case["test_args"],
            "suite_id": suite_id
        })
        
        if result.get("passed"):
            print(f"  ✓ PASSED (duration: {result.get('duration', 0):.3f}s)")
        else:
            print(f"  ✗ FAILED: {result.get('error', 'Unknown error')}")
        
        # Print details if available
        details = result.get("details", {})
        if details and details != {"result": None}:
            if "valid" in details:
                print(f"    Valid: {details['valid']}")
            if "reason" in details:
                print(f"    Reason: {details['reason']}")
            if "actual_distance" in details:
                print(f"    Distance: {details['actual_distance']:.2f}")
            if "path_cost" in details:
                print(f"    Cost: {details['path_cost']:.2f}")
    
    # Finish suite and get report
    print("\n=== Finishing Test Suite ===")
    report = client.send_event("testing:suite:finish", {
        "suite_id": suite_id
    })
    
    print(f"\nTest Results Summary:")
    print(f"  Total Tests: {len(report.get('tests', []))}")
    print(f"  Passed: {report.get('passed', 0)}")
    print(f"  Failed: {report.get('failed', 0)}")
    print(f"  Pass Rate: {report.get('pass_rate', 0)*100:.1f}%")
    print(f"  Duration: {report.get('duration', 0):.3f}s")
    
    # Run assertions directly for comparison
    print("\n=== Direct Assertion Tests ===")
    
    # Test equals assertion
    assert_result = client.send_event("testing:assert:equals", {
        "expected": 5.0,
        "actual": 5.0,
        "test_name": "Assert Equals - Same Values",
        "suite_id": suite_id
    })
    print(f"Assert Equals: {'✓' if assert_result.get('passed') else '✗'}")
    
    # Test in-range assertion
    range_result = client.send_event("testing:assert:in_range", {
        "value": 7.5,
        "min_value": 5.0,
        "max_value": 10.0,
        "test_name": "Assert In Range - Valid",
        "suite_id": suite_id
    })
    print(f"Assert In Range: {'✓' if range_result.get('passed') else '✗'}")
    
    # Generate final report
    print("\n=== Generating Final Report ===")
    final_report = client.send_event("testing:report:generate", {
        "suite_ids": [suite_id],
        "save_to_file": True
    })
    
    if "report_file" in final_report:
        print(f"Report saved to: {final_report['report_file']}")
    
    print(f"\nFinal Summary:")
    summary = final_report.get("summary", {})
    print(f"  Total Suites: {summary.get('total_suites', 0)}")
    print(f"  Total Tests: {summary.get('total_tests', 0)}")
    print(f"  Total Passed: {summary.get('total_passed', 0)}")
    print(f"  Total Failed: {summary.get('total_failed', 0)}")
    print(f"  Overall Pass Rate: {summary.get('overall_pass_rate', 0)*100:.1f}%")

if __name__ == "__main__":
    run_comprehensive_test_suite()