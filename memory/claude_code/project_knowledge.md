# KSI Technical Knowledge

Essential technical reference for KSI (Kubernetes-Style Infrastructure) - a resilient daemon system for orchestrating autonomous AI agents with production-grade reliability.

**Core Philosophy**: Pure event-based architecture with coordinated shutdown, automatic checkpoint/restore, and resilient error handling.

**LLM Reality**: KSI is designed for LLM orchestration where API calls dominate timing (2-30+ seconds). Architecture prioritizes coordination resilience, cost management, and graceful degradation over microsecond optimizations.

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
- **transformer**: load_pattern, unload_pattern, reload_pattern, list_by_pattern
- **composition**: get, create, list, rebuild_index
- **orchestration**: spawn, coordinate, aggregate, track
- **evaluation**: prompt, compare

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
- **core/state.py**: Graph database state management
- **core/reference_event_log.py**: High-performance event logging
- **core/checkpoint.py**: State persistence across restarts
- **core/health.py**: System health monitoring

### Service Modules
- **completion/completion_service.py**: Async completion orchestration
- **agent/agent_service.py**: Agent lifecycle and spawning
- **observation/observation_manager.py**: Event observation routing
- **transformer/transformer_service.py**: Pattern-based event transformation
- **orchestration/orchestration_service.py**: Multi-agent orchestration patterns
- **composition/composition_service.py**: YAML pattern management
- **evaluation/prompt_evaluation.py**: Declarative prompt testing
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

### Event Enrichment and Response Standardization

**Core System Functionality**: All events are automatically enriched with context metadata before handler execution. This is fundamental KSI behavior providing complete event traceability.

#### Event Enrichment
```python
# The event system automatically injects these fields into ALL events:
{
  "_agent_id": "agent_123",           # Agent that emitted this event (if from agent)
  "_client_id": "ksi-cli",            # Client that emitted this event (if from client)
  "_event_id": "evt_abc123",          # Unique event identifier
  "_correlation_id": "corr_xyz789",   # Request correlation (if available)
  "_event_timestamp": "2025-07-15T..." # System timestamp
}
# NOTE: session_id is NOT enriched - it's private to completion system
# NOTE: Orchestration lineage is handled at orchestration layer, not event system
```

#### Handler Categories and Patterns

**Two distinct handler types with different requirements:**

##### Business Logic Handlers (Most handlers)
```python
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder

@event_handler("your:event")
async def your_handler(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
    # REQUIRED: Strip system metadata to get clean handler data
    data = event_format_linter(raw_data, YourEventType)  # YourEventType is TypedDict
    
    # Process with clean, type-safe data
    result = your_processing_logic(data)
    
    # REQUIRED: Return standardized response
    return event_response_builder(result, "your_handler", "your:event", context)
```

##### System Infrastructure Handlers (monitor, event_system, transport)
```python
from ksi_common.event_parser import extract_system_handler_data
from ksi_common.event_response_builder import event_response_builder

@event_handler("system:event")
async def system_handler(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
    # Extract clean business data and system metadata (SYSTEM_METADATA_FIELDS is source of truth)
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    
    # Access business data
    handler_field = clean_data.get("your_field")
    
    # Use system metadata dict directly when needed
    if system_metadata.get("_agent_id"):
        # Filter or process based on agent
        pass
    
    # Process with clean data and metadata dict
    result = system_processing_logic(clean_data, system_metadata)
    
    # REQUIRED: Return standardized response
    return event_response_builder(result, "system_handler", "system:event", context)
```

#### Response Standardization
**All handlers return standardized responses via `event_response_builder()`:**
```python
# Standard response format for ALL handlers:
{
  "status": "success",           # or "error", "pending"
  "result": {...},              # Handler-specific result data
  "handler": "your_handler",    # Handler identifier
  "event": "your:event",        # Source event name
  "_agent_id": "agent_123",     # Preserved from enriched context
  "_timestamp": "2025-07-14T...", # Response timestamp
  "_response_id": "resp_abc123"   # Unique response ID
}
```

