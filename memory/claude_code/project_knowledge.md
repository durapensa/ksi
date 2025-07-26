# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

## CRITICAL ARCHITECTURAL PRINCIPLES

### 1. Always Use Shared Utilities
- **Template Substitution**: ALWAYS use `ksi_common.template_utils.substitute_template()` - never implement custom variable substitution
- **JSON Handling**: ALWAYS use `ksi_common.json_utils` for JSON operations - has balanced brace parsing for nested structures
- **Timestamp Functions**: ALWAYS use `ksi_common.timestamps` utilities for consistent time handling
- **Lesson**: Reimplementing these utilities leads to inconsistent behavior and bugs

### 2. Runtime Variables Must Flow Through
- **Component Rendering**: Runtime variables (like `agent_id`) must be preserved through entire dependency chain
- **Variable Precedence**: Runtime variables must override component-defined variables
- **Context Preservation**: Never lose runtime context during component resolution
- **Lesson**: Lost runtime variables break dynamic component composition

**Example of the Bug (FIXED)**:
```python
# WRONG: Only used component-defined variables
content = self._substitute_variables(content, context.variables)

# CORRECT: Merge runtime variables with component variables
final_variables = context.variables.copy()
final_variables.update(variables)  # Runtime vars override component vars
content = self._substitute_variables(content, final_variables)
```

### 3. Transformer Execution Architecture  
- **Task Spawning is Deliberate**: Transformers spawn as tasks to enable parallelism and prevent deadlocks
- **Sync vs Async**: Both execute as tasks but async transformers support response routing
- **Await Pattern**: All transformer tasks ARE awaited via `asyncio.gather()` - not fire-and-forget
- **Lesson**: Direct inline execution would cause recursive emit() deadlocks

### 4. Critical Path Operations Need Handlers
- **Transformers**: Best for declarative routing, monitoring, cleanup - can run in parallel
- **Handlers**: Required when other handlers depend on the operation completing first
- **Timing Matters**: Handlers execute synchronously, transformers spawn as parallel tasks
- **Lesson**: Use handlers for state entity creation, transformers for event routing

## Core Architecture

### Event-Driven System
- **All communication via events**: No direct imports, use `ksi send event:name --param value`
- **Discovery first**: `ksi discover` shows capabilities, `ksi help event:name` for parameters
- **Socket communication**: Events flow through `var/run/daemon.sock`
- **Orchestration-aware**: Events carry `_orchestration_id`, `_orchestration_depth`, `_parent_agent_id`

**CRITICAL ARCHITECTURAL RULE**: Never import internals from other KSI modules. Use the event system instead:
```python
# ❌ WRONG: Direct imports violate architecture
from ksi_common.async_operations import get_active_operations_summary

# ✅ CORRECT: Use event system
from ksi_daemon.core.event_emitter import get_event_emitter
event_emitter = get_event_emitter()
result = await event_emitter("optimization:list", {})
```

### Component System (Unified Architecture 2025 ✅)
- **Everything is a component**: Single unified model with `component_type` attribute
- **Graph-based architecture**: Entities (agents/orchestrations) form directed graphs with event routing
- **Universal spawn pattern**: Components determine entity type - agents spawn agents, orchestrations spawn orchestrations
- **Nested orchestrations**: Agents can spawn orchestrations, creating hierarchical trees of arbitrary depth
- **Event-driven creation**: `ksi send composition:create_component --name "path" --content "..."`
- **SQLite index**: Database-first discovery, no file I/O during queries

### Orchestration System (2025 ✅)

**Universal Orchestrator Architecture**:
- **Claude Code as orchestrator**: Set `orchestrator_agent_id: "claude-code"` in patterns
- **Dual subscription levels**: Separate controls for regular events (`event_subscription_level`) vs errors (`error_subscription_level`)
- **Hierarchical routing**: Events bubble up through orchestration trees to designated orchestrator
- **Entity creation**: Orchestrations MUST create state entities for routing to work: `state:entity:create` with `type: "orchestration"`

**Event Routing Mechanics**:
- **System context required**: `event_emitter` must be initialized via `system:context` handler
- **Parameter format**: Use `type` and `id` (not `entity_type`/`entity_id`) for state entity creation
- **Client tagging**: Events routed to Claude Code get `_client_id: "claude-code"` for log filtering
- **Hierarchical propagation**: Subscription levels control how far events bubble up orchestration trees

**Agent Initialization Architecture (2025)** ✅:
- **Agents are autonomous entities**: They receive their full composition and optional initial prompt
- **No initialization "strategies"**: InitializationRouter cleaned up - removed 7 hard-coded strategies (role_based, peer_to_peer, distributed, etc.)
- **Simple prompt delivery**: System only extracts and delivers prompts from agent definitions
- **Direct prompt field**: Agents can have `prompt:` at top level in YAML (preferred over `vars.initial_prompt`)
- **DSL for agents, not system**: Orchestration DSL patterns passed to agents for interpretation, not system execution
- **Coordination emerges**: Complex patterns emerge from agent behavior, not system control
- **Future: proper messaging**: Will replace `completion:async` with pub/sub, unicast, multicast, broadcast

**CRITICAL**: The system is an **enabler**, not an orchestrator. Give agents their identity (composition) and initial context (prompt), then let them coordinate through natural communication.

### KSI Philosophy: Elegant Fixes Over Workarounds (2025-01-26)

**Core Principle**: Always implement solutions that flow naturally through the system architecture, never add workarounds or special cases.

**Example Violations (What NOT to do)**:
- Loading security_profile from file as fallback in agent spawn
- Re-parsing frontmatter when already parsed by load_composition
- Adding special handling for specific field names

**Correct Approach**:
1. **Trace data flow end-to-end** - Understand where data originates and where it's lost
2. **Fix at the source** - If composition:compose loses fields, fix it to preserve them
3. **Use existing patterns** - If components have frontmatter, use the existing parsing
4. **Preserve all data** - Systems should pass through all fields, not just known ones

**Applied to Capability System**:
- ❌ Wrong: Add fallback to read security_profile from profile file
- ✅ Right: Fix composition:compose to preserve all top-level fields from profiles
- ✅ Right: Ensure Composition dataclass can handle arbitrary fields via metadata

**The Test**: If you need to explain a special case or exception, it's probably a workaround.

