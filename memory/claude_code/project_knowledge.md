# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

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

**Indexing Strategy**:
1. **Exclude patterns**: Skip `_archive/tests/`, `README*`, `.*` files
2. **File-type validation**: YAML checks root fields, MD checks frontmatter
3. **Error handling**: DEBUG level for expected failures, WARNING for unexpected
4. **Continue on error**: Don't let one bad file stop indexing

## Critical Fixes (2025)

### JSON Extraction System Fix ✅
**Problem Solved**: Original regex could only handle 1 nesting level, KSI events need 3 levels.
**Solution**: `ksi_common/json_utils.py` with balanced brace parsing for arbitrary nesting.
**Result**: Agents now emit legitimate `agent:*`, `state:*`, `message:*` events successfully.

### Persona-First Architecture ✅
**Breakthrough**: Agents are Claude adopting personas, not artificial "KSI agents".
**Structure**: Pure personas + KSI capabilities = natural JSON emission.
**Location**: `components/personas/` + `components/capabilities/` → `components/agents/`

### Session Continuity Fix ✅
**Problem**: Claude CLI stores sessions by working directory, KSI created new sandboxes per request.
**Solution**: Persistent agent sandboxes using `sandbox_uuid` in `var/sandbox/agents/{uuid}/`
**Result**: Agents maintain conversation continuity across multiple requests.

### Unified Composition System (COMPLETE) ✅
**Problem**: Type-specific endpoints (composition:profile, composition:prompt) created unnecessary complexity.
**Solution**: Single `composition:compose` endpoint - component type determines behavior.
**Status**: COMPLETE - All type-specific endpoints removed.
**Impact**: Clean, elegant system where intelligent agents determine usage from context.

### DSL Meta-Optimization System ✅
**Innovation**: The orchestration DSL itself can now be optimized using MIPRO.
**Implementation**: 
  - `dsl_optimization_with_mipro.yaml` - Optimizes DSL constructs for LLM interpretability
  - `prompt_dsl_hybrid_optimization.yaml` - Blends natural language with DSL structure
**Potential**: Self-improving orchestration language, optimal human-AI communication patterns.
**See**: `/docs/DSL_PATTERNS_AND_OPTIMIZATION.md` for complete analysis.

### State Query Performance Fix (JSON Aggregation) ✅
**Problem**: N+1 query pattern in state:entity:query - fetched 100 entities with 101 queries.
**Solution**: SQLite JSON aggregation (json_group_object/array) - single optimized query.
**Performance**: 100x-200x faster (10+ seconds → <100ms for typical queries).
**See**: `/docs/KUZU_MIGRATION_ANALYSIS.md` for migration strategy.

### Composition Path Resolution Fix ✅
**Problem**: `composition:get_component` failed for orchestrations - incorrectly assumed all under COMPONENTS_BASE.
**Solution**: Created `ksi_common/composition_utils.py` with shared path resolution utilities.
**Result**: Both `composition:get` and `composition:get_component` now correctly resolve all composition types.
**Key Functions**: `resolve_composition_path()`, `get_composition_base_path()`, `load_composition_with_metadata()`.

### Web UI Agent-State Visualization System ✅
**Architecture**: Clear separation between Agent Ecosystem (left) and State System (right).
**Agent Ecosystem**: Shows agents, orchestrations, spawning edges, event routing, orchestrator feedback.
**State System**: Shows arbitrary data entities agents create, color-coded by type, hover tooltips.
**Interactions**: Agent hover → pulsate related state entities, draggable panel dividers.
**Event Routing**: Real-time edge animation, subscription level labels, hierarchical relationships.
**Implementation**: Native WebSocket transport, systematic entity routing, duplicate prevention.

## Optimization Architecture (2025) ✅

### Philosophy: Components All the Way Down
**Key Insights**: 
- **Everything is a component**: Signatures, metrics, optimization strategies
- **No embedded prompts**: All prompts live in versioned components
- **Framework-agnostic service**: Core optimization events, framework-specific adapters
- **Manual bootstrapping first**: Discover patterns before creating orchestrations

### Bootstrapping Methodology ✅
**DSPy-First Approach**: Programmatic → Judge → Hybrid
1. **Manual Discovery**: Spawn agents directly, run optimization manually
2. **Pattern Recognition**: Track decisions, identify what works
3. **Crystallize Patterns**: Create minimal orchestrations only after proving value

### DSPy Integration Events (NEW) ✅
- `optimization:optimize_component` - Run MIPROv2 on components
- `optimization:run_dspy_program` - Execute Predict, ChainOfThought, ReAct
- `optimization:evaluate_with_metric` - Score with DSPy metrics
- `optimization:bootstrap_examples` - Generate training data
- `optimization:register_metric` - Add custom metrics (including LLM judges)
- `optimization:list_metrics` - Discover available metrics

### Component Types for Optimization
- **Signatures**: `components/signatures/` - DSPy input/output specs
- **Metrics**: `components/metrics/` - Programmatic and judge-based
- **Personas**: `components/personas/developers/optimization_engineer.md`
- **Behaviors**: `components/behaviors/optimization/continuous_iterator.md`

