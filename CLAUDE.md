# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Memory System Integration

**IMPORTANT**: This project uses a structured memory system. For comprehensive knowledge:

1. **Read the memory system**: `memory/README.md` (start here)
2. **Claude Code specific knowledge**: `memory/claude_code/project_knowledge.md`
3. **Return here** for basic project information

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Quick Start
```bash
# Start system
uv run python daemon.py
uv run python chat.py

# Run tests  
uv run python tests/test_daemon_protocol.py

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

### File Deletion Policy
**CRITICAL**: Always confirm with user before deleting files, especially:
- `claude_logs/` session files (conversation history)
- Any existing data files or user-generated content
- Configuration files or persistent state
**Exception**: Only delete files without confirmation if user explicitly requests deletion

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

Quick start:
```bash
# Test the system
python test_multi_claude.py

# Start a debate
python orchestrate.py "AI ethics" --mode debate

# Monitor in another terminal
python monitor_tui.py
```

## Available Tools
When working with the system, you have access to:
- Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## Extending the System

### Option 1: Using Your Tools
- Use `Edit` to modify daemon.py directly
- Use `Write` to create state files, databases, etc.
- Use `Bash` to run any commands you need

### Option 2: Writing Python Modules
- Create `claude_modules/handler.py` with a `handle_output(output, daemon)` function
- The daemon will automatically load and call it
- You can reload modules by sending "RELOAD:handler" to the daemon socket

### Option 3: Analyze Logs
- All sessions are in `claude_logs/<session-id>.jsonl`
- Use `Read` tool to analyze conversation patterns, costs, performance
- Latest session is symlinked at `claude_logs/latest.jsonl`

## Key Points for Claude Code
- Keep the daemon minimal and focused
- Organize files by purpose and audience
- Check the memory system for detailed knowledge
- The daemon is intentionally minimal - it's just plumbing

## Running the System
```bash
# Start chatting (auto-starts daemon)
uv run python chat.py

# Or start daemon directly
uv run python daemon.py
```

---

**Note**: For detailed knowledge about daemon protocols, autonomous agents, or system engineering patterns, see the `memory/` system. This file focuses on what Claude Code needs for basic development work.