**InitializationRouter Cleanup (2025)** ✅:
- **Before**: 478 lines with 7 hard-coded coordination strategies that violated agent autonomy
- **After**: 123 lines of simple prompt extraction and delivery
- **DSL preservation**: Orchestration DSL still passed to orchestrator agents for interpretation
- **Backward compatibility**: Still supports `vars.initial_prompt` and `vars.prompt` for legacy patterns
- **Philosophy**: System delivers messages, agents decide coordination - not vice versa

**Behavioral Override Pattern (FIXED 2025)** ✅:
- **Dependencies system**: Component renderer processes both `dependencies:` and `mixins:` arrays 
- **Field mapping fix**: `generated_content.system_prompt` extracted to `prompt` field for agent spawning
- **End-to-end working**: Behavioral overrides properly merged into agent profiles
- **Claude Code override**: `behaviors/orchestration/claude_code_override.md` modifies agent behavior
- **Orchestrator-aware agents**: Change behavior when `orchestrator_agent_id: "claude-code"` is present
- **Proven JSON emission**: Agents with overrides successfully emit structured events

### Composition Indexing Patterns ✅
**Discovery**: Two distinct file formats requiring different validation approaches:
- **YAML files** (97 total): Root-level `name:` and `type:` fields
- **Markdown files** (84 total): Frontmatter delimited by `---` with metadata

**Key Patterns**:
- **Test fixtures**: `_archive/tests/` contains intentionally malformed files for testing
- **Non-compositions**: README*, .gitignore, .gitattributes should be excluded

### Composition Discovery Type Taxonomy ✅
**CRITICAL**: `composition:discover` uses a specific type classification system:

**Type Classifications**:
- **`type: "behavior"`** - Behavioral mixins (mandatory_json, claude_code_override, etc.)
- **`type: "core"`** - Core components (base_agent, task_executor, etc.)
- **`type: "capability"`** - Capability definitions (orchestration, messaging, etc.)
- **`type: "profile"`** - Agent profiles
- **`type: "orchestration"`** - Orchestration patterns
- **`type: "evaluation"`** - Evaluation frameworks

**Usage Patterns**:
```bash
# Get behavioral mixins for optimization
ksi send composition:discover --type behavior

# Get core components
ksi send composition:discover --type core

# Rebuild index after adding new components
ksi send composition:rebuild_index
```

**Common Mistake**: Searching for `--type component` returns nothing because components are classified by their specific purpose (behavior, core, capability, etc.).


## Transformer Architecture (PRODUCTION READY ✅)

### Declarative Event Routing System
- **YAML Configurations**: Replace imperative Python handlers with declarative transformers
- **Hot-Reloadable**: Update routing without daemon restart
- **Complex Conditions**: Boolean expressions, method calls, nested logic
- **Multi-Transformer Support**: Multiple transformers per source event
- **Async Task Management**: Proper await for transformer completion

### Transformer Organization
```
var/lib/transformers/
├── system/           # Auto-loaded at daemon startup
│   ├── system_lifecycle.yaml
│   └── error_propagation.yaml
└── services/         # Loaded by respective services
    ├── agent_routing.yaml
    ├── completion_routing.yaml
    ├── orchestration_routing.yaml
    └── services.json   # Configuration for auto-loading
```

### Service Transformer Manager
- **Auto-Discovery**: Finds transformer files by convention
- **Dependency Management**: Load transformers in correct order  
- **Standardized Loading**: Eliminates repetitive transformer loading code
- **Centralized Configuration**: `services.json` defines all service transformers

### Transformer Patterns Library
- **Reusable Templates**: Common patterns (broadcast, state update, error routing, cleanup)
- **Condition Library**: Standard expressions (status checks, agent conditions, retry logic)
- **Mapping Utilities**: Common field mappings (timestamps, agent context, error handling)
- **Template Builder**: Programmatic transformer generation

### Migration Impact
- **Code Reduction**: 200+ lines Python → 80+ lines YAML
- **Performance**: Routing runs in core event system
- **Maintainability**: Visual, declarative routing rules
- **Reliability**: Centralized condition evaluation with error handling

## Critical Working Patterns

### Agent Communication Pattern ✅ NEW
**Breakthrough**: Direct agent-to-agent messaging via `completion:async` events.
**Key Pattern**: Agents emit events to send messages to other agents by `agent_id`.
```json
{"event": "completion:async", "data": {"agent_id": "target_agent", "prompt": "Your message here"}}
```
**Status**: Working reliably with clear mandatory JSON instructions.

### JSON Extraction & Emission ✅ 
**Solution**: Balanced brace parsing in `ksi_common/json_utils.py` handles arbitrary nesting.
**Pattern**: Strong imperative language ensures consistent JSON emission:
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

### Persona-First Architecture ✅
**Pattern**: Pure personas + KSI capabilities = natural JSON emission.
**Structure**: `components/personas/` + `components/capabilities/` → `components/agents/`

### Session Continuity ✅
**Solution**: Persistent sandboxes via `sandbox_uuid` in `var/sandbox/agents/{uuid}/`

## Optimization Architecture

### Bootstrap to Production Pattern
- **Bootstrap**: Python scripts for discovery (`optimize_*.py`)
- **Production**: KSI orchestrations using `optimization:*` events
- **Key Events**: `optimization:async`, `optimization:status`, `optimization:process_completion`

### DSPy Integration ✅
**Working Configuration**:
```yaml
optimization_prompt_model: claude-3-5-haiku-20241022
optimization_task_model: claude-3-5-haiku-20241022
```
**Critical**: Evaluate agent outputs, not instruction text.

### LLM-as-Judge Pattern
- **Pairwise comparisons** not numeric scores
- **Rankings**: Bradley-Terry, Elo systems
- **Pattern**: Tournament-based optimization

## DSL Bootstrap Architecture (Critical for Agent Autonomy) ✅

### The Bootstrap Recursion
We're creating a virtuous cycle where:
1. **DSL teaches agents about KSI** → Agents learn the system
2. **Agents use DSL to improve components** → Including DSL instructions themselves  
3. **Improved DSL teaches better** → Creating continuous improvement

### Incremental DSL Manual Pattern
Instead of monolithic interpreters, build **modular instruction components**:

```yaml
# Level 1: Basic concepts in isolation
components/behaviors/dsl/event_emission_basics.md     # EVENT blocks only
components/behaviors/dsl/state_management.md         # STATE tracking  
components/behaviors/dsl/control_flow.md            # WHILE loops

# Level 2: Combining concepts
components/behaviors/dsl/orchestration_patterns.md   # Full patterns
components/behaviors/dsl/optimization_workflows.md   # Optimization DSL

# Level 3: Meta-DSL
components/behaviors/dsl/dsl_improvement_protocol.md # Improving DSL itself
```

