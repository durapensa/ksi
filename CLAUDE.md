# KSI Development Guide

This document shares what we've learned building KSI — patterns that work, pitfalls to avoid, and the reasoning behind both. It's written for you as a collaborator, not a subordinate.

## Orientation

KSI is a research agent ecosystem. You're likely working within or on it. Two resources will save you significant time and confusion:

- **`memory/claude_code/project_knowledge.md`** — Technical reference, architecture details, implementation patterns. Worth reading before diving into unfamiliar areas.
- **`ksi discover`** — The system is self-documenting. Running this before development work lets you see what's already built and how to use it.

For research priorities and roadmap: `/docs/KSI_FUTURE_ROADMAP_V2.md`
For documentation navigation: `/docs/DOCUMENTATION_INDEX.md`

## How KSI Works (the short version)

Everything is **event-driven**. Agents, components, and services communicate through events routed by the daemon. This isn't a stylistic preference — it's what makes the system observable, composable, and resilient. When you bypass the event system (e.g., with standalone scripts), you lose all three.

Everything is a **component**. Components have a `component_type` (core, persona, behavior, workflow, evaluation, tool) and live in a directory structure organized by type. They compose through dependencies and capabilities.

Everything is a **graph**. Entities are nodes, events route through edges. Subscription levels control traversal depth (0 = node only, 1 = direct children, N = N deep, -1 = full subtree).

## Development Patterns Worth Following

### Discovery First

The system has a progressive discovery mechanism:
```bash
ksi discover                              # Namespace overview
ksi discover --namespace <name>           # Specific area
ksi help <event:name>                     # Event details
```

This is genuinely useful, not bureaucratic overhead. Discovery tells you what already exists, what parameters handlers expect, and how things connect. It prevents reinventing what's already built.

### Investigation Over Workarounds

This one comes from hard experience. When errors, timeouts, or unexpected behavior appear:

1. Read the error message — it usually says what's wrong
2. Check daemon logs — `tail -f var/logs/daemon/daemon.log.jsonl`
3. Isolate the problem with minimal test cases
4. Fix the root cause

The temptation to work around issues is real, especially under time pressure. But workarounds in an event-driven system compound — they create subtle inconsistencies that surface later as mysterious failures. Fixing at the source keeps the system trustworthy.

For deeper investigation:
```bash
# Enable debug logging dynamically (no restart needed)
ksi send config:set --type daemon --key log_level --value DEBUG
tail -f var/logs/daemon/daemon.log.jsonl

# Restore when done
ksi send config:set --type daemon --key log_level --value INFO
```

### Agent Design

**Agents are Claude adopting domain expertise**, not "KSI agents." The persona is primary; KSI awareness is a capability layered on top.

```
components/personas/universal/data_analyst.md    # Pure domain expertise
components/capabilities/ksi_json_reporter.md     # Minimal KSI awareness
components/agents/ksi_aware_analyst.md           # Combined
```

**Capabilities are compositional** and determine what an agent can do:
- `base` — Core completion
- `composition` — Access components
- `optimization` — Run MIPRO/SIMBA
- `state` — Persistent state
- `agent` — Spawn other agents
- `routing_control` — Create/modify routing rules
- `observation` — Subscribe to events

An agent spawned with only `base` can only emit `system:health`, `system:help`, `system:discover`. If an agent seems unable to do something, check its capabilities first.

### Communication Between Agents

Direct agent-to-agent messaging works:
```json
{"event": "completion:async", "data": {"agent_id": "analyzer", "prompt": "FINDINGS: [results]. Please analyze."}}
```

A known limitation: agents don't reliably emit structured JSON directly. The proven pattern uses layers:
1. **Analysis layer** — Agents provide natural language recommendations
2. **Translation layer** — JSON transformers convert to events
3. **Execution layer** — System processes the events

For reliable JSON emission, use the KSI tool use pattern (see `/docs/KSI_TOOL_USE_PATTERNS.md`), which leverages LLMs' native tool-calling abilities.

### Component Creation

Components use markdown with YAML frontmatter:
```yaml
---
component_type: persona
name: data_analyst
version: 2.0.0
description: Senior data analyst with statistical expertise
dependencies:
  - core/base_agent
  - behaviors/communication/mandatory_json
capabilities:
  - statistical_analysis
  - data_visualization
---
```

Organization by type:
- `core/` — Building blocks (base_agent, json_emitter)
- `personas/` — Domain expertise (analysts/, developers/, thinkers/)
- `behaviors/` — Reusable mixins (communication/, coordination/)
- `workflows/` — Multi-agent patterns
- `evaluations/` — Quality assessments
- `tools/` — External integrations

### Dynamic Routing