#### Universal Utilities
- **event_format_linter()**: Strips system metadata from incoming events (REQUIRED for ALL handlers)
- **event_response_builder()**: Creates standardized responses (REQUIRED for ALL handlers)
- **Benefits**: System-wide observability, consistent tooling, clean separation of concerns

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

## Testing Long-Running Orchestrations
See `docs/LONG_RUNNING_COORDINATION_TEST_PLAN.md` for comprehensive test approach.

**Key Testing Focus**:
- **Coordination resilience** (not system resources)
- **Timeout handling** (agents will fail/timeout)
- **Cost tracking** (prevent runaway expenses)
- **Partial results** (orchestrations must progress)

## Architecture Analysis
See `docs/KSI_LLM_ORCHESTRATION_ANALYSIS.md` for LLM-centric architecture analysis.

**Key Insights**:
- LLM latency (2-30s) dominates all timing considerations
- Async event logging is non-blocking (not a bottleneck)
- Queue unboundedness acceptable for realistic agent counts
- Real bottlenecks: coordination efficiency, timeout cascades, cost control

### Development Mode Features
- Watches Python files in ksi_daemon/, ksi_common/, ksi_client/
- Preserves state through checkpoint/restore

## Quick Reference

### Common Commands
```bash
# Daemon control
./daemon_control.py start|stop|restart|status|dev

# Health check
ksi send system:health

# List agents
ksi send agent:list

# Module introspection
ksi send module:list
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

## Socket Communication Patterns

### KSI CLI Tool (Recommended)
- **Primary Interface**: `ksi` command-line tool for all daemon interactions
- **Advantages**: No JSON escaping, parameter validation, connection management
- **Permission-free**: Avoids Claude Code `Bash(echo:*)` permission requirements
- **Examples**: `ksi send event:name --param value` or `ksi send event:name --json '{...}'`

### Direct Unix Socket (Legacy)
- **Pattern**: `echo '{"event": "name", "data": {}}' | nc -U var/run/daemon.sock`
- **Response**: Always includes event, data, count, correlation_id, timestamp
- **Use cases**: Python scripts, when ksi CLI unavailable
- **Documentation**: See `experiments/socket_patterns_documentation.md`

### Event Log Features
- **Timestamp Filtering**: Use `since` parameter in monitor:get_events
- **Pattern Matching**: Supports wildcards and arrays of patterns
- **Efficient Queries**: Server-side filtering reduces data transfer

## Real-Time Visualization System

### WebSocket Bridge
- **Architecture**: `websocket_bridge.py` connects KSI daemon to web clients
- **Per-Client Connections**: Each WebSocket client gets dedicated KSI daemon connection
- **Event Normalization**: Converts KSI event format for web client compatibility
- **Health Monitoring**: Automatic KSI daemon connectivity checking
- **Graceful Shutdown**: Notifies clients before termination for clean reconnection

### Web Visualization Components
- **Agent Ecosystem**: Real-time graph of agent spawn relationships and activity
- **State System**: Visualization of entities and relationships (excludes agent data)
- **Event Stream**: Live feed of all KSI events with filtering and categorization
- **Connection Management**: Automatic reconnection with health checking

### Usage
```bash
# Terminal 1: Start daemon
./daemon_control.py start

# Terminal 2: WebSocket bridge  
python websocket_bridge.py

