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

**Remember**: Timeouts, connection issues, and serialization errors are symptoms of underlying problems. Always investigate and fix the root cause.

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

## Development Workflow

### Task Management
- **Use TodoWrite tool** - Track progress on all multi-step tasks
- **Completion = Code + Test + Deploy + Verify** - Not just code creation
- **Test within KSI system** - Use orchestrations and evaluations for testing

### Discovery-First Development
```bash
# Always start with discovery
ksi discover --namespace composition
ksi help composition:get_component

# Use KSI CLI (preferred over direct socket)
ksi send event:name --param value
```

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