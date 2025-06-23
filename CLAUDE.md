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

### Daemon Refactoring (2025-06-23)
**Major refactoring completed to improve code quality**:
- **Pydantic models** (`daemon/models.py`): Type-safe command/response validation
- **Base manager pattern** (`daemon/manager_utils.py`): Eliminates code duplication
- **Strategy pattern** (`daemon/utils_refactored.py`): Replaces 50+ line if/elif chains
- **Command registry** (`daemon/command_registry.py`): Self-registering command pattern
- **File operations** (`daemon/file_operations.py`): Centralized I/O with retry logic
- **Migration guide** (`daemon/migration_guide.md`): Gradual adoption path
- **~35% code reduction** with better patterns and type safety

When working on daemon code:
- Prefer Pydantic models over manual validation
- Use decorators from manager_utils for error handling
- Add new commands via @command_handler decorator
- Use FileOperations for all file I/O
- See `daemon/REFACTORING_SUMMARY.md` for full details

## Architecture

### Core Components
- **daemon.py**: Modular async daemon with multi-agent coordination capabilities
- **chat.py**: Simple interface for chatting with Claude
- **daemon/**: Modular daemon architecture (core, state_manager, agent_manager, etc.)

### How It Works
1. Daemon receives commands via Unix socket
2. Spawns: `claude --model sonnet --print --output-format json --allowedTools "..." --resume sessionId`
3. Logs all sessions to `claude_logs/<session-id>.jsonl` in JSONL format
4. Uses `--resume sessionId` for conversation continuity

### Multi-Agent Capabilities (Implemented - Requires Testing)
- **Agent coordination**: Register agents, route tasks, manage state
- **Inter-agent messaging**: Communication between Claude instances
- **Shared state**: Persistent coordination across agents
- **Agent profiles**: Pre-configured specialist roles

### Multi-Claude Orchestrator (NEW)
- **Peer-to-peer conversations**: Multiple Claudes conversing autonomously
- **Event-driven architecture**: No polling, efficient async design
- **Rich conversation modes**: Debate, collaboration, teaching, brainstorming
- **Real-time TUI monitor**: Observe conversations, tool calls, metrics
- **Persistent Claude nodes**: Maintain context across messages

## Design Principles

### Event-Driven Architecture
**CRITICAL**: This system follows strict event-driven design principles:
- **No polling**: Never poll for state changes or results. Use message bus events instead
- **No timers**: Avoid setTimeout, sleep loops, or periodic checks
- **No wait loops**: Don't spin waiting for conditions. Subscribe to events
- **Blocking is OK when necessary**: Acceptable only for unavoidable operations (e.g., waiting for Claude CLI responses)
- **Push, don't pull**: All communication via events pushed through the message bus
- **Async by default**: Use SPAWN:async:claude for non-blocking Claude invocations

Examples of what NOT to do:
```python
# BAD: Polling for result
while not result_ready:
    await asyncio.sleep(1)
    result = check_if_ready()

# BAD: Timer-based heartbeats
async def heartbeat():
    while True:
        send_ping()
        await asyncio.sleep(30)
```

Instead, use event subscriptions and callbacks:
```python
# GOOD: Event-driven completion
await subscribe(['PROCESS_COMPLETE'])
process_id = await spawn_async(prompt)
# Handler will be called when ready
```

Quick start:
```bash
# Test the system
python test_multi_claude.py

# Start a debate
python interfaces/orchestrate.py "AI ethics" --mode debate

# Monitor in another terminal
python monitor_tui.py
```

#### Monitor TUI Troubleshooting
If the monitor shows no data:
1. The monitor must CONNECT_AGENT before SUBSCRIBE (fixed in latest version)
2. Start in debug mode ('d' key) to see raw message flow
3. Check Event Stream panel for connection/subscription status
4. Ensure daemon is running and interfaces/orchestrate.py is actively sending messages

#### Multi-Claude Conversation Troubleshooting
If nodes disconnect with "Broken pipe" errors:
- This was fixed on 2025-06-21 - agent_process.py (formerly claude_node.py) now uses separate connections for commands
- Kill all existing processes and restart with fresh daemon and interfaces/orchestrate.py
- Check logs/daemon.log for connection errors
- Nodes should now maintain stable connections and continue conversing

## Available Tools
When working with the system, you have access to:
- Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## CRITICAL TUI WARNING
**NEVER RUN chat_textual.py**: This script corrupts Claude Code's TUI and forces session restart. Use `chat.py` instead for command-line interaction with the daemon.

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

## Key Points for Claude Code
- **FIRST**: Always read `memory/claude_code/project_knowledge.md` at session start
- Keep the daemon minimal and focused
- Organize files by purpose and audience
- Check the memory system for detailed knowledge
- The daemon is intentionally minimal - it's just plumbing
- **IMPORTANT**: Always update your todo list when receiving updated instructions from the user
- **WORKFLOW**: Don't exit early with summaries - continue working systematically through tasks

## Running the System
```bash
# Start chatting (auto-starts daemon)
python3 chat.py

# Or start daemon directly
python3 daemon.py
```

---

**Note**: For detailed knowledge about daemon protocols, autonomous agents, or system engineering patterns, see the `memory/` system. This file focuses on what Claude Code needs for basic development work.