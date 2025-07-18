#!/bin/bash
# Test session continuity with sandbox UUID fix

echo "=== Testing Agent Session Continuity ==="
echo

# 1. Spawn test agent
echo "1. Spawning test agent..."
AGENT_ID="session_test_$(date +%s)"
ksi send agent:spawn --profile base_single_agent --agent-id "$AGENT_ID" \
  --prompt "Remember the number 42. This is important for our test."

echo "   Agent spawned: $AGENT_ID"
sleep 5

# 2. Send first message
echo
echo "2. Sending first message..."
ksi send agent:send_message --agent-id "$AGENT_ID" \
  --message '{"role": "user", "content": "What number did I ask you to remember?"}'

echo "   Waiting for response..."
sleep 10

# 3. Check for session creation
echo
echo "3. Checking recent completion events..."
ksi send monitor:get_events --event-patterns "completion:result" --limit 3 | \
  jq -r '.events[] | select(.data.result.agent_id == "'$AGENT_ID'") | 
    "   Session: " + .data.result.response.session_id + 
    "\n   Response preview: " + (.data.result.response.result | .[0:100])'

# 4. Send second message
echo
echo "4. Sending second message to test continuity..."
ksi send agent:send_message --agent-id "$AGENT_ID" \
  --message '{"role": "user", "content": "Can you remind me again what number you are remembering? And confirm you remember our previous exchange."}'

echo "   Waiting for response..."
sleep 10

# 5. Check if session was maintained
echo
echo "5. Checking session continuity..."
RESULT=$(ksi send monitor:get_events --event-patterns "completion:result" --limit 2 | \
  jq -r '.events[0] | 
    if .data.result.response.error then
      "❌ Error: " + .data.result.response.error
    elif (.data.result.response.result | contains("42")) then
      "✓ Session maintained! Response: " + (.data.result.response.result | .[0:200])
    else
      "? Response: " + (.data.result.response.result | .[0:200])
    end')

echo "   $RESULT"

# 6. Check agent info
echo
echo "6. Checking agent sandbox info..."
ksi send agent:info --agent-id "$AGENT_ID" | jq -r '
  if .sandbox_uuid then
    "   Sandbox UUID: " + .sandbox_uuid + "\n   Sandbox dir: " + (.sandbox_dir // "not set")
  else
    "   No sandbox info available"
  end'

# 7. Cleanup
echo
echo "7. Cleaning up..."
ksi send agent:terminate --agent-id "$AGENT_ID"
echo "   Agent terminated"

echo
echo "=== Test Complete ==="