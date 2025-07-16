# CLAUDE.md

Essential development practices for Claude Code when working with KSI.

## Session Start
**ALWAYS**: Read `memory/claude_code/project_knowledge.md` first for technical details.

## Core Principles

### Configuration Management
- **Use ksi_common/config.py** - Always import `from ksi_common.config import config`
- **Path handling**: **NEVER hardcode paths** - Always use config properties
- **❌ WRONG**: `Path("var/logs/daemon")`, `"var/run/daemon.sock"`
- **✅ CORRECT**: `config.daemon_log_dir`, `config.socket_path`, `config.evaluations_dir`

### Task Management
- **Completion = Code + Test + Deploy + Verify** (not just code creation)
- **Never mark complete until testing demonstrates completeness**
- **Always update TodoWrite** when receiving new instructions
- **Test comprehensively** - implementation without working tests is incomplete

### Development Practices
- **Event-driven only** - no polling or wait loops, modules communicate only through events
- **Complete migrations** - when implementing new features, migrate entire system, remove ALL old code
- **Separation of concerns** - Event log (infrastructure) vs Graph database (application data)
- **Inspect before implementing** - check existing code before writing new functionality
- **Profile hierarchy** - JSON instructions in base profiles, avoid duplication in specialized profiles
- **Progressive testing** - Start simple (single agent), progress to complex (multi-agent orchestration)

### Session ID Management (Critical)
- **NEVER invent session IDs** - claude-cli only accepts session IDs it has generated
- **Claude-cli returns NEW session_id from EVERY request** - even continuation requests
- **Always use session_id from previous response as input**

### Code Hygiene
- **NO bare except clauses** - Always catch specific exceptions
- **Clean as you go** - remove dead code immediately when found
- **Complete transitions** - when moving features, verify functionality then remove old locations
- **Investigate failures** - NEVER create workarounds for errors; instead find and fix root causes
  - When a file is not found, check if the path reference is correct
  - Don't create duplicate files in wrong locations
  - Fix the code that has the wrong path, not create the file where it's looking

## Discovery-First Development

**CRITICAL**: Always use the discovery system before reading source code. The discovery system is your primary tool for understanding available events and their parameters.

### KSI CLI Tool (Preferred Method)

**Always use the `ksi` CLI tool** for daemon interactions. It provides:
- Clean parameter syntax (no JSON escaping)
- Built-in connection management
- Structured output formatting (minimal by default)
- No permission issues (avoids `Bash(echo:*)` restrictions)

**Output Modes:**
- **Default**: Clean output with no logging info
- **Verbose**: Use `--health` flag to show daemon connection status
  ```bash
  ksi discover                    # Clean output only
  ksi --health discover           # Shows connection/health info
  ```

### Basic Discovery Workflow

```bash
# 1. Find events in a namespace
ksi discover --namespace evaluation

# 2. Get detailed help for a specific event (with rich parameter info!)
ksi help evaluation:prompt

# 3. List all available events
ksi discover

# 4. Send events with parameters
ksi send state:set --key config --value '{"theme": "dark"}' --namespace user
```

### Legacy Method (Deprecated)

<details>
<summary>Echo/netcat pattern (avoid if possible)</summary>

The `echo | nc` pattern is deprecated due to:
- JSON escaping complexity
- Permission requirements for `Bash(echo:*)`
- Less readable commands

```bash
# Old way - not recommended
echo '{"event": "system:discover", "data": {"namespace": "evaluation"}}' | nc -U var/run/daemon.sock
```
</details>

### Enhanced Discovery Features (2025-07-09)

The discovery system now provides:
- **Actual parameter types** from TypedDict definitions (not just "Any")
- **Parameter descriptions** from inline comments
- **Validation constraints** like `allowed_values` from structured comments
- **Better examples** based on parameter names and types

**Implementation details**: See `memory/claude_code/discovery_enhancement_design.md` and `memory/claude_code/discovery_progress.md`

### Common Discovery Patterns

**Finding Event Parameters:**
```bash
# Wrong: Grepping source code
grep "@event_handler" ksi_daemon/evaluation/*.py  # ❌ Don't do this

# Right: Use ksi CLI
ksi help evaluation:prompt  # ✅ Do this
```

**Exploring Namespaces:**
```bash
# List all events in a namespace
ksi discover --namespace composition

# Get all events (with filtering)
ksi discover | grep evaluation

# Complex JSON parameters (use --json flag)
ksi send evaluation:prompt --json '{"prompt": "test", "params": {"model": "sonnet"}}'
```

### Discovery Best Practices

