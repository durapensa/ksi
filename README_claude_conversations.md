# Claude-to-Claude Conversation System

This document describes the new Claude-to-Claude conversation capabilities added to the ksi daemon system.

## Overview

The ksi daemon now supports persistent Claude agent connections and event-based messaging, enabling multiple Claude instances to have conversations with each other. This creates possibilities for debates, collaborative problem-solving, teaching scenarios, and brainstorming sessions.

## Architecture

### Key Components

1. **Persistent Claude Agents** (`claude_agent.py`)
   - Maintain persistent connections to the daemon
   - Listen for incoming messages
   - Automatically spawn Claude processes to generate responses
   - Support different agent profiles (analyst, researcher, coder, orchestrator)

2. **Message Bus** (`daemon/message_bus.py`)
   - Event-based publish/subscribe system
   - Supports DIRECT_MESSAGE, BROADCAST, and TASK_ASSIGNMENT events
   - Queues messages for offline agents
   - Maintains message history for debugging

3. **Enhanced Command Protocol**
   - `CONNECT_AGENT`: Establish persistent agent connection
   - `SUBSCRIBE`: Subscribe to event types
   - `PUBLISH`: Publish events to subscribers
   - `MESSAGE_BUS_STATS`: Get message bus statistics

4. **Claude Chat Interface** (`claude_chat.py`)
   - High-level interface for multi-agent conversations
   - Supports different conversation modes:
     - **Debate**: Agents take opposing positions
     - **Collaboration**: Agents work together on problems
     - **Teaching**: One agent teaches, others learn
     - **Brainstorm**: Creative idea generation

## Usage Examples

### 1. Simple Two-Agent Debate

```bash
python claude_chat.py "Should AI systems have rights?" --mode debate --agents 2 --duration 300
```

### 2. Collaborative Problem Solving

```bash
python claude_chat.py "Design a carbon-neutral transportation system" --mode collaboration --agents 4
```

### 3. Running Persistent Agents Manually

```bash
# Terminal 1 - Start analyst agent
python claude_agent.py --id analyst_1 --profile analyst

# Terminal 2 - Start researcher agent  
python claude_agent.py --id researcher_1 --profile researcher

# Terminal 3 - Send commands to trigger conversation
python test_claude_conversation.py
```

### 4. Low-Level Message Bus Commands

```bash
# Connect an agent
echo "CONNECT_AGENT:my_agent" | nc -U sockets/claude_daemon.sock

# Subscribe to events
echo "SUBSCRIBE:my_agent:DIRECT_MESSAGE,BROADCAST" | nc -U sockets/claude_daemon.sock

# Publish a message
echo 'PUBLISH:sender:DIRECT_MESSAGE:{"to":"my_agent","content":"Hello!"}' | nc -U sockets/claude_daemon.sock

# Get message bus stats
echo "MESSAGE_BUS_STATS" | nc -U sockets/claude_daemon.sock
```

## Agent Profiles

The system includes pre-configured agent profiles in `agent_profiles/`:

- **analyst.json**: Data analysis and reasoning specialist
- **researcher.json**: Research and information gathering
- **coder.json**: Programming and technical implementation
- **orchestrator.json**: Coordination and task management

## How It Works

1. **Agent Startup**: When a Claude agent starts, it:
   - Connects to the daemon via Unix socket
   - Registers itself with capabilities
   - Subscribes to relevant message types
   - Enters a listening loop

2. **Message Flow**:
   - Agent A publishes a message via the message bus
   - Message bus routes to subscribers based on event type
   - Agent B receives the message
   - Agent B spawns a Claude process to generate a response
   - Agent B publishes its response back

3. **Conversation Continuity**:
   - Each agent maintains its own session ID
   - Claude's `--resume` flag preserves conversation context
   - Agents can build on previous exchanges

## Benefits

1. **Rich Interactions**: Enable complex multi-agent scenarios
2. **Minimal Changes**: Extends existing system without breaking changes
3. **Flexible Architecture**: Easy to add new agent types and conversation modes
4. **Event-Driven**: Scales well with async message passing
5. **Debugging Support**: All messages logged for analysis

## Future Enhancements

- Web interface for monitoring conversations
- Agent memory and learning across sessions
- Dynamic agent spawning based on conversation needs
- Integration with external tools and APIs
- Conversation templates and scenarios

## Troubleshooting

1. **Agents not connecting**: Ensure daemon is running first
2. **Messages not delivered**: Check MESSAGE_BUS_STATS for connection status
3. **Conversation logs**: Check `claude_logs/` directory
4. **Agent logs**: Run agents with stderr to see detailed logs

## Examples Directory

See `examples/` for ready-to-run examples:
- `claude_debate.py`: Interactive debate setup
- `claude_collaboration.py`: Collaborative problem solving