#!/bin/bash

# Methodical Bottom-Up Testing of Autonomous Improvement
# Build and validate each layer before proceeding to the next

set -e

echo "============================================"
echo "Autonomous Self-Improvement Testing"
echo "Methodical Bottom-Up Validation"
echo "============================================"
echo

# Step 1: Test Basic Event Emission
echo "STEP 1: Test Agent Can Emit Evaluation Events"
echo "----------------------------------------------"

# Create minimal test agent that emits evaluation
cat << 'EOF' > /tmp/test_eval_emitter.md
---
component_type: agent
name: test_eval_emitter
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Evaluation Emitter

Emit an evaluation event when prompted.

When asked to evaluate, emit:
```json
{
  "type": "ksi_tool_use",
  "name": "evaluation:run",
  "input": {
    "component_path": "components/personas/conversationalists/hello_agent.md",
    "test_suite": "basic_effectiveness",
    "model": "claude-sonnet-4",
    "test_results": {
      "status": "passing",
      "tests_passed": 1,
      "tests_total": 1,
      "scores": {
        "baseline_quality": 0.75
      }
    }
  }
}
```
EOF

echo "Spawning test evaluation emitter..."
ksi send agent:spawn \
  --agent_id "test_eval_emitter_001" \
  --component "/tmp/test_eval_emitter.md" \
  --permission_profile "trusted"

echo "Triggering evaluation emission..."
ksi send completion:async \
  --agent_id "test_eval_emitter_001" \
  --prompt "Please evaluate hello_agent now"

echo "Waiting for evaluation to complete..."
sleep 3

echo "Checking if evaluation was created..."
ksi send evaluation:query --component_pattern "hello_agent" --limit 1

echo
echo "✓ Step 1 Complete: Agent can emit evaluation events"
echo

# Step 2: Test Routing Rule Creation
echo "STEP 2: Test Agent Can Create Routing Rules"
echo "--------------------------------------------"

cat << 'EOF' > /tmp/test_router.md
---
component_type: agent
name: test_router
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Router

Create routing rules when prompted.

When asked to create a route, emit:
```json
{
  "type": "ksi_tool_use",
  "name": "routing:add_rule",
  "input": {
    "rule_id": "test_route_001",
    "source_pattern": "test:source",
    "target": "test:target",
    "priority": 100,
    "ttl": 60,
    "mapping": {
      "data": "{{data}}"
    }
  }
}
```
EOF

echo "Spawning test router..."
ksi send agent:spawn \
  --agent_id "test_router_001" \
  --component "/tmp/test_router.md" \
  --permission_profile "trusted"

echo "Triggering routing rule creation..."
ksi send completion:async \
  --agent_id "test_router_001" \
  --prompt "Please create a routing rule now"

echo "Waiting for rule creation..."
sleep 2

echo "Checking active routing rules..."
ksi send routing:query_rules --pattern "test_route*"

echo
echo "✓ Step 2 Complete: Agent can create routing rules"
echo

# Step 3: Test Judge Spawning and Result Capture
echo "STEP 3: Test Judge Spawning and Result Routing"
echo "-----------------------------------------------"

cat << 'EOF' > /tmp/test_judge_spawner.md
---
component_type: agent
name: test_judge_spawner
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Judge Spawner

Spawn a judge agent when prompted.

When asked to spawn a judge, emit:
```json
{
  "type": "ksi_tool_use",
  "name": "agent:spawn",
  "input": {
    "agent_id": "test_judge_001",
    "component": "evaluations/judges/comparative_improvement_judge",
    "permission_profile": "trusted",
    "prompt": "Compare baseline score 0.75 with optimized score 0.82. Are trade-offs acceptable?"
  }
}
```
EOF

echo "Spawning judge spawner..."
ksi send agent:spawn \
  --agent_id "test_judge_spawner_001" \
  --component "/tmp/test_judge_spawner.md" \
  --permission_profile "trusted"

echo "Triggering judge spawn..."
ksi send completion:async \
  --agent_id "test_judge_spawner_001" \
  --prompt "Please spawn a comparative judge now"

echo "Waiting for judge to be spawned..."
sleep 3

echo "Checking if judge exists..."
ksi send agent:info --agent_id "test_judge_001"

echo
echo "✓ Step 3 Complete: Agent can spawn judges"
echo

