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

### Building Longer-Running Orchestrations (2025-01-24)
- **Goal**: Orchestrator agents with spawned subagents working through phases
- **Foundation**: Agent communication patterns proven and working
- **Next Steps**: State-based coordination, multi-phase orchestrations
- **Pattern**: Composition components driving all behavior

### Critical Issues Discovered (2025-01-24)
- **Agent State Entity Transformer Not Working**: The `agent_spawned_state_create` transformer in `var/lib/transformers/services/agent_routing.yaml` is not creating state entities for spawned agents
- **Workaround**: Manually create state entities with `state:entity:create` including `sandbox_uuid` property
- **Impact**: Completion system requires state entities to find agent sandbox_uuid
- **Behavior Override Not Working**: Agents ignore JSON emission instructions in prompts, requesting bash permissions instead


---

*Essential development knowledge - for workflows see CLAUDE.md*