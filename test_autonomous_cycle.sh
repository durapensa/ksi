#!/bin/bash
# Test the complete autonomous improvement cycle

set -e

echo "=== Testing Autonomous Improvement Cycle ==="
echo "This will:"
echo "1. Bootstrap judge variations"
echo "2. Run tournament to evaluate them"
echo "3. Select best performers"
echo "4. Save results for deployment"
echo ""

# Run the autonomous improvement cycle
echo '{"event": "evaluation:autonomous_improvement_cycle", "data": {"test_suite": "judge_ground_truth", "num_variations": 2, "tournament_config": {"match_timeout": 60, "parallel_matches": 2}, "auto_deploy": false}}' | nc -U var/run/daemon.sock | jq

echo ""
echo "Monitor progress with:"
echo "  tail -f var/logs/daemon/daemon.log.jsonl | grep -E '(autonomous|bootstrap|tournament)'"
echo ""
echo "Check results in:"
echo "  ls -la var/lib/evaluations/autonomous_cycles/"