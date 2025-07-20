# Claude Code Development Guide for KSI

Essential development practices and workflow for Claude Code when working with KSI.

## MANDATORY WORKFLOW RULES

1. **MUST read `memory/claude_code/project_knowledge.md` FIRST** - NO EXCEPTIONS
2. **MUST run `ksi discover` BEFORE any development** - NO EXCEPTIONS  
3. **MUST investigate errors immediately** - NEVER create workarounds
4. **MUST use TodoWrite for multi-step tasks** - NO EXCEPTIONS
5. **MUST complete ALL steps**: Code + Test + Deploy + Verify
6. **MUST update documentation IMMEDIATELY when discovering patterns**
7. **MUST use discovery system BEFORE attempting tasks**
8. **MUST verify agent claims against actual system behavior**

## Session Start Protocol

**MANDATORY**: You MUST read `memory/claude_code/project_knowledge.md` FIRST before any KSI development work. NO EXCEPTIONS.

**MANDATORY**: You MUST run `ksi discover` to understand system capabilities BEFORE attempting any development tasks.

This document serves as your primary instructions for KSI development. For technical reference, architecture details, and implementation patterns, see `memory/claude_code/project_knowledge.md`.

## Investigation-First Philosophy

**MANDATORY**: When encountering errors, timeouts, or unexpected behavior - you MUST investigate immediately. NEVER create workarounds. NEVER bypass issues.

### Investigation Process (REQUIRED STEPS)

1. **MUST read the error message carefully** - It often contains the exact problem
2. **MUST check daemon logs** - `tail -f var/logs/daemon/daemon.log.jsonl`
3. **MUST search for patterns** - Search logs for related errors
4. **MUST test with minimal cases** - Isolate the problem
5. **MUST fix the root cause** - NEVER bypass or work around issues

### Advanced Debugging Techniques

**Enable Debug Logging**: For deep system investigation
```bash
# Dynamic method (no restart required)
ksi send config:set --type daemon --key log_level --value DEBUG
tail -f var/logs/daemon/daemon.log.jsonl

# Disable when done
ksi send config:set --type daemon --key log_level --value INFO
```

**Agent Behavior Investigation**: When agents claim to perform actions:
1. **Verify actual vs claimed behavior** - Check logs for real activity
2. **Count claude-cli spawns** - Should match claimed conversation turns
3. **Examine completion results** - Look for actual JSON vs descriptions
4. **Use monitor events** - Verify claimed events actually appear

**Remember**: Timeouts, connection issues, and serialization errors are symptoms of underlying problems. Always investigate and fix the root cause. **Agent claims must be verified against actual system behavior.**

## Core Development Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import `from ksi_common.config import config`
- **Never hardcode paths** - Use config properties: `config.daemon_log_dir`, `config.socket_path`

### Event-Driven Development
- **All communication through events** - No direct module imports between services
- **Use discovery system first** - `ksi discover`, `ksi help event:name`
- **Event handlers use TypedDict** - For parameter documentation and validation

### Component Creation (Unified Architecture 2025)
**CRITICAL**: Everything is a component! The system forms a directed graph where:
- **Nodes**: Event-emitting entities (agents, orchestrations)
- **Edges**: Parent-child relationships, routing rules, capabilities
- **Universal spawn**: Component type determines what gets created
- **Nested orchestrations**: Agents can spawn orchestrations, creating arbitrary depth trees

```bash
# Create components via events with proper type
ksi send composition:create_component --name "personas/analysts/data_analyst" \
  --content "---\ncomponent_type: persona\nname: data_analyst\nversion: 2.0.0\n---\n# Senior Data Analyst\n..."

# Component types: core|persona|behavior|orchestration|evaluation|tool
# Organization: components/{type}/{category}/{name}.md
```

**New Component Organization**:
- `core/` - Essential building blocks (base_agent, json_emitter)
- `personas/` - Domain expertise (analysts/, developers/, thinkers/)
- `behaviors/` - Reusable mixins (communication/, coordination/)
- `orchestrations/` - Multi-agent patterns (optimization/, workflows/)
- `evaluations/` - Quality assessments (metrics/, judges/, suites/)
- `tools/` - External integrations (mcp/, git/, apis/)

### Persona-First Agent Design (PROVEN WORKING) ✅

**Core Principle**: Agents are **Claude adopting personas**, not "KSI agents".

**MAJOR SUCCESS**: This approach completely solved the JSON emission problem!

**Working Component Architecture**:
```bash
# Pure domain expertise (no KSI)
components/personas/universal/data_analyst.md

# Minimal KSI communication capability
components/capabilities/claude_code_1.0.x/ksi_json_reporter.md

# Combined: Domain expert + System awareness
components/agents/ksi_aware_analyst.md
```

