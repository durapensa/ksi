# KSI - Kubernetes-Style Infrastructure for AI Agents

> A resilient, event-driven daemon system for orchestrating autonomous AI agents with production-grade reliability

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Overview

KSI provides infrastructure for running and managing AI agents as persistent, autonomous services. Originally conceived as a "Knowledge System Interface," it has evolved into a comprehensive daemon platform that treats AI agents like microservices - with health checks, lifecycle management, and automatic recovery from failures.

### Key Features

- 🔄 **Resilient Operations** - Automatic checkpoint/restore and retry on failures
- ⚡ **Event-Driven Architecture** - Pure async event system with no polling
- 🛡️ **Coordinated Shutdown** - Graceful shutdown with completion guarantees
- 🤖 **Multi-Agent Support** - Orchestrate conversations between multiple AI instances
- 🔌 **Plugin Architecture** - Extend functionality without modifying core
- 📊 **Real-time Monitoring** - Beautiful TUI for observing system state
- 🚀 **Production Ready** - Proper daemonization, logging, and error handling
- 🔧 **MCP Integration** - Model Context Protocol server for tool access

## Installation

### Prerequisites

- Python 3.8 or higher
- Unix-like operating system (macOS, Linux)
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) (for Claude integration)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/ksi.git
cd ksi

# Set up the environment
./setup.sh

# Activate virtual environment
source .venv/bin/activate

# Start the daemon
./daemon_control.py start

# Verify it's running
./daemon_control.py health
```

## Usage

### Basic Chat Interface

```bash
# Interactive chat with Claude
python interfaces/chat.py
```

### Python Client

```python
from ksi_client import AsyncClient

async with AsyncClient() as client:
    # Send a completion request
    response = await client.create_completion(
        prompt="Explain quantum computing",
        model="claude-cli/sonnet"
    )
    print(response.text)
```

### Multi-Agent Orchestration

```bash
# Start a debate between two Claude instances
python interfaces/orchestrate.py "Is P=NP?" --mode debate

# Monitor the conversation in real-time
python interfaces/monitor_tui.py
```

### Event-Based Operations

```python
from ksi_client import EventClient

async with EventClient() as client:
    # Subscribe to completion events
    await client.subscribe("completion:*")
    
    # Emit an event
    response = await client.emit("completion:async", {
        "prompt": "Write a haiku about coding",
        "model": "claude-cli/sonnet"
    })
```

## Architecture

KSI follows a microkernel architecture where the core daemon is minimal (~500 lines) and all functionality is provided through plugins:

```
┌─────────────────┐
│   Unix Socket   │  ← Single communication interface
└────────┬────────┘
         │
┌────────▼────────┐
│  Event Router   │  ← Core daemon (minimal)
└────────┬────────┘
         │
┌────────▼────────────────────────────────┐
│              Plugins                     │
├──────────────┬──────────────┬───────────┤
│ Completion   │   Agent      │    MCP    │
│  Service     │  Manager     │  Server   │
├──────────────┼──────────────┼───────────┤
│ Message Bus  │ Conversation │ Checkpoint│
│              │   Lock       │  System   │
└──────────────┴──────────────┴───────────┘
```

### Core Principles

1. **Everything is an Event** - No polling, no timers, pure event-driven
2. **Fail-Safe by Default** - Automatic recovery from all failure modes
3. **Plugin-First Design** - Core functionality implemented as plugins
4. **Single Socket** - All communication through one Unix domain socket
5. **Async Native** - Built on Python's asyncio for performance

### Resilience Features

- **Checkpoint/Restore**: System state automatically saved and restored across restarts
- **Retry Logic**: Failed operations automatically retried with exponential backoff
- **Graceful Shutdown**: Critical operations complete before daemon exit
- **Process Monitoring**: Automatic detection and recovery of failed agent processes

## Plugin Development

Create custom plugins to extend KSI:

```python
from ksi_daemon.event_system import event_handler

@event_handler("my:custom:event")
async def handle_custom_event(data):
    # Your logic here
    return {"status": "processed"}

# Plugin is auto-registered on import
```

See [Plugin Development Guide](ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md) for details.

## Documentation

- [API Reference](docs/API_REFERENCE.md) - Complete REST-style API documentation
- [Event Catalog](ksi_daemon/EVENT_CATALOG.md) - All available system events
- [Plugin Architecture](ksi_daemon/PLUGGY_ARCHITECTURE.md) - Plugin system design
- [Architecture Analysis](docs/ksi_architecture_analysis.md) - Deep technical dive

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black .
ruff .
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for [Claude](https://claude.ai) by Anthropic
- Plugin system powered by [pluggy](https://pluggy.readthedocs.io/)
- TUI components use [Textual](https://textual.textualize.io/)
- Inspired by Kubernetes' approach to container orchestration

## Status

KSI is under active development. Core functionality is stable and used in production environments. See [Issues](https://github.com/yourusername/ksi/issues) for current work.

---
*"Like Kubernetes for AI agents"* - A resilient infrastructure for the autonomous AI era.