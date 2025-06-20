# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Architecture

### Core Components
- **daemon.py**: Minimal async daemon that spawns Claude processes and tracks sessionId
- **chat.py**: Simple interface for chatting with Claude
- **claude_modules/**: Python modules for extending daemon functionality

### How It Works
1. Daemon receives commands via Unix socket
2. Spawns: `claude --model sonnet --print --output-format json --allowedTools "..." --resume sessionId`
3. Logs all sessions to `claude_logs/<session-id>.jsonl` in JSONL format
4. Uses `--resume sessionId` for conversation continuity

## File Organization (Claude Code Standards)

### Directory Structure
```
ksi/
├── daemon.py, chat.py          # Core system files
├── claude_modules/             # Python extensions
├── autonomous_experiments/     # Autonomous agent outputs
├── cognitive_data/             # Analysis input data
├── memory/                     # Knowledge management system
├── tests/                      # Test files
├── tools/                      # Development utilities
└── logs/                       # System logs
```

### Development Conventions
- **Tests**: Place in `tests/` directory
- **Tools**: Place in `tools/` directory  
- **Logs**: System logs go to `logs/`
- **Scripts**: Temporary scripts should be cleaned up or organized
- **Documentation**: Keep README.md focused on project basics

## Build/Test Commands
```bash
# Start system
uv run python daemon.py
uv run python chat.py

# Run tests  
uv run python tests/test_daemon_protocol.py

# Monitor system
./tools/monitor_autonomous.py
```

## Key Development Principles
- Keep daemon minimal and focused
- Organize files by purpose and audience
- Clean up temporary files promptly
- Document significant changes in appropriate memory stores

## Integration Points
- **Memory system**: Check `memory/` for audience-specific knowledge
- **Autonomous experiments**: Results in `autonomous_experiments/`
- **Cognitive data**: Analysis inputs in `cognitive_data/`

---
*For Claude Code interactive development sessions*