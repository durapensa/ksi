# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

## Core Architecture

### Event-Driven System
- **All communication via events**: No direct imports, use `ksi send event:name --param value`
- **Discovery first**: `ksi discover` shows capabilities, `ksi help event:name` for parameters
- **Socket communication**: Events flow through `var/run/daemon.sock`

### Component System (Production Ready ✅)
- **Event-driven creation**: `ksi send composition:create_component --name "path" --content "..."`
- **Progressive frontmatter**: YAML metadata with mixins, variables, version control
- **SQLite index**: Database-first discovery, no file I/O during queries
- **60x+ cached rendering**: LRU cache with intelligent invalidation

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

## Component Architecture

### Current Standards (2025)
```yaml
---
version: 2.1.0
author: ksi_system
mixins:
  - capabilities/claude_code_1.0.x/ksi_json_reporter
variables:
  agent_id: "{{agent_id}}"
---
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

### Working Component Library
- `components/personas/universal/` - Pure domain expertise (no KSI awareness)
- `components/capabilities/claude_code_1.0.x/` - KSI integration mixins
- `components/agents/` - Complete agents (persona + capability)
- `orchestrations/` - Game theory experiments, MIPRO optimization (modernized)

## Development Patterns

### Agent Management
```bash
# Spawn agent from component
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst" 
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
```bash
export KSI_DEBUG=true && export KSI_LOG_LEVEL=DEBUG && ./daemon_control.py restart
tail -f var/logs/daemon/daemon.log
```

### Common Issues
- **Timeouts**: Usually JSON serialization failures (dates, complex objects)
- **Agents not responding**: Check profile has `prompt` field
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
- **Component System**: Full event-driven lifecycle, SQLite index, caching
- **JSON Extraction**: Balanced brace parsing, error feedback
- **Session Continuity**: Agent-based persistent sandboxes
- **Persona-First Architecture**: Proven natural JSON emission
- **Composition Cleanup**: 40 obsolete files removed, all components modernized

### Key File Locations
- **Core Systems**: `ksi_common/json_utils.py`, `ksi_common/component_renderer.py`
- **Event Handlers**: `ksi_daemon/composition/composition_service.py`
- **Components**: `var/lib/compositions/components/`
- **Logs**: `var/logs/daemon/daemon.log`, `var/logs/responses/{session_id}.jsonl`

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