#!/bin/bash
# Fast tournament test with optimized prompts

set -e

echo "=== Fast Tournament Test with Optimized Prompts ==="
echo "Using concise prompts for rapid evaluation"
echo ""

# Spawn just 3 judges for quick test
echo "Spawning 3 judge agents..."

echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge", "purpose": "Fast test 1"}}' | nc -U var/run/daemon.sock > agent1.json
AGENT1=$(jq -r '.data.agent_id' agent1.json)
echo "  Agent 1: $AGENT1"

echo '{"event": "agent:spawn", "data": {"profile": "analyst_judge", "purpose": "Fast test 2"}}' | nc -U var/run/daemon.sock > agent2.json
AGENT2=$(jq -r '.data.agent_id' agent2.json)
echo "  Agent 2: $AGENT2"

echo '{"event": "agent:spawn", "data": {"profile": "rewriter_judge", "purpose": "Fast test 3"}}' | nc -U var/run/daemon.sock > agent3.json
AGENT3=$(jq -r '.data.agent_id' agent3.json)
echo "  Agent 3: $AGENT3"

sleep 2

# Create tournament with shorter timeout
TOURNAMENT_ID="fast_test_$(date +%Y%m%d_%H%M%S)"
echo -e "\nCreating fast tournament $TOURNAMENT_ID..."

echo "{\"event\": \"tournament:create\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"config\": {\"participants\": [], \"rounds\": 1, \"match_timeout\": 30, \"min_participants\": 3, \"test_cases_per_match\": 1, \"parallel_matches\": 3}, \"auto_start\": false}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

# Start registration
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"registration\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

# Register agents
echo -e "\nRegistering agents..."
echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$AGENT1\", \"role\": \"evaluator\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'
echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$AGENT2\", \"role\": \"analyst\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'
echo "{\"event\": \"tournament:register\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"agent_id\": \"$AGENT3\", \"role\": \"rewriter\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

# Start round-robin
echo -e "\nStarting round-robin..."
START_TIME=$(date +%s)
echo "{\"event\": \"tournament:start_phase\", \"data\": {\"tournament_id\": \"$TOURNAMENT_ID\", \"phase\": \"round_robin\"}}" | nc -U var/run/daemon.sock | jq -c '.data.status'

echo -e "\n=== Tournament Running ===="
echo "Tournament ID: $TOURNAMENT_ID"
echo "Start time: $(date)"
echo ""
echo "Monitor progress:"
echo "  watch -n 2 'grep -c \"$TOURNAMENT_ID.*complete\" var/logs/daemon/daemon.log'"
echo ""
echo "Expected: 6 matches (3 agents × 2 opponents each)"