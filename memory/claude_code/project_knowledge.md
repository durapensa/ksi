# KSI Project Knowledge for Claude Code

Essential technical reference for developing with KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

## Core Architecture

### Event-Driven System
- **All communication via events**: No direct imports, use `ksi send event:name --param value`
- **Discovery first**: `ksi discover` shows capabilities, `ksi help event:name` for parameters
- **Socket communication**: Events flow through `var/run/daemon.sock`

### Component System (Unified Architecture 2025 ✅)
- **Everything is a component**: Single unified model with `component_type` attribute
- **Event-driven creation**: `ksi send composition:create_component --name "path" --content "..."`
- **Progressive frontmatter**: YAML metadata with type, dependencies, capabilities
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

### Profile to Component Migration (COMPLETE) ✅
**Problem**: Dual system (profiles + components) created confusion and inconsistency.
**Solution**: Full migration to component-only system.
**Status**: COMPLETE - All profiles removed, system uses only components.
**Impact**: 139 files changed, 1487 insertions(+), 4185 deletions(-) - massive simplification!

### DSL Meta-Optimization System ✅
**Innovation**: The orchestration DSL itself can now be optimized using MIPRO.
**Implementation**: 
  - `dsl_optimization_with_mipro.yaml` - Optimizes DSL constructs for LLM interpretability
  - `prompt_dsl_hybrid_optimization.yaml` - Blends natural language with DSL structure
**Potential**: Self-improving orchestration language, optimal human-AI communication patterns.
**See**: `/docs/DSL_PATTERNS_AND_OPTIMIZATION.md` for complete analysis.

## Optimization Architecture (2025) ✅

### Philosophy: Minimal Utilities, Maximum Composability
**Key Insight**: Optimization = Orchestration + Evaluation + Minimal Utilities
- **No new abstractions**: Use existing KSI systems
- **Composable patterns**: Mix and match components
- **See**: `/docs/OPTIMIZATION_APPROACH.md` for full architecture

### Optimization Events (Minimal)
- `optimization:get_framework_info` - Query available frameworks
- `optimization:validate_setup` - Check if ready
- `optimization:format_examples` - Convert data for frameworks
- `optimization:get_git_info` - Track experiments

### LLM-as-Judge System ✅
**Breakthrough**: Replace programmatic metrics with nuanced judge evaluation
- **Pairwise Comparison**: Judges compare strategies for relative ranking
- **Elo Rating System**: Dynamic skill ratings from comparisons
- **Judge Personas**: `game_theory_pairwise_judge`, `optimization_technique_judge`
- **Co-Evolutionary**: Judges and strategies improve together

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
- **Unified Component System**: Everything is a component with type attribute (2025 reorganization)
- **JSON Extraction**: Balanced brace parsing, error feedback
- **Session Continuity**: Agent-based persistent sandboxes
- **Persona-First Architecture**: Proven natural JSON emission
- **Hybrid Evaluation**: Component definitions + runtime data separation

### Known Issues
- **Discovery --level full timeout**: FIXED - Now requires namespace/event filter. With cache: 78-90% faster on subsequent runs.

### Discovery Cache System ✅
- **SQLite cache**: `var/db/discovery_cache.db` caches expensive TypedDict/AST analysis
- **Automatic invalidation**: Tracks file mtime, invalidates when code changes
- **Performance**: 78-90% faster on cached lookups (0.13s vs 0.6-1.5s)
- **Requirements**: `--level full` now requires `--namespace` or `--event` filter

### Key File Locations
- **Core Systems**: `ksi_common/json_utils.py`, `ksi_common/component_renderer.py`
- **Event Handlers**: `ksi_daemon/composition/composition_service.py`
- **Discovery Cache**: `ksi_daemon/core/discovery_cache.py`
- **Components**: `var/lib/compositions/components/` (organized by type)
- **Evaluation Data**: `var/lib/evaluations/` (runtime results)
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
*Last updated: 2025-01-18*