# Terminal 3: Web UI
cd ksi_web_ui && python -m http.server 8080
# Open http://localhost:8080
```

### Event Origination Tracking
- **Agent Activity**: Events originated by agents are visually marked
- **Real-Time Updates**: Agent termination and entity deletion immediately reflected
- **Spawn Relationships**: Visual hierarchy showing which agents spawned others
- **Pulse Effects**: Visual feedback when agents emit events

## Claude Code Integration

### Hook System
- **Configuration**: `.claude/settings.local.json` (project-specific)
- **Implementation**: `ksi_claude_code/ksi_hook_monitor.py`
- **Output Format**: JSON `{"decision": "block", "reason": "[KSI] message"}` with exit 0
- **Smart Filtering**: Only triggers on KSI-related commands (see `ksi_hook_monitor_filters.txt`)
- **Verbosity Modes**: 
  - `summary` (default): Shows event/agent counts
  - `verbose`: Shows detailed event timeline
  - `errors`: Only shows error events
  - `silent`: No output
- **Mode Commands**: `echo ksi_summary`, `echo ksi_verbose`, `echo ksi_errors`, `echo ksi_silent`, `echo ksi_status`
- **State Persistence**: Tracks last seen timestamp to show only new events
- **Connection Pooling**: Reuses socket connections for performance
- **Error Handling**: Graceful degradation when daemon offline

### Session Management
- **Conversation Files**: `~/.claude/projects/{encoded-path}/*.jsonl`
- **Session ID**: Filename without .jsonl extension
- **Resume Pattern**: `claude --resume {session_id} --print` (doesn't work for injection)

### Key Discoveries
- **Context Contamination**: Spawned agents inherit Claude Code context
- **Simple Tasks Work**: Direct instructions succeed without contamination
- **Roleplay Triggers Protection**: Identity assertions prevent roleplay
- **File Watching Works**: Monitor response files for agent outputs

## Active Systems & Architecture

### Self-Configuring Agent Architecture
**Overview**: Agents receive complete YAML context at spawn time for self-configuration, enabling full structural awareness.

**Key Features**:
- **Context Assembly**: `composition:agent_context` constructs complete agent context
- **Minimal Redaction**: Only genuine secrets removed (API keys, tokens)
- **Full Context**: Agents receive profile, orchestration context, and variables
- **Natural Adaptation**: Agents understand their place in larger systems

**Usage**:
```bash
# Spawn self-configuring agent with orchestration context
ksi send agent:spawn --profile worker --orchestration distributed_analysis \
  --variables '{"task": "analyze_data", "priority": "high"}'
```

### Event Feedback System
**Overview**: Agents receive emission results when they emit JSON events, enabling them to react to success/failure and adapt behavior.

**Key Features**:
- **JSON Extraction**: Extracts events from agent responses automatically
- **Non-blocking**: Event extraction runs in background tasks
- **Feedback Delivery**: Complete emission results sent back to agents
- **Loose Coupling**: Feedback sent via `completion:async`

**Feedback Format**:
```json
{
  "event": "completion:async",
  "data": {
    "messages": [{
      "role": "system",
      "content": "=== EVENT EMISSION RESULTS ===\n{\"event\": \"state:get\", \"emission_result\": {\"status\": \"success\", \"value\": \"test_data\"}}"
    }],
    "agent_id": "agent_123",
    "is_feedback": true
  }
}
```

**Benefits**:
- Agents learn from event outcomes
- Natural error handling without explicit retry logic
- Enables sophisticated agent behaviors based on system feedback

### Tracked Issues
- **EventClient Discovery** ([#6](https://github.com/durapensa/ksi/issues/6)): Format mismatch, use direct socket
- **Parameter Documentation** ([#1](https://github.com/durapensa/ksi/issues/1)): Remove legacy docstring patterns
- **Safety Guards** ([#2](https://github.com/durapensa/ksi/issues/2)-[#5](https://github.com/durapensa/ksi/issues/5)): Agent limits, rate limiting, timeouts
- **Future Architecture** ([#7](https://github.com/durapensa/ksi/issues/7)): Hybrid database with Kùzu

### Development Workflow
- **Small fixes**: Direct commits with clear messages
- **Large changes**: Create PRs for review and testing
- **Documentation**: Update in same commit as implementation

## Experimental Framework

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

## Pattern-Based Orchestration

### Transformer System
Patterns define custom event vocabularies via transformers in YAML:

```yaml
transformers:
  # Sync transformer
  - source: "pattern:command"
    target: "agent:send_message"
    mapping:
      agent_id: "{{target_agent}}"
      message: "Command: {{instruction}}"
  
  # Async with response routing
  - source: "pattern:analyze"
    target: "completion:async"
    async: true
    mapping:
      prompt: "Analyze this data: {{data}}"
      model: "claude-cli/claude-sonnet-4-20250514"
      request_id: "{{transform_id}}"
    response_route:
      from: "completion:result"
      to: "pattern:analysis_complete"
  
  # Conditional
  - source: "pattern:notify"
    target: "message:broadcast"
    condition: "priority == 'high'"
    mapping:
      message: "Alert: {{notification}}"
```

### Template Substitution
- **Simple**: `{{variable}}`
- **Embedded**: `"Status: {{status}} at {{time}}"`
- **Nested**: `{{user.name}}`, `{{config.timeout}}`
- **Arrays**: `{{items.0}}`, `{{tags.1}}`
- **Special**: `{{transform_id}}` available in async transformers

### Composition System
- **Preserves all YAML sections**: transformers, agents, routing, custom fields
- **Patterns location**: `var/lib/compositions/orchestrations/`
- **Hot reload**: `transformer:reload_pattern` event
- **Reference counting**: Multiple systems can share patterns

## Declarative Evaluation System

### Architecture
```
var/lib/evaluations/
├── test_suites/           # Test definitions (YAML)
├── evaluators/            # Reusable evaluator definitions
└── results/               # Evaluation results
```

### Features
- **YAML test suites**: Declarative test definitions
- **11 evaluator types**: exact_match, contains, regex, length, etc.
- **Weighted scoring**: Configure weight and success threshold per test
- **Format options**: summary, rankings, detailed
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

## Discovery System

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

## Autonomous Judge System

### Overview
Implemented a self-improving evaluation system where AI judges collaborate to improve prompts and their own capabilities.

### Current Status
- **Bootstrap Results**: 
  - Evaluator Judge: 64% success rate
  - Analyst Judge: 72% success rate  
  - Rewriter Judge: 60% success rate
- **Prompt Library**: Fully integrated at `var/lib/compositions/prompts/`
- **Index System**: Fixed and working - use `composition:rebuild_index` after changes

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

### Prompt Library Infrastructure

#### Organization
```
var/lib/compositions/prompts/
├── agent_tasks/           # Task-specific agent prompts
├── evaluation/            # Evaluation and judge prompts
│   ├── judges/           # Autonomous judge variations
│   └── test_cases/       # Ground truth examples
└── system/               # System and utility prompts
```

#### Key Files
- **Evaluator Judge**: `var/lib/compositions/prompts/evaluation/judges/evaluator-judge-v1.yaml`
- **Analyst Judge**: `var/lib/compositions/prompts/evaluation/judges/analyst-judge-v1.yaml`
- **Rewriter Judge**: `var/lib/compositions/prompts/evaluation/judges/rewriter-judge-v1.yaml`
- **Bootstrap Script**: `ksi_claude_code/scripts/judge_bootstrap_v2.py`

### Key Discoveries
1. **KSI capabilities sufficient** - No new features needed:
   - Dynamic compositions via `composition:create`
   - Structured messaging via `agent:send_message` with Dict[str, Any]
   - Multi-agent coordination via broadcast + state system

2. **Prompt improvement results**:
   - Base prompt: 50% success (missing brackets)
   - With explicit examples: 100% success
   - 8/10 technique variations succeeded

3. **Common utilities in ksi_common**:
   - `file_utils`: Atomic writes, safe path operations
   - `cache_utils`: Memory caching with TTL
   - `event_utils`: Event formatting helpers
   - `json_utils`: Safe JSON operations
   - `logging_utils`: Structured logging
   - `time_utils`: Timestamp handling

4. **Session tracking critical fix**:
   - Never create session IDs - only claude-cli creates them
   - Each completion:async request returns NEW session_id
   - Created session_manager_v2.py to respect this principle
   - Fixed MCP path handling to use absolute paths

### Tournament Results
Successfully ran first complete judge tournament:
- **Participants**: 6 judges (from fixed list, not bootstrap)
- **Matches**: 30 complete (each judge evaluated the other 5)
- **Duration**: ~12 minutes total
- **Results**: All judges scored 0.85 (simulated scoring)
- **Next Step**: Implement real evaluation logic in tournament

### Tournament Evaluation System
**Implementation**: Real evaluation logic for judge tournaments with autonomous scoring.

**Key Components**:
- `tournament_evaluation.py` - Handles real-time evaluation responses
- Score extraction from JSON responses with proper float conversion
- Optimized evaluation prompts for speed (reduced by ~80%)
- Working aggregate score calculation with reputation weighting

**Results**: Successfully running tournaments with real scores (e.g., 0.675 for top evaluator)

### Integration Status
- ✅ Judge variations can be created dynamically
- ✅ Tournament system can orchestrate multi-agent evaluation
- ✅ Communication protocols defined and documented
- ✅ Prompt library infrastructure complete
- ✅ Bootstrap protocol functional with real results
- ✅ Session tracking fixed for agent completions
- ✅ Tournament handlers implemented and working
- ✅ Real evaluation logic in tournaments complete
- ✅ Full autonomous improvement loop working
- 🔄 Ground truth test cases being expanded
- ⏳ Deployment of winning judges to evaluation system

### Autonomous Improvement Cycle

Successfully implemented complete autonomous improvement cycle:

**Components**:
- `tournament_bootstrap_integration.py` - Orchestrates full improvement cycle
- Bootstrap phase creates judge variations (2 per role for tournaments)
- Tournament phase evaluates judges against each other
- Selection phase identifies best performers per role
- Results tracking for deployment decisions

**First Successful Run**:
- Evaluator judge: 0.675 score (detailed_rubric technique)
- Analyst judge: 0.5 score (root_cause_focus technique)
- Rewriter judge: 0.5 score (incremental_improvement technique)
- Total cycle time: ~2 minutes for 6 agents, 12 matches

**Key Fixes**:
- Bootstrap event uses roles/techniques_per_role parameters
- Tournament response parsing handles emit_event list format
- Agent spawning creates multiple instances per role
- Real evaluation scoring with JSON extraction

**Full documentation**: See [`docs/AUTONOMOUS_JUDGE_ARCHITECTURE.md`](../../docs/AUTONOMOUS_JUDGE_ARCHITECTURE.md)

## Intelligent Orchestration Patterns

### Overview
Hybrid approach combining intelligent agents as orchestrators with shareable declarative patterns.

**Key Concepts**:
- Orchestration agents (like Claude) act as the orchestration engine
- Patterns are learned through experience and shared between orchestrators
- Adaptation happens naturally through agent intelligence
- Meta-orchestration enables orchestrators to coordinate other orchestrators

### Current Implementation Status
**Status**: Implementation partially complete, blocked on composition system redesign

**Completed**:
- ✅ `ksi_daemon/transformer/transformer_service.py` - Pattern-level transformer management
- ✅ `ksi_daemon/orchestration/orchestration_service.py` - Updated to use transformer service
- ✅ Core transformer infrastructure in `ksi_daemon/event_system.py`

**Blocked**: 
- ❌ Composition system strips `transformers` section from YAML patterns
- 📋 **Next Step**: Implement `docs/GENERIC_COMPOSITION_SYSTEM_REDESIGN.md` to enable full pattern loading

### Pattern Evolution System
**Status**: Fully implemented and tested (2025-07-13)

**Core Features**:
- **Pattern Fork/Merge**: `composition:fork`, `composition:merge`, `composition:diff` - Evolution with lineage tracking
- **Decision Tracking**: `composition:track_decision` - Records orchestration decisions for learning
- **Automatic Crystallization**: Performance thresholds trigger new pattern creation
- **Self-Contained Storage**: Patterns and decisions stored in composition files

**Test Results**:
- ✅ Fork chains working: evolution_test_base → evolution_test_improved → evolution_test_advanced
- ✅ Crystallization tested: auto_crystallization_test → crystallized_high_performance_auto
- ✅ Decision tracking scales: Handles high-volume events (500+ decisions)
- ✅ Pattern library growth: 32+ orchestration patterns with clear lineages

**Pattern Format**:
- Enhanced orchestration compositions with DSL section for agent interpretation
- Performance metrics, learnings, and lineage tracking in metadata
- Decision logs stored alongside patterns in `*_decisions.yaml` files
- Natural language strategies mixed with structured DSL

**Orchestrator Capabilities**:
- `base_orchestrator` profile with pattern awareness
- Discover patterns via `composition:discover` 
- Interpret DSL and implement using `event:emit`
- Fork successful adaptations, merge improvements
- Track decisions for continuous learning

**Benefits**:
- Natural adaptation to unexpected situations
- Patterns evolve and improve through use
- Explainable decisions with documented rationale
- Federation-ready for sharing across KSI networks
- Loose coupling through event-based architecture

### Orchestration Primitives
**Status**: Implemented all 6 core primitives + aggregate planned

**Core Primitives**:
- `orchestration:spawn` - Create agents with orchestration context
- `orchestration:send` - Flexible message targeting (one, many, criteria)
- `orchestration:await` - Wait for responses with conditions
- `orchestration:track` - Record any orchestration data
- `orchestration:query` - Get orchestration state information
- `orchestration:coordinate` - Flexible synchronization patterns

**Planned Enhancement**: `orchestration:aggregate` for voting, statistics, consensus

**Full documentation**: See [`docs/INTELLIGENT_ORCHESTRATION_PATTERNS.md`](../../docs/INTELLIGENT_ORCHESTRATION_PATTERNS.md)

## Event Router Enhancement (Planned)

### Generic Event Transformation System
A powerful enhancement to the event router enabling event transformation without duplicate events in the log.

**Concept**:
```python
# Any module can register transformers
@event_transformer("source:event", target="target:event")
async def transform_something(data: Dict[str, Any]) -> Dict[str, Any]:
    # Transform source event data into target event data
    return transformed_data
```

**Benefits**:
- **No duplicate events**: Transformers convert events before emission
- **Protocol adapters**: Transform external events to internal format
- **API versioning**: Transform v1 events → v2 events seamlessly
- **Cross-module bridges**: Module A's output → Module B's expected input
- **Event enrichment**: Add context/metadata without wrapper events
- **Backwards compatibility**: Old event names → new event names

**Implementation Plan**:
1. Add transformer registry to EventRouter class
2. Modify emit logic to check transformers before handlers
3. Create @event_transformer decorator similar to @event_handler
4. Add transform logging for debugging/observability
5. Update orchestration primitives to use transformers instead of wrapping

**Example Use Cases**:
```python
# Orchestration primitives become transformers
@event_transformer("orchestration:spawn", target="agent:spawn")
async def transform_spawn(data: Dict[str, Any]) -> Dict[str, Any]:
    context = get_or_create_context(data)
    # Enrich with orchestration metadata
    return enriched_data

# API version migration
@event_transformer("api:v1:user_create", target="user:create")
async def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    # Transform old format to new
    return {"username": data["name"], "email": data["mail"]}
```

**Impact on Orchestration**:
- Orchestration primitives will use transformers instead of emit_event
- Cleaner event log without wrapper events
- Same loose coupling but more efficient
- Better performance with less event processing overhead

## Agent JSON Event Emission

### Overview
Agents emit events by including JSON objects in their responses. The completion service automatically extracts and emits these events asynchronously.

### How It Works
1. **Agent outputs JSON**: Include `{"event": "some:event", "data": {...}}` in response
2. **Automatic extraction**: Completion service extracts JSON objects with 'event' field
3. **Async emission**: Events are emitted in background tasks (non-blocking)
4. **Metadata added**: System adds `_agent_id` and `_extracted_from_response` fields

### Supported Patterns
- JSON in code blocks: ` ```json {...} ``` `
- Standalone JSON objects: `{...}`
- Multiple events in single response

### Benefits
- **No tools required**: Agents orchestrate without tool permissions
- **Natural workflow**: Agents think and emit events in same response
- **Non-blocking**: Event extraction doesn't delay completion response
- **Traceable**: Events marked with source agent and context

---
*Last updated: 2025-07-15*
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*