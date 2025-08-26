#!/bin/bash
# Comprehensive test of single agent functionality outside orchestrations

echo "=== Testing Single Agent Functionality ==="
echo

# Clean up any existing test agents
ksi send agent:kill --agent-id standalone_demo 2>/dev/null || true
ksi send monitor:clear

echo "1. Spawning standalone agent with direct prompt..."
ksi send agent:spawn_from_component \
  --component "components/core/base_agent" \
  --agent-id "standalone_demo" \
  --vars '{"agent_id": "standalone_demo"}' \
  --prompt 'You are a standalone demonstration agent operating independently.

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "standalone_demo", "status": "initialized", "message": "Standalone agent operational"}}

Your mission is to demonstrate autonomous functionality:

1. First, create a state entity to track your work:
{"event": "state:entity:create", "data": {"type": "demo_state", "id": "standalone_demo_state", "properties": {"task": "Demonstrate autonomy", "phase": "starting"}}}

2. Report progress:
{"event": "agent:progress", "data": {"agent_id": "standalone_demo", "progress": 0.5, "message": "Executing autonomous tasks"}}

3. Update your state:
{"event": "state:entity:update", "data": {"id": "standalone_demo_state", "properties": {"phase": "completed", "results": "Successfully demonstrated autonomous operation"}}}

4. Send a completion status:
{"event": "agent:status", "data": {"agent_id": "standalone_demo", "status": "completed", "message": "Standalone demonstration complete"}}

Remember: Emit these events directly as JSON. Do not use external tools or commands.'

echo
echo "2. Waiting for agent to initialize and process..."
sleep 5

echo
echo "3. Checking for agent events..."
echo "   Status events:"
ksi send monitor:get_events --event-patterns "agent:status" --data-contains "standalone_demo" --extracted --limit 5

echo
echo "   Progress events:"
ksi send monitor:get_events --event-patterns "agent:progress" --data-contains "standalone_demo" --extracted --limit 5

echo
echo "   State events:"
ksi send monitor:get_events --event-patterns "state:entity:*" --data-contains "standalone_demo" --extracted --limit 5

echo
echo "4. Sending follow-up message to test interaction..."
ksi send agent:send_message --agent-id standalone_demo --message '{
  "role": "user",
  "content": "Great work! Please emit one final status confirming you can receive and respond to messages: {\"event\": \"agent:status\", \"data\": {\"agent_id\": \"standalone_demo\", \"status\": \"responsive\", \"message\": \"Message received and processed\"}}"
}'

sleep 3

echo
echo "5. Checking for response..."
ksi send monitor:get_events --event-patterns "agent:status" --data-contains "responsive" --extracted --limit 3

echo
echo "6. Agent info:"
ksi send agent:info --agent-id standalone_demo | jq '{agent_id, status, created_at, sandbox_uuid}'

echo
echo "=== Test Complete ==="
echo "Summary: Agents can operate independently outside orchestrations with:"
echo "- Direct prompt delivery via agent:spawn_from_component"
echo "- Autonomous event emission"
echo "- Message handling and response"
echo "- State management capabilities"