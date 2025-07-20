# KSI Ξ Agent Improving Ecosystem

> A graph-based orchestration system for evolving AI agents through collaborative improvement and meta-optimization

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Overview

KSI (not an acronym) is an experimental ecosystem where AI agents improve themselves and each other through orchestrated interactions. It provides a graph-based architecture where agents and orchestrations form nodes in a directed graph, with events flowing through edges based on hierarchical routing rules. The system enables meta-optimization - agents can optimize their own prompts, behaviors, and even the orchestration language itself.

### Key Features

- 🧬 **Self-Improving Agents** - Agents optimize their own prompts and behaviors through MIPRO/DSPy
- 🕸️ **Graph-Based Architecture** - Agents and orchestrations as nodes with hierarchical event routing
- 🔄 **Meta-Optimization** - The orchestration DSL itself can be optimized by agents
- ⚡ **Event-Driven Core** - Pure async event system with discoverable APIs
- 🎭 **Persona-First Design** - Agents are Claude adopting personas, not artificial constructs
- 📊 **Live Visualization** - Real-time web UI showing agent ecosystem and event flow
- 🛡️ **Production Ready** - Resilient daemon with checkpoint/restore and graceful shutdown
- 🔧 **Native Transports** - Built-in WebSocket and Unix socket transports
- 🧩 **Component System** - Unified architecture where everything is a versioned component
- 🌐 **Federated Development** - Git submodules enable collaborative component evolution

## Installation

### Prerequisites

- Python 3.8 or higher
- Unix-like operating system (macOS, Linux)
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) (for Claude integration)

### Quick Start

```bash
# Clone the repository with submodules
git clone --recursive https://github.com/yourusername/ksi.git
cd ksi

# Or if already cloned, initialize submodules
git submodule update --init --recursive

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

### Command-Line Interface

```bash
# Use the ksi command (no installation required during development)
./ksi discover                    # Discover available events
./ksi help completion:async       # Get help for specific events
./ksi send state:set --key mykey --value '{"data": "test"}'
```

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

### Agent Orchestration & Improvement

```bash
# Spawn an agent from a component
./ksi send agent:spawn_from_component --component "components/personas/analysts/data_analyst"

# Start an optimization orchestration
./ksi send orchestration:start --pattern "orchestrations/optimization/mipro_prompt_optimization" \
  --vars '{"target_component": "personas/analysts/data_analyst"}'

# Run a tournament between different agent strategies
./ksi send orchestration:start --pattern "orchestrations/tournaments/strategy_evaluation"

# Monitor the ecosystem in real-time
python interfaces/monitor_tui.py
```

### Web Visualization

```bash
# Start the web UI
./web_control.py start

# Open http://localhost:8080 to see:
# - Live agent ecosystem graph
# - Real-time event stream
# - State system visualization
# - Hierarchical orchestration trees
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

KSI implements a graph-based architecture where agents and orchestrations form nodes in a directed graph:

```
┌─────────────────────────────────────────────────┐
│            Orchestration (Root)                  │
│         orchestrator_agent_id: "claude-code"     │
└───────────────┬─────────────┬───────────────────┘
                │             │
       ┌────────▼────┐   ┌────▼────────┐
       │   Agent A   │   │   Agent B    │  ← Agents as nodes
       │  (Analyst)  │   │ (Optimizer)  │
       └─────┬───────┘   └──────┬──────┘
             │                  │
       ┌─────▼───────────────────▼─────┐
       │    Sub-Orchestration          │  ← Nested orchestrations
       │  (Strategy Tournament)        │
       └───────────────────────────────┘
```

### Core Principles

1. **Graph-Based Entities** - Agents and orchestrations are nodes with edges representing relationships
2. **Hierarchical Routing** - Events bubble up through subscription levels (graph traversal depth)
3. **Everything is a Component** - Unified system with personas, behaviors, orchestrations as components
4. **Persona-First Agents** - Agents are Claude adopting domain expertise, not artificial constructs
5. **Meta-Optimization** - The system can optimize its own components and orchestration language

