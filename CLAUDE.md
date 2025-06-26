# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Start Instructions

**MANDATORY FIRST STEP**: At the beginning of every session, read:
1. **`memory/claude_code/project_knowledge.md`** - Contains critical project-specific knowledge, architecture decisions, and recent changes
2. **This file (CLAUDE.md)** - For current development guidelines and practices

## Memory System Integration

**PROJECT KNOWLEDGE STRUCTURE**:
- **`memory/README.md`** - Overview of the memory system organization
- **`memory/claude_code/project_knowledge.md`** - **[READ EVERY SESSION]** Technical details, issues, fixes, and architectural decisions
- **`memory/human/`** - Human audience documentation (if you need background context)

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Quick Start
```bash
# Start system
python3 daemon.py
python3 chat.py

# Run tests  
python3 tests/test_daemon_protocol.py

# Monitor system
./tools/monitor_autonomous.py
```

## File Organization Standards

### Directory Structure
- `tests/` - Test files
- `tools/` - Development utilities  
- `logs/` - System logs
- `memory/` - Knowledge management system
- `autonomous_experiments/` - Autonomous agent outputs
- `cognitive_data/` - Analysis input data

### Development Conventions
- Place test files in `tests/` directory
- Place development tools in `tools/` directory
- Clean up temporary files promptly
- Organize files by purpose and audience

### Documentation Practices
**IMPORTANT**: Do not create temporary markdown files in the project root
- **Use TodoWrite tool** for tracking issues, tasks, and findings
- **Update existing docs** (CLAUDE.md, memory/, README.md) for permanent knowledge
- **Avoid creating files like**: ISSUE.md, TODO.md, FINDINGS.md, STATUS.md
- **If you must create a doc**: Clean it up in the same session
- **Exception**: Only create .md files when explicitly requested by user

### File Deletion Policy
**CRITICAL**: Always confirm with user before deleting files, especially:
- `claude_logs/` session files (conversation history)
- Any existing data files or user-generated content
- Configuration files or persistent state
**Exception**: Only delete files without confirmation if user explicitly requests deletion

## Development Environment

### Virtual Environment
**IMPORTANT**: This project uses a virtual environment at `.venv/`
- **Always activate before running**: `source .venv/bin/activate`
- **Never create a new venv** - use the existing `.venv/`
- **All dependencies are in requirements.txt**: PyYAML, textual, psutil, pydantic, structlog, tenacity

### Running Commands
```bash
# Always activate venv first
source .venv/bin/activate
python3 test_composition_system.py
python3 hello_goodbye_test.py
```

### Daemon Management
**CRITICAL**: ALWAYS use `./daemon_control.sh` for daemon operations. NEVER start the daemon directly with `python3 ksi-daemon.py`.

**Commands**:
```bash
# Start daemon (required before running tests that use daemon)
./daemon_control.sh start

# Check status
./daemon_control.sh status

# Check health (shows agents and processes)
./daemon_control.sh health

# Restart daemon
./daemon_control.sh restart

# Stop daemon (graceful shutdown)
./daemon_control.sh stop
```

**Why daemon_control.sh**:
- Handles proper socket cleanup
- Manages PID files correctly
- Ensures graceful shutdown via SHUTDOWN command
- Provides consistent logging
- Prevents zombie processes
- Sets up correct environment

**Example workflow**:
```bash
# Start daemon before testing
./daemon_control.sh start

# Run tests that need daemon
python3 tests/test_completion_command.py

# Check daemon health
./daemon_control.sh health

# Stop when done
./daemon_control.sh stop
```

## Technical Details

**See `memory/claude_code/project_knowledge.md` for:**
- Architecture details and component descriptions
- Plugin system documentation
- Testing procedures
- Recent changes and fixes
- Event namespaces and protocols

## Design Principles

### Event-Driven Architecture
- **No polling, timers, or wait loops** - Use events and callbacks
- **Push, don't pull** - All communication via message bus
- **Async by default** - Non-blocking operations

