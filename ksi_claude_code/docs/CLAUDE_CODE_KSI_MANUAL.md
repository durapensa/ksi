# Claude Code's KSI Integration Manual

This manual documents how I, Claude Code, interface with the KSI system for multi-agent orchestration, state management, and task execution.

**For practical examples and usage patterns, see [PRACTICAL_GUIDE.md](PRACTICAL_GUIDE.md)**

## Overview

KSI is an event-driven multi-agent system that provides:
- **Agent spawning and lifecycle management** through event-based APIs
- **Conversation continuity** via claude-cli session management
- **Observation system** for monitoring agent behavior
- **Composition system** for dynamic agent creation
- **State management** through a full graph database with entities and relationships

My approach is to use **Python tools that send events to KSI's Unix socket**, providing clean abstractions over the raw protocol.

## Primary Interface: Event-Based Python Tools

I use Python tools that communicate with KSI via Unix socket events:

1. **Direct Socket Communication** - Send JSON events to `/var/run/daemon.sock`
2. **Event-Driven Architecture** - All operations are event-based
3. **Async Support** - Handle async responses and streaming
4. **Type Safety** - TypedDict definitions for event data
5. **Error Handling** - Proper timeout and error management

## Core Tools I Use

### 1. Agent Spawn Tool
```python
# Spawn an agent via completion:async event
tool = AgentSpawnTool()
result = await tool.spawn_agent(
    profile="researcher",  # Or use composition name
    prompt="Research quantum computing impact on cryptography",
    model="claude-cli/sonnet"
)
# Returns: {"request_id": "abc123", "session_id": "generated-id"}

# Continue conversation with existing agent
result = await tool.continue_conversation(
    session_id="previous-session-id",
    prompt="What are the key findings?"
)
```

### 2. Graph State Management
```python
# Create entities and relationships in the graph database
graph_tool = GraphStateTool()

# Create an entity
agent_entity = await graph_tool.create_entity(
    entity_type="agent",
    properties={"name": "researcher", "status": "active"}
)

# Create relationships
await graph_tool.create_relationship(
    from_entity=coordinator.id,
    to_entity=agent_entity.id,
    relationship_type="spawned"
)

# Traverse the graph
network = await graph_tool.traverse_graph(
    start_entity=coordinator.id,
    max_depth=3,
    direction="outgoing"
)

# Simple key-value operations still available
state_tool = StateManagementTool()
await state_tool.set("project:status", {
    "completed_features": ["auth", "database"],
    "current_focus": "api_design"
})

# Query state via state:get event
value = await state_tool.get("project:status")

# Query by pattern via state:query
matches = await state_tool.query_pattern("project:*")
```

### 3. Observation Tools
```python
# Subscribe to agent events
observer = ObservationTool()
subscription = await observer.subscribe(
    target_agent="agent-123",
    event_patterns=["agent:progress:*", "agent:thought:*"]
)

# Process observations
async for observation in observer.stream_observations(subscription):
    if observation["event"] == "agent:progress:update":
        print(f"Progress: {observation['data']['percentage']}%")
```

### 4. Discovery and Introspection Tools

The discovery system provides comprehensive API documentation and event introspection:

```python
# Get comprehensive event documentation with parameters and descriptions
echo '{"event": "system:discover", "data": {"detail": true, "namespace": "composition"}}' | nc -U var/run/daemon.sock

# Multiple output formats supported
echo '{"event": "system:discover", "data": {"format_style": "compact"}}' | nc -U var/run/daemon.sock
echo '{"event": "system:discover", "data": {"format_style": "mcp"}}' | nc -U var/run/daemon.sock

# Get help for specific events  
echo '{"event": "system:help", "data": {"event": "composition:create"}}' | nc -U var/run/daemon.sock

# Filter by namespace, module, or pattern
echo '{"event": "system:discover", "data": {"namespace": "agent", "pattern": "*spawn*"}}' | nc -U var/run/daemon.sock
```

**Key Discovery Features:**
- **Parameter extraction**: Automatically analyzes function signatures and docstrings
- **Event triggers**: Shows which events each handler emits  
- **Multiple formats**: Verbose, compact, ultra-compact, MCP-compatible
- **Comprehensive filtering**: By namespace, module, pattern, or specific events
- **Real-time**: Always reflects current daemon state and loaded modules

