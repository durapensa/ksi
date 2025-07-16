# KSI Project Knowledge for Claude Code

Essential technical reference for developing and using KSI (Knowledge System Infrastructure) - an event-driven orchestration system for autonomous AI agents.

**Purpose**: This document contains the critical knowledge Claude Code needs to effectively work with KSI. Focus is on current patterns, validated examples, and practical usage.

## Core Concepts

### Event-Driven Architecture
Everything in KSI communicates through events. No direct module imports, no shared state, just events.

```bash
# Using the ksi CLI (preferred)
ksi send state:set --key mykey --value "myvalue"
ksi send agent:spawn --profile base_single_agent --prompt "Do something"

# Direct socket (when ksi unavailable)
echo '{"event": "state:get", "data": {"key": "mykey"}}' | nc -U var/run/daemon.sock
```

### Composition System
All configurations (profiles, prompts, orchestrations) are YAML compositions stored in git submodules.

```bash
# Create components using events (NEW!)
ksi send composition:create_component --name "components/mycomponent" --content "# My Component"
ksi send composition:get_component --name "components/mycomponent"
ksi send composition:fork_component --parent "base" --name "variant"

# Work with compositions
ksi send composition:get --name base_single_agent --type profile
ksi send composition:create --type prompt --name myprompt --content "Do this task"
ksi send composition:list --type profile
```

## Development Patterns

### Creating Event Handlers
```python
from ksi_daemon.event_system import event_handler
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder

@event_handler("mymodule:myevent")
async def handle_my_event(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
    # ALWAYS: Parse data with TypedDict for type safety
    data = event_format_linter(raw_data, MyEventData)
    
    # Process the event
    result = {"status": "success", "value": data['key']}
    
    # ALWAYS: Return standardized response
    return event_response_builder(result, context=context)
```

### TypedDict Patterns for Discovery
```python
from typing import TypedDict, NotRequired, Required

class MyEventData(TypedDict):
    """Event data for my:event."""
    key: Required[str]  # The key to look up
    format: NotRequired[Literal['json', 'yaml']]  # Output format: 'json' or 'yaml'
    limit: NotRequired[int]  # Maximum results to return (default: 10)
```

### Configuration Management
```python
from ksi_common.config import config

# NEVER hardcode paths!
log_path = config.daemon_log_dir / "mymodule.log"  # ✓ Good
log_path = Path("var/logs/daemon/mymodule.log")    # ✗ Bad

# Available config properties:
# config.socket_path, config.db_dir, config.compositions_dir, config.evaluations_dir
```

## Working with Agents

### Agent Spawning
```bash
# Basic agent spawn
ksi send agent:spawn --profile base_single_agent --prompt "Analyze this data"

# With orchestration context
ksi send agent:spawn --profile worker --orchestration my_orchestration \
  --vars '{"task": "process_data", "priority": "high"}'

# Spawn returns agent_id for tracking
{"agent_id": "agent_abc123", "status": "spawned"}
```

### Agent Profiles

Key profiles and their purposes:
- **base_single_agent**: Simple tasks, no multi-agent coordination
- **base_multi_agent**: Can spawn children and send messages
- **base_orchestrator**: Pattern-aware orchestration with DSL interpretation

### Agent JSON Event Emission
Agents emit events by including JSON in their responses:

```
I'll analyze the data now. {"event": "orchestration:track", "data": {"stage": "analysis_start"}}

The analysis shows interesting patterns. {"event": "state:set", "data": {"key": "results", "value": {"score": 0.95}}}

Analysis complete. {"event": "agent:task_complete", "data": {"status": "success"}}
```

## Orchestration Patterns

### Creating Orchestrations
```yaml
# var/lib/compositions/orchestrations/my_pattern.yaml
name: my_pattern
type: orchestration
agents:
  coordinator:
    profile: base_orchestrator
    vars:
      pattern_name: "my_pattern"
  
  worker:
    profile: base_single_agent
    vars:
      task: "{{task_description}}"

orchestration_logic:
  strategy: |
    SPAWN worker WITH task="analyze data"
    AWAIT worker COMPLETION
    TRACK results
    CLEANUP all agents

variables:
  task_description: "Default task"
```

### Running Orchestrations
```bash
# Start orchestration
ksi send orchestration:start --pattern my_pattern --vars '{"task_description": "custom task"}'

# Monitor progress (orchestrations can take 10+ minutes!)
python monitor_orchestration.py orch_abc123

# Check for background agents
ps aux | grep claude | grep "??"  # Safe to manage (spawned by KSI)
ps aux | grep claude | grep ttys   # DO NOT KILL (Claude Code itself)
```

## State System (Graph Database)

### Entity Management
```bash
# Create entity
ksi send state:create_entity --type user --attributes '{"name": "Alice", "role": "analyst"}'

# Update entity
ksi send state:update_entity --entity_id "ent_123" --attributes '{"status": "active"}'

# Query entities
ksi send state:query_entities --entity_type user --filters '{"role": "analyst"}'
```

### Relationship Management
```bash
# Create relationship
ksi send state:create_relationship --from_id "ent_123" --to_id "ent_456" \
  --type "supervises" --attributes '{"since": "2024-01-01"}'

# Query graph
ksi send state:query_graph --start_entity "ent_123" --max_depth 2
```

## Discovery System