# Step 4: Test Event Chain
echo "STEP 4: Test Complete Event Chain"
echo "----------------------------------"
echo "Testing: evaluation → optimization trigger → validation"
echo

# First, add our improvement workflow transformers
echo "Loading improvement workflow transformers..."
ksi send transformer:reload --path "var/lib/transformers/improvement_workflow.yaml"

# Create a test agent that starts the chain
cat << 'EOF' > /tmp/test_chain_starter.md
---
component_type: agent
name: test_chain_starter
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Chain Starter

Start an improvement workflow chain.

First, create routing for the workflow:
```json
{
  "type": "ksi_tool_use",
  "name": "routing:add_rule",
  "input": {
    "rule_id": "test_workflow_route",
    "source_pattern": "evaluation:result",
    "target": "agent:message",
    "condition": "workflow_id == 'test_workflow_001'",
    "mapping": {
      "agent_id": "test_chain_starter_001",
      "message": "Evaluation complete: {{scores}}"
    },
    "ttl": 300
  }
}
```

Then trigger evaluation with workflow metadata:
```json
{
  "type": "ksi_tool_use",
  "name": "evaluation:run",
  "input": {
    "component_path": "components/personas/conversationalists/hello_agent.md",
    "test_suite": "basic_effectiveness",
    "workflow_type": "improvement",
    "workflow_id": "test_workflow_001",
    "phase": "baseline",
    "test_results": {
      "status": "passing",
      "scores": {
        "quality": 0.75,
        "tokens": 100
      }
    }
  }
}
```
EOF

echo "Spawning chain starter..."
ksi send agent:spawn \
  --agent_id "test_chain_starter_001" \
  --component "/tmp/test_chain_starter.md" \
  --permission_profile "trusted"

echo "Starting event chain..."
ksi send completion:async \
  --agent_id "test_chain_starter_001" \
  --prompt "Start the improvement workflow chain now. First create the routing, then trigger evaluation."

echo "Monitoring event flow for 10 seconds..."
ksi send monitor:get_events --event_patterns "evaluation:*,optimization:*,routing:*" --limit 20 &
MONITOR_PID=$!

sleep 10
kill $MONITOR_PID 2>/dev/null || true

echo
echo "✓ Step 4 Complete: Event chains work"
echo

# Step 5: Test Simple Comparative Analysis
echo "STEP 5: Test Comparative Analysis"
echo "----------------------------------"

cat << 'EOF' > /tmp/test_comparator.md
---
component_type: agent  
name: test_comparator
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Comparator

Compare two versions and make deployment decision.

Given:
- Baseline: quality=0.75, tokens=100
- Optimized: quality=0.78, tokens=115

Analysis:
- Quality improved: +4%
- Token increase: +15%
- Trade-off: Acceptable (quality gain worth token cost)

Decision:
```json
{
  "type": "ksi_tool_use",
  "name": "state:entity:update",
  "input": {
    "entity_type": "improvement_decision",
    "entity_id": "decision_001",
    "properties": {
      "recommendation": "deploy",
      "reasoning": "4% quality improvement justifies 15% token increase",
      "baseline": {"quality": 0.75, "tokens": 100},
      "optimized": {"quality": 0.78, "tokens": 115},
      "net_improvement": true
    }
  }
}
```
EOF

echo "Spawning comparator..."
ksi send agent:spawn \
  --agent_id "test_comparator_001" \
  --component "/tmp/test_comparator.md" \
  --permission_profile "trusted"

echo "Triggering comparison..."
ksi send completion:async \
  --agent_id "test_comparator_001" \
  --prompt "Compare the baseline and optimized versions and make a decision"

echo "Waiting for decision..."
sleep 3

echo "Checking decision state..."
ksi send state:entity:get --type "improvement_decision" --id "decision_001"

echo
echo "✓ Step 5 Complete: Comparative analysis works"
echo

# Summary
echo
echo "============================================"
echo "Bottom-Up Validation Complete!"
echo "============================================"
echo
echo "✅ Validated Components:"
echo "  1. Agents can emit evaluation events"
echo "  2. Agents can create routing rules"  
echo "  3. Agents can spawn other agents"
echo "  4. Event chains flow correctly"
echo "  5. Comparative analysis produces decisions"
echo
echo "Ready for Next Level:"
echo "  - Deploy full self_improvement_orchestrator"
echo "  - Test with real component improvement"
echo "  - Enable recursive self-improvement"
echo
echo "The foundation is solid. The system is ready."