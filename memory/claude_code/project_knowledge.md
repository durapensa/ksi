# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven system for autonomous AI agents with dynamic routing architecture.

**Related Documents**: 
- [Documentation Index](../../docs/DOCUMENTATION_INDEX.md) - Complete navigation for 200+ documents
- [Empirical Laboratory](../../docs/KSI_AS_EMPIRICAL_LABORATORY.md) - Revolutionary finding: Intelligence naturally promotes fairness
- [CLAUDE.md](../../CLAUDE.md) - Development workflow guide
- [Context Reference Architecture](../../docs/CONTEXT_REFERENCE_ARCHITECTURE.md) - Dual-Path Context Architecture details
- [KSI Transparency & Alignment Enhancements](../../docs/KSI_TRANSPARENCY_ALIGNMENT_ENHANCEMENTS.md) - AI safety research platform initiative
- [Optimization Approach](../../docs/OPTIMIZATION_APPROACH.md) - DSPy/MIPRO integration and optimization philosophy
- [Optimization Metrics Guide](../../docs/OPTIMIZATION_METRICS_GUIDE.md) - Metric design for effective agent optimization
- [Tournament Optimization Approach](../../docs/TOURNAMENT_OPTIMIZATION_APPROACH.md) - Pairwise comparison-based optimization

## Core Architecture

### Event-Driven System
- **All communication via events**: No direct imports between services
- **Discovery first**: `ksi discover` shows capabilities, `ksi help event:name` for parameters
- **Socket communication**: Events flow through `var/run/daemon.sock`
- **Never import internals**: Always use the event system for cross-service communication

### Dual-Path Context Architecture
- **Implicit Path**: Python contextvars for automatic async propagation
- **Explicit Path**: Context dict parameters for manipulation and boundaries
- **Reference-based storage**: 70.6% storage reduction via context references
- **Both paths essential**: Not legacy/modern, but complementary solutions
- **See**: `/docs/CONTEXT_REFERENCE_ARCHITECTURE.md` for complete details

### Component System (Unified 2025)
- **Everything is a component**: Single model with `component_type` attribute
- **Types**: `core`, `persona`, `behavior`, `workflow`, `evaluation`, `tool`
- **Graph-based**: Entities form directed graphs with event routing
- **Universal spawn**: Component type determines what gets created

### Dynamic Routing Architecture (PRODUCTION)
- **Orchestration system deprecated**: Completely removed - NO backward compatibility
- **Two-layer architecture**: Agents control routing, Infrastructure (transformers + foreach) executes
- **Runtime routing control**: Agents create/modify/delete routing rules via `routing:*` events
- **Foreach transformers**: Multi-target emission replaces static orchestration patterns
- **Parent-scoped rules**: Automatic cleanup when parent entities (agents/workflows) terminate
- **Hierarchical routing**: Events bubble up based on subscription levels (0, 1, N, -1)
- **Full implementation**: See `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` for complete technical details

### Orchestration System Migration
**BREAKING CHANGE - NO BACKWARD COMPATIBILITY**

Technical changes implemented:
- **Service removed**: Deleted `ksi_daemon/orchestration/` directory entirely
- **Event handlers removed**: No `orchestration:*` events handled by services anymore
- **References cleaned**: Updated agent, completion, routing services to remove orchestration imports
- **Component types updated**: `orchestration` → `workflow` in all metadata
- **Discovery updated**: `orchestration` namespace no longer exists (confirmed 33 namespaces)

Migration path for users:
```bash
# OLD: Static orchestration (no longer supported)
# orchestration YAML files are ignored

# NEW: Dynamic workflows via routing
ksi send workflow:create --workflow_id "my_workflow" \
  --agents '[{"id": "coordinator", "component": "components/patterns/workflow_coordinator"}]'

# Coordinator agent uses routing:add_rule to create dynamic routing
```

## Critical Principles

### 1. Always Use Shared Utilities
- **Templates**: `ksi_common.template_utils.substitute_template()`
- **JSON**: `ksi_common.json_utils` (handles nested structures)
- **Timestamps**: `ksi_common.timestamps` utilities
- **Config**: `from ksi_common.config import config`