Agents with `routing_control` coordinate through routing rules they create at runtime — this is how emergent coordination works. Rules are parent-scoped and auto-cleanup when agents terminate.

```bash
# Spawn a coordinator that creates its own routing
ksi send agent:spawn --profile "coordination_specialist" \
  --prompt "Coordinate analysis by spawning analysts and routing their outputs"
```

See `/docs/DYNAMIC_ROUTING_QUICKSTART.md` for examples.

### Self-Improvement

Agents can optimize their own and others' instructions:
```yaml
# Analyze a component
{"event": "composition:get_component", "data": {"name": "personas/data_analyst"}}

# Run optimization
{"event": "optimization:async", "data": {
  "component": "personas/data_analyst",
  "method": "mipro",
  "goal": "Reduce token usage by 30% while maintaining quality"
}}
```

Long-running optimizations (5-15 min) are handled by the subprocess system. Start them with `optimization:async` and check results at completion with `optimization:status` — no need to poll.

## Configuration & Infrastructure

### Configuration
Always use `from ksi_common.config import config` — never hardcode paths. Key config properties: `config.daemon_log_dir`, `config.socket_path`, etc. Environment variables use `KSI_*` prefix.

### Session Continuity
Each agent gets a `sandbox_uuid` at spawn. All requests use the same sandbox at `var/sandbox/agents/{uuid}/`, maintaining conversation state. External APIs use `agent_id` only — session IDs are internal to the completion system and shouldn't be exposed.

### Daemon Management
```bash
./daemon_control.py start|stop|restart|status|health
./daemon_control.py dev  # Auto-restart on code changes
```

### Monitoring
```bash
ksi send monitor:get_status --limit 10
ksi send monitor:get_events --event-patterns "composition:*"
ksi send agent:list
ksi send agent:info --agent-id agent_123
```

### Git Workflow
Components are stored in git submodules under `var/lib/`. After changes:
```bash
cd var/lib/compositions
git add . && git commit -m "descriptive message"
git push origin main
cd ../../..
git add var/lib/compositions
git commit -m "Update composition submodule"
```

## Known Issues & Gotchas

These are things that have bitten us before:

- **Agent not responding?** Check if its profile has a `prompt` field.
- **JSON extraction failing?** Validate format; use the KSI tool use pattern.
- **sandbox_uuid missing?** The `agent_spawned_state_create` transformer may not have fired. Manual fix: `ksi send state:entity:create --type agent --id "agent_id" --properties '{"sandbox_uuid": "uuid"}'`
- **Orchestration prompts not delivered?** Put prompts in `vars.initial_prompt`, not directly in agent config.
- **Components not found?** Run `ksi send composition:rebuild_index`.
- **Optimization showing 0% improvement?** Default metric is too simplistic — implement proper evaluation metrics or LLM-as-Judge.
- **KSI hook output not visible in Claude Code?** Known issue (#3983). Workaround: `tail -f /tmp/ksi_hook_diagnostic.log`

## Shared Utilities

When creating service transformers, these exist and are worth using:
- `auto_load_service_transformers(service_name)` — Centralized transformer loading
- `TransformerTemplateBuilder` — Common routing patterns
- `ConditionEvaluator` — Complex boolean expressions
- `EventResponseBuilder` — Standardized responses with KSI context

## Principles

These aren't rules — they're the design philosophy that has made KSI coherent:

- **System as enabler, not controller** — Infrastructure enables agents; it doesn't orchestrate their behavior.
- **Fix at the source** — Workarounds accumulate. Root-cause fixes compound.
- **Data flow integrity** — Preserve all fields through system boundaries.
- **Composition over configuration** — Components, capabilities, and profiles compose naturally.
- **Observable by default** — If it can't be monitored, it can't be trusted.
- **Evolve, don't expand** — Improve existing patterns rather than adding new sections.

See `/docs/KSI_PHILOSOPHY_ELEGANT_ARCHITECTURE.md` for the full picture.

## Research & Scientific Rigor

When conducting experiments, export complete datasets (not just summaries) to files for reproducibility. Use descriptive filenames with timestamps. Reference saved data files in documentation. Raw data enables independent verification.

## Keeping This Document Useful

This guide should help you work effectively, not document history. When you learn something that would have saved you time:

- Improve an existing section rather than adding a new one
- Replace outdated practices rather than accumulating alternatives
- Keep technical architecture details in `project_knowledge.md`
- Keep research plans in their respective docs under `/docs/`

For technical details and implementation patterns: `memory/claude_code/project_knowledge.md`
For transparency and alignment research: `docs/KSI_TRANSPARENCY_ALIGNMENT_ENHANCEMENTS.md`

*See git log for update history*
