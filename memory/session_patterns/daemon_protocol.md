# Daemon Protocol Knowledge for Spawned Claude Sessions

## Socket Communication Format

The daemon expects text-based commands via Unix socket (NOT JSON):
- **Fresh spawn**: `SPAWN::prompt_text` (double colon for empty sessionId)
- **Resume session**: `SPAWN:sessionId:prompt_text`
- **Module reload**: `RELOAD:module_name`
- **Shutdown**: `SHUTDOWN`

## AutonomousResearcher Usage
- Use `spawn_independent_claude(experiment_name, prompt, resume_session=None)`
- Prompts must be single-line strings (no multiline strings with \n)
- Fresh sessions use format: `SPAWN::prompt` (empty sessionId)
- Resume sessions use format: `SPAWN:sessionId:prompt`

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