### 2. Elegant Architecture
- **No workarounds**: Fix issues at source, never special case
- **Data flow integrity**: Preserve all fields through system boundaries
- **System as enabler**: Infrastructure enables, doesn't control behavior
- **Test for workarounds**: If you need exceptions, it's probably wrong

### 3. Component Composition
- **Dependencies work**: Both `dependencies:` and `mixins:` arrays processed
- **Runtime variables flow**: Must preserve through entire dependency chain
- **Behavioral overrides merge**: Applied in dependency order
- **Security profiles compose**: Capabilities resolved through profiles

### 4. Documentation Standards
- **Single-line docstrings**: Event handlers should have concise, descriptive docstrings
- **TypedDict parameters**: Define all parameters in TypedDict classes with inline comments
- **Auto-discovery**: Discovery system extracts parameters from TypedDict + AST analysis
- **No manual examples**: Examples are auto-generated from parameter definitions
- **Why**: Prevents docstring parsing errors where content is misinterpreted as parameters

**Pattern to follow**:
```python
class MyEventData(TypedDict):
    """Event data for my_event handler."""
    name: str  # Component name (e.g., "core/base_agent")
    enabled: NotRequired[bool]  # Whether to enable (default: true)

@event_handler("namespace:my_event")
async def handle_my_event(data: MyEventData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Single-line description of what this handler does."""
    # Implementation here
```

**Anti-pattern to avoid**:
```python
@event_handler("namespace:my_event")
async def handle_my_event(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Long docstring with detailed description.
    
    Args:
        data: Event data with fields:
            - name: Component name
            - enabled: Whether to enable
    
    Returns:
        Success response
        
    Examples:
        ksi send namespace:my_event --name "test"
    """
    # This pattern causes parsing issues!
```

## Working Patterns

### Behavioral Components (Proven)
```yaml
---
component_type: behavior
name: claude_code_override
---
<identity_shift>
You are not Claude Assistant. You execute tasks directly and efficiently.
</identity_shift>
```

### Event Emission Patterns

#### Tool Use Pattern (Production)
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_status_001",
  "name": "agent:status",
  "input": {
    "agent_id": "{{agent_id}}",
    "status": "initialized"
  }
}
```
- **Production Status**: Validated with 100% success rate
- **Component**: `behaviors/communication/ksi_events_as_tool_calls` 
- **Architecture**: Dual-path extraction engine in `ksi_common/tool_use_adapter.py`
- **Validation**: 4/4 event types (agent:status, state:entity:create/update) successfully extracted
- **Integration**: Works seamlessly with base_agent.md v2.0.0 and modern behavioral components

#### Event JSON Format (Dual-Path JSON Emission)
```json
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```
- Direct event emission pattern
- Dual-path extraction supports both event and tool-use formats
- Choose based on agent capabilities and reliability needs

#### Discovery Response Format (Dual-Path)
**CLI Context** (standard format):
```json
{
  "events": {"agent:spawn": {...}, "agent:list": {...}},
  "total": 15,
  "namespaces": ["agent"]
}
```

**Agent Context** (ksi_tool_use format):
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_discover_abc123",
  "name": "discovery:results",
  "input": {
    "request": {"namespace": "agent"},
    "results": {
      "total_events": 15,
      "events": ["agent:spawn", "agent:list", ...],
      "namespaces": {"agent": 15}
    }
  }
}
```

### Agent Communication
```json
{"event": "completion:async", "data": {"agent_id": "target", "prompt": "message"}}
```

### Unified Evaluation
```bash
# Discover evaluated components
ksi send composition:discover --tested_on_model "claude-sonnet-4" --evaluation_status passing

# Certify a component
ksi send evaluation:run --component_path "behaviors/core/claude_code_override" \
  --model "claude-sonnet-4-20250514" --test_suite "basic_effectiveness"
```

## Key Systems

### Discovery System
- **Namespace-based**: `system`, `agent`, `routing`, `workflow`, `composition`, `state`, etc.
- **Dynamic CLI**: Parameters discovered from handlers, not hardcoded
- **Caching**: SQLite cache for expensive TypedDict analysis
- **UX Enhancement**: Automatic namespace level when filtering by namespace
- **Dual-Path JSON Output**:
  - CLI tools receive standard JSON format
  - Agents receive ksi_tool_use format
  - Context detection via `_agent_id` presence
  - Errors remain standard format for all consumers

