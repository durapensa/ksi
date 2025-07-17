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

### Persona-First Agent Design (Critical)

**Core Principle**: Agents are **Claude adopting personas**, not "KSI agents".

**When** designing agent components:
- **Then** establish domain persona FIRST (analyst, researcher, coordinator)
- **Then** add minimal KSI-awareness as communication capability
- **Then** test with authentic domain scenarios, not system scenarios

**Component Architecture Pattern**:
```markdown
# components/personas/data_analyst.md
You are a Senior Data Analyst with 10 years experience in business intelligence.
Your approach: methodical, evidence-based, collaborative.

# components/capabilities/ksi_json_reporter.md  
When reporting to systems, use structured JSON:
- Progress: {"event": "analyst:progress", "data": {"stage": "...", "findings": "..."}}
- Results: {"event": "analyst:complete", "data": {"recommendation": "..."}}

# components/agents/business_analyst.md
---
mixins:
  - components/personas/data_analyst.md
  - components/capabilities/ksi_json_reporter.md
---
```

**Key Insight**: JSON becomes a natural reporting tool for domain experts, not forced "agent behavior".

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
```

### Event Result Propagation

**When** agents emit events:
- **Then** check if there's an originator in context
- **Then** route results back via appropriate channel:
  - Agent originators: `completion:async` injection
  - External originators: `monitor:event_chain_result`
  - System originators: Logging/monitoring

**When** spawning agents from agents:
- **Then** propagate originator context
- **Then** spawned agent's events flow back to parent
- **Then** parent can orchestrate based on real-time feedback

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