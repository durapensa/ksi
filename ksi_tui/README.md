# KSI TUI - Modern Terminal User Interfaces

Beautiful, focused TUI applications for the KSI system built with Textual.

## Overview

The KSI TUI package provides a collection of modern terminal applications designed for specific tasks:

- **ksi-chat**: Focused chat interface for Claude conversations
- **ksi-monitor**: Real-time system monitoring dashboard
- **ksi-history**: Conversation browser and search (coming soon)
- **ksi-agents**: Multi-agent orchestration interface (coming soon)

## Features

### Design Principles
- **Focused Applications**: Each app does one thing well
- **Beautiful UI**: Catppuccin-inspired dark theme
- **Keyboard-First**: Intuitive shortcuts for all operations
- **Responsive**: Smooth animations and real-time updates
- **Modular**: Reusable components and services

### Technical Features
- Component-based architecture
- Clean service layer abstractions
- Reactive data binding
- Async/await throughout
- Comprehensive error handling

## Installation

### Prerequisites

1. **Activate the virtual environment** (required):
   ```bash
   source .venv/bin/activate
   ```

2. **Install dependencies** (if not already done):
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the KSI daemon**:
   ```bash
   ./daemon_control.py start
   ```

The TUI applications are included with KSI and ready to use once dependencies are installed.

## Usage

### Terminal Requirements

The TUI applications require an interactive terminal with:
- TTY support (stdin/stdout must be terminals)
- Minimum 80x24 size (larger recommended)
- 256 color support preferred
- Not running in CI/automation environments

The apps automatically detect and prevent startup in non-interactive environments.

### ksi-chat

Beautiful chat interface for Claude conversations:

```bash
# From the KSI project root
./ksi-chat

# Or with Python
python3 ksi-chat

# Specify model
./ksi-chat --model sonnet
./ksi-chat --model opus
```

Features:
- Clean, distraction-free interface
- Session management
- Input history (↑/↓ arrows)
- Export to markdown
- Real-time connection status

Keyboard shortcuts:
- `Ctrl+N` - New session
- `Ctrl+S` - Switch session
- `Ctrl+E` - Export session
- `Ctrl+L` - Clear display
- `Ctrl+Q` - Quit
- `F1` - Help

### ksi-monitor

Real-time system monitoring dashboard:

```bash
# From the KSI project root
./ksi-monitor

# Or with Python
python3 ksi-monitor

# Custom update interval
./ksi-monitor --update-interval 0.5
```

Features:
- System health indicators
- Active agent tracking
- Live event stream with filtering
- Performance metrics
- Multi-pane dashboard

Keyboard shortcuts:
- `Ctrl+R` - Refresh dashboard
- `Ctrl+C` - Clear events
- `Ctrl+P` - Pause/Resume
- `Ctrl+F` - Filter events
- `Ctrl+Q` - Quit
- `F1` - Help

Event filter examples:
- `agent:*` - All agent events
- `completion:*` - All completion events
- `*:error` - All error events
- `agent:spawn,agent:terminate` - Multiple patterns

## Architecture

### Package Structure

```
ksi_tui/
├── apps/           # Individual applications
│   ├── chat/       # Chat interface
│   ├── monitor/    # System monitor
│   ├── history/    # Conversation browser
│   └── agents/     # Agent coordinator
├── components/     # Reusable UI components
├── services/       # Business logic layer
├── themes/         # Visual themes
└── utils/          # Shared utilities
```

### Key Components

#### UI Components
- `MessageBubble` - Beautiful message display
- `EventStream` - Real-time event log
- `MetricsBar` - Animated metrics display
- `ConnectionStatus` - Connection state indicator

#### Services
- `ChatService` - Chat operations abstraction
- `MonitorService` - Monitoring operations
- `HistoryService` - Conversation browsing (coming soon)
- `AgentService` - Agent coordination (coming soon)

### Theme System

Uses Catppuccin Mocha theme with CSS variables:

```css
--base: #1e1e2e      /* Background */
--text: #cdd6f4      /* Primary text */
--lavender: #b4befe  /* Accent color */
--green: #a6e3a1     /* Success */
--red: #f38ba8       /* Error */
--yellow: #f9e2af    /* Warning */
```

## Development

### Creating a New Component

```python
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

class MyComponent(Container):
    """A reusable component."""
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Static("Hello from component!")
```

### Creating a New Service

```python
from ksi_client import EventBasedClient

class MyService:
    """Service abstraction."""
    
    async def connect(self) -> bool:
        """Connect to daemon."""
        self._client = EventBasedClient()
        return await self._client.connect()
```

### Adding a New App

1. Create app module in `apps/myapp/`
2. Implement `MyApp(App)` class
3. Create entry point script
4. Add keyboard bindings and help

## Testing

Run the test suite:

```bash
python -m pytest tests/test_tui/
```

## Contributing

When contributing:
1. Follow the established patterns
2. Use type hints
3. Add docstrings
4. Include keyboard shortcuts
5. Test with various terminal sizes

## Future Plans

### ksi-history (Coming Soon)
- Full-text conversation search
- Timeline visualization
- Bulk export functionality
- Statistics dashboard

### ksi-agents (Coming Soon)
- Agent spawn/terminate controls
- Conversation flow visualization
- Permission management
- Resource monitoring

## Credits

Built with:
- [Textual](https://textual.textualize.io/) - TUI framework
- [Catppuccin](https://github.com/catppuccin/catppuccin) - Color scheme inspiration