#!/bin/bash
# Complete tournament test with all fixes

set -e

echo "=== Complete Tournament Test with Real Evaluation ==="
echo "This test includes:"
echo "- Fixed base profile with KSI agent context"
echo "- Fixed tournament evaluation prompts"
echo "- Real evaluation logic with metadata tracking"
echo ""

# Step 1: Spawn diverse judge agents
echo "Step 1: Spawning judge agents..."

AGENTS=()

# Evaluator judges
echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge", "purpose": "Tournament evaluator 1"}}' | nc -U var/run/daemon.sock > agent1.json
AGENT1=$(jq -r '.data.agent_id' agent1.json)
AGENTS+=($AGENT1)
echo "  Evaluator judge: $AGENT1"

echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge_detailed_rubric", "purpose": "Tournament evaluator 2"}}' | nc -U var/run/daemon.sock > agent2.json
AGENT2=$(jq -r '.data.agent_id' agent2.json)
AGENTS+=($AGENT2)
echo "  Detailed evaluator: $AGENT2"

# Analyst judges
echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge", "purpose": "Tournament analyst 1"}}' | nc -U var/run/daemon.sock > agent3.json
AGENT3=$(jq -r '.data.agent_id' agent3.json)
AGENTS+=($AGENT3)
echo "  Analyst judge: $AGENT3"

# Rewriter judge
echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge", "purpose": "Tournament rewriter 1"}}' | nc -U var/run/daemon.sock > agent4.json
AGENT4=$(jq -r '.data.agent_id' agent4.json)
AGENTS+=($AGENT4)
echo "  Rewriter judge: $AGENT4"

sleep 3

# Step 2: Create tournament
TOURNAMENT_ID="complete_test_$(date +%Y%m%d_%H%M%S)"
echo -e "\nStep 2: Creating tournament $TOURNAMENT_ID..."

echo "{\"event\": \"tournament:create\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"config\": {\"participants\": [], \"rounds\": 1, \"match_timeout\": 120, \"min_participants\": 3, \"test_cases_per_match\": 1, \"parallel_matches\": 2}, \"auto_start\": false}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

# Step 3: Start registration
echo -e "\nStep 3: Opening registration..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"registration\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

sleep 1

# Step 4: Register agents
echo -e "\nStep 4: Registering ${#AGENTS[@]} agents..."
for i in "${!AGENTS[@]}"; do
    agent="${AGENTS[$i]}"
    # Determine role based on index
    if [ $i -lt 2 ]; then
        role="evaluator"
    elif [ $i -eq 2 ]; then
        role="analyst"
    else
        role="rewriter"
    fi
    
    echo "  Registering $agent as $role..."
    echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$agent\", \"role\": \"$role\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'
done

sleep 2

# Step 5: Start round-robin
echo -e "\nStep 5: Starting round-robin phase..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"round_robin\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

echo -e "\n=== Tournament Running ==="
echo "Tournament ID: $TOURNAMENT_ID"
echo "Participants: ${#AGENTS[@]} judges (2 evaluators, 1 analyst, 1 rewriter)"
echo ""
echo "Monitor real evaluations:"
echo "  tail -f var/logs/daemon/daemon.log | grep -E '(tournament_evaluation|match.*complete|Processed tournament)'"
echo ""
echo "Check specific agent responses:"
echo "  ls -lat var/logs/responses/*.jsonl | head -5"
echo ""
echo "Watch for completion:"
echo "  while true; do grep -c \"Match.*complete\" var/logs/daemon/daemon.log; sleep 5; done"
echo ""
echo "When matches complete, finalize:"
echo "  echo '{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"finalize\"}}' | nc -U var/run/daemon.sock"
echo ""
echo "Results will be in:"
echo "  cat var/lib/evaluations/tournament_${TOURNAMENT_ID}_results.yaml"