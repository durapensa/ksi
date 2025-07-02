# Daemon Events Knowledge

You have knowledge of the KSI daemon's event-based architecture:

## Core Events

### System Events
- `system:startup` - Daemon initialization
- `system:shutdown` - Graceful shutdown
- `system:health` - Health check
- `system:discover` - Event discovery
- `system:help` - Get help for events

### Composition Events
- `composition:list` - List available compositions
- `composition:get` - Get composition details
- `composition:compose` - Compose configuration
- `composition:profile` - Compose a profile
- `composition:prompt` - Compose a prompt
- `composition:select` - Select best composition
- `composition:create` - Create dynamic composition
- `composition:validate` - Validate composition

### Agent Events
- `agent:spawn` - Create new agent
- `agent:terminate` - Stop agent
- `agent:list` - List active agents
- `agent:send_message` - Send message to agent
- `agent:update_composition` - Update agent composition
- `agent:discover_peers` - Find other agents
- `agent:negotiate_roles` - Coordinate roles

### Other Services
- `completion:async` - Request AI completion
- `permission:set_agent` - Set agent permissions
- `sandbox:create` - Create agent sandbox
- `state:get/set` - State management
- `monitor:get_events` - Monitor events

Use this knowledge to help with daemon operations and event handling.