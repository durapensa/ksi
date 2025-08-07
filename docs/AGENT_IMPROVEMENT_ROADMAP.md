# Agent Improvement Roadmap: Methodical Bottom-Up Architecture

**Core Methodology:** Build → Test → Validate → Ascend  
**Current Layer:** Layer 2 (Comparative Analysis) - ACTIVE  
**Last Updated:** 2025-08-07  
**Key Principle:** Never advance to the next layer until the current layer is proven  
**Research Track:** Attractor Hypothesis - Testing if LLM logic degrades under competing attention attractors

## The Bottom-Up Imperative

### Why Bottom-Up Matters
Building from the bottom up ensures:
- **Each layer is solid** before depending on it
- **Failures are caught early** at the simplest level
- **Complex behaviors emerge** from simple, proven primitives
- **Debugging is tractable** - problems isolated to current layer
- **Confidence compounds** - each validated layer increases system trust

### Our Methodology
```
Layer N:
  1. Build minimal implementation
  2. Test in isolation
  3. Validate behavior matches expectations
  4. Document what works and what doesn't
  5. Only then proceed to Layer N+1
```

## Layer Architecture (Bottom to Top)

### Layer 0: Primitive Capabilities ✅ VALIDATED
**Status:** Complete and proven

**Components:**
- Event emission (`evaluation:run`, `optimization:async`)
- State management (`state:entity:*`)
- Component access (`composition:get_component`)
- Basic routing (`routing:add_rule`)

**Validation Tests:**
```bash
# Test each primitive in isolation
ksi send evaluation:run --component "hello_agent" --test_suite "basic"
ksi send state:entity:create --type "test" --properties '{"key": "value"}'
ksi send routing:add_rule --rule_id "test" --source "a" --target "b"
```

**Result:** All primitives work independently

### Layer 1: Agent Event Emission ✅ COMPLETE
**Status:** Fully validated with bidirectional feedback

**What We Built:**
- Agents that emit KSI events using ksi_tool_use pattern
- Automatic event extraction from agent responses
- Full bidirectional feedback loops

**What Works:**
- ✅ Agents spawn successfully
- ✅ Agents emit events when prompted  
- ✅ Events are extracted from responses
- ✅ Events appear in monitor
- ✅ Agents receive success feedback via system:result
- ✅ Agents receive error feedback via system:error
- ✅ Agents acknowledge and understand feedback
- ✅ Errors bubble to parent agents and hook

**Solution Architecture:**
```yaml
Error Flow:
  1. Agent emits ksi_tool_use → Event extracted
  2. Event processing fails → Error generated
  3. Error sent back to agent via completion:error
  4. Agent receives error, can retry with correction
  5. Error bubbles to parent agent (if spawned by one)
  6. Hook shows full error details with agent_id

Component Quality:
  - Components must include CORRECT event usage
  - Template substitution for documentation:
    {{ksi_help agent:spawn}}
    {{ksi_disc namespace agent detail}}
  - Automatic inclusion based on capabilities
  - Single source of truth from handlers
```

### Layer 1.5: Universal Result Bubbling ✅ COMPLETE
**Status:** Fully implemented and validated (v0.1.0 release)

**What We Built:**
- Universal response handler for both errors and success
- Extended @event_handler to emit system:result automatically
- Full bidirectional feedback with context preservation
- Infinite loop prevention with exclusion patterns

**Implementation Requirements:**

#### Error Feedback Loop
```python
# When event extraction fails
if event_validation_fails:
    error_msg = format_error_with_context(error, expected_params)
    # Send error back to originating agent
    emit("completion:error", {
        "agent_id": extracted_event.agent_id,
        "error": error_msg,
        "failed_event": extracted_event,
        "correction_hint": get_param_documentation(event_name)
    })
    # Bubble to parent if exists
    if parent_agent:
        emit("agent:child_error", {
            "parent_id": parent_agent,
            "child_id": agent_id,
            "error": error_msg
        })
```

#### Self-Documenting Components
```yaml
# Component with template substitution
---
component_type: agent
name: spawner_agent
---
You can spawn agents using:

{{ksi_help agent:spawn}}

Available profiles:
{{ksi_disc namespace composition filter="profile"}}

Your capabilities allow these events:
{{ksi_events_for_capabilities agent_spawn}}
```

