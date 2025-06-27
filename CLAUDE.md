# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

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

## Critical Warnings
⚠️ **NEVER run TUI scripts** without `--test-connection` flag:
- `interfaces/chat_textual.py`
- `interfaces/monitor_tui.py`
- `interfaces/monitor_textual.py`

## Quick Reference
```bash
source .venv/bin/activate          # Always first
./daemon_control.sh start          # Start daemon
./daemon_control.sh status         # Check status
./daemon_control.sh stop           # Stop daemon

# Common operations
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock
echo '{"event": "conversation:active", "data": {}}' | nc -U var/run/daemon.sock
```

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

---
**Technical Details**: See `memory/claude_code/project_knowledge.md`