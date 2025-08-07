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

## Current Development Priority (2025-08-07)

**ACTIVE**: Layer 2 - Comparative Analysis with Attractor Testing
- **Major Discovery**: Turn count reveals 2100% cognitive overhead on emergence topics
- **Status**: Testing optimization under conceptual attractors
- **Research**: See `/docs/PAPER_DRAFT_COGNITIVE_OVERHEAD_IN_LLMS.md`
- **Results**: See `/docs/PERSONAL_INTEREST_ATTRACTOR_RESULTS.md`

**COMPLETED**: Dynamic Routing Architecture Implementation ✅
- **Status**: Production ready - agents can control routing at runtime
- **Details**: See `memory/claude_code/project_knowledge.md` → Dynamic Routing System
- **Guide**: See `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` for operational guide

**Previous**: Agent-Driven Optimization via Orchestration Patterns
- **Foundation**: Direct JSON emission by agents proven impossible ❌
- **Solution**: Three-layer orchestration pattern discovered ✅
- **Status**: Can now be implemented using dynamic routing

## Investigation-First Philosophy

**MANDATORY**: When encountering errors, timeouts, or unexpected behavior - you MUST investigate immediately. NEVER create workarounds. NEVER bypass issues.

### CRITICAL RULE: FIX BEFORE PROCEEDING

**STOP ALL OTHER WORK** when you encounter:
- Daemon startup/connection issues
- Repeated error messages in logs
- Timeout errors
- "No event emitter configured" or similar infrastructure errors
- **Handler errors during testing** (e.g., "'str' object has no attribute 'get'")
- **Type mismatches or parsing errors**
- **Any error that prevents expected functionality**

**YOU MUST**:
1. Fix the issue completely
2. Verify the fix works
3. Update documentation
4. ONLY THEN continue with other tasks

**VIOLATION OF THIS RULE IS UNACCEPTABLE**

### Investigation Process (REQUIRED STEPS)

1. **MUST read the error message carefully** - It often contains the exact problem
2. **MUST check daemon logs** - `tail -f var/logs/daemon/daemon.log.jsonl`
3. **MUST search for patterns** - Search logs for related errors
4. **MUST test with minimal cases** - Isolate the problem
5. **MUST fix the root cause** - NEVER bypass or work around issues
6. **MUST handle edge cases** - Fix parameter parsing, type validation, etc.
7. **MUST verify the fix** - Test the exact failing case again after fixing

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

### Architecture Consistency (CRITICAL)
- **Event-Driven Only**: All production functionality must use KSI's event system
- **Bootstrap vs Production Pattern**: Python scripts acceptable for discovery, dynamic routing + components required for production
- **Anti-Pattern Warning**: Standalone scripts bypassing event system are acceptable for bootstrapping only
- **Observable Systems**: All processes must be introspectable through KSI's monitoring

### Configuration Management
- **Use ksi_common/config.py** - Always import `from ksi_common.config import config`
- **Never hardcode paths** - Use config properties: `config.daemon_log_dir`, `config.socket_path`

### Event-Driven Development
- **All communication through events** - No direct module imports between services
- **Use discovery system first** - `ksi discover`, `ksi help event:name`
- **Event handlers use TypedDict** - For parameter documentation and validation

### Shared Utilities (MANDATORY USAGE ✅)
- **Service Transformer Manager** - Use `auto_load_service_transformers(service_name)` instead of manual loading
- **Transformer Patterns** - Use `TransformerTemplateBuilder` for common routing patterns
- **Condition Evaluator** - Complex boolean expressions for transformer conditions
- **Event Response Builder** - Standardized responses with KSI context

**When** creating service transformers:
- **Then** use `ServiceTransformerManager` for centralized loading
- **Then** add service to `var/lib/transformers/services.json` configuration
- **Then** use `TransformerPatterns` for broadcast, state update, error routing
- **Then** leverage `CommonConditions` and `CommonMappings` libraries

### Component Creation (Unified Architecture 2025)
**CRITICAL**: Everything is a component! The system forms a directed graph where:
- **Nodes**: Event-emitting entities (agents, workflows)
- **Edges**: Parent-child relationships, routing rules, capabilities  
- **Universal spawn**: Component type determines what gets created
- **Dynamic routing**: Agents control event routing at runtime through routing rules