**Proven Pattern**:
```bash
# Agent spawned successfully
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst"

# Real events captured by system
ksi send monitor:get_events --event-patterns "agent:*"
# Result: agent:status events with _extracted_from_response: true
```

**Revolutionary Insight**: JSON becomes a natural reporting tool for domain experts, not forced "agent behavior".

### JSON Emission Standards (MANDATORY PATTERNS)

**Proven Reliable Pattern**: Strong imperative language ensures consistent behavior:
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

**Success Factors Discovered**:
- ✅ **Imperative Language**: "MANDATORY:", "MUST" work better than conditional "when"
- ✅ **Direct Instructions**: "Start your response with" not "emit when starting"
- ✅ **Complete JSON Examples**: Provide exact JSON structures
- ✅ **Processing Time**: Allow 30-60 seconds for complex tasks

**When** creating agent components:
- **Then** use MANDATORY/imperative language for JSON instructions
- **Then** provide exact JSON structures agents should emit
- **Then** allow sufficient processing time for complex tasks
- **Then** test with monitor to verify actual event emission

## Development Workflow

### Task Management (MANDATORY)
- **MUST use TodoWrite tool** - Track progress on ALL multi-step tasks. NO EXCEPTIONS.
- **MUST complete ALL steps**: Code + Test + Deploy + Verify - NEVER stop at code creation
- **MUST test within KSI system** - Use orchestrations and evaluations for testing

### Discovery-First Development (MANDATORY)

**MANDATORY**: You MUST use discovery BEFORE attempting any task. NO EXCEPTIONS.

**Progressive Discovery Methodology** (saves tokens/context):
1. **Start broad**: `ksi discover` - Get namespace overview
2. **Narrow focus**: `ksi discover --namespace <name>` - Explore specific area
3. **Get details**: `ksi help <event:name>` - Understand specific events
4. **NEVER use --level full without redirect**: Output can be massive

**Understanding Discovery Layers**:
- **System Discovery** (`ksi discover`): MUST run this first to understand capabilities
- **Domain Discovery** (`composition:discover`, `agent:discover`): MUST use for actual data queries

```bash
# MANDATORY: Progressive Discovery Pattern (saves tokens/context)
ksi discover                    # Start with summary view
ksi discover --namespace composition  # Explore specific namespace
ksi help composition:get_component  # Get event details

# --level full REQUIRES namespace or event filter
ksi discover --level full --namespace agent  # ✅ Fast with cache (0.1-1.5s)
ksi discover --level full --event agent:spawn  # ✅ Single event detail

# First run builds cache, subsequent runs 78-90% faster
# Cache invalidates automatically when code changes

# MANDATORY: Use domain discovery for data
ksi send composition:discover --type component  # Query components from SQLite
ksi send composition:list --filter '{"author": "ksi"}'  # List with filters
ksi send agent:list  # List active agents
```

**CRITICAL RULE**: System discovery guides you to domain discovery events, it NEVER returns domain data itself.

### Error Handling
- **No bare except clauses** - Catch specific exceptions
- **Use error_response()** - For handler errors
- **Log with context** - Include relevant details for debugging

## Component Development Patterns

### Modern Component Standards (Unified Architecture 2025)

**When** creating components:
- **Then** specify `component_type` attribute (MANDATORY)
- **Then** use proper directory structure by type
- **Then** declare dependencies and capabilities
- **Then** apply MANDATORY imperative patterns for JSON emission
- **Then** test with actual agent spawning and monitor verification

**Component Frontmatter Standard**:
```yaml
---
component_type: persona  # MANDATORY: core|persona|behavior|orchestration|evaluation|tool
name: data_analyst      # Component identifier
version: 2.0.0         # Semantic versioning
description: Senior data analyst with statistical expertise
dependencies:          # Components this needs
  - core/base_agent
  - behaviors/communication/mandatory_json
capabilities:          # What this provides
  - statistical_analysis
  - data_visualization
---
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

**Behavioral Override Pattern**:
```bash
# Core persona with behavioral dependencies
dependencies:
  - core/base_agent
  - behaviors/communication/mandatory_json
  - behaviors/orchestration/claude_code_override
