#!/bin/bash

# Test script for fail-fast error propagation

echo "Testing Fail-Fast Error Propagation"
echo "===================================="
echo ""

# Test 1: Template resolution with missing variable (strict mode)
echo "1. Testing template resolution failure (strict mode)..."
echo "   Template: {{missing_variable}}"
echo "   Expected: TemplateResolutionError"
echo ""

# Create a test transformer with bad template mapping
cat > var/lib/transformers/test_fail_fast.yaml << 'EOF'
transformers:
  - name: test_template_failure
    source: test:fail_fast:input
    target: test:fail_fast:output
    mapping:
      result: "{{missing_variable}}"
      value: "{{existing_value}}" 
EOF

echo "Running: ksi send test:fail_fast:input --existing_value 'test'"
ksi send test:fail_fast:input --existing_value "test" 2>&1 | grep -E "(error|Error|missing)" || echo "No error detected"
echo ""

# Test 2: Agent error propagation
echo "2. Testing agent error propagation..."
echo "   Spawning test agent and triggering error"
echo ""

# Spawn a test agent
echo "Running: ksi send agent:spawn --component 'core/base_agent' --agent_id 'test_error_agent'"
SPAWN_RESULT=$(ksi send agent:spawn --component "core/base_agent" --agent_id "test_error_agent" 2>&1)
echo "$SPAWN_RESULT" | jq -r '.status' 2>/dev/null || echo "$SPAWN_RESULT"
echo ""

# Wait for agent to be ready
sleep 2

# Trigger an error that should propagate to the agent
echo "Running: ksi send error:template_resolution with agent context"
ERROR_RESULT=$(ksi send error:template_resolution \
  --error_message "Cannot resolve variable 'missing_field'" \
  --details '{"template": "{{missing_field}}", "missing_variable": "missing_field"}' \
  --_ksi_context '{"_client_id": "agent_test_error_agent"}' 2>&1)
echo "$ERROR_RESULT" | jq -r '.status' 2>/dev/null || echo "$ERROR_RESULT"
echo ""

# Check if agent received the error
echo "Checking agent info for errors..."
AGENT_INFO=$(ksi send agent:info --agent_id "test_error_agent" 2>&1)
echo "$AGENT_INFO" | jq -r '.errors' 2>/dev/null || echo "No errors field found"
echo ""

# Test 3: Context auto-generation warning
echo "3. Testing context auto-generation warning..."
echo "   Emitting event without context"
echo ""

# This should trigger a warning about auto-generated context
echo "Running: ksi send test:no_context --data 'test'"
NO_CONTEXT_RESULT=$(ksi send test:no_context --data "test" 2>&1)
echo "$NO_CONTEXT_RESULT"
echo ""

# Check daemon logs for warning
echo "Checking daemon logs for context warnings..."
tail -n 50 var/logs/daemon/daemon.log.jsonl | grep -i "auto-generated.*context" | jq -r '.message' 2>/dev/null | head -3
echo ""

# Test 4: Template validation with strict mode
echo "4. Testing template validation..."
echo ""

# This should fail validation
echo "Testing invalid template with validation:"
python3 -c "
from ksi_common.template_utils import validate_template

# Test with missing variable
template = '{{missing_var}}'
available_vars = {'existing_var': 'value'}

result = validate_template(template, available_vars=available_vars)
print(f'Validation result for {{{{missing_var}}}}: {result}')

# Test with present variable
template = '{{existing_var}}'
result = validate_template(template, available_vars=available_vars)
print(f'Validation result for {{{{existing_var}}}}: {result}')
"
echo ""

# Cleanup
echo "5. Cleaning up test resources..."
echo ""

# Terminate test agent
echo "Running: ksi send agent:terminate --agent_id 'test_error_agent'"
ksi send agent:terminate --agent_id "test_error_agent" 2>&1 | jq -r '.status' 2>/dev/null || echo "Cleanup done"

# Remove test transformer
rm -f var/lib/transformers/test_fail_fast.yaml

echo ""
echo "Test complete!"
echo ""
echo "Summary:"
echo "- Template resolution with strict mode: Check for TemplateResolutionError"
echo "- Agent error propagation: Agents should receive errors via agent:error event"
echo "- Context auto-generation: Warning logged when _ksi_context missing"
echo "- Template validation: validate_template() detects unresolvable variables"