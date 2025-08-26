#!/bin/bash
# Test simplified agent initialization with direct prompt field

echo "Testing simplified agent initialization..."

# Clear monitor
ksi send monitor:clear

# Test 1: Agent with direct prompt field
echo -e "\n1. Testing agent with direct prompt field..."
ksi send agent:spawn_from_component \
  --component "components/core/base_agent" \
  --agent-id "test_direct_prompt" \
  --vars '{"agent_id": "test_direct_prompt"}'

# Give direct prompt in the spawn call
ksi send agent:kill --agent-id test_direct_prompt 2>/dev/null || true

# Create test orchestration with direct prompt field
cat > /tmp/test_direct_prompt.yaml << 'EOF'
name: test_direct_prompt_init
type: orchestration
version: 1.0.0
description: Test direct prompt field initialization

agents:
  test_agent:
    component: components/core/base_agent
    prompt: |
      ## MANDATORY: Start your response with this exact JSON:
      {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "message": "Received direct prompt successfully"}}
      
      You are a test agent. This prompt was delivered through the direct prompt field.
      Your task is to confirm you received this initialization message.

coordination:
  termination:
    conditions:
      - timeout: 30
EOF

echo -e "\n2. Starting orchestration with direct prompt..."
ksi send orchestration:start --pattern /tmp/test_direct_prompt.yaml

sleep 3

echo -e "\n3. Checking for agent status events..."
ksi send monitor:get_events --event-patterns "agent:status" --extracted --limit 5

echo -e "\nTest complete. Cleaning up..."
rm -f /tmp/test_direct_prompt.yaml