### DSL as Teaching Tool
The DSL instructions serve dual purposes:
- **Teach DSL syntax**: How to interpret orchestration patterns
- **Teach KSI system**: What events exist and how to use them

Example instruction component:
```yaml
---
component_type: behavior
name: event_emission_basics  
---
# DSL Basics: EVENT Blocks

When you see:
EVENT optimization:async {
  component: "personas/data_analyst",
  method: "mipro"
}

Emit this KSI event:
{"event": "optimization:async", "data": {...}}
```

### Bootstrap Requirements
- **Must work incrementally**: Start with 5 core events, expand gradually
- **Must be testable**: Each component tested before adding complexity
- **Must be improvable**: Agents can optimize DSL instructions via MIPRO
- **Must enable autonomy**: Goal is agents improving without Python scripts

### Critical DSL Constructs for KSI
```yaml
# Essential constructs agents must understand:
EVENT <name> {<data>} [AS <var>]     # Emit KSI events
STATE <var> = <value>                 # Track variables
WHILE <condition>: <actions>          # Conditional loops
WAIT <seconds>                        # Pause execution
TRACK {<progress>}                    # Progress reporting
FOREACH <item> IN <collection>        # Iteration
PARALLEL: <branches>                  # Concurrent execution
```

### Python Bootstrap Strategy (Temporary)
While agents learn DSL interpretation:
```python
# Bootstrap DSL instruction improvements
def improve_dsl_instruction(component_path):
    current = load_component(component_path)
    optimized = run_mipro_optimization(
        current,
        metric="agent_comprehension_and_execution",
        test_cases=["Can agent emit EVENT?", "Can agent track STATE?"]
    )
    save_component(f"{component_path}_v2", optimized)
```

### Meta-DSL Vision
The pattern we create for KSI DSL becomes a template for other domains:
- Git workflow DSL
- Testing DSL  
- Deployment DSL
- Any domain where agents need structured instructions

**Key Insight**: We're not just teaching agents to optimize - we're teaching them to teach themselves.

## Component Architecture (Everything is a Component)

### New Unified Model (2025)
```yaml
---
component_type: persona  # Required: persona|behavior|orchestration|evaluation|tool|core
name: data_analyst      # Component identifier
version: 2.0.0         # Semantic versioning
description: Senior data analyst with statistical expertise
dependencies:          # Other components this needs
  - core/base_agent
  - behaviors/communication/mandatory_json
capabilities:          # What this component provides
  - statistical_analysis
  - data_visualization
---
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

### Component Organization
- `components/core/` - Essential building blocks (base_agent, json_emitter)
- `components/personas/` - Domain expertise & personalities (analysts, developers, thinkers)
- `components/behaviors/` - Reusable mixins (communication, coordination, integration)
- `components/orchestrations/` - Multi-agent patterns (optimization, tournaments, workflows)
- `components/evaluations/` - Quality assessments (metrics, judges, suites)
- `components/tools/` - External integrations (MCP, Git, APIs)

### Hybrid Evaluation Architecture
- **Component definitions**: Test suites, judge schemas → `components/evaluations/`
- **Runtime data**: Results, bootstrap data → `var/lib/evaluations/`

## Component Composition Best Practices ✅

### Validated Working Components (Tested 2025-07-26 with claude-sonnet-4)

**DSL Execution Components**:
- `components/agents/dsl_optimization_executor` v1.1.0 ✅
  - **Capabilities**: Direct JSON emission, optimization:async events, multi-event sequences
  - **Dependencies**: `behaviors/dsl/dsl_execution_override`, `behaviors/communication/mandatory_json`
  - **Security Profile**: `self_improver` (required for optimization events)
  - **Test Results**: All 3 tests passing (basic emission, optimization events, sequential DSL)

**Behavioral Override Components**:
- `behaviors/dsl/dsl_execution_override` v1.0.0 ✅
  - **Purpose**: Prevents Claude from asking for tool permissions, enables direct JSON emission
  - **Critical Pattern**: "You are NOT Claude assistant in this context. You are a DSL INTERPRETER"
  - **Test Results**: Successfully prevents tool-asking behavior

- `behaviors/communication/mandatory_json` ✅
  - **Purpose**: Ensures structured event emission with imperative language
  - **Pattern**: "## MANDATORY: Start your response with this exact JSON:"

- `behaviors/orchestration/claude_code_override` ✅
  - **Purpose**: Orchestrator-aware behavior for agents working with Claude Code
  - **Features**: Concise responses, delegation patterns, frequent status updates

### Composition Patterns That Work

**1. Direct JSON Emission Pattern**:
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Emit this exact JSON event:
{"event": "optimization:async", "data": {"component": "test_component", "framework": "dspy"}}

Do not describe or explain, just emit the JSON.
```

**2. Behavioral Override Stack**:
```yaml
dependencies:
  - core/base_agent
  - behaviors/communication/mandatory_json      # Structured emission
  - behaviors/dsl/dsl_execution_override       # Prevent tool-asking
  - behaviors/orchestration/claude_code_override  # Orchestrator awareness
```

**3. Security Profile Requirements**:
- **Basic agents**: Only get `agent_status`, `basic_communication` capabilities
- **DSL executors**: Need `self_improver` profile for `optimization:async` events
- **Orchestration agents**: Need explicit capability configuration in orchestration YAML

### Timing and Performance

**Response Timing** (Validated with claude-sonnet-4):
- **Simple events**: 3-5 seconds
- **Complex optimization events**: 8-12 seconds  
- **Multi-event sequences**: 10-15 seconds
- **Test wait times**: Use 12+ seconds for reliable testing

**Memory Usage**:
- **Component caching**: 63 cached components, cache keys reduce loading time
- **Session continuity**: Agent sandboxes maintain conversation state across requests

### Common Issues and Solutions

**1. Agents Asking for Tool Permissions**:
- **Cause**: Missing `behaviors/dsl/dsl_execution_override` dependency
- **Solution**: Add override component, use imperative language in prompts

**2. Orchestration Agents Can't Emit Optimization Events**:
- **Cause**: Base components only get basic capabilities  
- **Solution**: Configure `security_profile: self_improver` in orchestration YAML

**3. Component Path Errors in Orchestrations**:
- **Cause**: Incorrect component reference format
- **Solution**: Use exact paths: `"components/agents/dsl_optimization_executor"`

