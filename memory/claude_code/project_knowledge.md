# KSI Technical Knowledge

Essential technical reference for KSI (Kubernetes-Style Infrastructure) - a resilient daemon system for orchestrating autonomous AI agents with production-grade reliability.

**Core Philosophy**: Pure event-based architecture with coordinated shutdown, automatic checkpoint/restore, and resilient error handling.

## System Architecture

### Event-Driven Core
- **Event Router**: Central message broker - all inter-module communication via events
- **Module System**: Self-registering handlers via `@event_handler` decorators
- **Protocol**: Unix socket with newline-delimited JSON (NDJSON)
- **REST Patterns**: Single response = object, multiple = array
- **No Cross-Module Imports**: Modules communicate only through events

### Directory Structure
```
ksi/
├── ksi_daemon/          # Core daemon modules
│   ├── core/           # Infrastructure (state, health, discovery)
│   ├── transport/      # Socket transport layer
│   ├── completion/     # Completion orchestration
│   ├── agent/          # Agent lifecycle
│   └── plugins/        # Plugin system (pluggy-based)
├── ksi_client/         # Python client library
├── ksi_common/         # Shared utilities and config
├── var/                # Runtime data
│   ├── run/           # Socket and PID file
│   ├── logs/          # All system logs
│   ├── db/            # SQLite databases
│   └── lib/           # Configurations and schemas
└── memory/             # Knowledge management
```

## Core APIs

### Event Handler Pattern
```python
from ksi_daemon.event_system import event_handler

@event_handler("my:event")
async def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "success"}
```

### Client Usage
```python
from ksi_client import EventClient

async with EventClient() as client:
    # Single response expected
    result = await client.send_single("state:get", {"key": "config"})
    
    # Multiple responses
    all_health = await client.send_all("system:health", {})
```

### Event Namespaces
- **system**: health, shutdown, discover, help, ready
- **completion**: async, status, cancel, result
- **agent**: spawn, terminate, list, info
- **state**: entity:*, relationship:*, graph:*
- **observation**: subscribe, unsubscribe, query_history
- **message**: publish, subscribe

## Infrastructure Services

### State Management
- **Universal Relational Model**: Entities with properties and relationships
- **For Agent Data**: Not for system infrastructure
- **EAV Pattern**: Flexible property storage
- **Graph Operations**: Traverse relationships between entities

### Event Logging
- **File-Based Storage**: Daily JSONL files in `var/logs/events/`
- **SQLite Metadata**: Fast queries without loading full events
- **Selective References**: Large payloads (>5KB) stored separately
- **Pattern Matching**: SQL LIKE queries (e.g., "system:*")

### Module System
- **Pure Event-Based**: All modules use `@event_handler` decorators
- **Auto-Registration**: Handlers register at module import time
- **Event Communication**: No direct module imports, only events
- **Background Tasks**: Use `@background_task` decorator

## Key Modules

### Core Infrastructure
- **transport/unix_socket.py**: NDJSON protocol handler
- **core/state.py**: Relational state management
- **core/reference_event_log.py**: High-performance event logging
- **core/checkpoint.py**: State persistence across restarts
- **core/health.py**: System health monitoring

### Service Modules
- **completion/completion_service.py**: Async completion orchestration
- **agent/agent_service.py**: Agent lifecycle and spawning
- **observation/observation_manager.py**: Event observation routing
- **mcp/dynamic_server.py**: MCP server with tool generation
- **capability_enforcer.py**: Runtime permission enforcement

## Configuration

### Import Pattern
```python
from ksi_common.config import config
# Use: config.socket_path, config.db_dir, config.log_dir
```

### Environment Variables
- `KSI_LOG_LEVEL`: DEBUG, INFO (default), WARNING, ERROR
- `KSI_SOCKET_PATH`: Override default socket location
- `KSI_PROPAGATE_ERRORS`: Set to "true" for debugging

### Never Hardcode
- Always use config properties for paths
- No manual file paths like `"var/logs/daemon"`
- Use `config.daemon_log_dir`, `config.socket_path`, etc.

## Development Patterns

### Module Communication
- **Events Only**: No direct imports between service modules
- **Context Access**: Use `context["emit_event"]` from system:context
- **Error Handling**: Specific exceptions, no bare except
- **Async First**: All handlers and operations async