### Path Resolution System
- **KSI root detection**: Consistent `find_ksi_root()` logic across all components
- **Centralized config**: All paths resolved via `ksi_common/config.py` properties
- **Subdirectory compatibility**: ksi wrapper and daemon work from any project subdirectory
- **Key components**: `daemon_control.py`, `ksi_client/`, `ksi_common/config.py`

### State Management
- **Entity system**: Agents, workflows, routing rules tracked as entities
- **Hierarchical**: Parent-child relationships preserved
- **Query patterns**: `state:entity:get --type agent --id agent_123`

### Capability System
- **Compositional**: Atomic capabilities → Mixins → Profiles
- **Security profiles**: Components declare profile in frontmatter
- **Event permissions**: Profiles map to allowed event lists

### Dynamic Routing System (Production Ready)
- **Runtime Rule Modification**: Agents with `routing_control` capability can add/modify/delete routes
- **Transformer Integration**: Routing rules become event transformers dynamically
- **Priority-Based Resolution**: Higher priority rules win when multiple match
- **TTL Support**: Rules can expire automatically after specified seconds
- **Introspection Integration**: Full visibility into routing decisions via introspection events
- **State Persistence**: Rules survive daemon restarts via state system
- **Validation & Safety**: Pattern validation, circular routing detection, conflict checking
- **Audit Trail**: Complete history of routing changes and decisions
- **Foreach Transformers**: Multi-target emission via iteration (Stage 2.0 complete)
- **See**: `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` for operational guide and architecture details

### Optimization System (Multi-Dimensional Framework)

#### Core Infrastructure
- **Framework Integration**: MIPRO and SIMBA optimizers operational via subprocess architecture
- **Agent-in-the-Loop**: Optimization requires behavioral testing, not just text analysis
- **Context Tracking**: Full optimization lineage through context system
- **Subprocess Architecture**: Long-running optimizations (5-15 min) via detached processes

#### Multi-Dimensional Quality Framework
**Five Quality Dimensions** - Beyond simple token reduction:

1. **Instruction Following Fidelity (IFF)** - 40% weight
   - Measures directive compliance and requirement satisfaction
   - Detects hallucinations and task substitutions
   - Formula: `(tasks_completed/requested * 0.4 + requirements_met/total * 0.3) * hallucination_penalty`

2. **Task Lock-in Persistence (TLP)** - 20% weight  
   - Evaluates focus through long-running tasks
   - Checks for context drift and distraction resistance
   - Formula: `(focus_time/total_time * 0.5 + context_switches_penalty * 0.5)`

3. **Agent Orchestration Capability (AOC)** - 15% weight
   - Assesses multi-agent coordination abilities
   - Tests communication patterns and delegation
   - Formula: `(successful_spawns/attempted * 0.4 + coordination_quality * 0.6)`

4. **Behavioral Consistency (BC)** - 15% weight
   - Validates cross-context stability
   - Ensures persona maintenance
   - Formula: `1 - (behavior_variance / baseline_variance)`

5. **Token Efficiency (TE)** - 10% weight
   - Optimizes cost while preserving quality
   - Formula: `(1 - tokens_used/baseline_tokens) * quality_preservation_factor`

**Overall Quality Score**: `Σ(dimension_score * dimension_weight)`

#### Hybrid Optimization Pipeline
**Three-Method Approach** with decision framework:

1. **DSPy/MIPRO** - Quantitative optimization
   - Best for: Structured tasks, tool-using agents
   - Metrics: Token count, latency, accuracy
   - Execution: 30-50 iterations, hyperparameter search

2. **LLM-as-Judge** - Qualitative refinement
   - Best for: Creative tasks, conversational agents
   - Evaluation: Specialized judge components per dimension
   - Process: Iterative refinement based on judge feedback

3. **Hybrid Pipeline** - Combined approach
   - Phase 1: DSPy quantitative optimization
   - Phase 2: Judge qualitative refinement
   - Phase 3: Tournament validation
   - Result: Balanced optimization across all dimensions

#### Evaluation Infrastructure
- **Judge Components**: Specialized evaluators for each quality dimension
   - `instruction_fidelity_judge.md` - IFF evaluation
   - `task_persistence_judge.md` - TLP evaluation
   - `orchestration_capability_judge.md` - AOC evaluation
   - `behavioral_consistency_judge.md` - BC evaluation
   - `token_efficiency_judge.md` - TE evaluation