**Note**: `system:discover` is the canonical discovery endpoint providing comprehensive API documentation.

## Key Usage Patterns

### 1. Agent Conversations for Complex Tasks

I spawn agents and maintain conversations through session IDs:

```python
# Start a new agent conversation
result = await agent_tool.spawn_agent(
    profile="coordinator",
    prompt="Design and implement real-time chat system"
)
session_id = result["session_id"]

# Continue guiding the agent
await agent_tool.continue_conversation(
    session_id=session_id,
    prompt="Start by analyzing the requirements. What components do we need?"
)

# Agent can spawn sub-agents if it has spawn_agents capability
# I observe their progress through the observation system
```

### 2. Parallel Analysis with Observations

For parallel tasks, I spawn multiple agents and observe their work:

```python
# Spawn multiple analysts
analysts = []
for task in ["auth", "sql", "crypto", "access", "deps"]:
    result = await agent_tool.spawn_agent(
        profile="security_analyst",
        prompt=f"Analyze {task} security aspects"
    )
    analysts.append(result["session_id"])

# Subscribe to their observations
for session_id in analysts:
    subscription = await observer.subscribe(
        target_agent=session_id,
        event_patterns=["agent:finding:*", "agent:complete:*"]
    )
    # Process findings as they arrive
```

### 3. Context Through Conversations

I maintain context through conversation continuity:

```python
# Check for active conversations
active = await conversation_tool.get_active_conversations()

# Find relevant conversation
for conv in active["conversations"]:
    if "project_x" in conv["last_message"]:
        # Continue existing conversation
        await agent_tool.continue_conversation(
            session_id=conv["session_id"],
            prompt="Let's continue working on the API design"
        )
        break
else:
    # Start new conversation
    result = await agent_tool.spawn_agent(
        profile="developer",
        prompt="Let's work on project X API design"
    )
```

## Working with Compositions

### Dynamic Agent Creation

I can create specialized agents using the composition system:

```python
# List available compositions
compositions = await composition_tool.list_compositions(type="profile")

# Create agent with specific composition
result = await agent_tool.spawn_agent(
    profile="base_multi_agent",  # Has spawn_agents capability
    prompt="Coordinate the development of a chat application"
)

# Agent with spawn capability can create sub-agents
await agent_tool.continue_conversation(
    session_id=result["session_id"],
    prompt="Spawn specialized agents for backend, frontend, and testing"
)
```

### Observation-Based Coordination

I coordinate agents through the observation system:

```python
# Spawn analysis coordinator
coordinator = await agent_tool.spawn_agent(
    profile="base_multi_agent",
    prompt="Analyze this codebase comprehensively"
)

# Subscribe to coordinator's spawn events
await observer.subscribe(
    target_agent=coordinator["session_id"],
    event_patterns=["agent:spawn:*", "agent:complete:*"]
)

# Guide coordinator to spawn specialists
await agent_tool.continue_conversation(
    session_id=coordinator["session_id"],
    prompt="Create specialized agents for architecture, performance, and security analysis"
)
```

### Conversation Phases

I guide agents through structured conversation phases:

```python
# Start research conversation
researcher = await agent_tool.spawn_agent(
    profile="researcher",
    prompt=f"Research {topic}. Start with a literature review."
)

# Guide through phases
phases = [
    "Now generate hypotheses based on your findings",
    "Critically analyze the most promising hypotheses", 
    "Synthesize your findings into key insights",
    "What are your final recommendations?"
]

for phase_prompt in phases:
    await agent_tool.continue_conversation(
        session_id=researcher["session_id"],
        prompt=phase_prompt
    )
    # Wait for completion signal or timeout
    await asyncio.sleep(5)
```

## Real-World Patterns

### 1. Session Management
```python
# KSI returns NEW session IDs with each response
# This is how conversation continuity works:

first_result = await agent_tool.spawn_agent(
    prompt="Hello"
)
# Returns: {"request_id": "abc", "session_id": "session-1"}

# Continue conversation - use previous session_id as input
continuation = await agent_tool.continue_conversation(
    session_id="session-1",  # From previous response
    prompt="What did I just say?"
)
# Returns: {"request_id": "def", "session_id": "session-2"}
# Note: NEW session_id returned!
```

