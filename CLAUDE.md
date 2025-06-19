# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Architecture

### Core Components
- **daemon.py**: Minimal async daemon that spawns Claude processes and tracks sessionId
- **chat.py**: Simple interface for chatting with Claude
- **claude_modules/**: Optional directory where you can write Python modules

### How It Works
1. Daemon receives commands via Unix socket
2. Spawns: `echo "prompt" | claude --model sonnet --print --output-format json --allowedTools "..." | tee sockets/claude_last_output.json`
3. Logs all sessions to `claude_logs/<session-id>.jsonl` in JSONL format
4. Uses `--resume sessionId` for conversation continuity

## Available Tools in Claude
When spawned by the daemon, you have access to:
- Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## Extending the System

You can extend this system in any way you prefer:

### Option 1: Using Your Tools
- Use `Edit` to modify daemon.py directly
- Use `Write` to create state files, databases, etc.
- Use `Bash` to run any commands you need

### Option 2: Writing Python Modules
- Create `claude_modules/handler.py` with a `handle_output(output, daemon)` function
- The daemon will automatically load and call it
- You can reload modules by sending "RELOAD:handler" to the daemon socket

### Option 3: Analyze Your Own Logs
- All sessions are in `claude_logs/<session-id>.jsonl`
- Use `Read` tool to analyze conversation patterns, costs, performance
- Latest session is symlinked at `claude_logs/latest.jsonl`

### Option 3: Both
- Combine tools and modules as needed
- You have complete flexibility

## Key Points
- The daemon is intentionally minimal - it's just plumbing
- You decide how to track sessions, store prompts, analyze outputs
- You can spawn new Claude sessions anytime
- Everything is under your control

## Running the System
```bash
# Start chatting (auto-starts daemon)
python3 chat.py

# Or start daemon directly
python3 daemon.py
```