```

**Hybrid Evaluation Architecture**:
- **Test suite definitions** → `components/evaluations/suites/`
- **Runtime results** → `var/lib/evaluations/` (separate from components)

### Optimization Development Pattern

**When** implementing optimization features (MIPRO, DSPy, etc.):
- **Then** create orchestration patterns, not new coordination systems
- **Then** use evaluation components for metrics, not embedded scoring
- **Then** provide minimal utilities only (framework config, data formatting)
- **Then** leverage agent conversation continuity for iterative optimization
- **See** `/docs/OPTIMIZATION_APPROACH.md` for architecture philosophy

### Model-Aware Development

**When** working with components across different environments:
- **Then** use git branches for model-specific optimizations
- **Then** declare compatibility in .gitattributes for discoverability  
- **Then** test components against target model/system combinations

**Model Optimization Workflow**:
```bash
# Work on Opus-optimized components
git checkout claude-opus-optimized
ksi send composition:create_component --name "personas/deep_researcher" \
  --content "You are a Senior Research Scientist with deep analytical capabilities..."

# Work on Sonnet-optimized components  
git checkout claude-sonnet-optimized
ksi send composition:create_component --name "personas/quick_analyst" \
  --content "You are a Data Analyst focused on rapid, actionable insights..."

# Update compatibility metadata
echo "components/personas/deep_researcher.md model=claude-opus performance=reasoning" >> .gitattributes
echo "components/personas/quick_analyst.md model=claude-sonnet performance=speed" >> .gitattributes

# Rebuild index to capture git metadata
ksi send composition:rebuild_index --include-git-metadata
```

## Graph-Based Architecture Principles

### Universal Entity Model
**When** designing KSI systems:
- **Then** think in graphs: Entities (nodes) connected by relationships (edges)
- **Then** treat agents and orchestrations as "event-emitting entities" 
- **Then** use unified patterns: `composition:compose` determines entity type from component
- **Then** embrace natural nesting: Any entity with capability can spawn others
- **Then** trust implicit context flow: Parent refs, depth, routing propagate automatically

### Capability Composition
**When** granting capabilities:
- **Then** remember capabilities are compositional - they work on any entity type
- **Then** agents with `orchestration` capability can spawn orchestrations
- **Then** orchestrations can have agents that spawn more orchestrations
- **Then** subscription levels control how deep in the graph events propagate

### Event Routing as Graph Traversal
**When** configuring event routing:
- **Then** Level 0 = node only (no traversal)
- **Then** Level 1 = direct edges (immediate children)
- **Then** Level N = traverse N edges deep
- **Then** Level -1 = full subtree traversal

### Module Interdependence (Intentional Design)
**When** working with agents and orchestrations:
- **Then** remember they are intentionally interdependent in the graph model
- **Then** agents with orchestration capability use `orchestration:start` to spawn orchestrations
- **Then** orchestrations use `agent:spawn` to create agents
- **Then** this reflects reality: graph nodes naturally need to create other nodes
- **Example**: An agent coordinator spawns an orchestration pattern = natural graph growth

### Claude Code as Orchestrator Agent
**When** spawning orchestrations from Claude Code:
- **Then** set `orchestrator_agent_id: "claude-code"` to receive feedback
- **Then** events from child agents will bubble up based on subscription levels
- **Then** configure dual subscriptions: `event_subscription_level` and `error_subscription_level`
- **Then** pass initial `prompt` to orchestration for agent initialization
- **Then** monitor events via `ksi send monitor:get_events --_client_id "claude-code"`

**Example orchestration spawn with feedback**:
```bash
ksi send orchestration:start --pattern "orchestrations/analysis" \
  --vars '{"orchestrator_agent_id": "claude-code", "prompt": "Analyze this document..."}'
```

**When** receiving bubbled events:
- **Then** regular events arrive based on `event_subscription_level`
- **Then** errors arrive based on `error_subscription_level` (often -1 for all errors)
- **Then** events tagged with `_client_id: "claude-code"` appear in response logs
- **Then** future: KSI hook will show these automatically when working

## System Management

### Daemon Management
```bash
./daemon_control.py start|stop|restart|status|health
./daemon_control.py dev  # Auto-restart on code changes
```

### System Monitoring
```bash
# Get system status
ksi send monitor:get_status --limit 10

# Check events
ksi send monitor:get_events --event-patterns "composition:*"

# Agent management
ksi send agent:list
ksi send agent:info --agent-id agent_123
```

## Session Management (Critical)

### Architectural Principles (ENFORCED 2025)

**Session IDs must NEVER leak outside completion system!**
- **Agents are the ONLY abstraction** - External systems use `agent_id` only
- **Session IDs are internal** - Completion system manages them privately

```bash
# ✅ CORRECT: External APIs use agent_id
ksi send completion:async --agent-id my_agent --prompt "..."

