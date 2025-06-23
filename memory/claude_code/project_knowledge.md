# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## Current System Status
- **Architecture**: In-Process Agent Controllers (Option B) with LiteLLM integration - FULLY IMPLEMENTED
- **Claude Execution**: claude_cli_provider.py is the single source of truth for all Claude calls
- **Agent Management**: MultiAgentOrchestrator + AgentController for efficient coordination
- **Commands**: 29/29 migrated to command registry pattern with Pydantic validation
- **Message Bus**: Event-driven architecture, no polling/timers

## Critical Patterns & Gotchas

### Command Development
1. **Parameter Models**: Never duplicate models between `daemon/models.py` and command handlers
2. **Response Factory**: Use `ResponseFactory.success()` and `ResponseFactory.error()` 
   - Error responses don't support extra kwargs - put details in the error message string
3. **Expected Errors**: SUBSCRIBE without connection should error (this is correct behavior)

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
- `daemon/models.py` - Pydantic parameter models (check COMMAND_PARAMETER_MAP)

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

## Recent Fixes (2025-06-23)

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

### Command Migration Pattern
1. Check `daemon/models.py` for existing parameter models
2. Create handler in `daemon/commands/` with `@command_handler` decorator
3. Use `ResponseFactory` for consistent responses
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