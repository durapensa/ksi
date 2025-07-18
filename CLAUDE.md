# Claude Code Development Guide for KSI

Essential development practices and workflow for Claude Code when working with KSI.

## Session Start Protocol

**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details, current patterns, and validated examples.

This document serves as your primary instructions for KSI development. For technical reference, architecture details, and implementation patterns, see `memory/claude_code/project_knowledge.md`.

## Investigation-First Philosophy

**CRITICAL**: When encountering errors, timeouts, or unexpected behavior - investigate immediately, don't create workarounds.

### Investigation Process

1. **Read the error message carefully** - It often contains the exact problem
2. **Check daemon logs** - `tail -f var/logs/daemon/daemon.log`
3. **Look for patterns** - Search logs for related errors
4. **Test with minimal cases** - Isolate the problem
5. **Fix the root cause** - Don't bypass or work around issues

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

### Example: Timeout Investigation

Recent example of proper investigation:
```bash
# Timeout on component retrieval
ksi send composition:get_component --name "complex_component"
# Error: timeout

# Investigation steps:
1. Check daemon logs: Found "Object of type date is not JSON serializable"
2. Root cause: YAML parser converting dates to Python objects
3. Fix: Add JSON serialization sanitization for date objects
4. Result: Timeout resolved, proper error handling added
```

### Example: Agent JSON Emission Investigation (2025-07-17)

Critical discovery about agent behavior patterns:
```bash
# Agent claims: "Emitted worker:initialized event"
# Monitor shows: No worker:* events

# Investigation steps:
1. Enable debug logging: KSI_DEBUG=true KSI_LOG_LEVEL=DEBUG
2. Check claude-cli spawns: Only 1 process, not claimed "13 turns"
3. Examine completion result: Descriptions only, no actual JSON
4. Root cause: Agents simulate/describe rather than actually emit JSON
5. Fix: Revise prompting to force actual JSON emission
```

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

### Progressive Component System
Components support frontmatter for enhanced features:
```markdown
---
mixins:
  - components/base.md
variables:
  style: professional
---
# {{title|Default Title}}

Enhanced content with variables.
```

### Persona-First Agent Design (BREAKTHROUGH ACHIEVED) ✅

**Core Principle**: Agents are **Claude adopting personas**, not "KSI agents".

**MAJOR SUCCESS**: This approach completely solved the JSON emission problem!

**Proven Results**:
- ✅ **Real JSON Events**: Agents emit `analyst:initialized`, `analyst:progress`
- ✅ **Authentic Expertise**: Domain knowledge maintained throughout interaction  
- ✅ **Natural Communication**: JSON feels like professional status reports
- ✅ **System Integration**: Events successfully extracted and monitored

**Working Component Architecture**:
```bash
# Pure domain expertise (no KSI)
components/personas/universal/data_analyst.md

# Minimal KSI communication capability
components/capabilities/claude_code_1.0.x/ksi_json_reporter.md

# Combined: Domain expert + System awareness
components/agents/ksi_aware_analyst.md
```

**Validated Testing**:
```bash
# Agent spawned successfully
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst"

# Real events captured by system
ksi send monitor:get_events --event-patterns "analyst:*"
# Result: analyst:initialized, analyst:progress events found
```

**Revolutionary Insight**: JSON becomes a natural reporting tool for domain experts, not forced "agent behavior".

### Model and System-Aware Development

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

**Discovery with Model Awareness**:
```bash
# Find components for current environment
ksi send composition:discover --compatible-with current

# Find speed-optimized components
ksi send composition:discover --optimize-for speed --model sonnet-4

# Find reasoning-optimized components
ksi send composition:discover --optimize-for capability --model opus-4

# Query by git attributes
git ls-files | git check-attr --stdin model performance
```

**Component Testing Pattern**:
```bash
# Test component with specific model
./test_component.py --component personas/analyst --model claude-opus-4 --system claude-code-1.0.54

# Validate compatibility across environments
./validate_compatibility.py --component personas/analyst --all-supported-environments

# Test persona-first agent with JSON emission (PROVEN WORKING)
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst" \
  --prompt "Analyze business scenario and report progress"

# Verify events are emitted and captured
ksi send monitor:get_events --event-patterns "analyst:*" --limit 5
```

## Current Development Priority

### Event Routing to Originators Testing ✅ **COMPLETE**

**Status**: Event routing infrastructure fully validated and proven working.

**Results**:
- ✅ **Technical Infrastructure**: All components working correctly
- ✅ **Originator Context**: Proper propagation through event chains
- ✅ **System Events**: Routing to originators via `monitor:event_chain_result`
- ❌ **Agent Behavior**: Inconsistent JSON emission despite identical profiles

**Key Finding**: Event routing works perfectly - the challenge is agent behavioral consistency.

**See**: `docs/PROGRESSIVE_COMPONENT_SYSTEM.md` for detailed validation findings.

### JSON Extraction System Fix (2025-07-18) ✅ **COMPLETE**

**Problem Solved**: Root cause of inconsistent JSON event extraction was a fundamental limitation in the JSON parsing system.

**Technical Issue**: 
- **Regex Pattern Limitation**: Could only handle 1 level of nesting, but legitimate KSI events have 3 levels
- **Silent Failures**: Complex events were ignored without error messages
- **Component Issues**: Multiple components using non-existent `analyst:*` events