- **Test Suites**: Comprehensive evaluation scenarios
   - `basic_effectiveness` - Fundamental functionality
   - `behavioral_effectiveness` - Behavioral consistency
   - `comprehensive_quality_suite` - All 5 dimensions
   - `ksi_tool_use_validation` - JSON emission patterns

- **Dependency Validation** (Enhanced)
   - Components must have passing dependencies
   - Registry tracks evaluation status per component
   - Certification requires all dependencies passing

#### Key Findings
- **0% improvement with minimal metrics** proves need for comprehensive evaluation
- **48.8% token reduction achieved** while maintaining 95% quality (hello_agent case)
- **LLM-as-Judge more reliable** for qualitative aspects than DSPy alone
- **Tournament approach effective** for comparative optimization

#### Documentation
- **See**: `/docs/OPTIMIZATION_APPROACH.md` - Philosophy and implementation
- **See**: `/docs/OPTIMIZATION_METRICS_GUIDE.md` - Metric design patterns
- **See**: `/docs/OPTIMIZATION_COMPARISON_FRAMEWORK.md` - Method selection guide
- **See**: `/docs/HYBRID_OPTIMIZATION_RUNBOOK.md` - Step-by-step execution
- **See**: `/docs/AGENT_IMPROVEMENT_ROADMAP.md` - 6-phase implementation plan

## File Locations

### Core Systems
- `ksi_common/json_extraction.py` - JSON extraction with dual-path support
- `ksi_common/tool_use_adapter.py` - Tool use pattern extraction and conversion
- `ksi_daemon/completion/extract_ksi_tool_use.py` - Tool use integration with completion service
- `ksi_common/component_renderer.py` - Component dependency resolution
- `ksi_daemon/composition/` - Component management and discovery
- `ksi_daemon/evaluation/` - Evaluation and certification

### Dynamic Routing System
- `ksi_daemon/routing/routing_service.py` - Core routing service with TTL management
- `ksi_daemon/routing/routing_events.py` - Event handlers for routing operations
- `ksi_daemon/routing/transformer_integration.py` - Converts rules to transformers
- `ksi_daemon/routing/routing_state_adapter.py` - State persistence for rules
- `ksi_daemon/routing/routing_validation.py` - Rule validation and conflict detection
- `ksi_daemon/routing/routing_audit.py` - Audit trail for routing decisions
- `ksi_daemon/routing/routing_introspection.py` - Visibility into routing decisions
- `ksi_daemon/routing/routing_event_patch.py` - Event router introspection patch
- `ksi_common/foreach_transformer.py` - Foreach transformer processing logic
- `var/lib/transformers/system/workflow_transformers.yaml` - Workflow patterns using foreach

### Optimization & Evaluation System
- `ksi_daemon/optimization/optimization_service.py` - Core optimization service
- `ksi_daemon/optimization/optimization_events.py` - Event handlers for optimization
- `ksi_daemon/optimization/adapters/mipro_adapter.py` - MIPRO/DSPy integration
- `ksi_daemon/optimization/adapters/simba_adapter.py` - SIMBA optimizer adapter
- `ksi_optimize_component.py` - Subprocess script for long-running optimizations
- `ksi_daemon/evaluation/evaluation_events.py` - Evaluation handlers with dependency validation
- `ksi_daemon/evaluation/evaluation_async.py` - Async evaluation support
- `var/db/mlflow_artifacts/` - MLflow tracking and optimization artifacts
- `var/lib/evaluations/registry.yaml` - Component evaluation registry
- `var/lib/evaluations/certificates/` - Evaluation certificates by date
- `components/personas/optimizers/` - Optimization-focused agent personas
- `components/evaluations/judges/` - LLM-as-Judge components for 5 dimensions
- `components/evaluations/suites/` - Test suite definitions
- `components/workflows/agent_optimization_flow` - Agent-driven optimization workflow
- `var/lib/transformers/evaluation/judge_result_routing.yaml` - Judge result transformers

### Configuration
- `var/lib/capabilities/` - Capability definitions
- `var/lib/transformers/` - Event routing rules
- `var/lib/compositions/components/` - All components

