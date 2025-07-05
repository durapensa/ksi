# Programmatic Capability Mapping Design

## Vision

Instead of manually listing every event/tool in compositions, we use a smart mapping system that:
1. Maps high-level capabilities to event patterns
2. Auto-generates tool lists based on capabilities
3. Allows optional overrides for special cases
4. Self-documents through code

## Proposed Architecture

### 1. Event Metadata via Decorators

```python
@event_handler("message:publish", 
    capability="agent_messaging",
    description="Publish message to channel",
    requires_auth=True
)
async def handle_publish(data):
    ...

@event_handler("agent:spawn",
    capability="spawn_agents", 
    description="Create child agent",
    requires_auth=True,
    resource_intensive=True
)
async def handle_spawn(data):
    ...
```

### 2. Capability Registry

```python
# ksi_daemon/capabilities.py

CAPABILITY_DEFINITIONS = {
    # Base capabilities every agent needs
    "base": {
        "description": "Essential system access",
        "event_patterns": [
            "system:health",
            "system:help",
        ],
        "always_included": True
    },
    
    # State management
    "state_read": {
        "description": "Read shared state",
        "event_patterns": [
            "state:get",
            "state:list"
        ]
    },
    
    "state_write": {
        "description": "Modify shared state", 
        "event_patterns": [
            "state:set",
            "state:delete"
        ],
        "requires": ["state_read"]  # Dependencies
    },
    
    # Agent communication
    "agent_messaging": {
        "description": "Inter-agent messaging",
        "event_patterns": [
            "message:*",           # All message bus events
            "agent:send_message",  # Direct messaging
            "conversation:active"  # See active conversations
        ],
        "mcp_tools": True  # Expose via MCP
    },
    
    # Agent orchestration
    "spawn_agents": {
        "description": "Create and manage child agents",
        "event_patterns": [
            "agent:spawn",
            "agent:terminate",
            "agent:list",
            "agent:status"
        ],
        "requires": ["agent_messaging"],
        "resource_limits": {
            "max_children": 5,
            "max_depth": 2
        }
    },
    
    # Task coordination
    "multi_agent_todo": {
        "description": "Shared task management",
        "claude_tools": ["TodoRead", "TodoWrite"],  # Maps to Claude's tools
        "event_patterns": ["todo:*"]  # If we had todo events
    },
    
    # External access
    "network_access": {
        "description": "External API and web access",
        "claude_tools": ["WebFetch", "WebSearch"],
        "security_review_required": True
    }
}
```

### 3. Capability Resolver

```python
# ksi_daemon/capabilities/resolver.py

class CapabilityResolver:
    def resolve_tools_for_profile(self, profile: Dict) -> Dict[str, List[str]]:
        """
        Given a profile with capabilities, return allowed/disallowed tools.
        """
        allowed_events = set()
        allowed_claude_tools = set()
        
        # Get capabilities from profile
        capabilities = profile.get("capabilities", {})
        
        # Always include base
        allowed_events.update(self._expand_capability("base"))
        
        # Expand each capability
        for cap_name, enabled in capabilities.items():
            if enabled:
                events, tools = self._expand_capability(cap_name)
                allowed_events.update(events)
                allowed_claude_tools.update(tools)
        
        # Apply overrides
        if "allowed_tools" in profile:
            allowed_events.update(profile["allowed_tools"])
        if "disallowed_tools" in profile:
            allowed_events -= set(profile["disallowed_tools"])
            
        return {
            "allowed_events": list(allowed_events),
            "allowed_claude_tools": list(allowed_claude_tools)
        }
    
    def _expand_capability(self, capability: str) -> Tuple[Set[str], Set[str]]:
        """Expand a capability into event patterns and Claude tools."""
        cap_def = CAPABILITY_DEFINITIONS.get(capability, {})
        
        events = set()
        tools = set()
        
        # Get event patterns
        for pattern in cap_def.get("event_patterns", []):
            if "*" in pattern:
                # Expand wildcard by querying event system
                events.update(self._expand_pattern(pattern))
            else:
                events.add(pattern)
        
        # Get Claude tools
        tools.update(cap_def.get("claude_tools", []))
        
        # Recursively include dependencies
        for required in cap_def.get("requires", []):
            req_events, req_tools = self._expand_capability(required)
            events.update(req_events)
            tools.update(req_tools)
            
        return events, tools
```

### 4. Simplified Composition Profiles

Before (explicit tool lists):
```yaml
name: base_multi_agent
components:
  - name: ksi_tools
    inline:
      allowed_tools:
        - "system:health"
        - "state:get"
        - "state:set"
        - "state:list"
        - "agent:spawn"
        - "agent:list"
        - "agent:status"
        - "agent:send_message"
        - "agent:terminate"
        - "conversation:create"
        - "conversation:active"
        - "message:subscribe"
        - "message:unsubscribe"
        - "message:publish"
        - "message:subscriptions"
```

After (capability-based):
```yaml
name: base_multi_agent
components:
  - name: capabilities
    inline:
      state_write: true
      agent_messaging: true
      spawn_agents: true
      # Tool list auto-generated from capabilities!
      
  - name: tool_overrides
    inline:
      # Optional - only if needed
      additional_tools: ["custom:event"]
      disallowed_tools: ["agent:terminate"]  # More restrictive
```

### 5. Integration Points

**Agent Service**:
```python
# When spawning agent
resolver = CapabilityResolver()
tools = resolver.resolve_tools_for_profile(composed_profile)
agent_info["allowed_events"] = tools["allowed_events"]
agent_info["allowed_claude_tools"] = tools["allowed_claude_tools"]
```

**MCP Server**:
```python
# Instead of querying permissions
tools = self._generate_tools_from_events(
    agent_info["allowed_events"]
)
```

**Claude CLI Provider**:
```python
# Use resolved Claude tools
allowed = ksi_params.get("allowed_claude_tools", [])
```

## Benefits

1. **DRY**: Define tool relationships once
2. **Maintainable**: Add new events → automatically included in right capability
3. **Self-documenting**: Code shows which events belong to which capability
4. **Flexible**: Still allow overrides when needed
5. **Discoverable**: Can query "what tools does agent_messaging give me?"

## Migration Path

1. Create capability registry with current mappings
2. Add capability resolver
3. Update agent service to use resolver
4. Gradually migrate compositions to capability-based
5. Keep backward compatibility for explicit tool lists

## Questions to Resolve

1. Should we store capability metadata in event handlers or separate registry?
2. How to handle Claude-specific tools vs KSI events?
3. Should capabilities have permission levels (read/write/admin)?
4. How to handle tool versioning as we add new events?

What do you think of this approach?