### 2. Observation Patterns
```python
# Subscribe to specific agent
subscription = await observer.subscribe(
    target_agent="agent-123",
    event_patterns=["agent:*"]  # All agent events
)

# Process observations
async for obs in observer.stream_observations(subscription["subscription_id"]):
    print(f"{obs['event']}: {obs['data']}")
    
    # Clean up when done
    if obs["event"] == "agent:complete":
        await observer.unsubscribe(subscription["subscription_id"])
        break
```

### 3. Composition Usage
```python
# Get composition details
comp = await composition_tool.get_composition("base_multi_agent")
print(f"Capabilities: {comp['capabilities']}")
# Shows: state_write, agent_messaging, spawn_agents

# Use composition for agent
agent = await agent_tool.spawn_agent(
    profile="base_multi_agent",
    prompt="You can spawn other agents and message them"
)
```

## My Practical Workflow

### 1. Check Active Conversations
```python
# See what conversations are active
active = await conversation_tool.get_active_conversations()
for conv in active["conversations"]:
    print(f"Session: {conv['session_id']}, Last: {conv['last_activity']}")
```

### 2. Spawn or Continue Agents
```python
# For new tasks - spawn fresh agent
if not relevant_conversation_found:
    agent = await agent_tool.spawn_agent(
        profile="researcher",  # or coordinator, developer, etc.
        prompt=user_request
    )
    session_id = agent["session_id"]
else:
    # Continue existing conversation
    session_id = relevant_conversation["session_id"]
    await agent_tool.continue_conversation(
        session_id=session_id,
        prompt=user_request
    )
```

### 3. Guide Through Observations
```python
# Subscribe to agent's work
subscription = await observer.subscribe(
    target_agent=session_id,
    event_patterns=["agent:progress:*", "agent:milestone:*"]
)

# Monitor and guide
async for event in observer.stream_observations(subscription["subscription_id"]):
    if event["event"] == "agent:milestone:complete":
        # Provide next guidance
        await agent_tool.continue_conversation(
            session_id=session_id,
            prompt="Great! Now let's move to the next phase..."
        )
```

### 4. Multi-Agent Coordination
```python
# Spawn coordinator with spawn capability
coordinator = await agent_tool.spawn_agent(
    profile="base_multi_agent",
    prompt="Coordinate analysis of this system"
)

# Guide coordinator to spawn specialists
await agent_tool.continue_conversation(
    session_id=coordinator["session_id"],
    prompt="Please spawn agents for security, performance, and architecture analysis"
)

# Observe all spawned agents
await observer.subscribe(
    target_agent=coordinator["session_id"],
    event_patterns=["agent:spawn:success", "agent:message:*"]
)
```

## Real Example: Refactoring a Codebase

```python
async def refactor_codebase(path: str):
    # Phase 1: Spawn analysis coordinator
    print("Starting codebase analysis...")
    coordinator = await agent_tool.spawn_agent(
        profile="base_multi_agent",
        prompt=f"Analyze codebase at {path} for refactoring opportunities"
    )
    
    # Subscribe to coordinator's events
    sub = await observer.subscribe(
        target_agent=coordinator["session_id"],
        event_patterns=["agent:spawn:*", "agent:finding:*"]
    )
    
    # Phase 2: Guide analysis
    await agent_tool.continue_conversation(
        session_id=coordinator["session_id"],
        prompt="""Spawn specialized agents to analyze:
        1. Code architecture and patterns
        2. Technical debt and code smells
        3. Test coverage and quality
        Report findings as you discover them."""
    )
    
    # Phase 3: Collect findings
    findings = []
    async for event in observer.stream_observations(sub["subscription_id"]):
        if event["event"] == "agent:finding:reported":
            findings.append(event["data"])
        elif event["event"] == "agent:analysis:complete":
            break
    
    # Phase 4: Create refactoring plan
    planner = await agent_tool.spawn_agent(
        profile="architect",
        prompt=f"Create refactoring plan based on findings: {findings}"
    )
    
    # Phase 5: Execute refactoring
    implementer = await agent_tool.spawn_agent(
        profile="developer",
        prompt="Execute the refactoring plan incrementally"
    )
    
    # Guide implementation
    await agent_tool.continue_conversation(
        session_id=implementer["session_id"],
        prompt="Start with the highest priority items. Ensure tests pass after each change."
    )
    
    return coordinator["session_id"], planner["session_id"], implementer["session_id"]
```