```bash
# Create components via events with proper type
ksi send composition:create_component --name "personas/analysts/data_analyst" \
  --content "---\ncomponent_type: persona\nname: data_analyst\nversion: 2.0.0\n---\n# Senior Data Analyst\n..."

# Component types: core|persona|behavior|workflow|evaluation|tool
# Organization: components/{type}/{category}/{name}.md
```

**New Component Organization**:
- `core/` - Essential building blocks (base_agent, json_emitter)
- `personas/` - Domain expertise (analysts/, developers/, thinkers/)
- `behaviors/` - Reusable mixins (communication/, coordination/)
- `workflows/` - Multi-agent patterns (optimization/, coordination/)
- `evaluations/` - Quality assessments (metrics/, judges/, suites/)
- `tools/` - External integrations (mcp/, git/, apis/)

### Persona-First Agent Design ✅ PROVEN

**Core Principle**: Agents are **Claude adopting personas**, not "KSI agents".

**Working Component Architecture**:
```bash
# Pure domain expertise (no KSI)
components/personas/universal/data_analyst.md

# Minimal KSI communication capability
components/capabilities/claude_code_1.0.x/ksi_json_reporter.md

# Combined: Domain expert + System awareness
components/agents/ksi_aware_analyst.md
```

### Agent Communication Pattern ✅ PROVEN WITH LIMITATIONS

**Direct Agent-to-Agent Messaging Works**:
```json
// Researcher agent sends findings to analyzer
{"event": "completion:async", "data": {"agent_id": "analyzer", "prompt": "FINDINGS: [research results]. Please analyze."}}

// Analyzer sends analysis back to researcher
{"event": "completion:async", "data": {"agent_id": "researcher", "prompt": "ANALYSIS: [analysis results]. Communication complete."}}
```

**Critical Limitation Discovered (2025-01-27)**:
- **Agents cannot reliably emit JSON directly** - Claude's default behavior overrides all prompt engineering attempts
- **Solution**: Use dynamic routing patterns where agents analyze and routing transformers emit JSON

**Working Pattern for Agent-Driven Optimization**:
1. **Analysis Layer**: Agents provide natural language recommendations
2. **Translation Layer**: JSON transformer converts to events
3. **Execution Layer**: System processes the JSON events
4. See `components/workflows/agent_optimization_flow` for implementation

### JSON Emission Patterns (VALIDATED 2025-01-27)

**PRODUCTION STATUS**: ✅ KSI tool use pattern validated and production-ready

#### KSI Tool Use Pattern (PRODUCTION VALIDATED) ✅
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

**Validation Results**:
- ✅ **100% success rate** in comprehensive agent testing
- ✅ **4/4 event types** successfully extracted and processed
- ✅ **End-to-end workflow** validation with state management
- ✅ **Component integration** with base_agent.md v2.0.0

**Implementation**:
- **Use** `behaviors/communication/ksi_events_as_tool_calls` component
- **Leverages** LLMs' native tool-calling abilities  
- **Dual-path extraction** supports both legacy and tool use formats
- **See** `/docs/KSI_TOOL_USE_PATTERNS.md` for complete specification

#### 2. Orchestration Pattern
```yaml
# Agents provide analysis in natural language
analyzer:
  component: "components/personas/optimizers/component_analyzer"
  prompt: "Analyze and recommend optimizations"

# Orchestrator translates to JSON
executor:
  component: "components/core/json_orchestrator" 
  prompt: "Convert recommendations to JSON events"
```

**When** creating agent systems:
- **Then** use KSI tool use pattern for reliable JSON event emission (see JSON Emission Patterns above)
- **Then** leverage LLMs' natural understanding of tool call formats
- **Then** use dynamic routing patterns for complex multi-agent flows when needed
- **Then** focus agents on their domain expertise

## Development Workflow

### Task Management (MANDATORY)
- **MUST use TodoWrite tool** - Track progress on ALL multi-step tasks. NO EXCEPTIONS.
- **MUST complete ALL steps**: Code + Test + Deploy + Verify - NEVER stop at code creation
- **MUST test within KSI system** - Use workflows and evaluations for testing

### Discovery-First Development (MANDATORY)

**MANDATORY**: You MUST use discovery BEFORE attempting any task. NO EXCEPTIONS.

