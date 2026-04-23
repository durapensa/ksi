# JSON Parameter Parsing Patterns in KSI

## Overview

The KSI system needs to handle parameters that might arrive as JSON strings from various external sources. This guide documents when and how to use `parse_json_parameter`.

## When to Use parse_json_parameter

### Use it for External-Facing Parameters

Parameters that come from **outside the daemon** might be JSON strings:

1. **CLI Parameters**
   - `--vars '{"model": "opus", "temperature": 0.7}'`
   - `--filter '{"type": "orchestration"}'`
   - `--properties '{"status": "active"}'`
   - `--metadata '{"tags": ["important"]}'`

2. **Agent-Emitted Events**
   - Agents often construct JSON in their text responses
   - The system extracts these and they arrive as strings
   - Example: An agent emitting `{"event": "state:entity:create", "data": {"properties": "..."}}`

3. **MCP Server Parameters**
   - MCP tools follow system parameter guidelines
   - May send structured data as JSON strings
   - Will become more common as MCP adoption grows

4. **External API Calls**
   - WebSocket clients
   - HTTP API endpoints
   - Any external integration

### Don't Use it for Internal Parameters

Parameters that flow **between daemon services** are already Python objects:

1. **System Context**
   - `context` parameter in handlers
   - Contains `_originator_id`, `_agent_id`, etc.
   - Flows programmatically between handlers

2. **Event Routing Data**
   - Internal event metadata
   - System-injected fields
   - Service-to-service communication

3. **Selection Context**
   - Used internally for dynamic spawn mode
   - Already a proper Python dict

## Common Parameters Needing JSON Parsing

Based on system analysis, these parameters commonly need JSON parsing:

### Currently Implemented
- `filter` - Query filtering (composition:list)
- `vars` - Variables for orchestrations (orchestration:start)
- `properties` - Entity properties (state:entity:create/update)
- `metadata` - Additional structured data (various handlers)

### Candidates for Addition
- `variables` - Alternative to `vars` in some handlers
- `config` - Configuration objects
- `payload` - Message payloads (orchestration:message)
- `message` - Message data (messaging:publish)

## Implementation Pattern

```python
@event_handler("some:event")
async def handle_some_event(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
    # For regular handlers
    from ksi_common.json_utils import parse_json_parameter
    data = event_format_linter(raw_data, SomeEventData)
    
    # Parse external-facing parameters that might be JSON strings
    parse_json_parameter(data, 'properties')
    parse_json_parameter(data, 'metadata')
    
    # For system handlers that need metadata
    clean_data, system_metadata = extract_system_handler_data(raw_data)
    parse_json_parameter(clean_data, 'properties')
```

## Key Principles

1. **Parse at Entry Points Only**
   - Parse JSON strings when data enters the system
   - Use Python objects internally
   - Never stringify and re-parse

2. **External vs Internal**
   - External sources: might send JSON strings
   - Internal services: use Python objects

3. **Safe by Default**
   - `parse_json_parameter` safely handles:
     - Missing parameters (returns None)
     - Non-string values (returns None)
     - Invalid JSON (logs warning, returns None)

4. **Merge Behavior**
   - By default, parsed JSON is merged into the data dict
   - Original string parameter is removed
   - Both behaviors can be controlled with function arguments

## Anti-Patterns to Avoid

1. **Don't parse system context**
   ```python
   # ❌ Wrong
   parse_json_parameter(data, 'context')
   
   # ✅ Context is already an object
   context = data.get('context', {})
   ```

2. **Don't double-parse**
   ```python
   # ❌ Wrong
   json_str = json.dumps(data)
   parsed = json.loads(json_str)
   
   # ✅ Use the data directly
   result = process(data)
   ```

3. **Don't parse between services**
   ```python
   # ❌ Wrong - internal service communication
   await emit_event("internal:event", json.dumps({"data": value}))
   
   # ✅ Pass Python objects
   await emit_event("internal:event", {"data": value})
   ```

## Testing Considerations

When testing handlers with JSON parameters:

1. **Test both forms**
   - As string: `{"properties": '{"key": "value"}'}`
   - As object: `{"properties": {"key": "value"}}`

2. **Test edge cases**
   - Invalid JSON strings
   - Missing parameters
   - Non-string values

3. **Test external sources**
   - CLI commands with JSON parameters
   - Agent responses with embedded JSON
   - MCP tool outputs

## Future Considerations

As the system evolves:

1. **More MCP Integration**
   - MCP servers will send more structured data
   - May need additional parameter parsing

2. **Agent Sophistication**
   - Agents generating more complex JSON
   - May need nested JSON parsing

3. **API Expansion**
   - More external integrations
   - Consistent parameter handling across all entry points

Remember: The goal is to make external data consumption seamless while keeping internal data flow efficient and type-safe.