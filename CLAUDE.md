# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import config from `ksi_common.config`
- **Import pattern**: `from ksi_common.config import config` (for all code including plugins)
- **Plugin imports**: Use absolute imports like `from ksi_daemon.config import config`
- **Path handling**: Use relative paths like `Path("var") / "lib"` for project directories
- **Never use get_config()** - The config is a global instance, just use `config` directly

### Task Management
- **Completion = Code + Test + Deploy + Verify** (not just code creation)
- **Never mark complete until testing demonstrates completeness** - if any related functionality fails during testing, the task remains incomplete
- **Always update TodoWrite** when receiving new instructions
- **Continue systematically** - don't exit early with summaries
- **Be honest** about failures - don't claim false success
- **Test comprehensively** - implementation without working tests is incomplete work

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
- **Inspect before implementing** - When needing new functionality:
  - First thoroughly inspect the module's source code
  - Look for existing classes, methods, or utilities
  - Check for related functionality that could be adapted
  - Only write new code if nothing suitable exists
- **Complete migrations** - When implementing new features:
  - Migrate entire system to use new feature
  - Remove ALL old code/implementations
  - No fallbacks or backward compatibility
  - Only declare complete after full migration

### Plugin System (Simplified)
- **Follows pluggy best practices** - plugins are just objects with hooks
- **No hot reloading** - restart daemon to reload plugins (simpler, more reliable)
- **Absolute imports** - all plugins use `from ksi_daemon.X import Y`
- **Centralized sys.path** - ksi_common ensures project root is on Python path
- **Async task pattern**: Plugins request async tasks via ksi_ready hook:
  ```python
  @hookimpl
  def ksi_ready():
      return {
          "service": "my_service",
          "tasks": [{"name": "background_task", "coroutine": my_async_function()}]
      }
  ```
- **Plugin introspection available**:
  - List plugins: `echo '{"event": "plugin:list", "data": {}}' | nc -U var/run/daemon.sock`
  - List hooks: `echo '{"event": "plugin:hooks", "data": {}}' | nc -U var/run/daemon.sock`
  - Inspect plugin: `echo '{"event": "plugin:inspect", "data": {"plugin_name": "..."}}' | nc -U var/run/daemon.sock`

### Code Hygiene
- **Clean as you go** - remove dead code immediately when found
- **No legacy handlers** - don't keep backward compatibility cruft
- **Trace execution paths** - ensure all code is reachable and used
- **Refactor boldly** - improve structure without preserving old patterns
- **Delete confidently** - if it's not used, remove it
- **Complete transitions** - when moving files/features, verify functionality then remove old locations
- **System integrity** - ensure system functions as designed after cleanup

### Cleanup Philosophy
- **Distinguish legacy from incomplete** - "Legacy" means truly obsolete; "Incomplete" means work-in-progress
- **Never remove intended functionality** - Even if it looks unused, it might be part of planned architecture
- **Document incomplete refactors** - Flag them in project_knowledge.md rather than removing
- **Preserve partial implementations** - They represent design decisions and future work
- **When uncertain, investigate** - Trace usage, check git history, understand intent
- **Update documentation** - When finding incomplete work, document it properly
- **Examples of intended but incomplete**:
  - Injection system (partially implemented, needed for async flows)
  - Session management (basic implementation, awaiting federation)
  - Circuit breakers (scaffold in place, logic pending)
  - Profile fallbacks (may be needed for edge cases)

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

# Plugin introspection
echo '{"event": "plugin:list", "data": {}}' | nc -U var/run/daemon.sock
echo '{"event": "plugin:hooks", "data": {}}' | nc -U var/run/daemon.sock

# Common operations
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock
echo '{"event": "conversation:active", "data": {}}' | nc -U var/run/daemon.sock
```

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

---
**Technical Details**: See `memory/claude_code/project_knowledge.md`