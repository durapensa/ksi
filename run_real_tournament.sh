#!/bin/bash
# Run tournament with real evaluation logic

set -e

echo "=== Running Tournament with Real Evaluation Logic ==="

# Step 1: Spawn judge agents
echo "Step 1: Spawning judge agents..."

AGENTS=()

# Spawn 2 evaluator judges
echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge", "purpose": "Tournament evaluator 1"}}' | nc -U var/run/daemon.sock > agent1.json
AGENT1=$(jq -r '.data.agent_id' agent1.json)
AGENTS+=($AGENT1)
echo "  Spawned evaluator judge: $AGENT1"

echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge_detailed_rubric", "purpose": "Tournament evaluator 2"}}' | nc -U var/run/daemon.sock > agent2.json
AGENT2=$(jq -r '.data.agent_id' agent2.json)
AGENTS+=($AGENT2)
echo "  Spawned detailed evaluator: $AGENT2"

# Spawn 2 analyst judges
echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge", "purpose": "Tournament analyst 1"}}' | nc -U var/run/daemon.sock > agent3.json
AGENT3=$(jq -r '.data.agent_id' agent3.json)
AGENTS+=($AGENT3)
echo "  Spawned analyst judge: $AGENT3"

echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge_root_cause_focus", "purpose": "Tournament analyst 2"}}' | nc -U var/run/daemon.sock > agent4.json
AGENT4=$(jq -r '.data.agent_id' agent4.json)
AGENTS+=($AGENT4)
echo "  Spawned root cause analyst: $AGENT4"

sleep 2

# Step 2: Create tournament
TOURNAMENT_ID="real_eval_$(date +%Y%m%d_%H%M%S)"
echo -e "\nStep 2: Creating tournament $TOURNAMENT_ID..."

echo "{\"event\": \"tournament:create\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"config\": {\"participants\": [], \"rounds\": 1, \"match_timeout\": 90, \"min_participants\": 3, \"test_cases_per_match\": 1, \"parallel_matches\": 2}, \"auto_start\": false}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

# Step 3: Start registration
echo -e "\nStep 3: Opening registration phase..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"registration\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

sleep 1

# Step 4: Register agents
echo -e "\nStep 4: Registering agents..."
for agent in "${AGENTS[@]}"; do
    echo "  Registering $agent..."
    echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$agent\", \"role\": \"judge\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'
done

sleep 2

# Step 5: Start round-robin
echo -e "\nStep 5: Starting round-robin phase..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"round_robin\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

echo -e "\n=== Tournament Running ==="
echo "Tournament ID: $TOURNAMENT_ID"
echo "Participants: ${#AGENTS[@]} judges"
echo ""
echo "Monitor progress:"
echo "  tail -f var/logs/daemon/daemon.log | grep -E '($TOURNAMENT_ID|tournament_evaluation|match.*complete)'"
echo ""
echo "Check evaluation responses:"
echo "  grep 'tournament:evaluation_response' var/logs/daemon/daemon.log | tail"
echo ""
echo "Results will be saved to:"
echo "  var/lib/evaluations/tournament_${TOURNAMENT_ID}_results.yaml"
echo ""
echo "Finalize when ready:"
echo "  echo '{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"finalize\"}}' | nc -U var/run/daemon.sock"