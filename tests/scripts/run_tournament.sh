#!/bin/bash
# Run complete tournament workflow

TOURNAMENT_ID="judge_championship_final_001"

echo "Creating tournament..."
cat <<EOF | nc -U var/run/daemon.sock | jq -c '.data'
{
  "event": "tournament:create",
  "data": {
    "tournament_id": "$TOURNAMENT_ID",
    "config": {
      "participants": [
        "agent_fa30bd22",
        "agent_e0a57fec",
        "agent_8cf257db",
        "agent_3b3a6a20",
        "agent_8b773f18",
        "agent_d50f52c0"
      ],
      "rounds": 1,
      "match_timeout": 300,
      "test_case_limit": 3,
      "parallel_matches": 3
    },
    "auto_start": false
  }
}
EOF

sleep 1

echo "Starting registration phase..."
echo '{"event": "tournament:start_phase", "data": {"tournament_id": "'$TOURNAMENT_ID'", "phase": "registration"}}' | nc -U var/run/daemon.sock | jq -c '.data'

sleep 2

echo "Registering agents..."
for agent_id in agent_fa30bd22 agent_e0a57fec agent_8cf257db agent_3b3a6a20 agent_8b773f18 agent_d50f52c0; do
  echo '{"event": "tournament:register", "data": {"tournament_id": "'$TOURNAMENT_ID'", "agent_id": "'$agent_id'"}}' | nc -U var/run/daemon.sock | jq -c '.data' 
done

sleep 2

echo "Starting round-robin phase..."
echo '{"event": "tournament:start_phase", "data": {"tournament_id": "'$TOURNAMENT_ID'", "phase": "round_robin"}}' | nc -U var/run/daemon.sock | jq -c '.data'

echo "Tournament is running. Matches will take a few minutes..."