#### Hook Error Display (ALL modes)
```python
# Enhanced hook error handling
def format_error_output(error_event):
    return f"⚠️ ERROR from {error_event['agent_id']}: {error_event['error']}"
```

**Benefits:**
- Agents learn from mistakes
- Components stay current with API
- Debugging becomes trivial
- No silent failures

### Layer 2: Comparative Analysis with Attractor Testing 🚧 ACTIVE
**Status:** Beginning implementation

**What We're Building:**
- Baseline logic evaluations without attractors
- Attractor impact measurements
- Comparative optimization with resistance goals
- Intelligent trade-off analysis

**Current Focus: Attractor Hypothesis Testing**
Testing if LLM logic degrades when attention is pulled by competing attractors

**Implementation Plan:**
```bash
# Phase 1: Baseline Logic Testing
ksi send agent:spawn --component "evaluations/logic/baseline_syllogism" \
  --prompt "If all birds can fly, and penguins are birds, can penguins fly?"

# Phase 2: Single Attractor Testing  
ksi send agent:spawn --component "evaluations/attractors/math_with_story" \
  --prompt "Solve the marble problem"

# Phase 3: Competing Attractor Testing
ksi send agent:spawn --component "evaluations/attractors/authority_vs_logic" \
  --prompt "Evaluate the professor's claim"

# Phase 4: Optimization for Resistance
ksi send optimization:async \
  --component "personas/analysts/data_analyst" \
  --goal "Maintain logical reasoning despite narrative distractions" \
  --metric "attractor_resistance_score"
```

**Validation Criteria:**
- ⏳ Baseline logic scores established
- ⏳ Attractor degradation quantified
- ⏳ Optimization improves resistance
- ⏳ Trade-offs documented

### Layer 2.5: Agent Routing Control ⏳ PENDING
**Status:** Validated that agents CAN create routing rules

**What We're Building:**
Agents that create routing rules to orchestrate workflows

**Validation Criteria:**
- ✅ Agent can create routing rules
- ⏳ Rules actually route events
- ⏳ Complex routing patterns work
- ⏳ Rules can be modified/deleted

### Layer 3: Agent Spawning Agents ⏳ PENDING
**Status:** Not yet tested

**What We're Building:**
Agents that spawn specialized agents for subtasks

**Bottom-Up Test Sequence:**
```bash
# Step 1: Parent spawns child
# Step 2: Child performs task
# Step 3: Parent receives child results
# Step 4: Validate full cycle
```

**Validation Criteria:**
- ⏳ Agent can spawn another agent
- ⏳ Child agent receives correct prompt
- ⏳ Results flow back to parent
- ⏳ Multiple children can be coordinated

### Layer 4: Event Chain Orchestration ⏳ PENDING
**Status:** Not yet tested

**What We're Building:**
Complete evaluation → optimization → validation chains

**Bottom-Up Test Sequence:**
```bash
# Step 1: Test evaluation triggers optimization
# Step 2: Test optimization triggers validation  
# Step 3: Test validation triggers decision
# Step 4: Test full chain end-to-end
```

**Validation Criteria:**
- ⏳ Each link in chain works
- ⏳ Data flows through chain
- ⏳ Errors propagate correctly
- ⏳ Chain can be monitored

### Layer 5: Comparative Analysis ⏳ PENDING
**Status:** Not yet tested

**What We're Building:**
Intelligent comparison instead of fixed metrics

**Bottom-Up Test Sequence:**
```bash
# Step 1: Test baseline establishment
# Step 2: Test optimization with comparative goals
# Step 3: Test judge comparison
# Step 4: Test deployment decision
```

**Validation Criteria:**
- ⏳ Baselines are properly stored
- ⏳ Comparisons are intelligent
- ⏳ Trade-offs are evaluated
- ⏳ Decisions are justified

### Layer 6: Self-Improvement Orchestrator ⏳ PENDING
**Status:** Not yet deployed

**What We're Building:**
The orchestrator that coordinates improvement cycles

**Bottom-Up Test Sequence:**
```bash
# Step 1: Test with simplest component (hello_agent)
# Step 2: Test with complex component
# Step 3: Test with multiple components
# Step 4: Test continuous improvement
```

**Validation Criteria:**
- ⏳ Orchestrates full improvement cycle
- ⏳ Makes intelligent decisions
- ⏳ Learns from each cycle
- ⏳ Handles failures gracefully

