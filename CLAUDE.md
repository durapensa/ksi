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
2. **MUST check daemon logs** - `tail -f var/logs/daemon/daemon.log`
3. **MUST search for patterns** - Search logs for related errors
4. **MUST test with minimal cases** - Isolate the problem
5. **MUST fix the root cause** - NEVER bypass or work around issues

### Advanced Debugging Techniques

**Enable Debug Logging**: For deep system investigation
```bash
export KSI_DEBUG=true && export KSI_LOG_LEVEL=DEBUG && ./daemon_control.py restart
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

### Component Creation (Event-Driven)
**CRITICAL**: Always use KSI events to create components, not direct file writes!

```bash
# Create components via events
ksi send composition:create_component --name "components/test/example" \
  --content "# Example Component\n\nContent here..."

# Get component content (handles progressive frontmatter)
ksi send composition:get_component --name "components/test/example"
```

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

# WARNING: --level full produces HUGE output AND can timeout
# Analysis of 220+ events takes >30s
ksi discover --level full > discovery_full.json 2>&1  # NEVER run without redirect
# Alternative: Use namespace filters to reduce scope
ksi discover --level full --namespace agent > discovery_agent_full.json

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

### Modern Component Standards (2025)

**When** creating components:
- **Then** use progressive frontmatter with version, mixins, variables
- **Then** apply MANDATORY imperative patterns for JSON emission
- **Then** use only legitimate KSI events (`agent:*`, `state:*`, `message:*`)
- **Then** test with actual agent spawning and monitor verification

**Component Structure**:
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
2. **Examine logs**: `tail -f var/logs/daemon/daemon.log`
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

### Major Accomplishments (2025)
- ✅ **Component System Cleanup**: 40 obsolete files removed, all components modernized
- ✅ **JSON Extraction Fix**: Balanced brace parsing for arbitrary nesting
- ✅ **Persona-First Architecture**: Proven natural JSON emission
- ✅ **Session Continuity**: Agent-based persistent sandboxes
- ✅ **Event Routing**: Complete originator context propagation
- ✅ **MANDATORY Patterns**: Reliable imperative JSON emission instructions

### Current Standards
- **Components follow 2025 patterns**: Progressive frontmatter, legitimate events, MANDATORY language
- **Comprehensive cleanup completed**: No old agent instructions linger in system
- **Production ready architecture**: All major technical challenges resolved

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

*Last updated: 2025-07-18*