### Logs & Data
- `var/logs/daemon/daemon.log.jsonl` - System logs
- `var/logs/responses/{session_id}.jsonl` - Agent responses
- `var/db/composition_index.db` - Unified component/evaluation index

## Common Issues & Solutions

### Agents Ask for Permissions
**Cause**: Missing behavioral override or wrong security profile
**Fix**: Add `behaviors/core/claude_code_override` dependency

### JSON Not Emitted
**Cause**: Conditional language instead of imperative
**Fix**: Use "MANDATORY:" and exact JSON examples

### Components Not Found
**Fix**: `ksi send composition:rebuild_index`

### Timeouts
**Fix**: Check logs, look for serialization errors

### Evaluation System Issues
**Common Issue**: `evaluation:run` times out even though agent tests complete
**Cause**: Multiple issues discovered:
1. `monitor:get_events` doesn't support field filtering - must fetch and filter manually
2. Behavioral components need `ksi_events_as_tool_calls` dependency to emit events
3. Possible async event loop blocking in evaluation handler
**Workaround**: 
- Fixed monitor filtering issue in evaluation_events.py
- Added required dependencies to behavioral components
- Further investigation needed for timeout root cause

## GitHub Issues Tracking

**Active critical issues being tracked on GitHub:**

### Issue #9: Conversation continuity broken for stateless providers (2025-08-07)
**Status**: Open
**Severity**: High - Makes agents unusable for multi-turn conversations with non-Claude models
**Link**: https://github.com/durapensa/ksi/issues/9

**Description**: Agents using stateless providers (ollama, openai, anthropic-api, etc.) cannot maintain conversation continuity. Each completion request creates a new session instead of reusing the agent's existing session.

**Root Cause**: The conversation tracker's `update_request_session()` method fails to properly map agent→session for litellm providers.

**Evidence**: Agent sessions get new IDs on each request instead of reusing existing sessions, causing complete memory loss between interactions.

**Impact**: All non-Claude providers cannot maintain conversation context.

## Current Development Focus (2025-01-27)

### Phase 1: Component Foundation ✅
- Unified evaluation system
- Basic behavioral components (claude_code_override, json_emission)
- Compositional pattern proven

### Phase 2: Dynamic Routing Implementation ✅ COMPLETED
- Build evaluation test suites
- Implement foreach transformers for multi-target emission
- Create parent-scoped routing with auto-cleanup
- Complete orchestration system deprecation

### Phase 3: Emergent Coordination (Current)
- Agent-driven optimization patterns
- Dynamic workflow creation using routing rules
- Meta-coordination and pattern discovery

## Key Insights

1. **Tool use patterns work reliably** - LLMs naturally structure tool calls correctly
2. **Dual-path architectures throughout** - Multiple complementary approaches, not legacy transitions:
   - **Context**: Implicit (contextvars) + Explicit (dict) paths
   - **JSON Emission**: Event JSON + Tool-use JSON paths
3. **Everything is a graph** - Entities, relationships, event routing
4. **Composition over configuration** - Mix behaviors, don't hardcode
5. **System enables, doesn't control** - Agents are autonomous
6. **Dynamic routing enables emergence** - Agents can discover optimal coordination patterns
7. **Infrastructure as substrate** - Two-layer architecture (agents + transformers) replaces three-layer
8. **Introspection is key** - Visibility into routing decisions enables debugging and learning
9. **Orchestration system completely replaced** - Foreach transformers + dynamic routing handle all coordination patterns
10. **Context propagation is foundational** - Enables event trees, request tracing, and system observability

---

## Future Development Patterns

### Long Docstring Migration
Many handlers still use long docstrings that should be migrated to single-line format:
```python
# Current (long form)
@event_handler("example:event")
async def handle_example(data, context):
    """
    Handle example event.
    
    Args:
        data: Event data
        context: System context
        
    Returns:
        Response dict
    """
    
# Target (concise form)  
@event_handler("example:event")
async def handle_example(data, context):
    """Handle example event with minimal description."""
```

This reduces discovery system overhead and improves performance. When migrating, preserve valuable sections like "Returns:", "Examples:" as they provide context for agents.

*Essential development knowledge - for workflows see CLAUDE.md*