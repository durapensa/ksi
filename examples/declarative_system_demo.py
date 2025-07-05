#!/usr/bin/env python3
"""
Demo showing how the declarative capability system would work.

Key insights:
1. Code contains only event handlers grouped by module
2. YAML declares which events belong to which capabilities  
3. Most Claude tools are generated from our events
4. Compositions become very simple
"""

# Mock the resolver for demo purposes
class MockCapabilityResolver:
    def resolve_capabilities_for_profile(self, capabilities):
        # Simulate resolution
        expanded = ["base"]
        events = ["system:health", "system:help"]
        tools = []
        
        if capabilities.get("state_write"):
            expanded.extend(["state_read", "state_write"])
            events.extend(["state:get", "state:set", "state:delete", "state:list"])
            
        if capabilities.get("agent_messaging"):
            expanded.append("agent_messaging")
            events.extend(["message:publish", "message:subscribe", "agent:send_message"])
            
        if capabilities.get("spawn_agents"):
            expanded.extend(["spawn_agents", "agent_messaging"])  # Dependencies
            events.extend(["agent:spawn", "agent:terminate", "agent:list"])
            
        if capabilities.get("multi_agent_todo"):
            tools.extend(["TodoRead", "TodoWrite"])
            
        return {
            "expanded_capabilities": expanded,
            "allowed_events": events,
            "allowed_claude_tools": tools
        }
    
    def get_security_profile(self, name):
        if name == "orchestrator":
            return {
                "description": "Full orchestration capabilities",
                "capabilities": ["base", "state_write", "agent_messaging", "spawn_agents", 
                               "composition_access", "system_monitoring"],
                "claude_tools": ["file_access", "multi_agent_todo"]
            }
        return None
        
    def get_mcp_tools_for_events(self, events):
        tools = []
        for event in events:
            tools.append({
                "name": f"ksi_{event.replace(':', '_')}",
                "description": f"Execute {event} - dynamically generated from event"
            })
        return tools

def get_capability_resolver():
    return MockCapabilityResolver()

def show_simple_composition():
    """Show how simple compositions become."""
    print("=== Simplified Composition ===")
    print("""
# Before: 30+ lines listing every event/tool
name: multi_agent_orchestrator
components:
  - name: ksi_tools
    inline:
      allowed_tools:
        - "system:health"
        - "state:get"
        - "state:set"
        - "agent:spawn"
        - "agent:list"
        - "message:publish"
        ... 20 more lines ...
        
# After: 3 lines of capabilities
name: multi_agent_orchestrator  
components:
  - name: capabilities
    inline:
      spawn_agents: true      # Includes agent:*, dependencies
      multi_agent_todo: true  # Adds TodoRead/TodoWrite
      network_access: true    # Adds WebFetch/WebSearch
    """)


def show_code_simplification():
    """Show how code becomes simpler."""
    print("\n=== Simplified Event Handlers ===")
    print("""
# Before: Decorated with capability metadata
@event_handler("message:publish",
    capability="agent_messaging",
    description="Publish to channel",
    requires_auth=True,
    mcp_visible=True)
async def handle_publish(data):
    ...

# After: Just the handler - metadata in YAML
@event_handler("message:publish")
async def handle_publish(data):
    \"\"\"Publish message to channel.\"\"\"
    channel = data["channel"]
    message = data["message"]
    # ... implementation ...
    """)


def demo_resolution():
    """Demo the resolution process."""
    resolver = get_capability_resolver()
    
    print("\n=== Resolution Examples ===")
    
    # Example 1: Simple agent
    print("\n1. Simple Agent Profile:")
    simple = resolver.resolve_capabilities_for_profile({
        "state_write": True,
        "agent_messaging": True
    })
    print(f"  Expanded capabilities: {simple['expanded_capabilities']}")
    print(f"  Allowed events: {', '.join(simple['allowed_events'][:5])}...")
    print(f"  Claude tools: {simple['allowed_claude_tools']}")
    
    # Example 2: Orchestrator
    print("\n2. Orchestrator Profile:")
    orchestrator = resolver.resolve_capabilities_for_profile({
        "spawn_agents": True,
        "multi_agent_todo": True,
        "composition_access": True
    })
    print(f"  Expanded capabilities: {orchestrator['expanded_capabilities']}")
    print(f"  Event count: {len(orchestrator['allowed_events'])}")
    print(f"  Claude tools: {orchestrator['allowed_claude_tools']}")
    
    # Example 3: Security profile
    print("\n3. Using Security Profile:")
    profile = resolver.get_security_profile("orchestrator")
    if profile:
        print(f"  Description: {profile['description']}")
        print(f"  Capabilities: {', '.join(profile['capabilities'][:5])}...")
        print(f"  Claude tools: {profile.get('claude_tools', [])}")


def show_mcp_generation():
    """Show how MCP tools are generated from events."""
    resolver = get_capability_resolver()
    
    print("\n=== MCP Tool Generation ===")
    print("Events are automatically exposed as MCP tools:")
    
    events = ["agent:spawn", "message:publish", "state:get"]
    tools = resolver.get_mcp_tools_for_events(events)
    
    for tool in tools:
        print(f"\nEvent: {tool['name'].replace('ksi_', '').replace('_', ':')}")
        print(f"MCP Tool: {tool['name']}")
        print(f"Description: {tool['description']}")


def show_integration_points():
    """Show how this integrates with existing systems."""
    print("\n=== System Integration ===")
    print("""
1. Agent Service (spawn):
   - Read composition capabilities
   - Call resolver.resolve_capabilities_for_profile()
   - Store allowed_events and allowed_claude_tools

2. MCP Server (tool generation):
   - Get agent's allowed_events
   - Call resolver.get_mcp_tools_for_events()
   - Return generated tool schemas

3. Permission Service:
   - Focus only on security (filesystem, resources)
   - Use resolver.validate_event_access() for checks

4. Completion Service:
   - Pass allowed_claude_tools to Claude CLI
   - No need to query permissions again
    """)


def show_benefits():
    """Summarize the benefits."""
    print("\n=== Benefits ===")
    print("""
1. Single Source of Truth:
   - capability_mappings.yaml defines everything
   - No duplication between code and configs

2. Maintainability:
   - Add new event? Just update YAML
   - Change capability grouping? Just update YAML
   - No code changes needed

3. Discoverability:
   - Can query which events belong to capability
   - Can see all capability dependencies
   - Security profiles are explicit

4. Simplicity:
   - Compositions are 3-5 lines
   - Event handlers are just functions
   - No complex decorators needed

5. Dynamic Tool Generation:
   - Most Claude tools come from our events
   - MCP automatically exposes allowed events
   - No manual tool list maintenance
    """)


if __name__ == "__main__":
    show_simple_composition()
    show_code_simplification()
    demo_resolution()
    show_mcp_generation()
    show_integration_points()
    show_benefits()