# KSI - Knowledge System Interface

A pure event-driven daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration.

## Features

- ⚡ **Event-Driven Architecture** - Pure Python modules with @event_handler decorators
- 🎯 **REST JSON API** - Standard patterns (single response = object, multiple = array)
- 🚀 **Single Socket Architecture** - Unified Unix socket for all communication
- 💬 **Conversation Continuity** - Maintains context across Claude interactions using sessionId
- 🤖 **Multi-Agent Orchestration** - Multiple Claude instances conversing autonomously
- 📊 **Real-time Monitoring** - Beautiful TUI for observing conversations and metrics
- 📝 **Complete Logging** - All sessions logged in JSONL format for analysis
- 🔧 **Smart Client Library** - Convenience methods for common API patterns

## Quick Start

### Prerequisites

- Python 3.8 or higher
- [Claude CLI](https://claude.ai/download) installed and configured
- Unix-like operating system (macOS, Linux)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ksi.git
cd ksi

# Run setup script
./setup.sh

# Activate virtual environment
source .venv/bin/activate
```

### Basic Usage

```bash
# Start the daemon
./daemon_control.py start

# Chat with Claude
python3 interfaces/chat.py

# Check daemon health
./daemon_control.py health

# Stop daemon gracefully
./daemon_control.py stop
```

### Multi-Claude Conversations

```bash
# Start a debate between Claudes
python3 interfaces/orchestrate.py "Should AI have rights?" --mode debate

# Monitor in another terminal
python3 interfaces/monitor_tui.py
```

## Architecture Overview

KSI uses a plugin-based architecture where the core daemon is a minimal event router (<500 lines) and all functionality is provided by plugins.

### Core Design Principles

- **Event-Driven**: Everything is an event - no polling or timers
- **Plugin-First**: Core only routes events, all logic in plugins
- **Single Socket**: Simple, unified communication via one Unix socket
- **Async Native**: Built on asyncio for maximum performance

### Key Components

| Component | Description |
|-----------|-------------|
| `daemon_control.py` | Start/stop/restart daemon operations |
| `ksi-daemon.py` | Main daemon wrapper using python-daemon |
| `ksi_client/` | Client libraries (AsyncClient, EventBasedClient) |
| `ksi_daemon/plugins/` | Plugin implementations |

For detailed technical information, see [memory/claude_code/project_knowledge.md](memory/claude_code/project_knowledge.md).

## Client Libraries

### Python Clients

```python
# Async client for full control
from ksi_client import AsyncClient

async with AsyncClient() as client:
    health = await client.health_check()
    response = await client.create_completion("Hello!")

# Simple chat interface
from ksi_client import SimpleChatClient

async with SimpleChatClient() as chat:
    response, session_id = await chat.send_prompt("What is 2+2?")
```

### Event-Based Client (New)

```python
from ksi_client import EventBasedClient

async with EventBasedClient() as client:
    # Subscribe to events
    client.subscribe("completion:*", handler)
    
    # Send events
    await client.emit_event("completion:request", {
        "prompt": "Hello!",
        "model": "sonnet"
    })
```

## Plugin Development

KSI is extensible through plugins. Create your own:

```python
from ksi_daemon.plugin_base import BasePlugin, hookimpl

class MyPlugin(BasePlugin):
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        if event_name == "my:event":
            return {"handled": True}

plugin = MyPlugin()
```

See [ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md](ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md) for complete documentation.

## Available Interfaces

- `interfaces/chat.py` - Simple CLI chat
- `interfaces/orchestrate.py` - Multi-Claude orchestration
- `interfaces/monitor_tui.py` - Real-time monitoring
- ~~`interfaces/chat_textual.py`~~ - (Avoid - corrupts Claude Code TUI)

## Testing

```bash
# Run plugin system tests
python3 tests/test_plugin_system.py

# Test event client
python3 tests/test_event_client.py

# Full protocol tests
python3 tests/test_daemon_protocol.py
```

## Documentation

- [Plugin Architecture](ksi_daemon/PLUGIN_ARCHITECTURE.md) - System design and status
- [Plugin Development Guide](ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md) - How to create plugins
- [Event Catalog](ksi_daemon/EVENT_CATALOG.md) - All system events
- [Project Knowledge](memory/claude_code/project_knowledge.md) - Detailed technical reference

## Project Status

The plugin architecture refactor is **90% complete**:
- ✅ Core infrastructure (event bus, plugin system)
- ✅ Transport plugins (Unix sockets)
- ✅ Service plugins (completion, state)
- ✅ Client libraries with event support
- ✅ Comprehensive documentation
- 🚧 Agent manager plugin (in progress)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built for [Claude AI](https://claude.ai)
- Plugin system powered by [pluggy](https://pluggy.readthedocs.io/)
- TUI powered by [Textual](https://textual.textualize.io/)
- Inspired by Unix philosophy of simple, composable tools