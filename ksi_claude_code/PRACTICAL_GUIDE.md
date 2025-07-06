# Practical Guide to Using ksi_claude_code

This guide shows real, working patterns for using KSI with Claude Code.

## Understanding KSI's Architecture

Before diving in, understand these key concepts:

1. **Agents are conversations** - Each agent maintains context through a conversation
2. **Session IDs change** - claude-cli returns a new session_id with each response
3. **Observation is async** - Subscribe to events to monitor progress
4. **Compositions are dynamic** - Create/edit agent profiles via events

## Basic Usage Patterns

### 1. Simple Agent Interaction

```python
from ksi_claude_code import ConversationTool

conv_tool = ConversationTool()

# Start a conversation with an agent
result = await conv_tool.start_conversation(
    profile="researcher",
    initial_prompt="Analyze the security vulnerabilities in this Python code: ..."
)

print(f"Response: {result['response']}")
print(f"New session ID: {result['session_id']}")

# Continue the conversation
result = await conv_tool.continue_conversation(
    session_id=result['session_id'],
    message="Can you focus specifically on SQL injection risks?"
)
```

### 2. Monitoring Agent Progress

```python
from ksi_claude_code import ObservationTool

obs_tool = ObservationTool()

# Start monitoring an agent
async for event in obs_tool.observe_agent(session_id):
    if event['type'] == 'progress':
        print(f"Progress: {event['percentage']}% - {event['message']}")
    elif event['type'] == 'milestone':
        print(f"Completed: {event['name']}")
    elif event['type'] == 'thought':
        print(f"Thinking: {event['content']}")
```

### 3. Multi-Agent Coordination

```python
from ksi_claude_code import ConversationTool, ObservationTool

conv_tool = ConversationTool()
obs_tool = ObservationTool()

# Create a research team
researcher = await conv_tool.start_conversation(
    "researcher", 
    "Research best practices for API design"
)

critic = await conv_tool.start_conversation(
    "critic",
    f"Review these research findings: {researcher['response']}"
)

synthesizer = await conv_tool.start_conversation(
    "synthesizer",
    f"""Synthesize these perspectives:
    Research: {researcher['response']}
    Critique: {critic['response']}"""
)
```

## Advanced Patterns

### 1. Phased Conversations

```python
from ksi_claude_code import ConversationTool

conv_tool = ConversationTool()

# Phase 1: Understanding
result = await conv_tool.start_conversation(
    "analyst",
    "Help me understand this legacy codebase"
)

# Phase 2: Analysis
result = await conv_tool.continue_conversation(
    result['session_id'],
    "Now analyze the architecture and identify improvement areas"
)

# Phase 3: Planning
result = await conv_tool.continue_conversation(
    result['session_id'],
    "Create a refactoring plan based on your analysis"
)

# Phase 4: Implementation guidance
result = await conv_tool.continue_conversation(
    result['session_id'],
    "Guide me through implementing the first phase of refactoring"
)
```

### 2. Creating Custom Agent Profiles

```python
from ksi_claude_code import CompositionTool

comp_tool = CompositionTool()

# Create a specialized security auditor
auditor_id = await comp_tool.create_composition(
    name="security_auditor_custom",
    base_profile="analyst",
    components=[
        {
            "type": "fragment",
            "source": "security/owasp_top_10.md"
        },
        {
            "type": "instruction",
            "content": "Always check for SQL injection, XSS, and CSRF vulnerabilities"
        }
    ],
    capabilities={
        "file_access": True,
        "state_write": True
    }
)

# Use the custom profile
result = await conv_tool.start_conversation(
    profile=auditor_id,
    initial_prompt="Audit this web application"
)
```

### 3. Parallel Analysis with Result Aggregation