### Finding Events
```bash
# List all events
ksi discover

# Filter by namespace
ksi discover --namespace agent

# Get detailed help
ksi help agent:spawn
```

### Best Practices for Discovery
1. Always use discovery before reading source code
2. The `ksi help` command shows parameter types and descriptions
3. TypedDict annotations are automatically extracted
4. Inline comments become parameter documentation

## Evaluation System

### Running Evaluations
```bash
# Evaluate a prompt
ksi send evaluation:prompt --prompt "Test this prompt" --test_suite basic_effectiveness

# Compare multiple prompts
ksi send evaluation:compare --prompts '["prompt1", "prompt2"]' \
  --test_suite reasoning_tasks --format detailed
```

### Test Suite Structure
```yaml
# var/lib/evaluations/test_suites/my_tests.yaml
name: my_tests
tests:
  - name: test_greeting
    prompt: "Say hello"
    evaluators:
      - type: contains_any
        patterns: ["hello", "hi", "greetings"]
        weight: 1.0
```

## Progressive Component System

### Phase 3 Complete: Advanced Rendering
✅ **ComponentRenderer system** with recursive mixin resolution
✅ **Variable substitution** with complex data types and defaults
✅ **Circular dependency detection** prevents infinite loops
✅ **Performance tested** up to 10-level inheritance chains
✅ **Conditional mixins** based on environment variables
✅ **Comprehensive caching** with 60x+ speedup on repeated renders

### Phase 4 In Progress: KSI System Integration
Component creation and rendering now integrates deeply with KSI event system:

```bash
# Create components
ksi send composition:create_component \
  --name "components/instructions/my_instruction" \
  --content "# My Instruction\n\nDo this specific thing..." \
  --description "Custom instruction component"

# Render components with variables
ksi send composition:render_component \
  --component "components/adaptive_agent" \
  --vars '{"mode": "analysis", "environment": "production"}'

# Generate orchestration from component
ksi send composition:generate_orchestration \
  --component "components/complex_workflow" \
  --pattern_name "workflow_orchestration"

# Spawn agent from component
ksi send agent:spawn_from_component \
  --component "components/specialized_analyst" \
  --vars '{"domain": "financial", "depth": "detailed"}'
```

### Component System Architecture
- **ksi_common/component_renderer.py**: Core rendering with caching
- **ksi_common/frontmatter_utils.py**: Robust frontmatter parsing
- **ksi_common/yaml_utils.py**: Modern YAML processing
- **ksi_daemon/composition/composition_service.py**: Event handlers

## Common Operations

### Daemon Management
```bash
./daemon_control.py start|stop|restart|status|health
./daemon_control.py dev  # Auto-restart on code changes
```

### Monitoring
```bash
# System status with recent events
ksi send monitor:get_status --limit 10

# Filter events by pattern
ksi send monitor:get_events --event-patterns "agent:*" --since "2025-01-01T00:00:00"

# Check agent statuses
ksi send agent:list
```

### Git Submodule Workflow
```bash
# After making changes via KSI events
cd var/lib/compositions
git status  # See what changed
git push origin main  # Push to GitHub

# Update parent repo
cd ../../..
git add var/lib/compositions
git commit -m "Update composition submodule"
```

## Debugging

### Enable Debug Logging
```bash
KSI_LOG_LEVEL=DEBUG ./daemon_control.py restart
tail -f var/logs/daemon/daemon.log
```

### Finding Agent Responses
```bash
# Get recent completion results with session IDs
ksi send monitor:get_events --event-patterns "completion:result" --limit 5 | \
  jq -r '.events[] | select(.data.result.response.session_id) | .data.result.response.session_id'

# Read agent response
cat var/logs/responses/{session_id}.jsonl | jq
```

### Common Issues

**Agents not executing prompts**:
- Check if profile has `prompt` field for receiving prompts
- Verify orchestration pattern includes concrete agents in `agents:` section
- Use `ksi send agent:info --agent-id {id}` to check agent state

**JSON extraction not working**:
- Agents must output valid JSON: `{"event": "name", "data": {...}}`
- Check for feedback events indicating malformed JSON
- Look in response logs for actual agent output

**Component creation fails**:
- Git submodules must be initialized: `git submodule update --init`
- Check write permissions on var/lib/compositions
- Ensure no duplicate component names without `--overwrite`

## Best Practices

### Event Design
- Use namespaces: `module:action` (e.g., `agent:spawn`, `state:get`)
- Return single object for single response, array for multiple
- Always use TypedDict for parameter documentation
- Include inline comments for discovery system

### Error Handling
- No bare except clauses - catch specific exceptions
- Use `error_response()` for handler errors
- Include helpful error messages for users

### Performance
- Long operations (10+ seconds) should use async patterns
- Monitor background processes with `ps aux | grep claude`
- Use `monitor_orchestration.py` for patient polling
- Remember: LLM calls take 2-30+ seconds each

### Testing
- Use composition:create_component for test components
- Create test orchestrations as compositions
- Use evaluation system for prompt testing
- Always verify with `ksi discover` after adding events

## Session Management Critical Rules

1. **NEVER create session IDs** - only claude-cli creates them
2. **Each completion returns NEW session_id** - use it for next request
3. **Response logs** use session_id as filename
4. **Agent logs** in `var/logs/responses/{session_id}.jsonl`

---
*This is a living document. Update immediately when discovering new patterns.*
*For user-facing documentation, see CLAUDE.md*