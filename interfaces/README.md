# User Interfaces

This directory contains all user-facing interfaces for the KSI daemon system.

## Available Interfaces

### Chat Interfaces

**`chat_textual.py`** - Enhanced textual TUI chat interface
- Rich TUI with conversation browsing
- Single-agent and multi-agent support
- Real-time conversation display
- Session management

**`claude_chat.py`** - Simple conversation starter
- Quick setup for multi-Claude conversations
- Automatic monitor launching
- Command-line conversation initiation

### Orchestration

**`orchestrate.py`** - Multi-Claude conversation orchestrator
- Start conversations between multiple Claude agents
- Multiple conversation modes: debate, collaboration, teaching, brainstorm, analysis
- Composition-based agent configuration
- Full conversation lifecycle management

### Monitoring

**`monitor_tui.py`** - Real-time conversation monitor
- Live conversation timeline view
- Agent activity tracking
- Message flow visualization
- Conversation metrics

## Quick Start

### Simple Chat
```bash
# Rich TUI chat interface
python3 interfaces/chat_textual.py

# Quick conversation starter
python3 interfaces/claude_chat.py "AI ethics" --mode debate
```

### Multi-Claude Conversations
```bash
# Start a debate
python3 interfaces/orchestrate.py "Should AI have rights?" --mode debate --agents 2

# Start collaboration
python3 interfaces/orchestrate.py "Design a sustainable city" --mode collaboration --agents 3

# Start teaching session
python3 interfaces/orchestrate.py "Explain quantum computing" --mode teaching --agents 2
```

### Monitor Conversations
```bash
# Watch conversations in real-time
python3 interfaces/monitor_tui.py
```

## Conversation Modes

- **debate** - Agents debate different sides of a topic
- **collaboration** - Agents work together on a problem
- **teaching** - Teacher/student dynamic
- **brainstorm** - Creative ideation session
- **analysis** - Analytical examination of a topic

## Dependencies

All interfaces require:
- Active daemon (`python3 daemon.py`)
- Virtual environment activated (`source .venv/bin/activate`)
- Python dependencies installed (`pip install -r requirements.txt`)

## Organization

This reorganization keeps the project root clean while providing logical grouping:
- **Root**: Core daemon and primary simple interface (`chat.py`)
- **interfaces/**: All user interfaces
- **daemon/**: Daemon system components
- **tests/**: Test scripts and examples
- **tools/**: Development and analysis tools