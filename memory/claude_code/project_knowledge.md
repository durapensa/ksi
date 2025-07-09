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

## Declarative Evaluation System (2025-07-08)

### ✅ Phase 2 Complete: YAML-Based Evaluation
- **Migrated to declarative test suites**: All tests now in YAML format
- **Implemented evaluator system**: 11 built-in evaluator types
- **Clean separation**: `config.evaluations_dir` separate from `config.compositions_dir`
- **File-based results**: Pattern `{type}_{name}_{eval}_{id}.yaml` in `var/lib/evaluations/results/`
- **Weighted scoring**: Each evaluator has configurable weight, success threshold per test
- **Format options for evaluation:compare**: summary (default), rankings, detailed - reduces output from 1500+ to ~20 lines

### Architecture
```
var/lib/evaluations/
├── test_suites/           # Test definitions
│   ├── basic_effectiveness.yaml
│   ├── reasoning_tasks.yaml
│   └── instruction_following.yaml
├── evaluators/            # (Future) Reusable evaluator definitions
├── schemas/               # (Future) Validation schemas  
└── results/               # Evaluation results
    └── profile_base-single-agent_basic-effectiveness_001.yaml
```

### Evaluator Types Implemented
1. **Pattern Matching**: contains, contains_any, contains_all, regex
2. **Structural**: word_count, exact_word_count, sentence_count, format_match
3. **Behavioral**: contains_reasoning_markers, no_contamination
4. **Composite**: weighted (combines multiple evaluators)

### Example Test Suite Structure
```yaml
name: basic_effectiveness
version: 1.0.0
tests:
  - name: simple_greeting
    prompt: "Hello! Please introduce yourself briefly."
    evaluators:
      - type: contains_any
        patterns: ["hello", "hi", "greetings"]
        weight: 0.3
      - type: no_contamination
        weight: 0.5
    success_threshold: 0.7
contamination_patterns:
  - pattern: regex
    value: "I (cannot|can't|don't)"
    severity: high
```

### Current Capabilities
- **Models**: claude-cli/sonnet (others require configuration)
- **Test Suites**: basic_effectiveness, reasoning_tasks, instruction_following
- **Evaluation Storage**: Filesystem-based, not in composition metadata
- **Comparison Reports**: Compare multiple compositions side-by-side
- **Performance**: ~5s average response time, reliable completion flow

### Next Priorities
1. **Test multi-composition comparison** with the new system
2. **Create semantic evaluators** (Phase 3 work)
   - Will use `expected_behaviors` metadata from test definitions
   - Check if responses semantically match expected behaviors
3. **Add pipeline evaluators** for complex multi-step evaluation
4. **Integrate with composition:discover** to show available evaluations
5. **Build evaluation index/query system**

### Design Notes
- **expected_behaviors** field preserved in YAML as metadata for future semantic evaluators
- Clean break from old system - no backward compatibility code
- All evaluation logic now in declarative evaluators

**Full documentation**: See [`docs/DECLARATIVE_PROMPT_EVALUATION.md`](../../docs/DECLARATIVE_PROMPT_EVALUATION.md) for complete architecture
**Development guide**: See [`memory/claude_code/evaluation_system_guide.md`](evaluation_system_guide.md) for implementation details

## Parameter Documentation Pattern

### Standard: Inline Comments
```python
name = data.get('name')  # Composition name to update
overwrite = data.get('overwrite', False)  # Replace existing file if True
format = data.get('format', 'summary')  # Output format: 'summary', 'rankings', 'detailed' - provides allowed values
```
- Discovery system extracts inline comments via AST
- Include workflow hints when helpful
- Migration tracked in [#1](https://github.com/durapensa/ksi/issues/1)

## Discovery System (2025-07-09)

### Enhanced Discovery Features
The discovery system now provides richer parameter information:

1. **TypedDict Type Extraction**: When handlers use `data: SomeTypedDict`, actual types are shown (not just "Any")
2. **Inline Comment Extraction**: Comments after `data.get()` calls become parameter descriptions
3. **Validation Pattern Parsing**: Comments like "one of: A, B, C" generate `allowed_values` constraints
4. **Context-Aware Examples**: Better example values based on parameter names and types

### Implementation Details
- Uses AST analysis to extract TypedDict field definitions
- Resolves type annotations to readable strings: `List[Dict[str, Any]]`
- Parses structured patterns in comments for validation rules
- Separate module analysis prevents parameter mixing between handlers

**Design documentation**: See [`memory/claude_code/discovery_enhancement_design.md`](discovery_enhancement_design.md)
**Implementation progress**: See [`memory/claude_code/discovery_progress.md`](discovery_progress.md)
**Issue tracking**: See [`memory/claude_code/discovery_findings.md`](discovery_findings.md)

### Best Practices for Module Authors
1. Use TypedDict for handler parameters: `async def handle_event(data: MyTypedDict)`
2. Add inline comments: `compositions = data.get('compositions', [])  # List of composition names`
3. Include allowed values: `format = data.get('format', 'summary')  # Output format: 'summary', 'rankings', 'detailed'`
4. TypedDict fields are automatically discovered - no need to duplicate in comments

## Autonomous Judge System (2025-07-09)

### Overview
Implemented a self-improving evaluation system where AI judges collaborate to improve prompts and their own capabilities.

### Architecture Components

#### 1. **Evaluation System Enhancements**
- **New Evaluators**: `all_of`, `any_of`, `exact_match`, `length_range`, `pipeline`
- **LLM Judge**: `llm_judge` evaluator using LLM-as-Judge pattern
- **Prompt Iteration**: Framework for testing multiple prompt variations
- **Results**: 80% success rate on bracket formatting problem

#### 2. **Judge Bootstrap Protocol** (`judge_bootstrap_v2.py`)
- Creates judge variations using `composition:create` 
- Tests against ground truth cases
- Runs tournaments for cross-evaluation
- Selects best performers based on scores

#### 3. **Tournament System** (`judge_tournament.py`)
- Multi-phase orchestration: registration → round-robin → consensus → results
- Uses `agent:broadcast_message` for coordination
- Reputation-weighted scoring
- Parallel match execution

#### 4. **Communication Schemas**
- Structured YAML schemas for judge-to-judge communication
- Self-documenting protocols shown to all judges
- Type-safe message passing

### Key Discoveries
1. **KSI capabilities sufficient** - No new features needed:
   - Dynamic compositions via `composition:create`
   - Structured messaging via `agent:send_message` with Dict[str, Any]
   - Multi-agent coordination via broadcast + state system

2. **Prompt improvement results**:
   - Base prompt: 50% success (missing brackets)
   - With explicit examples: 100% success
   - 8/10 technique variations succeeded

### Integration Status
- ✅ Judge variations can be created dynamically
- ✅ Tournament system can orchestrate multi-agent evaluation
- ✅ Communication protocols defined and documented
- 🔄 Ground truth test cases being created
- ⏳ Real agent testing pending
- ⏳ Full autonomous loop integration pending

**Full documentation**: See [`docs/AUTONOMOUS_JUDGE_ARCHITECTURE.md`](../../docs/AUTONOMOUS_JUDGE_ARCHITECTURE.md)

---
*Last updated: 2025-07-09*
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*