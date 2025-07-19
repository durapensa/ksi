#!/bin/bash
# Test tournament with real evaluation logic

set -e

echo "=== Testing Tournament with Real Evaluation Logic ==="

# First, spawn a few judge agents using existing profiles
echo "Spawning judge agents..."

# Spawn evaluator judges
echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge", "purpose": "Tournament participant - evaluator"}}' | nc -U var/run/daemon.sock > spawn1.json
AGENT1=$(jq -r '.data.agent_id' spawn1.json)
echo "Spawned evaluator judge: $AGENT1"

echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge_detailed_rubric", "purpose": "Tournament participant - detailed evaluator"}}' | nc -U var/run/daemon.sock > spawn2.json
AGENT2=$(jq -r '.data.agent_id' spawn2.json)
echo "Spawned detailed evaluator judge: $AGENT2"

# Spawn analyst judges
echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge", "purpose": "Tournament participant - analyst"}}' | nc -U var/run/daemon.sock > spawn3.json
AGENT3=$(jq -r '.data.agent_id' spawn3.json)
echo "Spawned analyst judge: $AGENT3"

echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge_root_cause_focus", "purpose": "Tournament participant - root cause analyst"}}' | nc -U var/run/daemon.sock > spawn4.json
AGENT4=$(jq -r '.data.agent_id' spawn4.json)
echo "Spawned root cause analyst judge: $AGENT4"

# Spawn rewriter judges
echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge", "purpose": "Tournament participant - rewriter"}}' | nc -U var/run/daemon.sock > spawn5.json
AGENT5=$(jq -r '.data.agent_id' spawn5.json)
echo "Spawned rewriter judge: $AGENT5"

echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge_incremental_improvement", "purpose": "Tournament participant - incremental rewriter"}}' | nc -U var/run/daemon.sock > spawn6.json
AGENT6=$(jq -r '.data.agent_id' spawn6.json)
echo "Spawned incremental rewriter judge: $AGENT6"

sleep 2

echo -e "\nCreating tournament with real evaluation..."

# Create tournament
TOURNAMENT_ID="real_eval_tournament_$(date +%Y%m%d_%H%M%S)"

echo "Creating tournament $TOURNAMENT_ID..."
echo "{\"event\": \"tournament:create\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"config\": {\"participants\": [\"$AGENT1\", \"$AGENT2\", \"$AGENT3\", \"$AGENT4\", \"$AGENT5\", \"$AGENT6\"], \"rounds\": 1, \"match_timeout\": 60, \"test_case_limit\": 2, \"parallel_matches\": 2}, \"auto_start\": false}}" | nc -U var/run/daemon.sock | jq -c '.data'

sleep 1

# Start registration phase
echo -e "\nStarting registration phase..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"registration\"}}" | nc -U var/run/daemon.sock | jq -c '.data'

sleep 2

# Register all agents
echo -e "\nRegistering agents..."
for agent_id in $AGENT1 $AGENT2 $AGENT3 $AGENT4 $AGENT5 $AGENT6; do
  echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$agent_id\"}}" | nc -U var/run/daemon.sock | jq -c '.data'
done

sleep 2

# Start round-robin phase
echo -e "\nStarting round-robin phase..."
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"round_robin\"}}" | nc -U var/run/daemon.sock | jq -c '.data'

echo -e "\nTournament is running with real evaluation logic..."
echo "This will take a few minutes as agents actually evaluate each other."
echo "Monitor with: tail -f var/logs/daemon/daemon.log.jsonl | grep -E '(tournament|evaluation|match)'"
echo ""
echo "Check progress with:"
echo "  grep -E '(match.*complete|evaluation.*response)' var/logs/daemon/daemon.log.jsonl | tail -20"
echo ""
echo "Tournament ID: $TOURNAMENT_ID"
echo "Results will be saved to: var/lib/evaluations/tournament_${TOURNAMENT_ID}_results.yaml"