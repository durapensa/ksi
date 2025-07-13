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

### Session ID Management (Critical)
- **NEVER invent session IDs** - claude-cli only accepts session IDs it has generated
- **Claude-cli returns NEW session_id from EVERY request** - even continuation requests
- **Always use session_id from previous response as input**

### Code Hygiene
- **NO bare except clauses** - Always catch specific exceptions
- **Clean as you go** - remove dead code immediately when found
- **Complete transitions** - when moving features, verify functionality then remove old locations

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

# Judge bootstrap protocol (for autonomous evaluation)
python ksi_claude_code/scripts/judge_bootstrap_v2.py --test-suite evaluation/judges --num-variations 5
```

## Common Utilities (ksi_common)

Essential utilities available throughout the codebase:
- **file_utils.py**: File operations, atomic writes, safe path handling
- **cache_utils.py**: Simple memory caching with TTL support
- **event_utils.py**: Event formatting and validation helpers
- **json_utils.py**: Safe JSON operations with error handling
- **logging_utils.py**: Structured logging configuration
- **time_utils.py**: Timestamp formatting and parsing

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

## KSI Hook Monitor
Claude Code has a hook that monitors KSI activity and provides real-time feedback:

- **Output format**: `[KSI]` or `[KSI: X events]` or `[KSI: X events, Y agents]`
- **Status indicators**: ✓ for success, ✗ for errors/failures
- **Test the hook**: Run `echo ksi_check` to verify hook is working
- **Hook only triggers on KSI commands**: Regular bash commands show no output

### Verbosity Control Commands
Control the hook's output verbosity without restarting Claude Code:

```bash
echo ksi_status    # Check current verbosity mode
echo ksi_summary   # Default mode - concise output
echo ksi_verbose   # Show all events with details
echo ksi_errors    # Only show error events
echo ksi_silent    # Temporarily disable output
```

### Hook Output Examples

**Summary mode (default)**:
```
[KSI: 3 events]                    # Basic event count
[KSI: ✗ 1 errors, 5 events]       # Errors highlighted
[KSI: 2 events, 3 agents]          # Agent activity
```

**Verbose mode**:
```
[KSI: 5 new] 19:45:23 ✓ evaluation:prompt
19:45:20 completion:* (×6)
19:45:15 ✓ spawn:agent_123
19:45:10 ✗ ERROR:event:error
```

**Errors mode**:
```
[KSI: 2 errors] 19:45:10 ✗ ERROR:event:error
19:43:20 ✗ agent:spawn failed
```

### Hook Monitoring Protocol
**After KSI-related commands, Claude should see `[KSI]` output.**

### Examples:
```bash
echo ksi_check                     # Should show: [KSI] or [KSI: X events]
./daemon_control.py status         # Should show: [KSI]
ls                                 # Shows: nothing (not KSI-related)
```

### Troubleshooting:
If no [KSI] output after KSI commands:
1. Test with `echo ksi_check`
2. Check current mode with `echo ksi_status`
3. Check `/tmp/ksi_hook_diagnostic.log` for hook execution
4. Restart Claude Code and re-enable hook via `/hooks` menu

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
```

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