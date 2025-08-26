#!/bin/bash

# Test Agent Orchestration Capability
# This script tests if agents can successfully spawn and coordinate other agents

echo "================================="
echo "Agent Orchestration Capability Test"
echo "================================="
echo

# Test 1: Simple delegation test
echo "Test 1: Simple Delegation (2-3 agents)"
echo "--------------------------------------"
echo "Spawning coordinator agent with orchestration capability..."

ksi send agent:spawn \
  --agent_id "test_coordinator_$(date +%s)" \
  --component "agents/simple_orchestrator" \
  --permission_profile "trusted" \
  --prompt "Please coordinate a simple analysis task by delegating to specialist agents. Create a data analyst and a report writer agent, have them work on analyzing sample data and creating a report."

echo
echo "Waiting for orchestration to begin..."
sleep 5

# Monitor events for coordination activity
echo "Checking for agent spawn events..."
ksi send monitor:get_events \
  --event_patterns "agent:spawn" \
  --limit 5

echo
echo "Test 2: Pipeline Orchestration Test"
echo "------------------------------------"
echo "Testing sequential pipeline coordination..."

# Create a more complex orchestration scenario
ksi send agent:spawn \
  --agent_id "pipeline_coordinator_$(date +%s)" \
  --component "agents/simple_orchestrator" \
  --permission_profile "trusted" \
  --prompt "Coordinate a 3-stage pipeline: 1) Data collection agent, 2) Analysis agent, 3) Summary agent. Each should pass results to the next."

echo
echo "Waiting for pipeline setup..."
sleep 5

# Check routing rules created
echo "Checking for active agents (coordination patterns)..."
ksi send agent:list --limit 5

echo
echo "Test 3: Dynamic Adaptation Test"
echo "--------------------------------"
echo "Testing adaptation to agent availability..."

# Test handling of failed agent
ksi send agent:spawn \
  --agent_id "adaptive_coordinator_$(date +%s)" \
  --component "agents/simple_orchestrator" \
  --permission_profile "trusted" \
  --prompt "Spawn 3 agents for parallel work. If any agent fails to respond, reassign their work to available agents."

echo
echo "================================="
echo "Test Summary"
echo "================================="
echo "Checking overall orchestration metrics..."

# Get summary of orchestration activity
ksi send monitor:get_events \
  --event_patterns "agent:*" \
  --limit 20

echo
echo "Orchestration capability test complete."
echo "Review the events above to verify:"
echo "1. Agents successfully spawned other agents"
echo "2. Coordination patterns were established (routing rules)"
echo "3. Multi-agent workflows were initiated"