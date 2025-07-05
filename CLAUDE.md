# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import config from `ksi_common.config`
- **Import pattern**: `from ksi_common.config import config` (for all code)
- **Path handling**: **NEVER hardcode paths** - Always use config properties like `config.daemon_log_dir`, `config.socket_path`, etc.
- **Never use get_config()** - The config is a global instance, just use `config` directly
- **❌ WRONG**: `Path("var/logs/daemon")`, `"var/run/daemon.sock"`, hardcoded directory paths
- **✅ CORRECT**: `config.daemon_log_dir`, `config.socket_path`, `config.db_dir`

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
- **Commit in order** - Always commit changes in the order they were made, but batch related work
- **Batch commits** - Group related changes together rather than committing every small fix
- **Document with commits** - Always update key docs (project_knowledge.md, design docs) in same commit as implementation
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

### Session ID Management (Critical)
- **NEVER invent session IDs** - claude-cli only accepts session IDs it has generated
- **No session ID = clean context** - omit session_id for new conversations
- **Session continuation** - only use session_id values returned by previous claude-cli responses
- **Claude-cli returns NEW session_id from EVERY request** - even continuation requests get new session_id
- **Log filename pattern** - response files are named by the NEW session_id returned by claude-cli
- **Conversation tracking** - use session_id from previous response as input, expect new session_id in response
- **Testing pattern**: Always test without session_id first, then use returned session_id for continuation
- **Example**:
  ```bash
  # First request - no session_id (clean context)
  echo '{"event": "completion:async", "data": {"prompt": "Say OK", "model": "claude-cli/sonnet"}}' | nc -U var/run/daemon.sock
  # Returns: request_id "abc123", creates file: var/logs/responses/NEW-SESSION-ID-1.jsonl
  
  # Continue conversation using session_id from previous response
  echo '{"event": "completion:async", "data": {"prompt": "What did I ask?", "model": "claude-cli/sonnet", "session_id": "NEW-SESSION-ID-1"}}' | nc -U var/run/daemon.sock  
  # Returns: request_id "def456", creates file: var/logs/responses/NEW-SESSION-ID-2.jsonl
  
  # Each response contains a DIFFERENT session_id for the next request
  ```

### Code Hygiene
- **NO bare except clauses** - Always catch specific exceptions (e.g. `KeyError`, `ValueError`, `asyncio.CancelledError`)
- **Exception groups** - Use `except*` for `asyncio.TaskGroup` errors
- **Clean as you go** - remove dead code immediately when found
- **No legacy handlers** - don't keep backward compatibility cruft
- **Trace execution paths** - ensure all code is reachable and used
- **Refactor boldly** - improve structure without preserving old patterns
- **Delete confidently** - if it's not used, remove it
- **Complete transitions** - when moving files/features, verify functionality then remove old locations
- **System integrity** - ensure system functions as designed after cleanup

### Simplification Patterns (Pluggy Best Practices)
- **Single source of truth** - Don't pass redundant objects (e.g., both plugin_loader and plugin_manager)
- **Minimal context** - Pass only what plugins actually need in ksi_plugin_context
- **Direct access** - Use plugin_manager directly, not through intermediate objects
- **Consistent naming** - Use the same name for the same concept everywhere (emit_event)
- **No unnecessary wrappers** - Avoid wrapping pluggy functionality unless adding value
- **Module-level simplicity** - Plugins are simple modules with functions, not complex classes
- **Avoid confusion** - Don't create multiple ways to access the same functionality

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

### Debugging & Logging
- **Enable DEBUG logging** - Set `KSI_LOG_LEVEL=DEBUG` environment variable before daemon commands
  ```bash
  KSI_LOG_LEVEL=DEBUG ./daemon_control.py restart  # Restart with debug logging
  KSI_LOG_LEVEL=DEBUG ./daemon_control.py start    # Start with debug logging
  ```
- **Log levels** - Default is INFO; DEBUG shows more verbose output including:
  - Plugin loading details
  - Event routing traces  
  - Module import attempts
  - Configuration details
- **Plugin logging** - Plugins use structured logging with logger names: `ksi.plugin.{plugin_name}`
- **Log locations**:
  - Main daemon log: `var/logs/daemon/daemon.log`
  - Response logs: `var/logs/responses/{session_id}.jsonl`
  - Tool usage: `var/logs/daemon/tool_usage.jsonl`
- **Logging configuration** - The daemon configures logging at startup based on environment variables
  - Logging is automatically configured when importing from ksi_daemon
  - Plugins should use `from ksi_common.logging import get_bound_logger`

## Capability System

### Overview
- **Declarative capabilities** - Agent profiles use capability flags instead of tool lists
- **Single source of truth** - `var/lib/capability_mappings.yaml` defines all capabilities
- **Automatic resolution** - Capabilities expand to events and Claude tools automatically
- **Clean inheritance** - base_single_agent → base_multi_agent → specialized profiles

### Working with Capabilities
- **When creating profiles** - Use capability flags, not explicit tool lists:
  ```yaml
  - name: "capabilities"
    inline:
      state_write: true
      agent_messaging: true
      spawn_agents: true
  ```
- **When updating capabilities** - Edit `capability_mappings.yaml`, then reload compositions
- **When debugging** - Check resolved events in agent spawn response
- **NO backward compatibility** - All profiles must use the new system

### Key Capabilities
- **base** - Core system access (always enabled)
- **state_write** - Shared state management
- **agent_messaging** - Inter-agent communication
- **spawn_agents** - Child agent creation
- **file_access** - Claude file tools (Read, Write, etc.)
- **network_access** - Web access tools

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

## Development Mode
- **Auto-restart on file changes**: `./daemon_control.py dev`
- **Watches**: `ksi_daemon/`, `ksi_common/`, `ksi_client/` directories
- **File types**: Only `.py` files trigger restart
- **Clear output**: Shows file changes and restart count
- **Graceful stop**: Ctrl+C stops both watcher and daemon
- **Future**: Will add checkpoint/restore for state preservation

## Quick Reference
```bash
source .venv/bin/activate          # Always first
./daemon_control.py start          # Start daemon
./daemon_control.py status         # Check status
./daemon_control.py stop           # Stop daemon
./daemon_control.py restart        # Restart daemon
./daemon_control.py dev            # Development mode with auto-restart

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