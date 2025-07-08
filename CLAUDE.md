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

## KSI Hook Monitor
Claude Code has a hook that monitors KSI activity and provides real-time feedback:

- **Output format**: `[KSI]` or `[KSI: X events]` or `[KSI: X events, Y agents]`
- **Test the hook**: Run `echo ksi_check` to verify hook is working
- **Hook only triggers on KSI commands**: Regular bash commands show no output

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
2. Check `/tmp/ksi_hook_diagnostic.log` for hook execution
3. Restart Claude Code and re-enable hook via `/hooks` menu

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