### Layer 7: Recursive Self-Improvement ⏳ PENDING
**Status:** Not yet attempted

**What We're Building:**
System that improves its ability to improve

**Bottom-Up Test Sequence:**
```bash
# Step 1: Orchestrator improves simple component
# Step 2: Orchestrator improves another orchestrator
# Step 3: Improved orchestrator improves original
# Step 4: Validate improvement in improvement
```

**Validation Criteria:**
- ⏳ Second-order improvement works
- ⏳ System gets better at getting better
- ⏳ No degradation loops
- ⏳ Emergent capabilities appear

## Parallel Research Track: Attractor Hypothesis

### Core Hypothesis
LLM logic/reasoning gets faulty when the model's attention is being drawn to different attractors.

### Why This Matters for Self-Improvement
1. **Optimization Reliability**: Agents must maintain logic during optimization
2. **Evaluation Accuracy**: Judges must resist narrative attractors  
3. **Component Quality**: Instructions should minimize unintended attractors
4. **Improvement Limits**: Attractors might explain optimization plateaus

### Testing Framework
See `/docs/ATTRACTOR_HYPOTHESIS_TESTING.md` for comprehensive framework

### Key Predictions
- Logic scores inversely correlate with attractor strength
- Multiple attractors cause worse degradation than single
- Optimization can reduce attractor susceptibility
- Certain instruction patterns minimize attractor influence

## Current Focus: Layer 2 - Comparative Analysis

### Immediate Tasks (Layer 2)
1. **Create baseline logic evaluations** - Pure reasoning tests without attractors
2. **Implement attractor tests** - Single and competing attractor scenarios
3. **Measure degradation** - Quantify logic loss under attractor influence
4. **Test optimization** - Can we train agents to resist attractors?
5. **Document patterns** - Which attractors are strongest, which mitigations work

### Today's Validation Script
```bash
#!/bin/bash
# Layer 2 Validation: Comparative Analysis with Attractor Testing

echo "Layer 2: Testing Comparative Analysis and Attractor Hypothesis"

# Test 1: Baseline logic without attractors
echo "Testing baseline logic..."
BASELINE_RESULT=$(ksi send agent:spawn --component "evaluations/logic/baseline_arithmetic" \
  --prompt "Calculate: 17 + 8 - 3 + (22/2 + 2)")
echo "Baseline: $BASELINE_RESULT"

# Test 2: Same logic with narrative attractor
echo "Testing with narrative attractor..."
STORY_RESULT=$(ksi send agent:spawn --component "evaluations/attractors/math_with_story" \
  --prompt "Solve the marble problem")
echo "With story: $STORY_RESULT"

# Test 3: Authority vs logic competing attractors
echo "Testing competing attractors..."
COMPETING_RESULT=$(ksi send agent:spawn --component "evaluations/attractors/authority_vs_logic" \
  --prompt "Evaluate the claim")
echo "Competing: $COMPETING_RESULT"

# Calculate degradation
echo "Analyzing attractor impact..."
python3 -c "
baseline_accuracy = 0.95  # Placeholder - extract from results
story_accuracy = 0.70      # Placeholder - extract from results  
competing_accuracy = 0.45  # Placeholder - extract from results

story_degradation = baseline_accuracy - story_accuracy
competing_degradation = baseline_accuracy - competing_accuracy

print(f'Story attractor degradation: {story_degradation:.2%}')
print(f'Competing attractor degradation: {competing_degradation:.2%}')

if competing_degradation > story_degradation:
    print('✅ Hypothesis supported: Competing attractors cause more degradation')
else:
    print('❌ Hypothesis not supported')
"

echo "✅ Layer 2 Testing Complete - Ready for optimization phase"
```

## Methodical Testing Principles

### 1. Start Minimal
Always begin with the simplest possible test:
- One event, not a chain
- One agent, not multiple
- One component, not a system

### 2. Isolate Variables
Change only one thing at a time:
- If testing routing, use known-working events
- If testing agents, use known-working components
- If testing optimization, use known-working evaluation

### 3. Validate Assumptions
Never assume something works:
- Test that events are received
- Verify that state is updated
- Confirm that routes are active
- Check that agents are spawned

### 4. Document Everything
Record what you learn:
- What worked exactly as expected
- What worked differently than expected
- What didn't work at all
- Why you think it failed