See `memory/claude_code/project_knowledge.md` for detailed patterns and examples.

## Available Tools
When working with the system, you have access to:
- Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## ⚠️ CRITICAL TUI WARNING ⚠️
**ABSOLUTELY NEVER RUN THESE INTERACTIVE PROGRAMS FROM CLAUDE CODE - THEY CORRUPT THE TUI AND FORCE SESSION RESTART:**

### ❌ FORBIDDEN IN CLAUDE CODE:
- **`python3 interfaces/chat_textual.py`** - Corrupts Claude Code interface
- **`python3 interfaces/monitor_tui.py`** - Corrupts Claude Code interface  
- **ANY interactive TUI/terminal program** - Will break Claude Code session

### ✅ SAFE ALTERNATIVES:
- **chat_textual.py**: Use `chat.py` instead for command-line interaction
- **monitor_tui.py**: Test in separate terminal OR use daemon health/status commands
- **Testing TUI**: Add `--test-connection` flag instead of running full interface

**IMPORTANT**: These programs use terminal control sequences that conflict with Claude Code's TUI, causing interface corruption and requiring session restart.

## Extending the System

### Option 1: Using Your Tools
- Use `Edit` to modify daemon.py directly
- Use `Write` to create state files, databases, etc.
- Use `Bash` to run any commands you need

### Option 2: Writing Python Modules
- Create `claude_modules/handler.py` with a `handle_output(output, daemon)` function
- The daemon will automatically load and call it
- You can reload modules by sending RELOAD_MODULE command with module_name parameter to the daemon socket

### Option 3: Analyze Logs
- All sessions are in `claude_logs/<session-id>.jsonl`
- Use `Read` tool to analyze conversation patterns, costs, performance
- Latest session is symlinked at `claude_logs/latest.jsonl`

## Development Philosophy
- **Fast-Moving Research Software**: KSI is experimental research software, not a production system
- **No Backward Compatibility**: We prioritize rapid iteration and better design over compatibility
- **Breaking Changes Welcome**: Feel free to refactor aggressively for cleaner architecture
- **Fail Fast**: If something breaks, that's valuable feedback - don't hide failures

## Key Points for Claude Code
- **FIRST**: Always read `memory/claude_code/project_knowledge.md` at session start
- Keep the daemon minimal and focused
- Organize files by purpose and audience
- Check the memory system for detailed knowledge
- The daemon is intentionally minimal - it's just plumbing
- **IMPORTANT**: Always update your todo list when receiving updated instructions from the user
- **WORKFLOW**: Don't exit early with summaries - continue working systematically through tasks
- **CRITICAL**: DO NOT claim success when things are failing. If sockets don't work, processes die, or commands fail - that is NOT success. Be honest about actual status. Don't waste tokens on false celebration.

## Library Architecture
- **ksi_client/**: For agents participating in the system (chat, coordination)
- **ksi_admin/**: For monitoring and controlling the system (observe, manage)
- **Independent**: No cross-dependencies between libraries

## Future Architecture Vision
- **Dockerized Nodes**: Each KSI instance will be containerized with declarative configuration
- **HTTP/gRPC Transport**: Supplement Unix sockets for inter-node communication
- **Kubernetes-like Orchestration**: Declarative agent deployment across multiple nodes
- **Agent Federation**: Multiple KSI clusters communicating and sharing agents
- **Composable Architecture**: Mix and match components like prompts and agent profiles

## Running the System
```bash
# Start daemon using control script
./daemon_control.sh start

# Start chatting (requires daemon to be running)
python3 chat.py

# ⚠️ NEVER RUN FROM CLAUDE CODE - Use separate terminal only!
# python3 interfaces/monitor_tui.py

# Stop daemon when done
./daemon_control.sh stop
```

---

**Note**: For detailed knowledge about daemon protocols, autonomous agents, or system engineering patterns, see the `memory/` system. This file focuses on what Claude Code needs for basic development work.