# ❌ WRONG: Session IDs should never be exposed
ksi send completion:async --session-id 943a3864-d5bb... --prompt "..."
```

### Session Continuity (FIXED 2025) ✅

**Problem Solved**: Claude CLI stores sessions by working directory
- Root cause: Each request created new sandbox → Claude couldn't find previous sessions
- Solution: Agent-based persistent sandboxes using UUIDs
- Result: Agents maintain conversation continuity across requests

**How it works**:
1. Each agent gets a `sandbox_uuid` at spawn time
2. All agent requests use same sandbox: `var/sandbox/agents/{uuid}/`
3. Claude CLI finds all sessions for that agent in one location

## Git Workflow

### Submodule Management
```bash
# After making changes via KSI events
cd var/lib/compositions
git add . && git commit -m "descriptive message"
git push origin main

# Update parent repo
cd ../../..
git add var/lib/compositions
git commit -m "Update composition submodule"
```

### Commit Standards
- Descriptive messages explaining the change
- Include testing results
- Use conventional commit format when appropriate

## Troubleshooting Patterns

### Common Issues and Solutions

**Timeouts and Connection Issues**:
1. **Check daemon status**: `./daemon_control.py status`
2. **Examine logs**: `tail -f var/logs/daemon/daemon.log.jsonl`
3. **Look for serialization errors**: JSON serialization failures cause timeouts
4. **Check for resource issues**: Memory, file handles, etc.

**Agent Issues**:
- **Agents not responding**: Check if profile has `prompt` field
- **JSON extraction failing**: Validate JSON format, verify legitimate KSI events
- **Session management**: Never create session IDs, use returned values

**Component System Issues**:
- **Components not found**: Run `ksi send composition:rebuild_index`
- **Frontmatter parsing errors**: Check YAML syntax, investigate date handling
- **Git operations failing**: Check submodule initialization

**KSI Hook Issues**:
- **Hook output not visible in Claude Code** (Known issue #3983)
  - **Workaround**: `tail -f /tmp/ksi_hook_diagnostic.log`
  - **Hook control**: `echo ksi_verbose` / `ksi_summary` / `ksi_silent`

## Meta-Principles

### Knowledge Capture (MANDATORY)
**MANDATORY**: When discovering new patterns or fixing issues, you MUST:
1. **Update this CLAUDE.md** IMMEDIATELY for workflow patterns - NO DELAYS
2. **Update project_knowledge.md** IMMEDIATELY for technical details - NO EXCEPTIONS
3. **Document the meta-pattern** IMMEDIATELY to ensure future knowledge capture

### Testing Philosophy
- **Test within KSI** - Use orchestrations and evaluations
- **Start simple** - Single agent tests before complex orchestrations
- **Validate assumptions** - Don't assume something works without testing

### Code Quality
- **Clean as you go** - Remove dead code immediately
- **Complete migrations** - When moving features, remove old code
- **Proper error handling** - No silent failures

## System Status (Current)

### Production Standards
- **Graph-based architecture**: Entities as nodes, events route through edges
- **Unified components**: Everything has `component_type`, organized by purpose
- **Native transports**: WebSocket integrated into daemon, no external bridges
- **Optimized queries**: JSON aggregation eliminates N+1 patterns
- **Session continuity**: Agent sandboxes maintain conversation state
- **Behavioral overrides**: Dependencies properly merge behaviors

## Document Maintenance Patterns

### EVOLVE WORKFLOWS, DON'T EXPAND

**ENHANCE EXISTING PATTERNS**: When updating this document:
- **Improve existing workflows** instead of adding new workflow sections
- **Update investigation examples** rather than accumulating case studies
- **Evolve principles in place** instead of creating new principle categories
- **Replace outdated practices** when better approaches are discovered

### What Belongs Here
- **Development Workflows**: Investigation methods, debugging patterns, development practices
- **Proven Patterns**: Component creation, agent design, testing approaches
- **Meta-Principles**: Knowledge capture, code quality, testing philosophy
- **System Management**: Daemon control, monitoring, troubleshooting

### What Doesn't Belong Here
- **Technical Architecture**: Belongs in PROGRESSIVE_COMPONENT_SYSTEM.md
- **Implementation Details**: Belongs in project_knowledge.md
- **Development History**: Belongs in git commits
- **Accomplishment Lists**: Remove when they become outdated
- **Progress Reports**: Temporary information that doesn't improve workflows

### Update Patterns
- **Workflow Improvements**: Update existing sections with better practices
- **New Discoveries**: Enhance existing principles rather than create new sections
- **Investigation Examples**: Replace old examples with more relevant cases
- **Status Updates**: Update current status, remove completed milestones
- **Meta-Pattern Evolution**: Improve knowledge capture patterns in place

**Principle**: This document should help Claude Code work more effectively, not document what was accomplished.

---

**Remember**: This is your workflow guide. For technical details, implementation patterns, and architecture, always refer to `memory/claude_code/project_knowledge.md`.

*Last updated: 2025-01-18*