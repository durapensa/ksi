#!/usr/bin/env python3
"""
Launch Agent-Based Test Orchestration
======================================

Spawns test coordinator and tester agents to run Melting Pot validator tests.
"""

import json
import time
from ksi_common.sync_client import MinimalSyncClient

def launch_test_orchestration():
    """Launch the agent-based test orchestration workflow."""
    client = MinimalSyncClient()
    
    print("\n=== Launching Agent-Based Test Orchestration ===\n")
    
    # Create the workflow
    workflow_config = {
        "workflow_id": "melting_pot_tests",
        "component": "workflows/melting_pot_test_orchestration",
        "vars": {
            "test_run_id": f"test_run_{int(time.time())}",
            "test_scope": "comprehensive"
        }
    }
    
    print("Creating workflow...")
    response = client.send_event("workflow:create", workflow_config)
    
    if response.get("error"):
        print(f"Error creating workflow: {response['error']}")
        return
    
    print(f"Workflow created: {response.get('workflow_id')}")
    print(f"Agents spawned: {response.get('agents_spawned', [])}")
    
    # Monitor the test execution
    print("\n=== Monitoring Test Execution ===")
    print("Agents are now running tests autonomously...")
    print("Check daemon logs for detailed test execution")
    print("Use 'ksi send monitor:get_events --event-patterns \"testing:*\"' to see test events")
    
    # Wait a bit for tests to complete
    time.sleep(5)
    
    # Get the latest test report
    print("\n=== Fetching Test Report ===")
    report = client.send_event("testing:report:get", {})
    
    if report:
        summary = report.get("summary", {})
        print(f"\nTest Summary:")
        print(f"  Total Tests: {summary.get('total_tests', 0)}")
        print(f"  Passed: {summary.get('total_passed', 0)}")
        print(f"  Failed: {summary.get('total_failed', 0)}")
        print(f"  Pass Rate: {summary.get('overall_pass_rate', 0)*100:.1f}%")
    
    print("\n=== Test Orchestration Complete ===")

if __name__ == "__main__":
    launch_test_orchestration()