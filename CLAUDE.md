# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Start Instructions

**MANDATORY FIRST STEP**: Read `memory/claude_code/project_knowledge.md` for critical project knowledge, then this file for development guidelines.

## Core Development Principles

### Work Practices
- **Task Completion**: A task is NOT complete until it's fully tested and deployed. Creating code is only step 1.
- **Workflow**: Continue working systematically through tasks - don't exit early with summaries
- **Honesty**: DO NOT claim success when things are failing. Be honest about actual status.
- **Todo Tracking**: Always update your todo list when receiving updated instructions
- **Version Control**: Git contains all backups - no need for manual file backups during development

### Documentation Standards
- **Session work belongs in git commits**, not in project documentation files
- **Avoid creating**: ISSUE.md, TODO.md, FINDINGS.md, STATUS.md (use TodoWrite instead)
- **DO document**: Architecture, APIs, troubleshooting patterns, essential working knowledge
- **DO NOT document**: Timestamps, PIDs, session details, "Recent work done", commit-style entries

### File Operations
- **Deletion Policy**: Always confirm with user before deleting files (especially claude_logs/, data files, configs)
- **Organization**: Place tests in `tests/`, tools in `tools/`, clean up temporary files promptly
- **Memory System**: See `memory/claude_code/project_knowledge.md` for detailed technical knowledge

## Design Philosophy

### System Architecture
- **Event-Driven Only**: No polling, timers, or wait loops
- **Fail Fast**: Let the system fail loudly rather than masking problems with fallbacks
- **Component Ownership**: Trust upstream components (e.g., claude-cli owns session_id generation)
- **Research Software**: Breaking changes are welcome - prioritize clean architecture over compatibility

### Libraries
- **ksi_client/**: For agents participating in the system
- **ksi_admin/**: For monitoring and controlling the system
- **Independent**: No cross-dependencies between libraries

## Technical Environment

### Virtual Environment
```bash
source .venv/bin/activate  # ALWAYS activate first
# Dependencies: PyYAML, textual, psutil, pydantic, structlog, tenacity
```

### Daemon Management
**ALWAYS use `./daemon_control.sh`** - never start daemon directly:
```bash
./daemon_control.sh start    # Start daemon
./daemon_control.sh status   # Check status
./daemon_control.sh health   # Show agents and processes
./daemon_control.sh restart  # Restart daemon
./daemon_control.sh stop     # Graceful shutdown
```

### Quick Status Check
```bash
./daemon_control.sh status
git log --oneline -5
echo '{"event": "conversation:active", "data": {}}' | nc -U var/run/daemon.sock
```

## ⚠️ Critical Warnings

### NEVER Run TUI Scripts from Claude Code
Running these without `--test-connection` flag corrupts Claude Code interface:
- `interfaces/chat_textual.py`
- `interfaces/monitor_tui.py`
- `interfaces/monitor_textual.py`

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## Extending the System

1. **Direct Modification**: Edit files directly with your tools
2. **Python Modules**: Create `claude_modules/handler.py` with `handle_output(output, daemon)`
3. **Log Analysis**: Sessions in `claude_logs/<session-id>.jsonl`

## Running the System
```bash
# Start daemon first
./daemon_control.sh start

# Then run interfaces
python3 chat.py                          # CLI chat
python3 interfaces/monitor_textual.py    # Monitor (separate terminal only!)

# Stop when done
./daemon_control.sh stop
```

---

**Note**: For detailed technical knowledge, see `memory/claude_code/project_knowledge.md`. This file focuses on essential development practices.