### Session Management
- **Never Invent IDs**: Only use session_ids from claude-cli
- **ID Flow**: Each request returns NEW session_id
- **Log Naming**: Response files named by session_id

### Capability System
- **Declarative**: Use capability flags in profiles
- **Mappings**: `var/lib/capability_mappings.yaml`
- **Inheritance**: base → specialized profiles
- **Runtime Enforcement**: capability_enforcer validates

### Development Mode
```bash
./daemon_control.py dev  # Auto-restart on file changes
```
- Watches Python files in ksi_daemon/, ksi_common/, ksi_client/
- Preserves state through checkpoint/restore

## Quick Reference

### Common Commands
```bash
# Daemon control
./daemon_control.py start|stop|restart|status|dev

# Health check
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# List agents
echo '{"event": "agent:list", "data": {}}' | nc -U var/run/daemon.sock

# Module introspection
echo '{"event": "module:list", "data": {}}' | nc -U var/run/daemon.sock
```

### Debugging
```bash
# Enable debug logging
KSI_LOG_LEVEL=DEBUG ./daemon_control.py restart

# Propagate errors (don't swallow exceptions)
KSI_PROPAGATE_ERRORS=true ./daemon_control.py start

# Check logs
tail -f var/logs/daemon/daemon.log
```

## Key Design Principles

1. **Event-Driven**: All communication through events
2. **Resilient**: Automatic retry, checkpoint/restore
3. **Observable**: Comprehensive event logging and monitoring
4. **Modular**: Clean module boundaries, no coupling
5. **Declarative**: Capabilities and permissions, not code

## Socket Communication Patterns (2025-07-06)

### Direct Unix Socket
- **More Reliable**: EventClient has discovery timeout issues
- **Pattern**: `echo '{"event": "name", "data": {}}' | nc -U var/run/daemon.sock`
- **Response**: Always includes event, data, count, correlation_id, timestamp
- **Documentation**: See `experiments/socket_patterns_documentation.md`

### Event Log Features
- **Timestamp Filtering**: Use `since` parameter in monitor:get_events
- **Pattern Matching**: Supports wildcards and arrays of patterns
- **Efficient Queries**: Server-side filtering reduces data transfer

## Claude Code Integration (2025-07-06)

### Hook System
- **Configuration**: `.claude/settings.local.json` (project-specific)
- **Input**: JSON via stdin with session_id, tool_name, tool_input, tool_response
- **Smart Filtering**: Only triggers on KSI-related commands
- **Implementation**: `experiments/ksi_hook_monitor.py`