1. **Start with `detail": false`** - Get overview before diving deep
2. **Use namespace filtering** - Focus on relevant subsystems
3. **Use `system:help` for specific events** - More focused than full discovery
4. **Try different format_style options** - verbose, compact, ultra_compact, mcp
5. **Chain discovery calls** - Start broad, then narrow down

### When Discovery Fails

If discovery doesn't provide needed information:
1. Document the gap in `memory/claude_code/discovery_findings.md`
2. Then (and only then) read source code
3. Propose discovery system improvements

**Note**: Discovery system improvements are tracked in `memory/claude_code/discovery_findings.md`

## Evaluation System

For prompt testing and composition evaluation:
- **Quick reference**: See the Declarative Evaluation System section in `memory/claude_code/project_knowledge.md`
- **Development guide**: See `memory/claude_code/evaluation_system_guide.md` for working on evaluation improvements
- **Full documentation**: See `docs/DECLARATIVE_PROMPT_EVALUATION.md` for complete architecture
- **Test suites**: Located in `var/lib/evaluations/test_suites/`
- **Results**: Stored in `var/lib/evaluations/results/`

## Prompt Library System

### Organization
- **Prompts location**: `var/lib/compositions/prompts/` - managed prompt library
- **Categories**: `agent_tasks/`, `evaluation/`, `system/` for different prompt types
- **Storage format**: YAML files with structured metadata
- **Index management**: Use `composition:rebuild_index` after changes

### Common Operations
```bash
# Rebuild composition index after changes
ksi send composition:rebuild_index

# Create new prompt composition
ksi send composition:create --name my-prompt --category agent_tasks --content "Test prompt content"

# List compositions
ksi send composition:list --category agent_tasks

# Git integration operations
ksi send composition:save --composition '{...}' --overwrite true  # Auto git commit
ksi send composition:fork --parent base_agent --name my_agent --reason "customization"
ksi send composition:sync                                         # Pull from remotes
ksi send composition:git_info                                     # Check repo status

# Judge bootstrap protocol (for autonomous evaluation)
python ksi_claude_code/scripts/judge_bootstrap_v2.py --test-suite evaluation/judges --num-variations 5

# Start orchestration pattern
ksi send orchestration:start --pattern mipro_bayesian_optimization --vars '{"task": "optimize this"}'

# Monitor long-running orchestrations
python monitor_orchestration.py start <pattern_name> [timeout_seconds]
python monitor_orchestration.py <orchestration_id> [timeout_seconds]
```

### Orchestration Workflows

**Long-Running Operations**: Orchestrations can take 10+ minutes due to LLM latency
- **Check processes**: `ps aux | grep claude | grep "??"` to find background agents
- **Find response logs**: Agent outputs in `var/logs/responses/{session_id}.jsonl`
- **Get session IDs**: 
  ```bash
  ksi send monitor:get_events --event-patterns "completion:result" --limit 5 | \
    jq -r '.events[] | select(.data.result.response.session_id) | 
    "\(.timestamp) \(.data.result.response.session_id) \(.data.request_id)"'
  ```
- **Read responses**: `cat var/logs/responses/{session_id}.jsonl | jq`

**Pattern Requirements**:
- Must define concrete agents in `agents:` section
- DSL in `orchestration_logic:` as natural language with commands
- Variables accessible throughout pattern

### Troubleshooting Patterns

**Process Management**:
```bash
# Check for background Claude processes (safe to manage)
ps aux | grep claude | grep "??"

# Check for active Claude Code process (DO NOT KILL)
ps aux | grep claude | grep ttys
```

**JSON Extraction Issues**:
```bash
# Check for extracted events
ksi send monitor:get_events --event-patterns "*" --limit 100 | \
  jq '.events[] | select(.data._extracted_from_response == true)'

# Check for agent feedback
ksi send monitor:get_events --event-patterns "completion:async" --limit 10 | \
  jq '.events[] | select(.data.is_feedback == true)'

# Find agent response logs
ls -lt var/logs/responses/ | head -10
cat var/logs/responses/{session_id}.jsonl | jq
```

**Git Submodule Workflow**:
```bash
# Always commit submodule first, then main repo
cd var/lib/compositions && git add . && git commit -m "submodule changes"
cd /path/to/main && git add . && git commit -m "main repo changes"
```

### Meta-Workflow: Pattern Documentation
**CRITICAL**: When discovering new useful patterns:
1. **Immediately document** in CLAUDE.md (workflows) or project_knowledge.md (technical)
2. **Include examples** - commands, file paths, expected outputs
3. **Note context** - when to use, when not to use
4. **Update this meta-pattern** if the documentation process itself improves