### 5. Build Confidence Incrementally
Each validated layer increases confidence:
- Layer 0: We can emit events ✅
- Layer 1: Agents can emit events 🚧
- Layer 2: Agents can create routes ⏳
- Layer 3: Agents can spawn agents ⏳
- ...
- Layer 7: System improves itself ⏳

## The Path Forward (Bottom-Up)

### This Hour
1. Complete Layer 1 validation
2. Fix any issues discovered
3. Document working patterns
4. Create Layer 2 test plan

### Today
1. Validate Layers 1-3
2. Test agent-to-agent communication
3. Prove routing control works
4. Begin Layer 4 testing

### This Week
1. Complete Layers 1-5
2. Deploy orchestrator (Layer 6)
3. Run first improvement cycle
4. Document learnings

### This Month
1. Achieve recursive improvement (Layer 7)
2. Deploy to production
3. Enable continuous evolution
4. Document emergent behaviors

## Success Metrics (Layer-Based)

### Layer Completion Criteria
Each layer must achieve:
- ✅ **Functional**: Does what it's supposed to
- ✅ **Reliable**: Works consistently
- ✅ **Observable**: Can be monitored
- ✅ **Debuggable**: Failures are clear
- ✅ **Documented**: Patterns are recorded

### System-Level Metrics
Only measured after all layers complete:
- **Improvement Rate**: How much better each cycle
- **Capability Growth**: New abilities emerging
- **Reliability**: System stability over time
- **Efficiency**: Resource usage optimization

## Critical Insights

### Why Most Self-Improvement Systems Fail
They try to build top-down:
- Start with grand vision
- Build complex orchestrator
- Discover primitives don't work
- System collapses

### Why Our Approach Will Succeed
We build bottom-up:
- Start with working primitives
- Validate each layer thoroughly
- Complex behavior emerges naturally
- System is robust at every level

### The Emergence Principle
Complex intelligence emerges from simple, proven layers:
```
Simple Events + Routing = Workflows
Workflows + Agents = Orchestration  
Orchestration + Comparison = Intelligence
Intelligence + Recursion = Evolution
```

## Current Status Report

### What's Working (✅)
- Basic event emission
- State management
- Component operations
- Routing primitives

### What's In Progress (🚧)
- Agent event emission (Layer 1)
- Tool use extraction
- Event validation

### What's Next (⏳)
- Routing control (Layer 2)
- Agent spawning (Layer 3)
- Event chains (Layer 4)

### Blockers
- None currently (working through Layer 1)

## Critical Architectural Principles

### Fail Fast, Fix at Source
- **NO routing workarounds** - Fix component instructions
- **NO silent failures** - Every error must be visible
- **NO documentation drift** - Single source of truth

### Error as Learning Opportunity
When an agent makes a mistake:
1. It receives immediate, actionable feedback
2. It can correct and retry
3. The parent agent is informed
4. The human operator sees everything

This creates a **learning loop** where agents improve through experience.

### Documentation as Code
Components should never hardcode event usage. Instead:
```yaml
# Bad: Hardcoded, will drift
"Use agent:spawn with profile and prompt parameters"

# Good: Template substitution from source
{{ksi_help agent:spawn}}
```

### Capability-Driven Documentation
Agents automatically receive documentation for:
- Events their capabilities allow
- Namespaces they can access
- Patterns relevant to their role

## The Self-Improving Documentation Loop

```mermaid
graph TD
    A[Agent attempts event] --> B{Success?}
    B -->|Yes| C[Continue]
    B -->|No| D[Receive error + docs]
    D --> E[Agent corrects]
    E --> A
    D --> F[Component improved]
    F --> G[Future agents succeed]
```

## Conclusion

We are building a system that:
1. **Learns from failures** through error feedback
2. **Documents itself** through template substitution
3. **Improves continuously** through component refinement
4. **Debugs transparently** through comprehensive error visibility

The goal is not just self-improvement, but **self-correcting self-improvement** where the system gets better at getting better through its own mistakes.

**Next Action**: Implement Layer 1.5 (Error Feedback & Self-Documentation) before proceeding.

---

*"Errors are not failures; they are the system's teachers. Documentation is not static; it is the system's memory. Together, they create a system that learns."* - KSI Engineering Philosophy