### LLM-as-Judge System ✅
**Rankings Over Scores**: Pairwise comparisons, not numeric ratings
- **"Is A better than B?"** not "Rate A from 1-10"
- **Stable preferences**: Relative comparisons more consistent
- **No calibration issues**: Avoids subjective score interpretation
- **Ranking systems**: Elo, Bradley-Terry, TrueSkill

### Hybrid Optimization Marketplace ✅
**Innovation**: Run optimization techniques in parallel, select empirically
- **Technique Competition**: DSPy vs Judge vs Hybrid approaches
- **Domain Learning**: System discovers which technique works where
- **Meta-Optimization**: Build knowledge about technique-domain mappings
- **Key Orchestrations**:
  - `mipro_judge_based_optimization.yaml` - Pure judge approach
  - `hybrid_optimization_marketplace.yaml` - Technique comparison
  - `test_hybrid_optimization.yaml` - Simple hybrid demo

**Pattern**: Let techniques compete during bootstrapping, use winner for production.

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

## System Status (Current)

### Production Ready ✅
- **Unified Component System**: Everything is a component with type attribute (2025 reorganization)
- **JSON Extraction**: Balanced brace parsing, error feedback
- **Session Continuity**: Agent-based persistent sandboxes
- **Persona-First Architecture**: Proven natural JSON emission
- **Behavioral Override System**: Dependencies properly processed, field mapping fixed
- **Hybrid Evaluation**: Component definitions + runtime data separation

### Known Issues
- **No current critical issues** - State timeout and discovery performance issues resolved

### Discovery Cache System ✅
- **SQLite cache**: `var/db/discovery_cache.db` caches expensive TypedDict/AST analysis
- **Automatic invalidation**: Tracks file mtime, invalidates when code changes
- **Performance**: 78-90% faster on cached lookups (0.13s vs 0.6-1.5s)
- **Requirements**: `--level full` now requires `--namespace` or `--event` filter

### Key File Locations
- **Core Systems**: `ksi_common/json_utils.py`, `ksi_common/component_renderer.py`, `ksi_common/composition_utils.py`
- **Event Handlers**: `ksi_daemon/composition/composition_service.py`
- **Discovery Cache**: `ksi_daemon/core/discovery_cache.py`
- **Hierarchical Routing**: `ksi_daemon/core/hierarchical_routing.py`
- **Components**: `var/lib/compositions/components/` (organized by type)
- **Behavioral Overrides**: `components/behaviors/orchestration/claude_code_override.md`
- **Evaluation Data**: `var/lib/evaluations/` (runtime results)
- **Logs**: `var/logs/daemon/daemon.log.jsonl`, `var/logs/responses/{session_id}.jsonl`

## System Evolution Roadmap

### Immediate Implementation
- **Long-running orchestrations**: Build optimization orchestrations using component system and MIPRO/DSPy utilities

### Phase 1: Transformer Architecture (Q2 2025)
- **Event Transformation Pipeline**: High-level events transform to primitives (e.g., `agent:send_message` → `state:entity:create` + `event:notify`)
- **Early-loading Transformer Module**: Load before other modules to enable virtual events
- **Virtual Namespace Registration**: Transformers create namespaces that don't exist in code

### Phase 2: Dynamic Event System (Q3 2025)
- **Event Registry in State**: Queryable metadata tree of all events, namespaces, and transformations
- **Namespace Emergence**: Namespaces created dynamically as modules register, not hard-coded
- **Event Builder**: Generate event handlers from function type annotations

### Phase 3: Self-Describing Meta-System (Q4 2025)
- **System Introspection**: Components can query entire system structure
- **Runtime Modification**: Orchestrations can modify system behavior
- **Graph Database Migration**: Move to Kùzu when graph operations exceed 50% of queries

### Long-Running Orchestration Support
- **Checkpoint/Resume**: Save orchestration state every N iterations
- **State-Driven Progress**: Use state system as orchestration memory
- **Self-Optimizing Pipelines**: Orchestrations that improve their own patterns

## Document Maintenance Patterns

### CRITICAL: Keep Lean (Target: ~100 lines)

**REPLACE, DON'T ACCUMULATE**: When updating this document:
- **Replace outdated status** instead of adding "Recent Updates" sections
- **Update patterns in place** rather than documenting pattern evolution
- **Remove resolved issues** when problems are fixed
- **Consolidate discoveries** into existing sections

### What Belongs Here
- **Current System Status**: Production readiness, major accomplishments
- **Critical Patterns**: Proven working approaches, essential technical knowledge
- **Key Locations**: File paths, important commands, debugging approaches
- **Immediate Development Needs**: Current standards, working examples

### What Doesn't Belong Here
- **Development History**: Belongs in git commits only
- **Completed Tasks**: Remove when finished, don't accumulate
- **Detailed Architecture**: Belongs in PROGRESSIVE_COMPONENT_SYSTEM.md
- **Workflow Instructions**: Belongs in CLAUDE.md
- **Session Details**: Temporary information that becomes outdated

**Update Pattern**: When discoveries are made, update existing sections rather than adding new ones. Remove content that's no longer essential for immediate development.

---

*Essential development knowledge only - for workflow instructions see CLAUDE.md*
*Last updated: 2025-01-18*