## Common Utilities (ksi_common)

Essential utilities available throughout the codebase:
- **file_utils.py**: File operations, atomic writes, safe path handling
- **cache_utils.py**: Simple memory caching with TTL support
- **event_utils.py**: Event formatting and validation helpers
- **json_utils.py**: Safe JSON operations with error handling
- **logging_utils.py**: Structured logging configuration
- **time_utils.py**: Timestamp formatting and parsing
- **timestamps.py**: Standard timestamp utilities (numeric_to_iso, parse_iso_timestamp)
- **git_utils.py**: Git operations for submodules (save_component, fork_component, sync_submodules)

## Capability System

### Overview
The capability system provides modular permission and knowledge management for agent profiles:
- **Location**: `var/lib/compositions/capabilities/` directory
- **Inheritance**: Capabilities extend other capabilities (e.g., orchestration → base)
- **Documentation**: See `docs/CAPABILITY_SYSTEM_USAGE.md` for full guide

### Common Operations
```bash
# Load and inspect capabilities
ksi send capability:load --name orchestration
ksi send capability:list
ksi send capability:validate --name orchestration

# Resolve profile capabilities
ksi send profile:resolve_capabilities --name "system/orchestrator"
```

### Creating Capabilities
1. **Create YAML file** in `var/lib/compositions/capabilities/`
2. **Define permissions** - what events the capability grants access to
3. **Add knowledge** - instructions and examples for using those permissions
4. **Set inheritance** - extend from base or other capabilities
5. **Test loading** - `ksi send capability:load --name your_capability`

### Profile Integration
```yaml
# In profile YAML - declare capabilities
metadata:
  capabilities:
    - orchestration
    - pattern_discovery

capabilities:
  orchestration: true
  pattern_discovery: true
```

### Built-in Capabilities
- **base**: Fundamental operations (state:get/set, monitor:*)
- **orchestration**: Multi-agent coordination (agent:spawn, orchestration:*)
- **pattern_discovery**: Pattern adaptation (composition:discover/fork)
- **agent_messaging**: Inter-agent communication
- **decision_tracking**: Orchestration analytics

## Orchestration Patterns

For intelligent multi-agent orchestration:
- **Architecture**: See `docs/INTELLIGENT_ORCHESTRATION_PATTERNS.md` for hybrid orchestration approach
- **Pattern Library**: See `var/lib/orchestration_patterns/` for shareable patterns
- **Orchestrator Agents**: Use pattern-aware orchestrators for adaptive workflows

## Test Compositions Pattern

**CRITICAL**: Tests should be compositions, not Python scripts. This enables:
- **Self-testing**: KSI tests itself using its own infrastructure
- **Declarative tests**: Define expected behavior in YAML
- **Reusable patterns**: Test compositions can be extended and evolved
- **No external dependencies**: Tests run entirely within KSI

### Creating Test Compositions

```yaml
# var/lib/compositions/orchestrations/test_feature_x.yaml
name: test_feature_x
type: orchestration
description: Test that feature X works correctly

agents:
  tester:
    profile: base_single_agent
    vars:
      initial_prompt: |
        Test feature X by:
        1. Emit event X with test data
        2. Verify response matches expected format
        3. Report success/failure via orchestration:track

orchestration_logic:
  strategy: |
    GIVEN test_data
    WHEN emit_event("feature:x", test_data)
    THEN verify_response_format
    TRACK test_result

variables:
  test_data: { "key": "test_value" }
  expected_format: { "status": "success", "result": "..." }
```

### Running Test Compositions

```bash
# Run a test composition
ksi send orchestration:start --pattern test_feature_x

# Run all tests matching a pattern
ksi send orchestration:start --pattern "test_*"

# Check test results
ksi send orchestration:query --pattern test_feature_x --field performance.test_results
```

### Test Composition Benefits

1. **Infrastructure testing**: Test KSI features using KSI itself
2. **Evolution**: Tests can evolve through pattern forking/merging
3. **Observability**: All test runs are tracked in event log
4. **Parallelism**: Run multiple test compositions concurrently
5. **Self-documenting**: Test logic is readable in YAML

### Example: Testing Agent Spawning

Instead of `test_prompt_removal.py`, use:

