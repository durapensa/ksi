#!/bin/bash

echo "Testing Universal Error Propagation System"
echo "=========================================="

# Test 1: Handler failure propagation
echo ""
echo "Test 1: Testing handler failure propagation"
echo "--------------------------------------------"
echo "Sending event that will trigger an error..."
ksi send test:trigger_error --message "This should fail" --error_type "handler_failure"

sleep 1

# Test 2: Template resolution error
echo ""
echo "Test 2: Testing template resolution error"
echo "--------------------------------------------"
echo "Creating transformer with missing variables..."
ksi send router:register_transformer \
  --name "test_strict_template_error" \
  --source "test:template_input" \
  --target "test:template_output" \
  --mapping '{"result": "{{missing_var}}"}' \
  --enabled true

echo "Triggering the transformer..."
ksi send test:template_input --data "test"

sleep 1

# Test 3: Agent error propagation
echo ""
echo "Test 3: Testing agent error propagation"
echo "--------------------------------------------"
echo "Spawning test agent..."
AGENT_RESPONSE=$(ksi send agent:spawn --profile "default" --name "test_error_agent")
AGENT_ID=$(echo "$AGENT_RESPONSE" | grep -o '"agent_id": "[^"]*"' | cut -d'"' -f4)
echo "Agent ID: $AGENT_ID"

echo "Sending event that will fail for this agent..."
ksi send test:agent_error --agent_id "$AGENT_ID" --error_message "Agent-specific error"

sleep 2

# Check if errors were stored
echo ""
echo "Test 4: Checking error storage"
echo "-------------------------------"
echo "Querying stored errors..."
ksi send state:entity:query --type "error" --limit 5

echo ""
echo "Test complete! Check daemon logs for error propagation details:"
echo "tail -f var/logs/daemon/daemon.log.jsonl | jq '.'"