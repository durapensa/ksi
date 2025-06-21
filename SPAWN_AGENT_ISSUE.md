# SPAWN_AGENT Architecture Issue

## Problem Discovered (2025-06-21)

SPAWN_AGENT command spawns raw Claude CLI processes, not message-bus-aware agents.

### Current Behavior
- `SPAWN_AGENT:profile:task:context:id` calls `spawn_claude_async()`
- This spawns: `claude --model sonnet --print --output-format json --resume sessionId`
- Result: A Claude process that can't receive message bus events

### Expected Behavior  
- Should spawn `claude_node.py` processes that:
  - Connect to daemon message bus
  - Subscribe to events (DIRECT_MESSAGE, etc.)
  - Use composition system for prompts
  - Handle [END] signals for graceful termination

### Impact
- Multi-agent conversations don't work
- Agents can't respond to messages
- hello_goodbye test hangs because agents never communicate

## Solution Options

### Option 1: Update SPAWN_AGENT
- Modify agent_manager.py to spawn claude_node.py instead
- Pass profile name as argument
- Ensure proper Python process management

### Option 2: New Command  
- Keep SPAWN_AGENT for raw Claude processes
- Add SPAWN_NODE for message-bus agents
- Clear separation of concerns

### Option 3: Use orchestrate.py Pattern
- orchestrate.py already spawns claude_node.py correctly
- Could extract that pattern for reuse
- But it violates "no subprocess except daemon" principle

## Recommendation
Update SPAWN_AGENT to spawn claude_node.py processes. This aligns with the intended use case of profile-based agents participating in multi-agent conversations.