```yaml
name: test_agent_spawn_no_composed_prompt
type: orchestration
description: Verify agents spawn without composed_prompt field

agents:
  test_coordinator:
    profile: base_orchestrator
    vars:
      initial_prompt: |
        1. Spawn a test agent
        2. Check agent:info response
        3. Verify no 'composed_prompt' field exists
        4. Track success/failure
        5. Terminate test agent

orchestration_logic:
  strategy: |
    SPAWN test_agent WITH profile="base_single_agent"
    GET agent_info = agent:info(agent_id=test_agent.id)
    ASSERT "composed_prompt" NOT IN agent_info
    TRACK result
    TERMINATE test_agent
```

## KSI System Monitoring & Discovery

### **✅ CURRENT: Use `monitor:get_status` for System Monitoring**

The KSI hook is working but not displaying output due to a Claude Code bug. **Use these commands for immediate system monitoring:**

```bash
# Get comprehensive system status (recent events + agents)
ksi send monitor:get_status --limit 10

# Monitor with specific patterns or timeframes
ksi send monitor:get_status --event-patterns "evaluation:*" --since "2025-07-15T10:00:00"
ksi send monitor:get_status --include-events --include-agents --limit 5
```

**Monitor provides:** Recent events with timestamps, active agents with status, event counts, system health

### **Discovery System Usage**

**System Overview & Getting Started:**
```bash
ksi help                           # Shows system overview with common commands
ksi discover                       # Lists all 30 namespaces, 191 total events
ksi discover --output-format pretty # Human-readable namespace listing
```

**Namespace Exploration:**
```bash
ksi discover --namespace agent     # Filter to agent namespace (20 events)
ksi discover --namespace monitor   # Monitor namespace (10 events)
ksi discover --namespace evaluation # Evaluation namespace (12 events)
```

**Event Details:**
```bash
ksi help agent:spawn               # Detailed parameters for agent spawning
ksi help monitor:get_status        # Parameters for system monitoring
ksi help evaluation:prompt         # Parameters for prompt evaluation
```

### **Key Namespaces (30 total)**
- **agent** (20): Agent lifecycle and management
- **monitor** (10): Event monitoring and status  
- **evaluation** (12): Testing and evaluation system
- **completion** (10): LLM completion handling
- **composition** (21): Profile and prompt composition
- **orchestration** (8): Multi-agent orchestration
- **state** (11): Entity and relationship management
- **system** (8): Core system functionality

### Legacy Hook Information (For When Fixed)

The hook is working but logs to `/tmp/ksi_hook_diagnostic.log` instead of displaying directly. When fixed, it will show:

- **Format**: `[KSI]` or `[KSI: X events]` or `[KSI: X events, Y agents]`
- **Status indicators**: ✓ for success, ✗ for errors/failures
- **Verbosity control**: `echo ksi_summary`, `echo ksi_verbose`, `echo ksi_errors`

**Current workaround**: Use `ksi send monitor:get_status` for the same monitoring functionality.

**Details**: See `ksi_claude_code/ksi_hook_monitor_filters.txt`

## Quick Reference
```bash
source .venv/bin/activate          # Always first
./daemon_control.py start          # Start daemon
./daemon_control.py status         # Check status
./daemon_control.py restart        # Restart daemon

# Common ksi commands (clean output by default)
ksi discover                       # List all available events
ksi discover --namespace system    # Filter by namespace  
ksi help completion:async          # Get detailed help for an event
ksi send state:set --key config --value '{"theme": "dark"}'
ksi send orchestration:start --pattern simple_echo_test --vars '{"num_messages": 2}'

# Use --health flag for verbose output with connection status
ksi --health discover              # Shows daemon health and discovery results

# Git submodule workflow
cd var/lib/compositions && git status  # Check submodule status
git add . && git commit -m "message"   # Commit changes
git push origin main                   # Push to GitHub
cd ../../.. && git add var/lib/*      # Update parent repo
git commit -m "Update submodules"      # Commit submodule references
```

## WebSocket Bridge & Visualization

Real-time KSI system visualization:
```bash
# Terminal 1: Start daemon
./daemon_control.py start

# Terminal 2: WebSocket bridge
python websocket_bridge.py

# Terminal 3: Web UI
cd ksi_web_ui && python -m http.server 8080
```

Then open http://localhost:8080 to see:
- **Agent Ecosystem**: Real-time agent nodes and relationships
- **State System**: Graph database entities
- **Event Stream**: All KSI events with timestamps

## Available Tools
Task, Bash, Glob, Grep, LS, Read, Edit, MultiEdit, Write, WebFetch, WebSearch

## KSI Integration Tools
**For Python tools to interact with KSI**: See `ksi_claude_code/CLAUDE.md`
- Agent spawning and conversation management
- Real-time observation and monitoring
- Graph database operations
- Composition and capability management

---
**Technical Details**: See `memory/claude_code/project_knowledge.md`