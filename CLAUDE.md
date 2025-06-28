# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import config from `ksi_common.config`
- **Import pattern**: `from ksi_common.config import config` or for daemon plugins: `from ...config import config`
- **Path handling**: Use relative paths like `Path("var") / "lib"` for project directories
- **Never use get_config()** - The config is a global instance, just use `config` directly

### Task Management
- **Completion = Code + Test + Deploy + Verify** (not just code creation)
- **Always update TodoWrite** when receiving new instructions
- **Continue systematically** - don't exit early with summaries
- **Be honest** about failures - don't claim false success

### Documentation
- **Git commits** contain session work (not project docs)
- **Avoid creating**: ISSUE.md, TODO.md, FINDINGS.md
- **Document**: Architecture, APIs, essential patterns
- **Don't document**: Timestamps, PIDs, session-specific details

### Development Practices
- **Git is the backup** - no manual file copies needed
- **Confirm before deleting** files (especially logs/data)
- **Event-driven only** - no polling or wait loops
- **Fail fast** - don't mask problems with fallbacks
- **Trust upstream** - e.g., claude-cli owns session_id
- **Complete migrations** - When implementing new features:
  - Migrate entire system to use new feature
  - Remove ALL old code/implementations
  - No fallbacks or backward compatibility
  - Only declare complete after full migration

### Code Hygiene
- **Clean as you go** - remove dead code immediately when found
- **No legacy handlers** - don't keep backward compatibility cruft
- **Trace execution paths** - ensure all code is reachable and used
- **Refactor boldly** - improve structure without preserving old patterns
- **Delete confidently** - if it's not used, remove it
- **Complete transitions** - when moving files/features, verify functionality then remove old locations
- **System integrity** - ensure system functions as designed after cleanup

## Project Organization

### Directory Structure
- **`var/`** - All runtime data (logs, state, experiments, exports)
  - `var/experiments/` - Experimental data (cognitive observations, results)
  - `var/lib/` - Compositions, profiles, fragments, schemas
  - `var/logs/` - All system logs
  - `var/state/` - Runtime state (including last_session_id)
- **`experiments/`** - Experimental code and modules
- **`memory/`** - Project knowledge and session compacts
- **NO legacy directories** - All migrated to proper locations

### Key File Locations
- `daemon_control.py` - Primary daemon control (not .sh)
- `interfaces/chat.py` - Basic chat interface
- `ksi_daemon/plugins/completion/claude_cli_litellm_provider.py` - Provider

## Critical Warnings
⚠️ **NEVER run TUI scripts** without `--test-connection` flag:
- `interfaces/chat_textual.py`
- `interfaces/monitor_tui.py`
- `interfaces/monitor_textual.py`

## Quick Reference
```bash
source .venv/bin/activate          # Always first
./daemon_control.py start          # Start daemon
./daemon_control.py status         # Check status
./daemon_control.py stop           # Stop daemon
./daemon_control.py restart        # Restart daemon

# Common operations
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock
echo '{"event": "conversation:active", "data": {}}' | nc -U var/run/daemon.sock
```

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

---
**Technical Details**: See `memory/claude_code/project_knowledge.md`