### Resilience Features

- **Checkpoint/Restore**: System state automatically saved and restored across restarts
- **Retry Logic**: Failed operations automatically retried with exponential backoff
- **Graceful Shutdown**: Critical operations complete before daemon exit
- **Process Monitoring**: Automatic detection and recovery of failed agent processes
- **Session Continuity**: Agents maintain conversation context across requests

### Component System

Components are the building blocks of KSI, organized by type:

- **Personas** (`components/personas/`) - Domain expertise and personalities
- **Behaviors** (`components/behaviors/`) - Reusable behavioral patterns and overrides
- **Orchestrations** (`components/orchestrations/`) - Multi-agent coordination patterns
- **Evaluations** (`components/evaluations/`) - Quality metrics and judge components
- **Tools** (`components/tools/`) - External integrations (MCP, Git, APIs)

### Agent Improvement Patterns

- **MIPRO Optimization** - Agents optimize their own prompts using DSPy/MIPRO
- **Behavioral Overrides** - Components can modify agent behavior through dependencies
- **Tournament Selection** - Strategies compete and evolve through orchestrated tournaments
- **Judge-Based Evaluation** - LLM judges provide nuanced feedback for improvement
- **Meta-Linguistic Evolution** - The orchestration DSL itself evolves through optimization

## Module Development & API Discovery

KSI features a self-documenting discovery system. To explore available APIs and learn how to write modules:

```bash
# Discover all available events and their parameters
echo '{"event": "system:discover", "data": {"detail": true}}' | nc -U var/run/daemon.sock | jq

# Get detailed help for any event
echo '{"event": "system:help", "data": {"event": "agent:spawn"}}' | nc -U var/run/daemon.sock | jq

# Discover events by namespace
echo '{"event": "system:discover", "data": {"namespace": "completion", "detail": true}}' | nc -U var/run/daemon.sock | jq
```

### Writing Discoverable Modules

```python
from typing import TypedDict
from ksi_daemon.event_system import event_handler

class MyEventData(TypedDict):
    """Parameters are auto-discovered from TypedDict."""
    action: str
    target: str

@event_handler("my:custom:event")
async def handle_custom_event(data: MyEventData):
    """This docstring becomes the event summary."""
    action = data['action']  # Required parameter
    target = data.get('target', 'default')  # Optional with default
    return {"status": "processed"}
```

The discovery system automatically extracts parameter types, descriptions, and validation rules from your code.

## Documentation

- **API Reference**: Use `system:discover` and `system:help` - the API is self-documenting!
- [Architecture Analysis](docs/ksi_architecture_analysis.md) - Deep technical dive
- [Optimization Approach](docs/OPTIMIZATION_APPROACH.md) - How agents improve themselves
- [DSL Patterns](docs/DSL_PATTERNS_AND_OPTIMIZATION.md) - Meta-linguistic evolution
- [Claude Code Integration](CLAUDE.md) - Development workflow with Claude Code
- [Technical Reference](memory/claude_code/project_knowledge.md) - Implementation details

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# For development, use the wrapper script (no installation needed)
./ksi discover    # Works immediately after setup.sh

# For production deployment, install the package
pip install -e ".[dev]"

# After installation, 'ksi' is available system-wide
ksi discover      # Available anywhere after pip install

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
- TUI components use [Textual](https://textual.textualize.io/)
- Web UI uses [Cytoscape.js](https://js.cytoscape.org/) for graph visualization
- Optimization powered by [DSPy](https://github.com/stanfordnlp/dspy) framework

## Status

KSI is under active development. Core functionality is stable and used in production environments. See [Issues](https://github.com/yourusername/ksi/issues) for current work.

---
*KSI Ξ Where agents evolve through orchestrated collaboration*