## Implementation Details

### Event Protocol
All KSI operations use JSON events over Unix socket:

```python
# Basic event structure
event = {
    "event": "completion:async",
    "data": {
        "prompt": "Hello",
        "model": "claude-cli/sonnet",
        "session_id": "optional-for-continuation"
    }
}

# Send to socket
reader, writer = await asyncio.open_unix_connection("/var/run/daemon.sock")
writer.write(json.dumps(event).encode() + b'\n')
response = await reader.readline()
```

### Key Events I Use:
- `completion:async` - Spawn agents or continue conversations
- `state:set/get/query` - State management
- `observation:subscribe/unsubscribe` - Monitor agents
- `composition:list/get` - Work with compositions
- `conversation:active/get` - Check conversation status

## Best Practices

### 1. Session ID Management
```python
# NEVER invent session IDs - always use what KSI returns
# Each response contains a NEW session_id for continuation

result = await agent_tool.spawn_agent(prompt="Hello")
current_session = result["session_id"]  # Use this for next request

# Continue conversation
next_result = await agent_tool.continue_conversation(
    session_id=current_session,  # From previous response
    prompt="Continue..."
)
current_session = next_result["session_id"]  # Update for next request
```

### 2. Observation Lifecycle
```python
# Always unsubscribe when done
subscription = await observer.subscribe(target_agent=agent_id)
try:
    async for event in observer.stream_observations(subscription["subscription_id"]):
        # Process events
        pass
finally:
    await observer.unsubscribe(subscription["subscription_id"])
```

### 3. Error Handling
```python
# Check for daemon connectivity
if not Path("/var/run/daemon.sock").exists():
    raise RuntimeError("KSI daemon not running")

# Handle event errors
result = await send_event(event_data)
if not result.get("success", False):
    error = result.get("error", "Unknown error")
    raise RuntimeError(f"KSI error: {error}")
```

## Working with KSI's Architecture

### Understanding Compositions

Compositions define agent capabilities and behaviors. Key compositions:
- `base_single_agent` - Basic agent with file access
- `base_multi_agent` - Can spawn other agents  
- `researcher`, `developer`, `coordinator` - Specialized roles

### Capability System

Agents have capabilities that determine what they can do:
- `file_access` - Read/write files via Claude tools
- `network_access` - Web search and fetch
- `state_write` - Modify shared state
- `spawn_agents` - Create child agents
- `agent_messaging` - Communicate with other agents

```python
# Check what a composition can do
comp = await composition_tool.get_composition("base_multi_agent")
print(comp["capabilities"])
# Output: {"spawn_agents": true, "agent_messaging": true, "state_write": true}
```

### State Management Patterns

KSI uses a simple key-value store for shared state:

```python
# Store analysis results
await state_tool.set("analysis:security:findings", {
    "vulnerabilities": [...],
    "severity": "high",
    "timestamp": datetime.utcnow().isoformat()
})

# Query by pattern
all_analyses = await state_tool.query_pattern("analysis:*")
for key, value in all_analyses.items():
    print(f"{key}: {value['severity']}")

# Clean up old state
for key in all_analyses:
    if is_old(key):
        await state_tool.delete(key)
```

### Conversation Management

Conversations are the primary way to interact with agents:

```python
# Get active conversations
active = await conversation_tool.get_active_conversations(
    max_age_hours=24  # Only recent conversations
)

# Find specific conversation
for conv in active["conversations"]:
    if conv["agent_profile"] == "researcher" and "AI safety" in conv["last_message"]:
        # Continue this conversation
        await agent_tool.continue_conversation(
            session_id=conv["session_id"],
            prompt="What are the most promising approaches you found?"
        )

# Export conversation for analysis
export = await conversation_tool.export_conversation(
    session_id=conv["session_id"],
    format="markdown"
)
```

### Event-Driven Coordination

All agent coordination happens through events:

```python
# Agent spawns child via event
# (If agent has spawn_agents capability)
await agent_tool.continue_conversation(
    session_id=coordinator_session,
    prompt="Spawn a security analyst to review authentication"
)

# Observe the spawn event
async for event in observer.stream_observations(subscription_id):
    if event["event"] == "agent:spawn:success":
        child_id = event["data"]["agent_id"]
        print(f"Child agent spawned: {child_id}")
        
        # Subscribe to child's events too
        child_sub = await observer.subscribe(
            target_agent=child_id,
            event_patterns=["agent:finding:*"]
        )
```

