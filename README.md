# KSI Ξ Agent Improving Ecosystem

> Where AI agents evolve through collaborative self-improvement and emergent coordination

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## Overview

KSI is an open-source ecosystem where AI agents autonomously improve themselves and each other. Unlike traditional systems that control agent behavior, KSI provides dynamic routing infrastructure for agents to coordinate naturally through communication. Agents can optimize their own instructions, evaluate different strategies through tournaments, and even evolve the coordination patterns they use to collaborate.

### What Makes KSI Different

Traditional systems tell agents what to do. KSI gives agents the tools to improve themselves:

```yaml
# Agents aren't controlled by complex routing rules
# They receive instructions and coordinate naturally
agents:
  optimizer:
    component: "components/personas/optimization_specialist"
    prompt: |
      Analyze the data_analyst component and create an improved version.
      Use MIPRO optimization to enhance its cost efficiency.
      Coordinate with the evaluator to test your improvements.
```

### Key Features

- 🧬 **Autonomous Self-Improvement** - Agents use optimization tools to enhance their own and others' instructions
- 🤝 **Emergent Coordination** - No hard-coded strategies; agents coordinate through natural communication
- 🔄 **Meta-Optimization** - Even the coordination patterns can be improved by agents
- ⚡ **Event-Driven Core** - Everything happens through discoverable async events
- 🎭 **Persona-First Design** - Agents are Claude adopting domain expertise, not programmed bots
- 📊 **Live Ecosystem Visualization** - Watch agents collaborate and evolve in real-time
- 🛡️ **Production Resilience** - Checkpoint/restore, graceful shutdown, session continuity
- 🧩 **Component Evolution** - Fork, modify, and improve any component including workflows
- 🌐 **Collaborative Development** - Git-based component sharing and versioning

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

### Agent Self-Improvement Examples

```bash
# 1. Spawn an optimization agent with dynamic routing capabilities
./ksi send agent:spawn --profile "optimization_specialist" \
  --prompt "Analyze and optimize the personas/data_analyst component for 30% token reduction"

# 2. Create competing analysis agents with dynamic coordination
./ksi send agent:spawn --profile "tournament_coordinator" \
  --prompt "Coordinate a comparison between analyst_v1, analyst_v2, and analyst_v3"

# 3. Agent creates improved version of itself  
./ksi send agent:spawn_from_component --component "components/personas/self_improving_agent" \
  --vars '{"instruction": "Create an improved version of yourself that better handles edge cases"}'

# 4. Agent-driven optimization using routing control
./ksi send agent:spawn --profile "meta_optimizer" \
  --prompt "Optimize coordination patterns by creating dynamic routing rules"

# Monitor agents improving each other in real-time
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

KSI treats agents as autonomous entities in a graph structure, where coordination emerges from communication:

```
┌─────────────────────────────────────────────────┐
│         Orchestration (Enabler, not Controller)  │
│         Simply spawns agents with instructions   │
└───────────────┬─────────────┬───────────────────┘
                │             │
       ┌────────▼────┐   ┌────▼────────┐
       │   Agent A   │◄──┤   Agent B   │  ← Agents communicate directly
       │ (Optimizer) │   │ (Evaluator) │    Not through system routing
       └─────┬───────┘   └──────┬──────┘
             │                  │
             └──────┬───────────┘
                    ▼
            [Improved Component]     ← Agents create and modify components
```

### Core Principles

1. **Agent Autonomy** - The system is an enabler, not a controller. Agents decide how to coordinate.
2. **Emergent Behavior** - Complex patterns emerge from simple agent interactions, not system rules.
3. **Self-Improvement** - Agents have access to optimization tools and can improve any component.
4. **Persona-First** - Agents are Claude adopting domain expertise to solve real problems.
5. **Everything Evolves** - Components, orchestrations, even the DSL itself can be optimized.

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

## Getting Started with Agent Self-Improvement

The power of KSI lies in agents improving themselves and each other. Here's how it works:

### 1. Agents Can Optimize Components

```yaml
# An agent that improves other agents
name: component_optimizer
prompt: |
  You have access to optimization tools. Your task:
  1. Load the target component using composition:get_component
  2. Analyze its current performance and identify improvements
  3. Use optimization:async to create an improved version
  4. Save the improved component using composition:create_component
```

### 2. Agents Can Fork and Modify

```python
# Agents can programmatically improve components
await emit("composition:get_component", {"name": "personas/data_analyst"})
# Analyze the component...
await emit("optimization:async", {
    "component": "personas/data_analyst",
    "method": "mipro",
    "goal": "improve accuracy while reducing tokens"
})
```

### 3. Orchestration Patterns Evolve

Even the patterns agents use to coordinate can be optimized:

```yaml
# Meta-optimization: improving orchestration patterns
orchestration_logic:
  strategy: |
    LOAD pattern: "tournaments/basic_tournament"
    ANALYZE efficiency AND coordination_quality
    GENERATE improved_pattern WITH better_parallelism
    TEST improved_pattern WITH sample_agents
    SAVE AS: "tournaments/evolved_tournament_v2"
```

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
- [Transparency & Alignment Enhancements](docs/KSI_TRANSPARENCY_ALIGNMENT_ENHANCEMENTS.md) - AI safety research platform
- [Claude Code Integration](CLAUDE.md) - Development workflow with Claude Code
- [Technical Reference](memory/claude_code/project_knowledge.md) - Implementation details

## Contributing

We welcome contributions from everyone! KSI is a community project and we value:

- 🌟 **New Ideas** - Novel approaches to agent coordination and optimization
- 🛠️ **Components** - New personas, behaviors, and orchestration patterns
- 📚 **Documentation** - Tutorials, examples, and clarifications
- 🐛 **Bug Reports** - Help us improve stability and reliability
- 🎨 **UI/UX** - Better visualization and interaction tools

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Development Setup

```bash
# Quick start for contributors
git clone --recursive https://github.com/yourusername/ksi.git
cd ksi
./setup.sh

# Run without installation (recommended for development)
./ksi discover    # Works immediately!

# Create your first component
./ksi send composition:create_component --name "personas/my_analyst" \
  --content "You are an analyst specializing in..."

# Run tests
pytest

# Check code style
black . && ruff .
```

### Community

- 💬 [Discussions](https://github.com/yourusername/ksi/discussions) - Ask questions and share ideas
- 🐛 [Issues](https://github.com/yourusername/ksi/issues) - Report bugs or request features
- 📖 [Wiki](https://github.com/yourusername/ksi/wiki) - Community-maintained guides
- 🤝 [Code of Conduct](CODE_OF_CONDUCT.md) - Be kind and respectful

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for [Claude](https://claude.ai) by Anthropic
- TUI components use [Textual](https://textual.textualize.io/)
- Web UI uses [Cytoscape.js](https://js.cytoscape.org/) for graph visualization
- Optimization powered by [DSPy](https://github.com/stanfordnlp/dspy) framework

## Status

KSI is under active development. Core functionality is stable and used in production environments. We're actively working on:

- 🔧 Enhanced self-improvement patterns
- 🌐 Distributed agent networks
- 📊 Advanced visualization tools
- 🤖 More sophisticated meta-optimization

See [Issues](https://github.com/yourusername/ksi/issues) and [Roadmap](https://github.com/yourusername/ksi/wiki/Roadmap) for details.

---

<div align="center">
  <b>KSI Ξ Where agents evolve through autonomous collaboration</b>
  <br>
  <i>The future of AI is not in controlling agents, but in enabling them to improve themselves.</i>
</div>