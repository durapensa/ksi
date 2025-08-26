#!/bin/bash

# Test Enhanced Dependency Validation
# Tests that dependencies must have passing evaluations, not just be tested

echo "========================================="
echo "Enhanced Dependency Validation Test"
echo "========================================="
echo

# Test 1: Component with all passing dependencies should succeed
echo "Test 1: Component with passing dependencies"
echo "-------------------------------------------"
# hello_agent_optimized depends on core/base_agent which has some passing evaluations
ksi send evaluation:run \
  --component_path "var/lib/compositions/components/personas/conversationalists/hello_agent_optimized.md" \
  --test_suite "dependency_validation_test" \
  --model "claude-sonnet-4" \
  --test_results '{"status": "passing", "tests_passed": 1, "tests_total": 1}'

echo
echo "Test 2: Component with non-passing dependency"
echo "----------------------------------------------"
# Create a test component that depends on something with only failing evaluations
cat << 'EOF' > /tmp/test_component_bad_dep.md
---
component_type: persona
name: test_bad_dep
version: 1.0.0
dependencies:
  - behaviors/core/claude_code_override  # This has only timeout/error evaluations
---
# Test Component
This is a test component with a dependency that has no passing evaluations.
EOF

# Try to evaluate it - should fail with enhanced validation
ksi send evaluation:run \
  --component_path "/tmp/test_component_bad_dep.md" \
  --test_suite "dependency_check" \
  --model "claude-sonnet-4" \
  --test_results '{"status": "passing", "tests_passed": 1, "tests_total": 1}'

echo
echo "Test 3: Component with untested dependency"
echo "-------------------------------------------"
# Create a test component that depends on something not in registry
cat << 'EOF' > /tmp/test_component_untested_dep.md
---
component_type: persona
name: test_untested_dep
version: 1.0.0
dependencies:
  - personas/nonexistent/fake_component
---
# Test Component
This is a test component with an untested dependency.
EOF

# Try to evaluate it - should fail with original validation
ksi send evaluation:run \
  --component_path "/tmp/test_component_untested_dep.md" \
  --test_suite "dependency_check" \
  --model "claude-sonnet-4" \
  --test_results '{"status": "passing", "tests_passed": 1, "tests_total": 1}'

echo
echo "Test 4: Verify Registry Status"
echo "-------------------------------"
# Check what's in the registry for validation
echo "Checking base_agent status (should have passing):"
grep -A 10 "ed68507097367dc195d26ad544546620c9fe7b6a03fc945c8e4b29f29aee7170" var/lib/evaluations/registry.yaml | grep status | head -5

echo
echo "Checking claude_code_override status (should have only timeout/error):"
grep -A 10 "18bb54a11b1062c34a232bb3c011225d9b40b3fd661b7658ccfbe5e37103af7a" var/lib/evaluations/registry.yaml | grep status | head -5

echo
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Expected results:"
echo "✓ Test 1: Should pass - hello_agent_optimized has base_agent with passing status"
echo "✗ Test 2: Should fail - claude_code_override has only timeout/error status"
echo "✗ Test 3: Should fail - fake_component not in registry"
echo
echo "The enhanced validation ensures dependencies have passing evaluations,"
echo "not just any evaluation status."