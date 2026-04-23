# KSI Future Directions

Observations and proposals for KSI's evolution, combining research directions with infrastructure development.

**Last updated**: 2026-03-24

## 1. Agents Developing KSI (Closing the Loop)

KSI is built *for* agents but currently built *by* humans (with Claude Code assistance). The composition system is architecturally ready for agents to modify components, test them, and propose changes — an agent can `composition:get_component`, modify it, `composition:create_component` with a new version, and have another agent evaluate the result.

**Prerequisites**: Developer-agent persona component, composite sandbox CLAUDE.md with development snippets (see AGENT_IMPROVEMENT_ROADMAP.md TODO).

**Outcome**: KSI agents that contribute to KSI's own development — self-improving infrastructure, not just self-improving prompts.

## 2. Documentation Consolidation

170+ docs files accumulated during rapid research and development phases. Many contain overlapping content, superseded approaches, or timelines that have passed. A documentation agent could periodically consolidate — archiving superseded docs, merging overlapping ones, updating timelines. This is itself a good task for a KSI agent.

**Status**: Initial consolidation performed 2026-03-24 — ~100 files archived, remaining docs organized by topic.

## 3. Provider-Specific Behavioral Overlays

Multi-model support exists in KSI's infrastructure but prompt composition remains Claude-centric. As Gemini and Ollama agents join the ecosystem, each needs provider-specific behavioral components that teach it how to emit KSI events in its native idiom.

**Approach**: `behaviors/providers/` directory with per-provider overlays (`claude_code.md`, `gemini_cli.md`, `openai_compatible.md`). The spawning system selects the right overlay based on the target provider.

**Foundation**: `core/ksi_agent_identity` component provides model-agnostic orientation; provider overlays add execution-environment specifics.

## 4. Inter-Model Agent Collaboration as Research

KSI's fairness and cooperation research has been Claude-to-Claude. Introducing agents with genuinely different training distributions (Gemini, Llama, Qwen) creates a natural extension of the phase transition research — model heterogeneity as another parameter in the phase space, alongside communication, memory, and reputation.

**Questions**:
- Does cooperation dynamics change when agents have different "cognitive styles"?
- Do mixed-model ecosystems exhibit different phase transition thresholds?
- Is fairness emergence model-dependent or a general property of sufficient intelligence?

## 5. Daemon Simplification

127 Python modules is substantial. Some accumulated complexity from exploratory development may be reducible. A simplification pass — merging small modules, removing unused event handlers, consolidating related services — would make the system more approachable for both human and agent developers, and reduce the surface area for bugs.

**Approach**: A KSI agent with developer context could audit module usage, identify dead code, and propose consolidation — eating its own dog food.

## 6. Agent Memory Across Sessions

Sandboxes are ephemeral, but agent learning shouldn't necessarily be. The state system (`state:entity:*`) provides persistence, but there's no structured pattern for an agent to accumulate and retrieve its own experiential knowledge across sessions.

A lightweight memory component — similar to Claude Code's memory system — would let agents build up understanding over time. This is essential for the self-improvement vision: an agent that remembers what worked and what didn't across sessions can improve more effectively than one that starts fresh each time.

**Design considerations**:
- Memory as a component behavior (composable, optional)
- Backed by the existing state system
- Agent-scoped: each agent's memories are its own, but shareable if desired
- Structured enough to be useful, flexible enough not to constrain

---

## Relationship to Existing Roadmaps

These directions complement rather than replace existing research plans:

- **Phase transition research** (KSI_FUTURE_ROADMAP_V2.md) — directions 4 and 6 extend this
- **Agent improvement** (AGENT_IMPROVEMENT_ROADMAP.md) — directions 1 and 5 enable this
- **Federated architecture** (architecture/FEDERATED_ARCHITECTURE_COMPLETE.md) — direction 3 supports multi-node heterogeneity

The common thread: KSI evolving from a system that *hosts* agents toward a system that *is* its agents.
