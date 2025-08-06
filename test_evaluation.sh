#!/bin/bash

# Test async evaluation service
echo "Testing Async Evaluation Service"
echo "================================"

# Test optimization result data
OPTIMIZATION_ID="test_opt_$(date +%s)"
OPTIMIZATION_RESULT=$(cat <<'EOF'
{
  "component_name": "personas/test_component",
  "original_content": "You are a helpful assistant.",
  "optimized_content": "You are a helpful AI assistant. Always provide clear, accurate, and well-structured responses.",
  "optimization_metadata": {
    "optimizer": "test",
    "improvement": 0.15,
    "method": "manual"
  }
}
EOF
)

# First, set up event monitoring
echo -e "\n1. Setting up event monitor..."
MONITOR_CMD='ksi send monitor:subscribe --event-patterns "evaluation:*" "routing:*" "agent:spawn*" "completion:*"'
echo "Running: $MONITOR_CMD"
eval $MONITOR_CMD

# Test evaluation:async directly
echo -e "\n2. Testing evaluation:async handler..."
TEST_CMD="ksi send evaluation:async --optimization_id \"$OPTIMIZATION_ID\" --optimization_result '$OPTIMIZATION_RESULT' --skip_git true"
echo "Running: $TEST_CMD"
eval $TEST_CMD

# Check routing rules
echo -e "\n3. Checking routing rules..."
ksi send routing:list | jq '.rules[] | select(.rule_id | contains("judge_complete"))'

# Check for spawned agents
echo -e "\n4. Checking spawned agents..."
ksi send agent:list | jq '.agents[] | select(.agent_id | contains("judge"))'

# Wait and check for events
echo -e "\n5. Waiting for evaluation to complete..."
sleep 3

# Get recent events
echo -e "\n6. Checking recent monitor events..."
ksi send monitor:get_events --event-patterns "evaluation:*" --limit 10

echo -e "\nTest complete!"