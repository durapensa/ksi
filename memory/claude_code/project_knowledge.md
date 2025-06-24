# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Current System Status
- **Architecture**: Multi-Socket Architecture with async completion flow - IMPLEMENTED (2025-06-24)
- **Claude Execution**: COMPLETION command via completion.sock replaces old SPAWN command
- **Agent Management**: MultiAgentOrchestrator + AgentController for efficient coordination
- **Commands**: All using JSON Protocol v2.0 with Pydantic validation
- **Message Bus**: Enhanced with targeted pub/sub for COMPLETION_RESULT events
- **Client Libraries**: New multi_socket_client.py supports full multi-socket architecture
- **Daemon Integration**: python-daemon package successfully integrated with ksi-daemon.py wrapper (2025-06-24)

## Critical Patterns & Gotchas

### Command Development
1. **Parameter Models**: All models centralized in `daemon/socket_protocol_models.py` - import from there, never duplicate
2. **Command Parameter Map**: All commands have entries in COMMAND_PARAMETER_MAP for validation
3. **Response Factory**: Use `SocketResponse.success()` and `SocketResponse.error()` 
   - Error responses don't support extra kwargs - put details in the error message string
4. **Expected Errors**: SUBSCRIBE without connection should error (this is correct behavior)

### Architecture Principles
- **Event-Driven Only**: No polling, timers, or wait loops - all communication via message bus
- **Socket Separation**: admin, agents, messaging, state, completion sockets for clean separation
- **Async Completions**: All LLM calls are async with event-based results via COMPLETION_RESULT
- **Targeted Delivery**: COMPLETION_RESULT events delivered directly to requesting client, not broadcast

### Multi-Socket Architecture (NEW - 2025-06-24)
1. **admin.sock**: System admin commands (HEALTH_CHECK, SHUTDOWN, etc.)
2. **agents.sock**: Agent lifecycle (REGISTER_AGENT, SPAWN_AGENT, etc.)
3. **messaging.sock**: Pub/sub events and agent communication
4. **state.sock**: Agent key-value state storage
5. **completion.sock**: Async LLM completion requests (replaces SPAWN)

### Completion Flow (Replaces SPAWN)
1. Client subscribes to COMPLETION_RESULT events (or COMPLETION_RESULT:client_id)
2. Client sends COMPLETION command with client_id to completion.sock
3. Daemon returns acknowledgment with request_id
4. Result delivered as COMPLETION_RESULT event to specific client
5. No polling, no blocking - pure event-driven async

## Key Files & Components

### Core System
- `daemon.py` - Main daemon with modular architecture
- `daemon/claude_process_v2.py` - Uses in-process agents (Option B)
- `claude_cli_provider.py` - LiteLLM provider for Claude CLI execution
- `daemon/agent_controller.py` - Individual agent lifecycle management
- `daemon/multi_agent_orchestrator.py` - Multi-agent coordination

### Command System
- `daemon/command_registry.py` - Self-registering command pattern
- `daemon/commands/` - Individual command handlers with `@command_handler` decorator
- `daemon/protocols/` - Protocol definitions organized by socket (NEW)
- `daemon/commands/completion.py` - COMPLETION command handler with async queue

### Client Libraries (NEW - 2025-06-24)
- `daemon/client/multi_socket_client.py` - Full multi-socket client with async completion support
- `daemon/client/utils.py` - Command builders and response handlers
- `daemon/enhanced_message_bus.py` - Enhanced message bus with targeted pub/sub
- `chat_simple.py` - Reference implementation using SimpleChatClient
- `interfaces/chat_textual.py` - Updated to use new architecture

### Development
- `tests/test_migrated_commands.py` - Test pattern for command validation
- `daemon_control.sh` - Use for start|stop|restart|status|health (not direct daemon.py)

## Current Architecture

### How It Works
1. Daemon receives commands via Unix socket
2. In-process AgentController handles Claude interactions via claude_cli_provider.py  
3. Progressive timeouts: 5min → 15min → 30min for long operations
4. All sessions logged to `claude_logs/<session-id>.jsonl`
5. Session continuity via `--resume sessionId`

### Multi-Agent System
- **Agent Registry**: REGISTER_AGENT, GET_AGENTS commands
- **Message Bus**: PUBLISH/SUBSCRIBE with event-driven communication
- **Shared State**: SET_SHARED/GET_SHARED with file persistence
- **Agent Profiles**: 15+ profiles in `agent_profiles/`
- **Dynamic Composition**: Agents select prompts via composition system

## Recent Fixes & Updates

### Python-daemon Integration (2025-06-24)
**Achievement**: Successfully integrated python-daemon package for production-grade Unix daemonization
**Problem**: Double PID file management conflict between python-daemon and internal core.py PID handling
**Root Cause**: 
1. python-daemon's DaemonContext doesn't preserve virtual environment after forking (creates clean environment by design)
2. Internal core.py was also writing PID files, creating race conditions
**Solution**:
1. **Removed internal PID management**: Disabled `_write_pid_file()` and `_cleanup_pid_file()` in core.py - let python-daemon handle it
2. **Fixed virtual environment**: Added `sys.path.insert(0, str(Path.cwd()))` in forked process instead of environment variable preservation
3. **Updated control scripts**: daemon_control.sh and com.ksi.daemon.plist now use ksi-daemon.py instead of deleted daemon.py
**Result**: All sockets working, proper Unix daemonization, no PID conflicts, daemon_control.sh fully functional

### Pydantic Migration Complete (2025-06-23)
**Achievement**: Complete consolidation of all parameter models to centralized location
**Changes**:
1. Moved all 13 duplicate local parameter models to `daemon/socket_protocol_models.py`
2. Added parameter models for 7 commands that didn't have them (HEALTH_CHECK, GET_PROCESSES, etc.)
3. Updated COMMAND_PARAMETER_MAP to include all commands
4. Updated all command handlers to import from centralized models
5. Removed all duplicate parameter model definitions
**Result**: Single source of truth for all Pydantic validation, eliminated duplication

## Previous Fixes

### Process List Issue (FIXED)
**Problem**: GET_PROCESSES returned 0 despite agents existing
**Causes**: 
1. @log_operation decorator wasn't async-aware (returned coroutine objects)
2. Client response parsing looked for `resp['processes']` instead of `resp['result']['processes']`
3. Daemon logging went to /dev/null (fixed daemon_control.sh)
**Solution**: Made decorator async-aware, fixed client parsing, logs now go to daemon_startup.log

### Connection Architecture (Previously Fixed)
**Pattern**: Separate connections for sending vs receiving messages
**Solution**: Main connection for receiving, temporary connections for commands

## Development Workflow

### Essential Commands
```bash
# Use daemon control script
./daemon_control.sh start|stop|restart|status|health

# Test commands
python3 tests/test_daemon_protocol.py
python3 debug_agent_disconnect.py
```

### Command Development Pattern
1. All parameter models are in `daemon/socket_protocol_models.py` - never duplicate
2. Create handler in `daemon/commands/` with `@command_handler` decorator and import models
3. Use `SocketResponse` factory methods for consistent responses
4. Add test to `tests/test_migrated_commands.py`

## File Organization Standards
- `tests/` - Test files
- `tools/` - Development utilities
- `logs/` - System logs
- `memory/` - Knowledge management
- `autonomous_experiments/` - Agent outputs

**IMPORTANT**: Don't create temporary .md files in project root (use TodoWrite instead)

---
*Essential knowledge for Claude Code development - see git history for detailed implementation timeline*