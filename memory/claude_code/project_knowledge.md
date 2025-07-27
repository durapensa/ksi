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

#### XML Tool Use (Most Reliable) ✅
```xml
<ksi:emit>
  <ksi:event>agent:status</ksi:event>
  <ksi:data>
    <agent_id>{{agent_id}}</agent_id>
    <status>initialized</status>
  </ksi:data>
</ksi:emit>
```
- Use `behaviors/tool_use/ksi_tool_use` behavior
- 100% reliable in testing
- Leverages Claude's natural tool capabilities

#### JSON Emission (Limited Reliability)
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```
- Works for simple events
- Complex structures often malformed

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

### State Management
- **Entity system**: Agents, orchestrations tracked as entities
- **Hierarchical**: Parent-child relationships preserved
- **Query patterns**: `state:entity:get --type agent --id agent_123`

### Capability System
- **Compositional**: Atomic capabilities → Mixins → Profiles
- **Security profiles**: Components declare profile in frontmatter
- **Event permissions**: Profiles map to allowed event lists

## File Locations

### Core Systems
- `ksi_common/json_utils.py` - JSON extraction with balanced braces
- `ksi_common/xml_event_extraction.py` - XML event extraction for tool use pattern
- `ksi_common/component_renderer.py` - Component dependency resolution
- `ksi_daemon/composition/` - Component management and discovery
- `ksi_daemon/evaluation/` - Evaluation and certification

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

1. **Agents can't emit JSON directly** - Use imperative overrides or translation layers
2. **Everything is a graph** - Entities, relationships, event routing
3. **Composition over configuration** - Mix behaviors, don't hardcode
4. **System enables, doesn't control** - Agents are autonomous

---

*Essential development knowledge - for workflows see CLAUDE.md*