### Session Management
- **Conversation Files**: `~/.claude/projects/{encoded-path}/*.jsonl`
- **Session ID**: Filename without .jsonl extension
- **Resume Pattern**: `claude --resume {session_id} --print` (doesn't work for injection)

### Key Discoveries
- **Context Contamination**: Spawned agents inherit Claude Code context
- **Simple Tasks Work**: Direct instructions succeed without contamination
- **Roleplay Triggers Protection**: Identity assertions prevent roleplay
- **File Watching Works**: Monitor response files for agent outputs

## Known Issues & Active Work

### Tracked Issues
- **EventClient Discovery** ([#6](https://github.com/durapensa/ksi/issues/6)): Format mismatch, use direct socket
- **Parameter Documentation** ([#1](https://github.com/durapensa/ksi/issues/1)): Remove legacy docstring patterns
- **Safety Guards** ([#2](https://github.com/durapensa/ksi/issues/2)-[#5](https://github.com/durapensa/ksi/issues/5)): Agent limits, rate limiting, timeouts
- **Future Architecture** ([#7](https://github.com/durapensa/ksi/issues/7)): Hybrid database with Kùzu

### Development Workflow
- **Small fixes**: Direct commits with clear messages
- **Large changes**: Create PRs for review and testing
- **Documentation**: Update in same commit as implementation

## Experimental Framework (2025-07-06)

### Prompt Testing Tools Created
- **Safety Framework**: `experiments/safety_utils.py` - Prevents runaway spawning
- **Socket Utils**: `experiments/ksi_socket_utils.py` - Reliable communication
- **Test Framework**: `experiments/prompt_testing_framework.py` - Systematic testing
- **Test Suites**: `experiments/prompt_test_suites.py` - Comprehensive scenarios

### Key Experimental Findings
- **Prompt Effectiveness**: Detailed > simple, 100% success on constrained tasks
- **Contamination**: 6.2% rate, properly handled with "I cannot" refusals  
- **Performance**: 4-6s normal, 18s+ indicates timeout/failure
- **Completion Flow**: Two-stage events - acknowledgment then result
- **Engineering**: Roleplay provides no benefit, negative framing works

See `ksi_claude_code/docs/PROMPT_EXPERIMENTS_GUIDE.md` for usage.

## Current Evaluation System Status (2025-07-08)

### Working Implementation
- **✅ Event-Driven Completion**: Uses `wait_for_event()` instead of polling, eliminates event cascades
- **✅ Shared Utilities**: `parse_completion_result_event()` in `ksi_common/completion_format.py`
- **✅ Production Integration**: Refactored injection_router.py and evaluation code
- **✅ 100% Test Success**: All basic_effectiveness tests pass consistently
- **✅ Consistent Configuration**: KSI_CLAUDE_BIN environment variable working

### Current Hardcoded Structure
```python
# In ksi_daemon/evaluation/prompt_evaluation.py
TEST_SUITES = {
    "basic_effectiveness": {
        "tests": [
            {
                "name": "simple_greeting",
                "prompt": "Hello! Please introduce yourself briefly.",
                "expected_behaviors": ["greeting", "introduction"]
            },
            {
                "name": "direct_instruction", 
                "prompt": "List the first 5 prime numbers.",
                "expected_behaviors": ["listing", "mathematical", "accurate"]
            },
            {
                "name": "creative_writing",
                "prompt": "Write a three-line story about a robot learning to paint.",
                "expected_behaviors": ["creative", "narrative", "robot_theme"]
            }
        ]
    }
}
```

### Path Forward: Incremental Enhancement
**Phase 1: Expand Current System (Next Steps)**
1. Test multiple compositions (`base_multi_agent`, specialized profiles)
2. Integrate evaluation results with `composition:discover` and `composition:suggest`
3. Generate comparative reports between compositions
4. Add more test suites (reasoning, creative, technical)

**Phase 2: Incremental YAML Migration**
1. Move test suites to YAML files (keeping current simple structure)
2. Add more sophisticated evaluator types gradually
3. Implement external evaluator support
4. Build proper file organization in `var/lib/evaluations/`

**Phase 3: Full Declarative System**
1. Implement comprehensive evaluator system from `docs/DECLARATIVE_PROMPT_EVALUATION.md`
2. Add semantic evaluators, DSL support, external frameworks
3. Build visual test builder and marketplace features
4. Complete integration with composition metadata

### Design Philosophy
- **Working System First**: Leverage proven 100% success rate
- **Incremental Value**: Each phase delivers immediate user benefit
- **Real Usage Feedback**: Let actual use cases drive feature priorities
- **Avoid Over-Engineering**: Build complexity only when justified by real needs

### Current Capabilities
- **Models**: claude-cli/sonnet (others require configuration)
- **Compositions**: Tested with base_single_agent, ready for multi-agent
- **Evaluators**: Pattern matching, contamination detection, behavior analysis
- **Integration**: Full event system integration, shared parsing utilities
- **Performance**: ~5s average response time, reliable completion flow

### Next Session Priorities
1. **Update TodoWrite** to reflect current evaluation success
2. **Multi-Composition Testing** with existing hardcoded system
3. **Composition Recommendation System** based on evaluation scores
4. **First YAML Migration** for test suites (simple structure)
5. **Integration with Discovery** to show evaluation summaries

This approach balances immediate value delivery with long-term architectural soundness.

## Parameter Documentation Pattern

### Standard: Inline Comments
```python
name = data.get('name')  # Composition name to update
overwrite = data.get('overwrite', False)  # Replace existing file if True
```
- Discovery system extracts inline comments via AST
- Include workflow hints when helpful
- Migration tracked in [#1](https://github.com/durapensa/ksi/issues/1)


---
*Last updated: 2025-07-08*
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*