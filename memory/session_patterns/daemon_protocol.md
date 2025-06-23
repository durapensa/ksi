# Daemon Protocol Knowledge for Spawned Claude Sessions

**Note**: This document describes the legacy protocol. For current protocol, see `memory/claude_code/project_knowledge.md`

## Socket Communication Format (LEGACY)

The daemon originally used these formats:
- **Fresh spawn**: `SPAWN::prompt_text` (double colon for empty sessionId)
- **Resume session**: `SPAWN:sessionId:prompt_text`
- **Module reload**: JSON command `{"command": "RELOAD_MODULE", "version": "2.0", "parameters": {"module_name": "handler"}}`
- **Shutdown**: `SHUTDOWN`

## Current Protocol (as of 2025-06-21)
The daemon now uses a unified SPAWN command:
- **Format**: `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>`
- **Example**: `SPAWN:sync:claude::sonnet::Hello world`
- Legacy formats are auto-detected for backward compatibility
- Use `GET_COMMANDS` to discover all available commands dynamically

## AutonomousResearcher Usage (LEGACY)
- Originally used `spawn_independent_claude(experiment_name, prompt, resume_session=None)`
- Modern agents should use the unified SPAWN command or SPAWN_AGENT for profile-based spawning
- Prompts must still be single-line strings (no multiline strings with \n)

## Debugging & Error Handling
- daemon.py captures stderr and adds to output JSON
- stderr appears as `output['stderr']` field when present  
- AutonomousResearcher logs stderr for debugging spawned agents
- Check `sockets/claude_last_output.json` for latest daemon response
- Session logs in `claude_logs/<session-id>.jsonl` format

## Common Issues
- Daemon uses text commands, NOT JSON - sending JSON will be ignored
- Multiline prompt strings break the daemon protocol
- Empty sessionId should be `::` not `:None:` in spawn commands
- Socket path is `sockets/claude_daemon.sock` (not `sockets/daemon.sock`)
- Commands must end with newline character

## Available Tools
When spawned by the daemon, you have access to:
- Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## Session Management
- All sessions logged to `claude_logs/<session-id>.jsonl`
- Latest session symlinked at `claude_logs/latest.jsonl`
- Session continuity via `--resume sessionId`
- Session tracking in daemon for module callbacks

## Key Points
- The daemon is intentionally minimal - it's just plumbing
- You decide how to track sessions, store prompts, analyze outputs
- You can spawn new Claude sessions anytime
- Everything is under your control

---
*For Claude instances spawned via daemon protocol*