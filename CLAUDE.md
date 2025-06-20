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

## Daemon Protocol & Quirks

### Socket Communication Format
The daemon expects text-based commands via Unix socket (NOT JSON):
- **Fresh spawn**: `SPAWN::prompt_text` (double colon for empty sessionId)
- **Resume session**: `SPAWN:sessionId:prompt_text`
- **Module reload**: `RELOAD:module_name`
- **Shutdown**: `SHUTDOWN`

### AutonomousResearcher Usage
- Use `spawn_independent_claude(experiment_name, prompt, resume_session=None)`
- Prompts must be single-line strings (no multiline strings with \n)
- Fresh sessions use format: `SPAWN::prompt` (empty sessionId)
- Resume sessions use format: `SPAWN:sessionId:prompt`

### Debugging & Error Handling
- daemon.py captures stderr and adds to output JSON
- stderr appears as `output['stderr']` field when present  
- AutonomousResearcher logs stderr for debugging spawned agents
- Check `sockets/claude_last_output.json` for latest daemon response
- Session logs in `claude_logs/<session-id>.jsonl` format

### Common Issues
- Daemon uses text commands, NOT JSON - sending JSON will be ignored
- Multiline prompt strings break the daemon protocol
- Empty sessionId should be `::` not `:None:` in spawn commands
- Socket path is `sockets/claude_daemon.sock` (not `sockets/daemon.sock`)
- Commands must end with newline character

## Autonomous Agent Workspace System

### Isolated Workspaces
- **Each experiment gets isolated workspace**: `autonomous_experiments/workspaces/{experiment_name}/`
- **Agents work only in their workspace**: Prevents contamination of ksi system files
- **Scripts and temp files stay isolated**: Easy cleanup and debugging
- **Final outputs go to parent directory**: `autonomous_experiments/{report}.md`

### Workspace Structure
```
autonomous_experiments/workspaces/
├── entropy_analysis/          # Isolated workspace per experiment
├── concept_graph_analysis/    
├── attractor_detection/       
├── cost_efficiency_analysis/  
├── meta_analysis/            
└── shared/                   # Read-only shared utilities
```

### Agent Instructions Pattern
Always include in autonomous agent prompts:
- `WORKSPACE: autonomous_experiments/workspaces/{experiment_name}/`
- `Create all analysis scripts in your workspace`
- `Use relative paths: ../../../cognitive_data/ for input data`
- `Final output: ../../{report_name}.md or .json`

### Benefits
- **No system contamination**: Agent scripts don't mix with ksi core files
- **Parallel execution**: Multiple agents can work without conflicts
- **Easy cleanup**: Delete entire workspace when experiment done
- **Organized debugging**: All experiment files in one place

## Key Points
- The daemon is intentionally minimal - it's just plumbing
- You decide how to track sessions, store prompts, analyze outputs
- You can spawn new Claude sessions anytime
- Everything is under your control
- **CRITICAL**: Document daemon quirks immediately when discovered
- **CRITICAL**: Keep agents in isolated workspaces to prevent system contamination

## Running the System
```bash
# Start chatting (auto-starts daemon)
uv run python chat.py

# Or start daemon directly
uv run python daemon.py
```