**Progressive Discovery Methodology**:
1. **Start broad**: `ksi discover` - Get namespace overview
2. **Narrow focus**: `ksi discover --namespace <name>` - Explore specific area
3. **Get details**: `ksi help <event:name>` - Understand specific events

**Domain Discovery with Evaluation** ✅:
```bash
# Query components with evaluation filters
ksi send composition:discover --type agent \
  --tested_on_model "claude-sonnet-4" \
  --evaluation_status "passing"

# Discover validated behavioral components
ksi send composition:discover --type behavior \
  --min_performance_class "fast"

# Check specific component evaluations
python ksi_evaluation/discover_validated.py dsl
```

**CRITICAL RULE**: System discovery guides you to domain discovery events, it NEVER returns domain data itself.

### Error Handling
- **No bare except clauses** - Catch specific exceptions
- **Use error_response()** - For handler errors
- **Log with context** - Include relevant details for debugging

### Event Handler Documentation
- **Use single-line docstrings** - Just describe what the handler does
- **Define parameters in TypedDict** - With inline comments for descriptions
- **Let discovery auto-extract** - Parameters, types, and examples are generated
- **No Args/Returns/Examples sections** - These cause parsing issues
- **See** `memory/claude_code/project_knowledge.md` → Documentation Standards for details

### Service Robustness
- **Use checkpoint_participant decorator** - For automatic state persistence
- **Implement collect_checkpoint_data()** - Return service state to checkpoint
- **Implement restore_from_checkpoint()** - Restore service state on restart
- **Example**: See `ksi_daemon/example_checkpoint_service.py` for usage pattern

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
component_type: persona  # MANDATORY: core|persona|behavior|workflow|evaluation|tool
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

### Self-Improving Agent Components (BOOTSTRAP COMPLETE) ✅

**Foundation for Autonomous Improvement**:
Agents can now optimize their own and other agents' instructions using KSI's optimization tools.

**Bootstrap Components Created**:
```bash
# Core self-improvement personas
personas/optimizers/self_improving_agent      # Optimizes any component
personas/optimizers/workflow_optimizer       # Evolves workflow patterns
personas/optimizers/tournament_coordinator    # Manages competitive evolution

# Evaluation components  
evaluations/judges/improvement_judge          # Validates optimizations

# Full ecosystem workflow
workflows/ecosystem/self_improvement_ecosystem
```

**Self-Improvement Workflow**:
```yaml
# Agent analyzes a component
{"event": "composition:get_component", "data": {"name": "personas/data_analyst"}}

# Agent runs optimization (MIPRO for comprehensive, SIMBA for incremental)
{"event": "optimization:async", "data": {
  "component": "personas/data_analyst",
  "method": "mipro",
  "goal": "Reduce token usage by 30% while maintaining quality"
}}

# Agent saves improved version
{"event": "composition:create_component", "data": {
  "name": "personas/data_analyst_v2_optimized",
  "content": "{{improved_instructions}}"
}}
```

**CRITICAL - Capability Requirements**:
```yaml
# Self-improving agents need expanded capabilities
# Standard agents only have "base"
agent:
  capabilities:
    - composition     # Access component system
    - optimization    # Run MIPRO/SIMBA
    - state          # Track improvements
    - agent          # Spawn test agents

# Grant via permission profile or orchestration config
```

**Meta-Optimization Capability**:
Agents can optimize the very orchestration patterns they use:
- Analyze coordination efficiency
- Evolve DSL for better clarity
- Create new coordination constructs
- Test improvements through tournaments

### Orchestration Pattern Design

**When** creating orchestration patterns:
- **Then** define agent behavior in prompts, not system routing rules
- **Then** use simple YAML with `agents:` → `component:` + `prompt:`
- **Then** let coordination emerge from agent communication
- **Then** include DSL in `orchestration_logic:` for agents to interpret (not system)
- **Remember**: InitializationRouter only delivers prompts - no coordination control

**Example orchestration pattern**:
```yaml
agents:
  coordinator:
    component: "components/core/orchestration_coordinator"
    prompt: |
      You coordinate the analysis workflow.
      Send tasks to analysts and synthesize results.
      
  analyst:
    component: "components/personas/data_analyst"  
    prompt: "Analyze the provided data and report findings."

orchestration_logic:  # DSL for coordinator agent to interpret
  strategy: |
    FOREACH data_source IN sources:
      SEND analyst: "Analyze {data_source}"
      AWAIT response
    SYNTHESIZE all_responses
```

