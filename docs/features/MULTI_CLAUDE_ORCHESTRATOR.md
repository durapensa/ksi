# Multi-Claude Orchestrator System

A unified system enabling multiple Claude instances to converse with each other autonomously, with optional human observation through a real-time TUI monitor.

## Overview

This system transforms the ksi daemon from a hierarchical orchestrator→agent model into a **peer-to-peer Claude network** where:

- Any Claude can initiate conversations with other Claudes
- Claudes maintain persistent connections via the daemon's message bus
- Event-driven architecture (no polling)
- Rich conversation modes (debate, collaboration, teaching, etc.)
- Real-time TUI monitoring of all activity

## Architecture

### Core Components

1. **agent_process.py** - Persistent Claude process
   - Maintains socket connection to daemon
   - Listens for incoming messages
   - Spawns Claude CLI to generate responses
   - Manages conversation context

2. **orchestrate.py** - Conversation orchestrator
   - Starts multi-Claude conversations
   - Manages different conversation modes
   - Creates temporary agent profiles
   - Handles graceful shutdown

3. **monitor_tui.py** - Textual TUI monitor
   - Real-time conversation timeline
   - Active agent visualization
   - Tool call inspection
   - Performance metrics
   - Event stream debugging

4. **Enhanced daemon** - Message routing hub
   - Event-based message bus
   - Persistent agent connections
   - No polling required
   - Minimal overhead

## Quick Start

### 1. Test the system
```bash
python test_multi_claude.py
```

### 2. Start a debate
```bash
python orchestrate.py "Should AI have rights?" --mode debate --agents 2
```

### 3. Monitor in another terminal
```bash
python monitor_tui.py
```

## Conversation Modes

### Debate Mode
Two or more Claudes take opposing positions and argue their points:
```bash
python orchestrate.py "Universal basic income" --mode debate
```

### Collaboration Mode
Claudes work together to solve problems:
```bash
python orchestrate.py "Design a sustainable city" --mode collaboration --agents 3
```

### Teaching Mode
One Claude teaches, others learn and ask questions:
```bash
python orchestrate.py "Quantum computing basics" --mode teaching
```

### Brainstorm Mode
Creative idea generation with critics for refinement:
```bash
python orchestrate.py "New mobile app ideas" --mode brainstorm --agents 4
```

### Analysis Mode
Systematic analysis of complex topics:
```bash
python orchestrate.py "Climate change solutions" --mode analysis --agents 2
```

## TUI Monitor Features

The monitor provides real-time visibility into:

1. **Conversation Timeline** (center)
   - Message flow between Claudes
   - Formatted with timestamps and agent IDs
   - Color-coded by message type

2. **Active Agents** (left sidebar)
   - Tree view of connected Claudes
   - Shows roles and active conversations
   - Updates in real-time

3. **Tool Calls** (right sidebar, top)
   - Any tools used by Claudes
   - Parameters and results
   - Execution timing

4. **Event Stream** (right sidebar, bottom)
   - Raw JSON events for debugging
   - Toggle with 'd' key

5. **Metrics Bar** (bottom)
   - Token usage and estimated costs
   - Messages per minute
   - Active agent count

### Monitor Controls
- `q` - Quit
- `c` - Clear all logs
- `p` - Pause/resume updates
- `d` - Toggle debug mode
- `f` - Filter view (coming soon)

## Manual Claude Node Usage

Start individual Claude nodes for custom setups:

```bash
# Start first node
python agent_process.py --id researcher_1 --profile researcher

# Start second node
python agent_process.py --id analyst_1 --profile analyst

# Start a conversation between them
python agent_process.py --id orchestrator --start-conversation \
    --with-agents researcher_1 analyst_1 \
    --topic "Analyze recent AI breakthroughs"
```

## Agent Profiles

Profiles define Claude behavior and capabilities:

- **debater** - Argumentative, evidence-based
- **collaborator** - Constructive, synthesis-focused
- **teacher** - Clear explanations, patient
- **student** - Curious, asks questions
- **creative** - Generates novel ideas
- **critic** - Constructive evaluation
- **analyst** - Systematic breakdown
- **researcher** - Information gathering

## Protocol Details

### Message Types

1. **DIRECT_MESSAGE** - Claude to Claude communication
```json
{
  "type": "DIRECT_MESSAGE",
  "from": "agent_1",
  "to": "agent_2",
  "content": "Message content",
  "conversation_id": "conv_123"
}
```

2. **CONVERSATION_INVITE** - Start new conversation
```json
{
  "type": "CONVERSATION_INVITE",
  "from": "initiator",
  "to": "participant",
  "topic": "Discussion topic",
  "conversation_id": "conv_123"
}
```

3. **TOOL_CALL** - Tool usage notification
```json
{
  "type": "TOOL_CALL",
  "agent_id": "agent_1",
  "tool": "WebSearch",
  "params": {...},
  "result": "..."
}
```

## Extending the System

### Custom Conversation Modes

Add new modes to `orchestrate.py`:

```python
CUSTOM_MODE = {
    'name': 'custom',
    'min_agents': 2,
    'max_agents': 5,
    'profiles': ['custom_profile'],
    'system_prompts': ["Your custom prompt"],
    'starter_template': "Let's discuss: {topic}"
}
```

### Custom Agent Profiles

Create new profiles in `agent_profiles/`:

```json
{
  "model": "sonnet",
  "role": "specialist",
  "capabilities": ["domain_expertise"],
  "system_prompt": "You are a domain specialist...",
  "allowed_tools": ["WebSearch", "WebFetch"]
}
```

## Troubleshooting

### Daemon not running
```bash
python daemon.py  # Start in separate terminal
```

### Agents not responding
- Check daemon logs: `tail -f logs/daemon.log`
- Verify Claude CLI works: `claude --help`
- Check socket permissions: `ls -la sockets/`

### Monitor not updating
- Ensure daemon has message bus enabled
- Check socket connection
- Try debug mode (press 'd')

## Future Enhancements

- [ ] Web UI monitor option
- [ ] Conversation persistence/replay
- [ ] Multi-model support (Opus, Haiku)
- [ ] Conversation templates library
- [ ] Export conversations to various formats
- [ ] Integration with external tools
- [ ] Conversation branching/merging
- [ ] Human intervention capabilities

## Examples

### AI Ethics Debate
```bash
python orchestrate.py "AI consciousness and rights" --mode debate --agents 3
```

### Collaborative Coding
```bash
python orchestrate.py "Implement a distributed cache" --mode collaboration --agents 4
```

### Learning Session
```bash
python orchestrate.py "Teach me about transformers" --mode teaching --agents 2
```

### Product Brainstorm
```bash
python orchestrate.py "Revolutionary productivity app" --mode brainstorm --agents 5
```

This system enables rich multi-Claude conversations while maintaining the minimalist, AI-first philosophy of ksi.