**Solution Implemented**:
1. **Enhanced JSON Extraction**: Created balanced brace parsing for arbitrary nesting levels
2. **Error Feedback System**: Comprehensive error responses sent back to agents
3. **Component Upgrades**: All old components updated to use legitimate KSI events (`agent:*`, `state:*`, `message:*`)

**Results**:
- ✅ **JSON Extraction Working**: Deeply nested events properly extracted
- ✅ **Agent Events Captured**: Monitor shows legitimate KSI events with `_extracted_from_response: true`
- ✅ **System Integration**: Events flow correctly through KSI monitoring system

**Components Fixed**:
- `components/agents/ksi_aware_analyst` ✅
- `components/agents/optimized_ksi_analyst` ✅
- `components/agents/prefill_optimized_analyst` ✅ 
- `components/agents/xml_structured_analyst` ✅

### Agent Behavioral Consistency Testing

**New Priority**: Manual prompt optimization to achieve consistent KSI-operating behavior.

**Challenge**: With JSON extraction working, focus shifts to LLM consistency:
- Technical infrastructure is solid
- Need to optimize prompts for reliable instruction following
- Test patterns that ensure consistent JSON emission behavior

**Approach**: Direct `claude -p` prompt optimization to enforce consistent instruction following.

**When** working on agent consistency:
- **Then** test prompt variations for reliable JSON emission
- **Then** identify patterns that ensure consistent behavior
- **Then** update component instructions based on proven patterns
- **Then** validate fixes with the working JSON extraction system

## Development Workflow

### Task Management
- **Use TodoWrite tool** - Track progress on all multi-step tasks
- **Completion = Code + Test + Deploy + Verify** - Not just code creation
- **Test within KSI system** - Use orchestrations and evaluations for testing

### Discovery-First Development

**Understanding Discovery Layers**:
- **System Discovery** (`ksi discover`): Shows what capabilities exist and where to find them
- **Domain Discovery** (`composition:discover`, `agent:discover`): Queries actual data within that domain

```bash
# System discovery - what can I do?
ksi discover                    # Shows all namespaces
ksi discover --namespace composition  # Points to composition events

# Domain discovery - what's in this domain?
ksi send composition:discover --type component  # Query components from SQLite
ksi send composition:list --filter '{"author": "ksi"}'  # List with filters
ksi send agent:list  # List active agents

# Get help for specific events
ksi help composition:get_component
```

**Key Principle**: System discovery guides you to domain discovery events, it doesn't return domain data itself.

### Error Handling
- **No bare except clauses** - Catch specific exceptions
- **Use error_response()** - For handler errors
- **Log with context** - Include relevant details for debugging

## Troubleshooting Patterns

### Timeouts and Connection Issues
When events timeout or connections fail:

1. **Check daemon status**: `./daemon_control.py status`
2. **Examine logs**: `tail -f var/logs/daemon/daemon.log`
3. **Look for serialization errors**: JSON serialization failures cause timeouts
4. **Check for resource issues**: Memory, file handles, etc.

### Common Timeout Causes
- **JSON serialization failures** - Date objects, complex nested structures
- **Large response payloads** - Break into smaller chunks
- **Blocking operations** - Long-running synchronous code in handlers
- **Network issues** - Socket connection problems

### Agent Issues
- **Agents not responding**: Check if profile has `prompt` field
- **JSON extraction failing**: Validate JSON format in agent responses
- **Session management**: Never create session IDs, use returned values

### Component System Issues
- **Components not found**: Run `ksi send composition:rebuild_index`
- **Frontmatter parsing errors**: Check YAML syntax, investigate date handling
- **Git operations failing**: Check submodule initialization

## Key Commands

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

### Development Tools
```bash
# Discovery
ksi discover
ksi help event:name

# Component management
ksi send composition:create_component --name "test" --content "..."
ksi send composition:get_component --name "test"

# Testing
ksi send orchestration:start --pattern test_pattern
```

## Session Management (Critical)

1. **Never create session IDs** - Only claude-cli creates them
2. **Each completion returns NEW session_id** - Use it for next request
3. **Response logs** use session_id as filename: `var/logs/responses/{session_id}.jsonl`

### Session ID Architectural Boundary (2025-07-17)

**Architectural Principle**: Session IDs must NEVER leak outside completion system!
- **Agents are the ONLY abstraction** - External systems use `agent_id` only
- **Session IDs are internal** - Completion system manages them privately
- **Boundary violations fixed** - Orchestration, injection, client interfaces

```bash
# ✅ CORRECT: External APIs use agent_id
ksi send completion:async --agent-id my_agent --prompt "..."

# ❌ WRONG: Session IDs should never be exposed
ksi send completion:async --session-id 943a3864-d5bb... --prompt "..."
```

### Session Continuity Fix (2025-07-17) ✅

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

## Meta-Principles

### Knowledge Capture
**CRITICAL**: When discovering new patterns or fixing issues:
1. **Update this CLAUDE.md** immediately for workflow patterns
2. **Update project_knowledge.md** for technical details
3. **Document the meta-pattern** to ensure future knowledge capture

### Testing Philosophy
- **Test within KSI** - Use orchestrations and evaluations
- **Start simple** - Single agent tests before complex orchestrations
- **Validate assumptions** - Don't assume something works without testing

### Code Quality
- **Clean as you go** - Remove dead code immediately
- **Complete migrations** - When moving features, remove old code
- **Proper error handling** - No silent failures

---

**Remember**: This is your workflow guide. For technical details, implementation patterns, and architecture, always refer to `memory/claude_code/project_knowledge.md`.

*Last updated: 2025-07-16*