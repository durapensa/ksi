# Component Evaluation Plan

## Objective
Systematically evaluate and clean up components in var/lib/compositions, keeping only those that follow the MANDATORY imperative pattern and work reliably with KSI.

## Component Categories to Evaluate

### 1. Agent Instructions (Priority: HIGH)
**Old Pattern Components (to update or discard):**
- `agent_instructions/json_messaging.md` - Replace with imperative version
- `agent_instructions/ksi_orchestration.md` - Replace with imperative version
- `agent_instructions/persona_bypass.md` - Evaluate if needed

**New Pattern Components (to test and keep):**
- `agent_instructions/imperative_json_messaging.md` ✓
- `agent_instructions/imperative_ksi_orchestration.md` ✓

### 2. Base Components (Priority: HIGH)
**Old Pattern Components (to update or discard):**
- `base/agent_core.md` - Replace with imperative version
- `base/task_executor.md` - Replace with imperative version

**New Pattern Components (to test and keep):**
- `base/imperative_agent_core.md` ✓
- `base/imperative_task_executor.md` ✓

### 3. Capabilities (Priority: HIGH)
**Components to evaluate:**
- `capabilities/claude_code_1.0.x/ksi_json_reporter.md` - Test for compatibility
- `capabilities/fixed_imperative_communication.md` - Keep if works
- `capabilities/imperative_ksi_communication.md` - Primary capability to use

### 4. Personas (Priority: MEDIUM)
**Components to update:**
- `personas/business_analyst.md` - Update to imperative pattern
- `personas/universal/data_analyst.md` - Update to imperative pattern

### 5. Stress Test Components (Priority: HIGH)
**Old Pattern Components (to discard):**
- `stress_test/base_orchestrator.md` - Replace with imperative
- `stress_test/worker_agent.md` - Replace with imperative

**New Pattern Components (to test):**
- `stress_test/imperative_base_orchestrator.md` ✓
- `stress_test/imperative_worker_agent.md` ✓

## Testing Criteria

### 1. JSON Event Emission Test
- Spawn agent with component
- Send test prompt
- Verify JSON events are emitted correctly
- Check event extraction works

### 2. Variable Substitution Test
- Verify {{agent_id}} is properly substituted
- Check other template variables work

### 3. Integration Test
- Test component combinations (base + capabilities + instructions)
- Verify mixins work correctly

### 4. Stress Test
- High-frequency event emission
- Multiple agents using same components
- Error recovery patterns

## Testing Commands

### Basic Component Test
```bash
# Test single component
ksi send agent:spawn_from_component --component "components/agent_instructions/imperative_json_messaging" --prompt "Test JSON emission"

# Check events
ksi send monitor:get_events --event-patterns "agent:*" --limit 10
```

### Integration Test
```bash
# Create test agent with multiple components
ksi send composition:create_profile --name "test_integration" --components '["base/imperative_agent_core", "capabilities/imperative_ksi_communication", "agent_instructions/imperative_json_messaging"]'

# Spawn and test
ksi send agent:spawn --profile "test_integration" --prompt "Perform a multi-step task"
```

### Stress Test
```bash
# Spawn orchestrator
ksi send agent:spawn_from_component --component "stress_test/imperative_base_orchestrator" --prompt "Run stress test with 3 workers"

# Monitor system
ksi send monitor:get_status --include-agents
```

## Cleanup Actions

### 1. Components to Remove
- All non-imperative versions in agent_instructions/
- All non-imperative versions in base/
- All non-imperative versions in stress_test/
- Duplicate component paths (components/components/...)

### 2. Components to Update
- All personas to use imperative pattern
- Any capabilities not using MANDATORY pattern

### 3. Components to Keep
- All imperative_* components that pass tests
- Essential mixins and capabilities that work

## Success Criteria
1. All kept components emit JSON events reliably
2. Variable substitution works correctly
3. No duplicate or conflicting components
4. Clear naming convention (imperative_* for new pattern)
5. All tests pass using KSI commands only