### Optimization Development Pattern

**When** implementing optimization features (MIPRO, DSPy, etc.):
- **Then** create orchestration patterns, not new coordination systems
- **Then** use evaluation components for metrics, not embedded scoring
- **Then** provide minimal utilities only (framework config, data formatting)
- **Then** leverage agent conversation continuity for iterative optimization
- **See** `/docs/OPTIMIZATION_APPROACH.md` for architecture philosophy

**Long-Running Optimization Pattern (CRITICAL)**:
- **NEVER over-monitor** - Subprocess system handles 5-15 minute optimizations automatically
- **Start and proceed** - Use `optimization:async`, then build evaluation flow while it runs
- **Trust the system** - MLflow tracking + KSI hook provide status without polling
- **Check results at completion** - Use `optimization:status` only when building evaluation/update flow
- **Complete full pipeline** - DSPy → LLM-as-Judge → Component Update → Git Commit

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

### Dynamic Routing Workflow

**When** implementing agent coordination:
- **Then** use dynamic routing instead of static orchestrations  
- **Then** grant agents `routing_control` capability
- **Then** see `/docs/DYNAMIC_ROUTING_QUICKSTART.md` for examples
- **Then** see `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` → Operational Guide for patterns

### Dynamic Agent Coordination (Current Architecture)
**When** working with agents and dynamic routing:
- **Then** remember agents coordinate through dynamic routing rules, not static orchestrations
- **Then** agents with routing_control capability use `routing:add_rule` to coordinate
- **Then** coordination emerges from agent communication and routing decisions
- **Then** this reflects reality: agents naturally create coordination patterns as needed
- **Example**: An agent creates routing rules to coordinate with other agents = emergent coordination

### Claude Code as Coordinating Agent
**When** coordinating agents from Claude Code:
- **Then** spawn agents with appropriate capabilities and prompts
- **Then** agents can create routing rules to coordinate with each other
- **Then** use agent:spawn with specific coordination instructions
- **Then** monitor coordination via `ksi send monitor:get_events --_client_id "claude-code"`

**Example agent-driven coordination**:
```bash
ksi send agent:spawn --profile "coordination_specialist" \
  --prompt "Coordinate analysis by spawning analysts and routing their outputs appropriately"
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
- **Parameter is hidden** - `session_id` marked with `[CLI:option,hidden=true]` and filtered from discovery

```bash
# ✅ CORRECT: External APIs use agent_id
ksi send completion:async --agent-id my_agent --prompt "..."