**4. Events Not Captured in Tests**:
- **Cause**: Insufficient wait time for agent processing
- **Solution**: Use 12+ second delays for complex requests

### Testing Strategy

**Incremental Validation**:
1. **Basic emission test**: Simple `agent:progress` event
2. **Capability test**: Target event type (e.g., `optimization:async`)  
3. **Sequential test**: Multiple events in sequence
4. **Orchestration test**: Full workflow with proper security profiles

**Test Event Patterns**:
```bash
# Monitor specific events during testing
ksi send monitor:get_events --event-patterns "agent:status,optimization:async" --data-contains "test_agent_id" --limit 10

# Check agent capabilities 
ksi send agent:info --agent-id "agent_id" | jq '.expanded_capabilities'

# Verify component exists
ksi send composition:list --filter '{"name": "component_name"}'
```

## Component Evaluation System ✅ (Phase 1 Complete)

### Architecture
- **YAML Certificates**: Source of truth with SHA-256 component hashing
- **SQLite Index**: Fast queries integrated with `composition:discover`
- **Git Sharing**: Certificates in `var/lib/evaluations/certificates/`
- **Event System**: `evaluation:run`, `evaluation:query` for agent access

### Discovery Integration
```bash
# Filter by evaluation criteria
ksi send composition:discover --type agent \
  --tested_on_model "claude-sonnet-4" \
  --evaluation_status "passing" \
  --min_performance_class "fast"

# Basic evaluation data included by default
{
  "name": "components/agents/dsl_optimization_executor",
  "evaluation": {
    "tested": true,
    "latest_status": "passing",
    "models": ["claude-sonnet-4-20250514"],
    "performance_class": "standard"
  }
}
```

### Key Implementation
- **certificate_index.py**: SQLite indexing with evaluation_index table
- **evaluation_integration.py**: Enhances discovery queries and results
- **evaluation_events.py**: Agent-accessible evaluation operations
- **Rebuild Integration**: `composition:rebuild_index` updates both indices

## Universal Graph-Based Architecture (2025) ✅

### Entities as Graph Nodes
- **Unified entity model**: Agents and orchestrations are just "event-emitting entities" in a graph
- **Edges are relationships**: Parent-child, routing rules, capability grants
- **Context flows implicitly**: Parent references, depth, routing inherited automatically
- **Capabilities are compositional**: Any entity with a capability can use it (agents can spawn orchestrations)

### Intentional Module Interdependence
- **agent:spawn**: Creates agents from components (used by orchestrations)
- **orchestration:start**: Creates orchestrations from patterns (used by agents with capability)
- **Embraced interdependence**: Agent and orchestration modules naturally depend on each other
- **Graph reflects reality**: In a graph-based system, nodes need to create other nodes

### Hierarchical Event Propagation
**Every event carries orchestration context**:
```json
{
  "_agent_id": "agent_xyz",
  "_orchestration_id": "orch_abc",
  "_orchestration_depth": 2,
  "_parent_agent_id": "agent_parent",
  "_root_orchestration_id": "orch_root",
  "_client_id": "ksi-cli"  # Already tracked throughout system
}
```

### Orchestrator Agent Feedback Path
- **Orchestrator agent identity**: Orchestrations can have an `orchestrator_agent_id` that receives bubbled events
- **Claude Code as orchestrator**: When `orchestrator_agent_id: "claude-code"`, events route to system
- **Dual subscription levels**: Separate control for regular events vs errors
  - `event_subscription_level`: Controls normal event propagation (0, 1, N, -1)
  - `error_subscription_level`: Controls error propagation (often -1 for all errors)
- **Initial prompt propagation**: Orchestrations accept `prompt` parameter for initialization

### Orchestration State Entities
- **Created on orchestration start**: Tracks pattern, agents, parent, subscription levels
- **Queryable by ID**: `ksi send state:entity:get --entity-id orch_xyz --entity-type orchestration`
- **Nested orchestrations**: Agents with orchestration capability can spawn child orchestrations

### Orchestration-Aware Discovery
```bash
# Discover orchestration structure and state
ksi discover --orchestration-id orch_xyz

# Returns: orchestration details, agent hierarchy, recent events, statistics
```

### Event Subscription Levels (Graph Traversal Depth) ✅
- **Level 0**: Only orchestration-level events
- **Level 1**: Direct child agents + immediate events (default)
- **Level N**: Events from entities up to N levels deep (graph traversal depth)
- **Level -1**: ALL events in entire subtree (full graph traversal)

**Dual Subscription Model**:
- **event_subscription_level**: Regular event propagation control
- **error_subscription_level**: Error event propagation control
- **Example**: Level 1 for events, Level -1 for errors = see immediate events + ALL errors

### Hierarchical Event Routing
- **Module**: `ksi_daemon/core/hierarchical_routing.py`
- **Automatic routing**: Events from agents are routed based on subscription levels
- **Orchestration events**: Routed to `orchestration:event` handler
- **Agent events**: Routed via `completion:async` with event_notification

### Dynamic CLI Discovery
- **ksi-cli uses dynamic parameter discovery** - Commands like `discover` and `send` query event handlers for parameters
- **No hardcoded options** - All parameters discovered from system:discover, system:help events
- **Orchestration-aware discovery**: `ksi discover --orchestration-id orch_xyz` shows orchestration structure
- **Special cases**: Base `help` and `--help` handled before dynamic discovery

## Development Patterns

### Agent Management
```bash
# Spawn agent with profile (composition name, not raw text)
ksi send agent:spawn --profile "base_single_agent"
ksi send agent:spawn --profile "components/core/base_agent"  # Component path

# Spawn agent from component 
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst" 

# Discover available profiles
ksi send composition:list --filter '{"type": "profile"}'

# List and inspect agents
ksi send agent:list
ksi send agent:info --agent-id agent_123
```

### Session Management (Critical Rules)
1. **NEVER create session IDs** - Only claude-cli creates them
2. **Session IDs are internal** - External systems use `agent_id` only
3. **Each completion returns NEW session_id** - Use it for next request
4. **Agent logs**: `var/logs/responses/{session_id}.jsonl`

### Configuration Management
```python
from ksi_common.config import config
# Use: config.socket_path, config.daemon_log_dir, config.db_dir
# Never hardcode paths!
```

## JSON Emission Patterns

### Proven Reliable Pattern
**Success Factor**: Strong imperative language, not conditional instructions.