## Common Patterns and Examples

### 1. Research Task Pattern
```python
async def research_topic(topic: str):
    # Spawn researcher
    researcher = await agent_tool.spawn_agent(
        profile="researcher",
        prompt=f"Research {topic}. Start with an overview."
    )
    
    # Guide through research phases
    phases = [
        "What are the key concepts and terminology?",
        "What are the current challenges?",
        "What solutions are being explored?",
        "What are your recommendations?"
    ]
    
    for phase in phases:
        await agent_tool.continue_conversation(
            session_id=researcher["session_id"],
            prompt=phase
        )
        await asyncio.sleep(3)  # Let agent work
    
    return researcher["session_id"]
```

### 2. Code Analysis Pattern
```python
async def analyze_codebase(path: str):
    # Spawn coordinator with multi-agent capability
    coordinator = await agent_tool.spawn_agent(
        profile="base_multi_agent",
        prompt=f"Analyze the codebase at {path}"
    )
    
    # Subscribe to observe child agents
    sub = await observer.subscribe(
        target_agent=coordinator["session_id"],
        event_patterns=["agent:spawn:*", "agent:finding:*"]
    )
    
    # Guide coordinator
    await agent_tool.continue_conversation(
        session_id=coordinator["session_id"],
        prompt="""Spawn specialized agents to analyze:
        1. Code quality and maintainability
        2. Security vulnerabilities
        3. Performance bottlenecks
        Coordinate their findings into a report."""
    )
    
    # Collect findings
    findings = []
    async for event in observer.stream_observations(sub["subscription_id"]):
        if event["event"] == "agent:finding:reported":
            findings.append(event["data"])
    
    return findings
```

### 3. Interactive Development Pattern
```python
async def develop_feature(description: str):
    # Start with planning
    developer = await agent_tool.spawn_agent(
        profile="developer",
        prompt=f"Let's develop: {description}. What's your implementation plan?"
    )
    
    # Interactive development loop
    while True:
        # Get user feedback
        user_input = input("> ")
        
        if user_input.lower() in ["done", "exit"]:
            break
            
        # Continue conversation
        result = await agent_tool.continue_conversation(
            session_id=developer["session_id"],
            prompt=user_input
        )
        
        # Check if agent needs to spawn helpers
        if "need help with" in result.get("response", "").lower():
            await agent_tool.continue_conversation(
                session_id=developer["session_id"],
                prompt="If you need specialized help, feel free to describe what assistance you need."
            )
    
    return developer["session_id"]
```

### 4. Observation-Based Monitoring
```python
async def monitor_long_task(agent_id: str):
    # Subscribe to multiple event types
    sub = await observer.subscribe(
        target_agent=agent_id,
        event_patterns=[
            "agent:progress:*",
            "agent:milestone:*",
            "agent:error:*",
            "agent:thought:*"
        ]
    )
    
    try:
        async for event in observer.stream_observations(sub["subscription_id"]):
            event_type = event["event"]
            data = event["data"]
            
            if "progress" in event_type:
                print(f"Progress: {data.get('percentage', 0)}%")
            elif "milestone" in event_type:
                print(f"Milestone: {data.get('name', 'Unknown')}")
            elif "error" in event_type:
                print(f"Error: {data.get('message', 'Unknown error')}")
                # Might need intervention
            elif "thought" in event_type:
                print(f"Thinking: {data.get('content', '')}")
                
            # Check if task complete
            if event_type == "agent:task:complete":
                break
                
    finally:
        await observer.unsubscribe(sub["subscription_id"])
```

## Summary

This manual documents my practical approach to using KSI for multi-agent orchestration. The key insights are:

1. **Event-driven communication** - All interactions happen through JSON events
2. **Session-based conversations** - Maintain context through session IDs
3. **Observation system** - Monitor agent behavior in real-time
4. **Composition-based capabilities** - Agents have specific abilities based on their composition
5. **Simple state management** - Share data between agents via key-value store

By using these patterns, I can effectively coordinate complex multi-agent workflows, maintain conversation continuity, and build sophisticated solutions through agent collaboration.