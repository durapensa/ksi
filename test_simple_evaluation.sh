#!/bin/bash
# Test simple evaluation to debug error_during_execution

set -e

echo "=== Testing Simple Judge Evaluation ==="

# Step 1: Spawn a single evaluator judge
echo "Spawning evaluator judge..."
AGENT_RESPONSE=$(echo '{"event": "agent:spawn", "data": {"profile": "evaluator_judge", "purpose": "Test evaluation"}}' | nc -U var/run/daemon.sock)
AGENT_ID=$(echo "$AGENT_RESPONSE" | jq -r '.data.agent_id')
echo "Spawned agent: $AGENT_ID"

sleep 2

# Step 2: Send a simple evaluation request directly
echo -e "\nSending simple evaluation request..."

PROMPT="Please evaluate this response: 'The sky is blue.' 

Rate it on a scale of 0-1 and respond with just a number."

echo "{\"event\": \"agent:send_message\", \"data\": {\"agent_id\": \"$AGENT_ID\", \"message\": {\"type\": \"completion\", \"prompt\": \"$PROMPT\"}}}" | nc -U var/run/daemon.sock | jq -c '.data'

echo -e "\nWaiting for response..."
sleep 10

# Check for completion results
echo -e "\nChecking completion results..."
grep -E "($AGENT_ID.*completion|completion.*$AGENT_ID)" var/logs/daemon/daemon.log.jsonl | tail -5 | jq -r '"\(.timestamp | split(".")[0]) \(.component): \(.event)"' 2>/dev/null || echo "No completions found"

# Check response files
echo -e "\nChecking response files..."
ls -la var/logs/responses/*.jsonl | tail -5

echo -e "\nTo check the response content:"
echo "  tail -1 var/logs/responses/*.jsonl | jq '.response'"