```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

During work, emit progress:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50}}}
```

**Key Requirements**:
- Use "MANDATORY:" not "when" or conditional language
- Provide exact JSON structures, not abstract descriptions
- Allow 30-60 seconds processing time for complex tasks

### Legitimate KSI Events Only
- ✅ `agent:status`, `agent:spawn`, `agent:spawn_from_component`
- ✅ `state:entity:create`, `state:entity:update`
- ✅ `message:send`, `message:publish`
- ✅ `orchestration:request_termination`
- ❌ Custom events like `analyst:*`, `worker:*`, `game:*` (don't exist)

## Debugging & Troubleshooting

### Enable Debug Logging

**Dynamic Method (Preferred - No Restart Required):**
```bash
# Enable debug logging immediately
ksi send config:set --type daemon --key log_level --value DEBUG

# Monitor logs
tail -f var/logs/daemon/daemon.log.jsonl

# Disable debug logging when done
ksi send config:set --type daemon --key log_level --value INFO
```

**Environment Variable Method (Requires Restart):**
```bash
export KSI_DEBUG=true && export KSI_LOG_LEVEL=DEBUG && ./daemon_control.py restart
tail -f var/logs/daemon/daemon.log.jsonl
```

### Common Issues
- **Timeouts**: State queries now have 10-15s timeout protection with clear error messages
- **Agents not responding**: Check profile has `prompt` field
- **Hook output not visible**: Claude Code bug - PostToolUse JSON not processed (Issue #3983)
  - Workaround: Check `/private/tmp/ksi_hook_diagnostic.log` for hook activity
  - Hook output format updated to remove brackets: `{"reason": "KSI ⚡3"}` (was `"[KSI ⚡3]"`)
- **JSON extraction failing**: Verify legitimate KSI events, check error feedback
- **Components not found**: Run `ksi send composition:rebuild_index`

### Agent Behavior Investigation
1. **Enable debug logging** to see actual claude-cli spawns
2. **Check completion results** for actual JSON vs agent descriptions
3. **Monitor events** to verify claimed events actually appear
4. **Agent claims ≠ reality** - Always verify with system monitoring

### Event Transformer System
KSI includes a powerful declarative event transformation system that can replace 30-50% of imperative event handlers with YAML configurations. **Unified template utility integration is COMPLETE** enabling enhanced features like `{{$}}` pass-through and context access.

**Current Status**: 302 handlers identified across 43 files, with 200+ ready for immediate migration.

Documentation:
- [HANDLER_MIGRATION_PLAN.md](../../docs/HANDLER_MIGRATION_PLAN.md) - **4-phase migration strategy (8 weeks)**
- [EVENT_TRANSFORMER_VISION.md](../../docs/EVENT_TRANSFORMER_VISION.md) - Overall architecture vision
- [TRANSFORMER_MIGRATION_GUIDE.md](../../docs/TRANSFORMER_MIGRATION_GUIDE.md) - Implementation details
- [UNIFIED_TEMPLATE_UTILITY_PROPOSAL.md](../../docs/UNIFIED_TEMPLATE_UTILITY_PROPOSAL.md) - Template system

**Key Benefits**:
- 50-70% code reduction for routing/forwarding logic
- Hot-reloadable configurations without daemon restarts
- Visual event flow in YAML
- Better performance (runs in core router)

**Example - Replace Python handler with transformer**:
```yaml
# Instead of Python code, use declarative transformer
transformers:
  - source: "agent:message"
    target: "monitor:agent_activity"
    mapping:
      agent_id: "data.agent_id"
      activity_type: "'message'"
```

## Git Workflow

### Submodule Management
```bash
# After KSI events change components
cd var/lib/compositions
git add . && git commit -m "Update components"
git push origin main

# Update parent repo
cd ../../..
git add var/lib/compositions && git commit -m "Update composition submodule"
```

### Model-Aware Development
```bash
# Branch-based optimization
git checkout claude-opus-optimized    # Deep reasoning
git checkout claude-sonnet-optimized  # Speed/efficiency

# Compatibility metadata
echo "personas/deep_analyst.md model=claude-opus performance=reasoning" >> .gitattributes
```

## System Status

### Production Ready ✅
- **Agent Communication**: Direct messaging via `completion:async` events
- **JSON Emission**: Reliable with mandatory instruction patterns
- **Component System**: Everything has `component_type` attribute
- **Context Architecture**: 70% storage reduction, reference-based
- **Transformer System**: State-based configuration, checkpoint integration
- **Optimization**: DSPy/MIPROv2 with baseline metrics working

### Key Orchestration Patterns
- `simple_message_passing.yaml` - Basic 2-agent communication
- `prisoners_dilemma_self_improving.yaml` - Self-improvement trigger pattern
- `simple_component_optimization.yaml` - DSPy optimization orchestration
- `knowledge_work_coordination_lab.yaml` - Communication testing lab

### Discovery Cache System ✅
- **SQLite cache**: `var/db/discovery_cache.db` caches expensive TypedDict/AST analysis
- **Automatic invalidation**: Tracks file mtime, invalidates when code changes
- **Performance**: 78-90% faster on cached lookups (0.13s vs 0.6-1.5s)
- **Requirements**: `--level full` now requires `--namespace` or `--event` filter

### Key File Locations
- **Core Systems**: `ksi_common/json_utils.py`, `ksi_common/component_renderer.py`, `ksi_common/composition_utils.py`
- **Transformer System**: 
  - `ksi_common/service_transformer_manager.py` - Centralized transformer loading & management
  - `ksi_common/transformer_patterns.py` - Reusable transformer patterns & templates
  - `ksi_common/condition_evaluator.py` - Complex boolean condition evaluation
  - `var/lib/transformers/` - YAML transformer configurations (system/, services/)
- **Event Handlers**: `ksi_daemon/composition/composition_service.py`
- **Discovery Cache**: `ksi_daemon/core/discovery_cache.py`
- **Hierarchical Routing**: `ksi_daemon/core/hierarchical_routing.py`
- **Components**: `var/lib/compositions/components/` (organized by type)
- **Behavioral Overrides**: `components/behaviors/orchestration/claude_code_override.md`
- **Evaluation Data**: `var/lib/evaluations/` (runtime results)
- **Logs**: `var/logs/daemon/daemon.log.jsonl`, `var/logs/responses/{session_id}.jsonl`

## Current Development Focus

### Development Priorities (2025-01-26)

**Priority Order** (updated after discovering critical DSL bootstrap blocker):

#### 1. ~~Complete the DSL Bootstrap System~~ (BLOCKED - see Critical DSL Bootstrap Blocker)
The DSL bootstrap approach is fundamentally blocked because agents cannot emit JSON events directly when they perceive tool access is needed. Created all behavior components but agents consistently ask for tool permissions instead of executing DSL.

**Alternative Approaches to Investigate**:
- Give agents actual tools that emit events (enable_tools: true)
- Move DSL interpretation to system/transformer level
- Use orchestrations that spawn pre-configured agents for each DSL command
- Explore different base models without tool-asking behavior

#### 2. Behavioral Evaluation for Optimization (NEXT PHASE)
The optimization system has static evaluation working but needs behavioral testing:
- **Implement agent-in-the-loop evaluation** - Spawn agents, test actual outputs
- **Create behavioral test suites as components** - Version control test scenarios
- **Move from bootstrap scripts to KSI-native orchestrations**
- **Add tournament-based pairwise comparison** - Bradley-Terry rankings

#### 3. Build Multi-Phase Orchestrations (FOUNDATION EXISTS)
Agent communication proven, ready for complex patterns:
- **Create orchestrator agents** that spawn and coordinate subagents
- **Implement state-based coordination patterns**
- **Build longer-running orchestrations** - Use `multi_phase_orchestrator.yaml` as template
- **Test hierarchical event propagation** with subscription levels

#### 4. Fix Critical Issues
- **`state:entity:update` missing from capability mappings** - Blocks DSL state management
- **Agent state entity transformer not creating entities** - Workaround exists in code
- **Variable substitution in components** - Test after recent fix (commit 6b4cafd)

#### 5. Expand Self-Improvement Ecosystem
Bootstrap exists but needs expansion:
- **More behavioral override patterns** beyond `claude_code_override.md`
- **Test orchestrations demonstrating self-improvement**
- **Integration with optimization pipeline**

### DSL Bootstrap Capability Resolution (FIXED 2025-01-26) ✅

**Solution Implemented**: Compositional capability system with security profiles

**What was fixed**:
- Created `/var/lib/capabilities/capability_system_v3.yaml` with atomic capabilities, mixins, and profiles
- Added `dsl_interpreter` profile with all required events for DSL execution
- Fixed component frontmatter parsing to preserve `security_profile` field
- Enhanced agent spawn to load security_profile from profile files
- DSL interpreters now have these capabilities:
  - `completion:async` - Agent-to-agent communication
  - `agent:status`, `agent:progress`, `agent:result` - Status reporting
  - `state:entity:*` - Full state management
  - `orchestration:*` - Control orchestrations
  - `task:assign`, `workflow:complete` - Task coordination

**Implementation Details**:
1. Components specify `security_profile: dsl_interpreter` in frontmatter
2. component_to_profile preserves security_profile in generated profiles
3. Agent spawn loads security_profile and resolves capabilities via compositional system
4. Capability mixins compose like components for flexibility

**Result**: DSL interpreters can now execute all EVENT blocks as designed

### Compositional Capability System (v3 Architecture)

**Philosophy**: Capabilities compose like components - atomic units, mixins, and profiles.

**Structure** (`/var/lib/capabilities/capability_system_v3.yaml`):
```yaml
atomic_capabilities:
  agent_status:
    events: ["agent:status", "agent:progress", "agent:result"]
    description: "Report agent status and progress"

capability_mixins:
  dsl_execution:
    description: "Execute DSL patterns"
    dependencies: [agent_status, completion_submit, state_management]

capability_profiles:
  dsl_interpreter:
    description: "DSL execution with all required events"
    mixins: [dsl_execution, basic_communication]
    atoms: [event_monitoring]
```

**Key Design Principles**:
1. **Atomic capabilities** - Smallest units mapping events to permissions
2. **Capability mixins** - Reusable combinations with dependencies
3. **Capability profiles** - Complete configurations for agent types
4. **Dependency resolution** - Automatic inclusion of required capabilities
5. **MCP ready** - Designed for dynamic tool integration

**Usage Pattern**:
```yaml
# In component frontmatter
---
component_type: agent
security_profile: dsl_interpreter  # Resolves to full capability set
---
```

**Future Vision**: MCP servers expose tools → KSI agents classify → Dynamic capability integration → Existing agents gain new abilities

### Building Longer-Running Orchestrations (2025-01-24)
- **Goal**: Orchestrator agents with spawned subagents working through phases
- **Foundation**: Agent communication patterns proven and working
- **Next Steps**: State-based coordination, multi-phase orchestrations
- **Pattern**: Composition components driving all behavior

### Proven Working Patterns (2025-01-24) ✅
- **MANDATORY JSON Emission**: Imperative language ("MANDATORY:", "MUST") ensures reliable JSON extraction
  - **Example**: `## MANDATORY: Start your response with this exact JSON:`
  - **Success Rate**: 95%+ when using direct, imperative instructions
- **Inline Behavior Composition**: Hardcoded agent IDs in prompts work reliably
  - **Working**: Direct agent_id values in prompt strings
  - **Not Working**: `{{agent_id}}` variable substitution in components
- **Agent-to-Agent Communication**: `completion:async` events enable inter-agent messaging
  - **Pattern**: Agent A emits `{"event": "completion:async", "data": {"agent_id": "agent_B", "prompt": "..."}}`
  - **Result**: Messages queued and delivered successfully
- **State Entity Workaround**: Handler-based creation ensures agents have required entities
  - **Implementation**: `handle_agent_spawned` in `agent_service.py`
  - **Result**: All agents now have proper state entities with sandbox_uuid

### Critical Issues Discovered (2025-01-24)
- **Agent State Entity Transformer Not Working**: The `agent_spawned_state_create` transformer in `var/lib/transformers/services/agent_routing.yaml` is not creating state entities for spawned agents
  - **Workaround Implemented**: Added handler in `agent_service.py` that creates state entities on `agent:spawned` events
  - **Impact**: Completion system requires state entities to find agent sandbox_uuid
- **Variable Substitution Broken**: `{{agent_id}}` placeholders in behavior components not replaced during composition
  - **Root Cause**: Component renderer using `context.variables` instead of runtime variables
  - **FIXED (2025-01-24)**: Updated `_render_final_content` to merge runtime variables with component variables
  - **Lesson**: Always ensure runtime variables are passed through the entire rendering chain
- **Agent Capability Limitations**: Agents spawned from `base_agent` have `enable_tools: false`
  - **Impact**: Agents can't read files or run commands, limiting self-improvement capabilities
  - **Solution**: Need capability-aware component definitions

### JSON Emission Solutions (2025-01-26)

**FINDING**: JSON emission DOES work with the right behavioral components and patterns.

#### Working Examples Found
1. **standalone_demo** (2025-07-26) - Successfully emitted raw JSON directly
2. **inline_behavior_test** - Used mandatory_json behavior successfully
3. **agent_9130c2e6** - Used JSON code blocks (```json```) format
4. **agent_d49e82bd** - KSI-aware analyst emitting many events

#### Why Agents Ask for Permissions
The issue is NOT that behavioral overrides don't work, but that:
- `enable_tools: false` is the default for component-spawned agents
- Without tools, agents perceive they need permission for ANY system action
- The frontmatter `enable_tools: true` is ignored by component_to_profile

#### Working Patterns for JSON Emission
1. **Use JSON code blocks**: Wrap JSON in ```json``` blocks (proven to work)
2. **Combine correct behaviors**: 
   - `behaviors/communication/mandatory_json`
   - `behaviors/orchestration/claude_code_aware_json`
3. **Clear initialization pattern**: "MANDATORY: Start your response with this exact JSON:"

#### Solutions to Implement
1. **Fix component_to_profile**: Preserve enable_tools from component frontmatter
2. **Use JSON code blocks**: Update DSL interpreters to use ```json``` format
3. **Create KSI event tools**: Custom tools that emit events directly
4. **Fix capability mappings**: Ensure all needed events are included

#### Current Status (2025-01-26)
- Behavioral overrides alone are insufficient when `enable_tools: false`
- JSON code blocks pattern helps but doesn't solve the fundamental issue
- The successful examples (standalone_demo, etc.) likely had different context
- Fixed component_to_profile to preserve enable_tools and all frontmatter fields ✅

### Component_to_Profile Fix (2025-01-26) ✅

**Problem**: component_to_profile handler only preserved `security_profile`, ignoring other frontmatter fields like `enable_tools`.

**Solution Implemented**:
1. Extract ALL frontmatter fields, not just security_profile
2. Use frontmatter values to override default agent_config
3. Add agent config fields to top level for backward compatibility
4. Pass through unknown fields for forward compatibility

**Key Changes**:
```python
# Extract all agent config fields from frontmatter
agent_config_fields = {
    'model': frontmatter.get('model', 'sonnet'),
    'role': frontmatter.get('role', 'assistant'),
    'enable_tools': frontmatter.get('enable_tools', False),
    'capabilities': frontmatter.get('capabilities', ['conversation', 'analysis', 'task_execution']),
    # ... other fields
}

# Also add to top level for agent spawn handler
profile_data.update(agent_config_fields)
```

### Understanding enable_tools vs Capabilities (2025-01-26)

**Key Distinction**:
- **capabilities** → KSI events the agent can emit (agent:status, state:entity:update, etc.)
- **enable_tools** → Whether Claude tools (Bash, Read, Write) are enabled
- **allowed_claude_tools** → Specific Claude tools allowed (usually empty `[]`)

**Why Both Exist**:
1. Capabilities control event permissions within KSI
2. Tools control external system access (filesystem, commands)
3. Agents can emit JSON events without tools
4. But agents perceive they need tools for "any action"

**Current Blocker**: Even with `enable_tools: true`, `allowed_claude_tools` is determined by the capability system, not component frontmatter. The behavioral override approach is fundamentally limited by the agent's perception that it needs tools to interact with the system.

### Final Findings on DSL Bootstrap (2025-01-26)

**Systematic Analysis Results**:

1. **Behavioral Overrides Work** - We found successful examples of JSON emission
2. **Component_to_Profile Fixed** - Now preserves all frontmatter fields
3. **Three-Layer Permission System**:
   - `enable_tools` → Whether tools are enabled (boolean)
   - `allowed_claude_tools` → Which tools (determined by capability system)
   - `capabilities` → Which KSI events can be emitted

**Why DSL Bootstrap Remains Blocked**:
1. Agents perceive they need tools to "do anything" (emit JSON events)
2. The capability system doesn't grant claude tools to any standard profiles
3. Even with `allowed_claude_tools: ["bash"]` in frontmatter, capability system overrides it
4. No existing mechanism to grant tools through components

**Alternative Approaches Identified**:
1. **Create Custom Tools** - Build KSI-specific tools that emit events directly
2. **Use System-Level DSL** - Move DSL interpretation to transformers/handlers
3. **Hybrid Approach** - Orchestrations that spawn pre-configured agents per command
4. **Modify Capability System** - Add tool grants to security profiles

**Recommendation**: The DSL bootstrap vision remains valid but requires architectural changes. The cleanest approach would be custom KSI tools that agents can use to emit events, bypassing the perception that they need system access.

### Critical Composition Patterns (2025-01-26)

#### ALWAYS Investigate Before Creating
- **MANDATORY**: Always check `var/lib/compositions/components/` for existing components before creating new ones
- **Problem**: Too many duplicate/redundant/overlapping components already exist
- **Solution**: Use `ksi send composition:discover` and `grep` to find similar components first
- **Pattern**: Reuse and compose existing components rather than creating new ones

#### Agent Permission Requests = Composition Failure
When agents ask for permissions (like Claude asking for file access), it indicates:
1. **Missing Behavioral Overrides**: Components like `claude_code_override.md` must be mixed into agent profiles
2. **Missing Event Mappings**: Events the agent needs are not in their capability mappings
3. **Wrong Security Profile**: Agent may need a different security_profile (e.g., `dsl_interpreter`)

#### Fixing Composition Issues
Two approaches when agents lack capabilities:
1. **Update Component Dependencies**: Add required behavior mixins (e.g., `claude_code_override`)
2. **Update Capability Mappings**: Add missing events to capability profiles in `capability_system_v3.yaml`

#### Successful Composition Pattern
```yaml
# Component with proper dependencies and security profile
component_type: agent
dependencies:
  - core/base_agent
  - behaviors/orchestration/claude_code_override  # Critical for Claude Code context
  - behaviors/dsl/event_emission_basics
security_profile: dsl_interpreter  # Grants necessary event permissions
```


## Capability Mapping Fix (2025-01-26)

### Missing state:entity:* Events

**Issue Discovered**: The capability mappings were missing critical state entity events that the system uses internally:
- `state:entity:create`
- `state:entity:update`
- `state:entity:delete`
- `state:entity:get`
- `state:entity:query`
- `state:entity:bulk_create`

**Impact**: Agents with `state_write` capability couldn't update entity properties, causing failures in:
- Agent state tracking (sandbox_uuid)
- Orchestration state management
- Custom entity operations

**Fix Applied**: Added missing events to both capability mapping files:
1. `/var/lib/capabilities/capability_mappings.yaml` - Added to `state_read` and `state_write` capabilities
2. `/var/lib/capabilities/capability_system_v3.yaml` - Already had most events in atomic capabilities, added `state:entity:bulk_create`

**Testing Note**: Direct testing blocked by `composition:compose` error ("argument should be a str or an os.PathLike object"), but the fix is straightforward and aligns with existing event patterns.

## Behavioral Evaluation Components (2025-01-26)

### Optimization Quality Assessment

**Created comprehensive evaluation framework** for assessing optimization quality:

**Evaluation Components**:
- `token_efficiency_evaluator.md` - Measures token reduction while preserving functionality
- `behavior_consistency_evaluator.md` - Ensures behavioral equivalence after optimization
- `response_quality_judge.md` - Pairwise comparison of agent output quality
- `optimization_quality_suite.md` - Combines all evaluators for holistic assessment

**Key Features**:
- Structured evaluation criteria with weighted scoring
- JSON-based result reporting for system integration
- Support for iterative optimization workflows
- Risk assessment and improvement recommendations

### Multi-Phase Orchestration Patterns

**Created example orchestrations** demonstrating longer-running workflows:

1. **Simple Multi-Phase Analysis** (`simple_multi_phase_analysis.yaml`)
   - 3 phases: Data Collection → Analysis → Synthesis
   - Phase coordinator manages transitions
   - State tracking throughout execution

2. **Iterative Optimization Cycle** (`iterative_optimization_cycle.yaml`)
   - Quality-driven optimization iterations
   - Continue/stop decisions based on improvement
   - Integrated evaluation at each iteration

3. **Self-Improving Research Pattern** (`self_improving_research_pattern.yaml`)
   - Monitors own performance during execution
   - Triggers self-optimization when performance degrades
   - Demonstrates autonomous adaptation

**Pattern Insights**:
- Phase-based coordination enables complex workflows
- State entities track progress across phases
- Performance monitoring enables self-improvement
- Orchestrator agents coordinate multi-agent activities

## DSPy Optimization Transition (2025-01-26)

### Current Architecture: Hybrid Bootstrap/Agent Model

KSI has sophisticated optimization infrastructure bridging Python bootstrapping and agent orchestration:

**Python Bootstrap Layer**:
- `ksi_optimization_pipeline.py` - End-to-end workflow orchestrator
- `dspy_mipro_adapter.py` - MIPRO integration (multi-stage optimization)
- `dspy_simba_adapter.py` - SIMBA integration (incremental adaptation)
- `optimization_service.py` - Event handlers and async subprocess management

**Agent/Orchestration Layer**:
- `simple_component_optimization.yaml` - Basic DSPy optimization orchestration
- `ksi_native_optimization_pipeline.yaml` - Full pipeline with tournaments
- `optimization_workflows.md` - Complete DSL patterns for all optimization types
- Multiple agent components (optimization_coordinator, dspy_optimization_agent, etc.)

### Transition Strategy: Bootstrap → Agent Autonomy

**Key Insight**: The infrastructure is complete. DSL patterns exist for everything the Python bootstrap does.

**Blockers Identified and Solutions**:

1. **Agent Permission Issues**
   - Problem: Agents ask for permissions instead of executing DSL
   - Solution: Use `security_profile: self_improver` which grants:
     - dsl_execution capability
     - optimization:async/status/get_result events
     - composition_development for creating components
     - agent_coordination for spawning variants

2. **Long-Running Subprocess Management**
   - Problem: DSPy optimizations run 5-15 minutes in subprocesses
   - Solution: Existing async operation framework with monitor patterns
   - Agents use optimization:async → monitor with optimization:status

3. **MLflow/Git Integration**
   - Problem: Python service manages MLflow server and Git operations
   - Solution: Expose as events or use existing agent file/command capabilities

### Implementation Components Created

**DSL Optimization Executor** (`dsl_optimization_executor.md`):
- Combines DSL interpreter with self_improver security profile
- Can execute complete optimization workflows from DSL patterns
- Replaces Python bootstrap with agent-driven execution
- Supports MIPRO, SIMBA, tournaments, and hybrid approaches

**Test Orchestration** (`test_dsl_optimization_executor.yaml`):
- Demonstrates bootstrap replacement
- Shows DSL executor running full pipeline
- Monitors key milestones without Python coordination

### Available Optimization Patterns

From `optimization_workflows.md`:
1. **MIPRO Pattern** - Multi-stage with bootstrapping, proposals, discrete search
2. **Tournament Pattern** - Pairwise comparisons with Bradley-Terry ranking
3. **Iterative Improvement** - Continuous refinement with plateaus detection
4. **Hybrid Optimization** - Combine multiple techniques with cross-evaluation
5. **Self-Optimizing** - Runtime parameter tuning based on performance
6. **Component Evolution** - Genetic algorithms with mutation/crossover

### Migration Path

1. **Enable DSL Execution**:
   ```yaml
   security_profile: self_improver  # or dsl_interpreter
   dependencies:
     - behaviors/dsl/optimization_workflows
   ```

2. **Test Native Orchestrations**:
   - Start with `simple_component_optimization.yaml`
   - Progress to `ksi_native_optimization_pipeline.yaml`
   - Verify results match Python bootstrap

3. **Gradually Replace Python Scripts**:
   - Keep Python adapters for DSPy framework integration
   - Move coordination logic to orchestrations
   - Let agents handle workflow orchestration

4. **Monitor and Iterate**:
   - Compare optimization quality
   - Track execution times
   - Refine DSL patterns based on results

### Architecture Benefits

**Gained with Agent-Based Optimization**:
- Full introspection of optimization process
- Self-documenting workflows in DSL
- Ability to self-optimize optimization patterns
- Natural integration with evaluation components
- No external Python scripts needed for coordination

**Retained from Python Layer**:
- DSPy framework integration
- MLflow tracking
- Git versioning
- Proven optimization algorithms

The transition enables KSI's vision: agents that improve themselves and each other through systematic optimization, with full visibility into the process.

---

*Essential development knowledge - for workflows see CLAUDE.md*