# ❌ WRONG: Session IDs should never be exposed (parameter hidden from discovery)
ksi send completion:async --session-id 943a3864-d5bb... --prompt "..."
```

**Implementation Notes** (2025-01-05):
- The `session_id` parameter still exists internally for completion system operations
- Discovery filtering removes parameters with `cli_hidden=True` from public visibility
- Agent_id provides automatic session continuity without exposing internal details

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
- **Conversation continuity** (FIXED 2025-01-07): Stateless providers now maintain perfect context
  - **Solution**: Conversation indices at `var/logs/conversations/`
  - **Details**: See `/docs/CONVERSATION_CONTINUITY_FIX_PLAN.md`
- **sandbox_uuid missing error**: Agent state entity not created by transformer
  - **Workaround**: Manually create state entity: `ksi send state:entity:create --type agent --id "agent_id" --properties '{"sandbox_uuid": "uuid_from_agent_info"}'`
  - **Root cause**: `agent_spawned_state_create` transformer not firing
- **Agents not emitting events**: Check capability restrictions! (CRITICAL)
  - **Problem**: Agents spawned with only "base" capability can ONLY emit: `system:health`, `system:help`, `system:discover`
  - **Impact**: DSL interpreters and most agents cannot emit `agent:status`, `completion:async`, etc.
  - **Check**: Look at spawn response for `allowed_events` field
  - **Missing events**: `state:entity:update` is NOT in any capability mapping!
  - **Location**: `/var/lib/capabilities/capability_mappings.yaml`

**Component System Issues**:
- **Components not found**: Run `ksi send composition:rebuild_index`
- **Frontmatter parsing errors**: Check YAML syntax, investigate date handling
- **Git operations failing**: Check submodule initialization

**Orchestration Prompt Delivery Issues**:
- **Agents not receiving initial prompts**: Put prompts in `vars.initial_prompt`, not directly in agent config
- **Correct YAML format**:
  ```yaml
  agents:
    coordinator:
      component: "components/core/base_agent"
      vars:
        initial_prompt: |
          Your prompt goes here
  ```
- **Legacy router behavior**: Only sends prompts from `vars.initial_prompt` field

**KSI Hook Issues**:
- **Hook output not visible in Claude Code** (Known issue #3983)
  - **Workaround**: `tail -f /tmp/ksi_hook_diagnostic.log`
  - **Hook control**: `echo ksi_verbose` / `ksi_summary` / `ksi_silent`

**Optimization Service Issues**:
- **Timestamp attribute errors**: `timestamp_utc()` returns string, not timestamp object
  - **Fix**: Use `time.time()` for numeric timestamps
  - **Location**: `ksi_daemon/optimization/optimization_service.py`
- **0% improvement with MIPRO/SIMBA**: Default metric too simplistic
  - **Solution**: Implement proper evaluation metrics or LLM-as-Judge
  - **Note**: Both optimizers run successfully but need better metrics

## Building Agent-Driven Systems

**When** creating agent-driven optimization or automation:
- **Then** use dynamic routing patterns with workflow components
- **Then** let agents focus on their expertise (analysis, recommendations)
- **Then** use routing transformers for system integration (JSON events)
- **Then** test each layer independently before integration

**Proven Dynamic Routing Pattern** (2025-07-28):
1. **Analysis Layer**: Domain expert agents that understand the problem
2. **Translation Layer**: JSON transformers that convert intent to events
3. **Execution Layer**: System handlers that process the events

**Example - Agent-Driven Optimization**:
```bash
# See components/workflows/agent_optimization_flow
ksi send workflow:create \
  --workflow_id "agent_optimization" \
  --agents '[{"id": "optimizer", "component": "personas/optimizers/component_optimizer"}]' \
  --vars '{"component_name": "personas/data_analyst", 
           "optimization_goal": "reduce tokens by 30%"}'
```

This pattern enables agents to effectively "optimize" components without fighting Claude's nature.

## Meta-Principles

### Elegant Architecture Philosophy (CRITICAL)
- **System as enabler, not controller** - Provide infrastructure, don't orchestrate behavior
- **No workarounds** - Fix issues at their source, never add special cases
- **Data flow integrity** - Preserve all fields through system boundaries
- **Compositional patterns** - Everything composes: components, capabilities, profiles
- **See** `/docs/KSI_PHILOSOPHY_ELEGANT_ARCHITECTURE.md` for detailed principles

### Knowledge Capture (MANDATORY)
**MANDATORY**: When discovering new patterns or fixing issues, you MUST:
1. **Update this CLAUDE.md** IMMEDIATELY for workflow patterns - NO DELAYS
2. **Update project_knowledge.md** IMMEDIATELY for technical details - NO EXCEPTIONS
3. **Document the meta-pattern** IMMEDIATELY to ensure future knowledge capture
4. **Update docs/** for architectural patterns and philosophy

### Testing Philosophy
- **Test within KSI** - Use workflows and evaluations
- **Start simple** - Single agent tests before complex workflows
- **Validate assumptions** - Don't assume something works without testing
- **Verify actual behavior** - Check logs, don't trust agent claims

### Code Quality
- **Clean as you go** - Remove dead code immediately
- **Complete migrations** - When moving features, remove old code
- **Proper error handling** - No silent failures
- **Trace data flow** - Understand where data is lost before fixing

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
- **AI Safety Research Plans**: Belongs in KSI_TRANSPARENCY_ALIGNMENT_ENHANCEMENTS.md
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

**Remember**: This is your workflow guide. For technical details, implementation patterns, and architecture, always refer to `memory/claude_code/project_knowledge.md`. For AI safety research initiatives and transparency enhancements, see `docs/KSI_TRANSPARENCY_ALIGNMENT_ENHANCEMENTS.md`.

*Last updated: 2025-01-27*