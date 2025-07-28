# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

## Core Architecture

### Event-Driven System
- **All communication via events**: No direct imports between services
- **Discovery first**: `ksi discover` shows capabilities, `ksi help event:name` for parameters
- **Socket communication**: Events flow through `var/run/daemon.sock`
- **Never import internals**: Always use the event system for cross-service communication

### Component System (Unified 2025)
- **Everything is a component**: Single model with `component_type` attribute
- **Types**: `core`, `persona`, `behavior`, `orchestration`, `evaluation`, `tool`
- **Graph-based**: Entities form directed graphs with event routing
- **Universal spawn**: Component type determines what gets created

### Orchestration System
- **Agents are autonomous**: Receive composition and optional prompt, then self-coordinate
- **No hardcoded strategies**: System delivers messages, agents decide coordination
- **Hierarchical routing**: Events bubble up based on subscription levels (0, 1, N, -1)
- **Claude Code as orchestrator**: Set `orchestrator_agent_id: "claude-code"` for feedback
- **Dynamic Routing Architecture**: See `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` for infrastructure-based dynamic routing (Stages 1.1-1.7 complete)

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

#### Tool Use Pattern (Production Validated) ✅
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
- **Production Status**: Validated 2025-01-27 with 100% success rate
- **Component**: `behaviors/communication/ksi_events_as_tool_calls` 
- **Architecture**: Dual-path extraction engine in `ksi_common/tool_use_adapter.py`
- **Validation**: 4/4 event types (agent:status, state:entity:create/update) successfully extracted
- **Integration**: Works seamlessly with base_agent.md v2.0.0 and modern behavioral components

#### Legacy JSON Format (Dual-Path Support)
```json
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```
- Maintained for backward compatibility
- Dual-path extraction supports both formats
- Tool use pattern preferred for new components

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
- **Namespace-based**: `system`, `agent`, `orchestration`, `composition`, etc.
- **Dynamic CLI**: Parameters discovered from handlers, not hardcoded
- **Caching**: SQLite cache for expensive TypedDict analysis
- **UX Enhancement**: Automatic namespace level when filtering by namespace

### Path Resolution System (Fixed 2025-01-27)
- **KSI root detection**: Consistent `find_ksi_root()` logic across all components
- **Centralized config**: All paths resolved via `ksi_common/config.py` properties
- **Subdirectory compatibility**: ksi wrapper and daemon work from any project subdirectory
- **Fixed components**: `daemon_control.py`, `ksi_client/`, `ksi_common/config.py`

### State Management
- **Entity system**: Agents, orchestrations tracked as entities
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

## Current Development Focus (2025-01-27)

### Phase 1: Component Foundation ✅
- Unified evaluation system
- Basic behavioral components (claude_code_override, json_emission)
- Compositional pattern proven

### Phase 2: Single Agent Optimization (Current)
- Build evaluation test suites
- Create component improver agent
- Test on single component
- No orchestrations yet

### Phase 3: Scale to Orchestrations
- Three-layer pattern (analysis → translation → execution)
- Multiple agents coordinating
- Tool integration (MIPRO/DSPy)

## Key Insights

1. **Tool use patterns work reliably** - LLMs naturally structure tool calls correctly
2. **Dual-path extraction** - Support both legacy JSON and modern tool use formats
3. **Everything is a graph** - Entities, relationships, event routing
4. **Composition over configuration** - Mix behaviors, don't hardcode
5. **System enables, doesn't control** - Agents are autonomous
6. **Dynamic routing enables emergence** - Agents can discover optimal coordination patterns
7. **Infrastructure as substrate** - Two-layer architecture (agents + transformers) replaces three-layer
8. **Introspection is key** - Visibility into routing decisions enables debugging and learning
9. **Foreach transformers unlock orchestration replacement** - Multi-target emission enables workflow patterns

---

*Essential development knowledge - for workflows see CLAUDE.md*