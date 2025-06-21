# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Architecture

### Core Components
- **daemon.py**: Modular async daemon with multi-agent coordination capabilities
- **daemon/**: Modular daemon architecture (core, state_manager, agent_manager, etc.)
- **chat.py**: Simple interface for chatting with Claude
- **claude_modules/**: Python modules for extending daemon functionality
- **prompts/**: Prompt composition system for modular prompt building

### How It Works
1. Daemon receives commands via Unix socket
2. Spawns: `claude --model sonnet --print --output-format json --allowedTools "..." --resume sessionId`
3. Logs all sessions to `claude_logs/<session-id>.jsonl` in JSONL format
4. Uses `--resume sessionId` for conversation continuity

### Daemon Command System
**Unified SPAWN Command** (as of 2025-06-21):
- Format: `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>`
- Examples:
  - `SPAWN:sync:claude::sonnet::Hello world`
  - `SPAWN:async:claude:session123:sonnet:agent1:Complex task`
- Legacy formats auto-detected for backward compatibility

**Command Organization**:
- Total: ~20 commands organized into functional groups
- Groups: Process Spawning, Agent Management, Communication & Events, State Management, System Management
- Aliases available: `S:` → `SPAWN:`, `R:` → `RELOAD:`, `SA:` → `SPAWN_AGENT:`, etc.
- Use `GET_COMMANDS` to discover all available commands dynamically

**GET_COMMANDS Response** (enhanced 2025-06-21):
```json
{
  "commands": { /* flat list of all commands */ },
  "grouped_commands": { /* commands organized by functional area */ },
  "total_commands": 20,
  "groups": ["Process Spawning", "Agent Management", ...]
}
```

### Prompt Composition System
**Architecture**:
- **composer.py**: Composition engine using simple string replacement
- **components/**: Reusable markdown templates with `{{variable}}` placeholders
- **compositions/**: YAML recipes defining which components to include

**How Claude Agents Use It**:
1. Call `GET_COMMANDS` to get available daemon commands
2. Pass commands as `daemon_commands` context to prompt composer
3. Composer replaces `{{daemon_commands}}` with stringified JSON

**Known Limitation**: 
- Template engine only does simple string replacement
- Handlebars syntax (`{{#each}}`) in components doesn't work
- Despite this, Claude agents still receive command info as JSON string

### Multi-Agent Infrastructure Status
**Implementation**: Core components operational with recent architectural improvements
- **Agent Registry**: `REGISTER_AGENT`, `GET_AGENTS` commands available
- **Inter-Agent Communication**: Message bus system with event-driven architecture
  - `PUBLISH:from_agent:event_type:json_payload` for sending messages
  - `SUBSCRIBE:agent_id:event_type1,event_type2` for receiving messages
  - `AGENT_CONNECTION:connect|disconnect:agent_id` (new unified command)
- **Shared State Store**: `SET_SHARED`/`GET_SHARED` with file persistence in `shared_state/`
- **Agent Templates**: 15+ profiles in `agent_profiles/` including orchestrator, researcher, coder, analyst, debater, teacher, etc.
- **Task Distribution**: `ROUTE_TASK` with capability-based routing
- **Process Spawning**: `SPAWN_AGENT:profile:task:context:agent_id` for profile-based agent creation

**Key Architectural Principles**:
- **Event-Driven**: No polling, timers, or wait loops - all communication via message bus events
- **SPAWN_AGENT vs SPAWN**: SPAWN_AGENT provides profile templating and auto-registration, justifying its separate existence
- **Command Consolidation**: Recent cleanup removed legacy commands and added aliases

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
**Root Cause**: agent_process.py (formerly claude_node.py) was using the same connection for:
1. Receiving messages (reader connection from CONNECT_AGENT)
2. Sending commands (PUBLISH, etc.)

This caused the daemon to close the connection when it received a command on a message-receiving connection.

**Solution**: Modified agent_process.py to use separate connections:
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

### Session 2025-06-21: Major Architecture Improvements

**Command System Unified**:
- Implemented unified SPAWN command: `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>`
- Removed all SPAWN_ASYNC usage - replaced with SPAWN:async format
- Consolidated CONNECT_AGENT/DISCONNECT_AGENT into AGENT_CONNECTION:connect|disconnect:agent_id
- Added command aliases: S: → SPAWN:, R: → RELOAD:, SA: → SPAWN_AGENT:, etc.
- Enhanced GET_COMMANDS with functional grouping and alias metadata

**SPAWN_AGENT Fixed for Multi-Agent Support**:
- Problem: Was spawning raw Claude CLI processes that couldn't use message bus
- Solution: Now spawns agent_process.py processes via spawn_agent_process_async()
- Agents can now receive DIRECT_MESSAGE events and participate in conversations
- Cleaned up confusing node/agent terminology throughout

**All Daemon Infrastructure Issues Resolved**:
- GET_AGENTS, SET_SHARED, GET_SHARED all working properly
- Directory creation on startup fixed
- Command handlers executing correctly
- Proper error responses for all commands

**Remaining Work**:
- Fix [END] signal handling (agents don't terminate properly)
- Renamed claude_node.py to agent_process.py (completed 2025-06-21)
- Complete terminology cleanup across codebase

---
*For Claude Code interactive development sessions*