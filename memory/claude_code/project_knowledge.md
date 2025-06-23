# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Current System Status
- **Architecture**: In-Process Agent Controllers (Option B) with LiteLLM integration - FULLY IMPLEMENTED
- **Claude Execution**: claude_cli_provider.py is the single source of truth for all Claude calls
- **Agent Management**: MultiAgentOrchestrator + AgentController for efficient coordination
- **Commands**: 31/31 migrated to command registry pattern with fully centralized Pydantic validation
- **Message Bus**: Event-driven architecture, no polling/timers

## Critical Patterns & Gotchas

### Command Development
1. **Parameter Models**: All models centralized in `daemon/socket_protocol_models.py` - import from there, never duplicate
2. **Command Parameter Map**: All 31 commands have entries in COMMAND_PARAMETER_MAP for validation
3. **Response Factory**: Use `SocketResponse.success()` and `SocketResponse.error()` 
   - Error responses don't support extra kwargs - put details in the error message string
4. **Expected Errors**: SUBSCRIBE without connection should error (this is correct behavior)

### Architecture Principles
- **Event-Driven Only**: No polling, timers, or wait loops - all communication via message bus
- **Single Source of Truth**: claude_cli_provider.py for all Claude execution
- **In-Process Agents**: Use AgentController/MultiAgentOrchestrator, not subprocess spawning

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
- `daemon/socket_protocol_models.py` - Centralized Pydantic parameter models (COMMAND_PARAMETER_MAP)

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

## Recent Fixes & Updates (2025-06-23)

### Pydantic Migration Complete (2025-06-23)
**Achievement**: Complete consolidation of all parameter models to centralized location
**Changes**:
1. Moved all 13 duplicate local parameter models to `daemon/socket_protocol_models.py`
2. Added parameter models for 7 commands that didn't have them (HEALTH_CHECK, GET_PROCESSES, etc.)
3. Updated COMMAND_PARAMETER_MAP to include all 31 commands
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