```python
from ksi_claude_code import batch_analysis

# Analyze different aspects in parallel
aspects = [
    ("performance", "Analyze performance bottlenecks"),
    ("security", "Identify security vulnerabilities"),
    ("maintainability", "Assess code maintainability"),
    ("scalability", "Evaluate scalability concerns")
]

results = await batch_analysis("analyst", aspects)

# Aggregate findings
aggregator = await conv_tool.start_conversation(
    "synthesizer",
    f"Synthesize these analyses into priorities: {results}"
)
```

### 4. Observing Multiple Agents

```python
from ksi_claude_code import ObservationTool
import asyncio

obs_tool = ObservationTool()

# Monitor multiple agents
async def monitor_team(session_ids):
    tasks = []
    for sid in session_ids:
        task = asyncio.create_task(
            monitor_single_agent(sid)
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)

async def monitor_single_agent(session_id):
    async for event in obs_tool.observe_agent(session_id):
        print(f"[{session_id[:8]}] {event['type']}: {event.get('message', '')}")
```

## Best Practices

### 1. Session ID Management

```python
# Always use the returned session_id for the next message
current_session_id = None

async def chat_with_agent(message):
    global current_session_id
    
    if current_session_id is None:
        # First message - start conversation
        result = await conv_tool.start_conversation("assistant", message)
    else:
        # Continue conversation
        result = await conv_tool.continue_conversation(current_session_id, message)
    
    # Update session ID for next interaction
    current_session_id = result['session_id']
    return result['response']
```

### 2. Error Handling

```python
try:
    result = await conv_tool.start_conversation("researcher", prompt)
except KSIError as e:
    if e.code == "PROFILE_NOT_FOUND":
        # Create a default profile or use base
        result = await conv_tool.start_conversation("base", prompt)
    else:
        raise
```

### 3. Resource Management

```python
# Always clean up observations when done
subscription = await obs_tool.create_subscription(session_id)
try:
    async for event in obs_tool.stream_events(subscription):
        process_event(event)
finally:
    await obs_tool.cancel_subscription(subscription)
```

## Common Pitfalls to Avoid

1. **Don't try to modify prompts after spawn** - Use conversation continuation
2. **Don't expect session_ids to remain stable** - They change with each response
3. **Don't poll for results** - Use the observation system
4. **Don't create agents without purpose** - Each agent costs resources
5. **Don't ignore the conversation context** - Agents remember previous messages

## Real-World Example: Code Review System

```python
async def comprehensive_code_review(file_path: str):
    # Step 1: Initial analysis
    analyzer = await conv_tool.start_conversation(
        "code_analyzer",
        f"Analyze this code file: {file_path}"
    )
    
    # Step 2: Security review
    security = await conv_tool.start_conversation(
        "security_analyst",
        f"Review this code for security issues: {file_path}"
    )
    
    # Step 3: Performance review
    performance = await conv_tool.start_conversation(
        "performance_analyst",
        f"Analyze performance characteristics: {file_path}"
    )
    
    # Step 4: Synthesize findings
    synthesis = await conv_tool.start_conversation(
        "synthesizer",
        f"""Create a comprehensive code review from:
        Analysis: {analyzer['response']}
        Security: {security['response']}
        Performance: {performance['response']}"""
    )
    
    # Step 5: Generate action items
    actions = await conv_tool.continue_conversation(
        synthesis['session_id'],
        "Generate specific action items with priority levels"
    )
    
    return {
        "review": synthesis['response'],
        "actions": actions['response']
    }
```

## Debugging Tips

1. **Enable debug logging**: `export KSI_LOG_LEVEL=DEBUG`
2. **Check daemon status**: `./daemon_control.py status`
3. **Monitor event flow**: Use observation tools to see all events
4. **Verify compositions**: Check that profiles exist before use
5. **Track session IDs**: Log them for debugging conversation flow

## Next Steps

- Explore creating custom compositions for your use cases
- Build multi-agent workflows for complex tasks
- Use the observation system for real-time monitoring
- Share successful patterns with the community

Remember: KSI is event-driven and conversation-based. Work with its architecture, not against it!