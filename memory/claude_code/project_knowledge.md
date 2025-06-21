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

### Multi-Agent Infrastructure Status
**Implementation**: Foundational components implemented but require testing
- **Agent Registry**: `REGISTER_AGENT`, `GET_AGENTS` commands available
- **Inter-Agent Communication**: `SEND_MESSAGE` with logging to `claude_logs/inter_agent_messages.jsonl`
- **Shared State Store**: `SET_SHARED`/`GET_SHARED` with file persistence in `shared_state/`
- **Agent Templates**: 4 profiles in `agent_profiles/` (orchestrator, researcher, coder, analyst)
- **Task Distribution**: `ROUTE_TASK` with capability-based routing

**Status**: Ready for multi-agent testing but not yet validated in production

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
python3 daemon.py
python3 chat.py

# Run tests  
python3 tests/test_daemon_protocol.py

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

## Known Issues & Fixes

### Monitor TUI Connection Issue (FIXED 2025-06-21)
**Problem**: Monitor would connect but display no data
**Root Cause**: The message bus requires agents to:
1. First call `CONNECT_AGENT:agent_id` to register the connection
2. Then call `SUBSCRIBE:agent_id:event_types` to subscribe to events

**Solution**: Modified monitor_tui.py to:
- Send CONNECT_AGENT command first
- Use separate connection for SUBSCRIBE command  
- Keep main connection exclusively for receiving messages
- Enable debug mode by default for troubleshooting

### Claude Node Connection Architecture Issue (FIXED 2025-06-21)
**Problem**: Claude nodes would connect, send 1-2 messages, then disconnect with "Broken pipe" errors
**Root Cause**: claude_node.py was using the same connection for:
1. Receiving messages (reader connection from CONNECT_AGENT)
2. Sending commands (PUBLISH, etc.)

This caused the daemon to close the connection when it received a command on a message-receiving connection.

**Solution**: Modified claude_node.py to use separate connections:
- Main connection (`self.reader`/`self.writer`) - exclusively for receiving messages
- Temporary connections for each command send operation:
  - `send_message()` - opens new connection for PUBLISH:DIRECT_MESSAGE
  - `start_conversation()` - opens new connection for PUBLISH:CONVERSATION_INVITE
  - `_subscribe_to_events()` - opens new connection for SUBSCRIBE command

**Additional Fixes**:
- Added allowedTools parameter to Claude CLI command (comma-separated list)
- Fixed Claude output parsing for new CLI format (`type: result` with `result` field)
- Enhanced error handling for broken connections (ConnectionResetError, BrokenPipeError)
- Added detailed logging for Claude CLI failures

---
*For Claude Code interactive development sessions*