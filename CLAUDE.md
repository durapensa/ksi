# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import `from ksi_common.config import config`
- **Path handling**: **NEVER hardcode paths** - Always use config properties
- **❌ WRONG**: `Path("var/logs/daemon")`, `"var/run/daemon.sock"`
- **✅ CORRECT**: `config.daemon_log_dir`, `config.socket_path`, `config.evaluations_dir`

### Task Management
- **Completion = Code + Test + Deploy + Verify** (not just code creation)
- **Never mark complete until testing demonstrates completeness**
- **Always update TodoWrite** when receiving new instructions
- **Test comprehensively** - implementation without working tests is incomplete

### Development Practices
- **Event-driven only** - no polling or wait loops, modules communicate only through events
- **Complete migrations** - when implementing new features, migrate entire system, remove ALL old code
- **Separation of concerns** - Event log (infrastructure) vs Relational state (application data)
- **Inspect before implementing** - check existing code before writing new functionality

### Session ID Management (Critical)
- **NEVER invent session IDs** - claude-cli only accepts session IDs it has generated
- **Claude-cli returns NEW session_id from EVERY request** - even continuation requests
- **Always use session_id from previous response as input**

### Code Hygiene
- **NO bare except clauses** - Always catch specific exceptions
- **Clean as you go** - remove dead code immediately when found
- **Complete transitions** - when moving features, verify functionality then remove old locations

## Discovery-First Development

**CRITICAL**: Always use the discovery system before reading source code. The discovery system is your primary tool for understanding available events and their parameters.

### Basic Discovery Workflow

```bash
# 1. Find events in a namespace (start with detail=false)
echo '{"event": "system:discover", "data": {"namespace": "evaluation", "detail": false}}' | nc -U var/run/daemon.sock | jq

# 2. Get detailed help for a specific event
echo '{"event": "system:help", "data": {"event": "evaluation:prompt"}}' | nc -U var/run/daemon.sock | jq

# 3. List events from a specific module
echo '{"event": "module:list_events", "data": {"module_name": "ksi_daemon.evaluation.prompt_evaluation", "detail": true}}' | nc -U var/run/daemon.sock | jq
```

### Common Discovery Patterns

**Finding Event Parameters:**
```bash
# Wrong: Grepping source code
grep "@event_handler" ksi_daemon/evaluation/*.py  # ❌ Don't do this

# Right: Use discovery system
echo '{"event": "system:help", "data": {"event": "evaluation:prompt"}}' | nc -U var/run/daemon.sock | jq '.data.parameters'  # ✅ Do this
```

**Exploring Namespaces:**
```bash
# List all events in a namespace without overwhelming detail
echo '{"event": "system:discover", "data": {"namespace": "composition", "detail": false}}' | nc -U var/run/daemon.sock | jq '.data.events | keys'

# Get summary of namespace
echo '{"event": "system:discover", "data": {"namespace": "evaluation", "format_style": "compact"}}' | nc -U var/run/daemon.sock | jq
```

### Discovery Best Practices

1. **Start with `detail": false`** - Get overview before diving deep
2. **Use namespace filtering** - Focus on relevant subsystems
3. **Use `system:help` for specific events** - More focused than full discovery
4. **Try different format_style options** - verbose, compact, ultra_compact, mcp
5. **Chain discovery calls** - Start broad, then narrow down

### When Discovery Fails

If discovery doesn't provide needed information:
1. Document the gap in `memory/claude_code/discovery_findings.md`
2. Then (and only then) read source code
3. Propose discovery system improvements

**Note**: Discovery system improvements are tracked in `memory/claude_code/discovery_findings.md`

## KSI Hook Monitor
Claude Code has a hook that monitors KSI activity and provides real-time feedback:

- **Output format**: `[KSI]` or `[KSI: X events]` or `[KSI: X events, Y agents]`
- **Status indicators**: ✓ for success, ✗ for errors/failures
- **Test the hook**: Run `echo ksi_check` to verify hook is working
- **Hook only triggers on KSI commands**: Regular bash commands show no output

### Verbosity Control Commands
Control the hook's output verbosity without restarting Claude Code:

```bash
echo ksi_status    # Check current verbosity mode
echo ksi_summary   # Default mode - concise output
echo ksi_verbose   # Show all events with details
echo ksi_errors    # Only show error events
echo ksi_silent    # Temporarily disable output
```

### Hook Output Examples

**Summary mode (default)**:
```
[KSI: 3 events]                    # Basic event count
[KSI: ✗ 1 errors, 5 events]       # Errors highlighted
[KSI: 2 events, 3 agents]          # Agent activity
```

**Verbose mode**:
```
[KSI: 5 new] 19:45:23 ✓ evaluation:prompt
19:45:20 completion:* (×6)
19:45:15 ✓ spawn:agent_123
19:45:10 ✗ ERROR:event:error
```

**Errors mode**:
```
[KSI: 2 errors] 19:45:10 ✗ ERROR:event:error
19:43:20 ✗ agent:spawn failed
```

### Hook Monitoring Protocol
**After KSI-related commands, Claude should see `[KSI]` output.**

### Examples:
```bash
echo ksi_check                     # Should show: [KSI] or [KSI: X events]
./daemon_control.py status         # Should show: [KSI]
ls                                 # Shows: nothing (not KSI-related)
```

### Troubleshooting:
If no [KSI] output after KSI commands:
1. Test with `echo ksi_check`
2. Check current mode with `echo ksi_status`
3. Check `/tmp/ksi_hook_diagnostic.log` for hook execution
4. Restart Claude Code and re-enable hook via `/hooks` menu

**Details**: See `ksi_claude_code/ksi_hook_monitor_filters.txt`

## Quick Reference
```bash
source .venv/bin/activate          # Always first
./daemon_control.py start          # Start daemon
./daemon_control.py status         # Check status
./daemon_control.py restart        # Restart daemon

# Module introspection
echo '{"event": "module:list", "data": {}}' | nc -U var/run/daemon.sock
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock
```

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## KSI Integration Tools
**For Python tools to interact with KSI**: See `ksi_claude_code/CLAUDE.md`
- Agent spawning and conversation management
- Real-time observation and monitoring
- Graph database operations
- Composition and capability management

---
**Technical Details**: See `memory/claude_code/project_knowledge.md`