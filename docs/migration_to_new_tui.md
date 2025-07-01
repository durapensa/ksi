# Migration Guide: Moving to the New KSI TUI

This guide helps you transition from the old Textual interfaces to the new, focused TUI applications.

## Overview of Changes

### Old Architecture
- **Single monolithic apps**: `chat_textual.py`, `monitor_textual.py`, `monitor_tui.py`
- **Complex multi-mode interfaces**: Chat, replay, and multi-agent in one app
- **Mixed concerns**: UI logic intertwined with business logic
- **Inconsistent design**: Each app had its own style

### New Architecture
- **Focused applications**: Separate apps for chat, monitor, history, agents
- **Single-purpose design**: Each app does one thing well
- **Clean separation**: UI components, services, and apps are separate
- **Consistent theme**: Beautiful Catppuccin-inspired dark theme across all apps

## Application Mapping

### Chat Interface

**Old**: `interfaces/chat_textual.py`
```bash
python interfaces/chat_textual.py --new
python interfaces/chat_textual.py --resume SESSION_ID
```

**New**: `ksi-chat`
```bash
./ksi-chat                    # Auto-resumes last session
./ksi-chat --model sonnet     # Specify model
```

Key improvements:
- Cleaner, more focused interface
- Better session management
- Smooth animations
- Improved keyboard navigation
- Real-time connection status

### Monitor Interface

**Old**: `interfaces/monitor_textual.py` or `interfaces/monitor_tui.py`
```bash
python interfaces/monitor_textual.py
python interfaces/monitor_tui.py
```

**New**: `ksi-monitor`
```bash
./ksi-monitor                        # Real-time dashboard
./ksi-monitor --update-interval 0.5  # Faster updates
```

Key improvements:
- Multi-pane dashboard layout
- Better event filtering
- Live metrics with sparklines
- Agent tree view
- Responsive design

## Feature Comparison

### Chat Features

| Feature | Old Interface | New ksi-chat |
|---------|--------------|--------------|
| Basic chat | ✓ | ✓ Enhanced |
| Session management | Complex modes | Simple & intuitive |
| Message history | ✓ | ✓ With better navigation |
| Export | Ctrl+E (in browse mode) | Ctrl+E (always available) |
| Multi-agent | Same interface | Separate app (coming) |
| Visual design | Basic | Beautiful & modern |

### Monitor Features

| Feature | Old Interface | New ksi-monitor |
|---------|--------------|-----------------|
| Event stream | ✓ | ✓ With filtering |
| Agent list | Basic | Tree view with details |
| System health | Limited | Comprehensive |
| Performance metrics | Text only | Visual graphs |
| Layout | Single column | Multi-pane dashboard |

## Migration Steps

### 1. Update Your Workflow

Instead of complex mode switching, use focused apps:

**Old workflow**:
```bash
# Start chat, switch to browse mode, switch to multi-agent mode
python interfaces/chat_textual.py
# Press Ctrl+B, Ctrl+R, etc. to switch modes
```

**New workflow**:
```bash
# Use separate apps for different tasks
./ksi-chat          # For chatting
./ksi-monitor       # For monitoring
./ksi-history       # For browsing (coming soon)
./ksi-agents        # For multi-agent (coming soon)
```

### 2. Update Your Scripts

If you have scripts that launch the old interfaces:

**Old**:
```bash
#!/bin/bash
python interfaces/chat_textual.py --resume $SESSION_ID
```

**New**:
```bash
#!/bin/bash
./ksi-chat  # Auto-resumes last session
```

### 3. Keyboard Shortcuts

Most shortcuts remain the same, but are more consistent:

| Action | Old | New |
|--------|-----|-----|
| Quit | Ctrl+Q | Ctrl+Q |
| New session | Ctrl+N | Ctrl+N |
| Clear | Ctrl+L | Ctrl+L |
| Help | F1 | F1 |
| Export | Ctrl+E (browse mode) | Ctrl+E (always) |

### 4. Command-Line Arguments

The new apps have simpler arguments:

**Old chat arguments**:
- `--new` - Start new session
- `--resume SESSION_ID` - Resume specific session
- `--profile` - Agent profile
- `--prompt` - Initial prompt file
- Many testing/debugging options

**New chat arguments**:
- `--model` - Choose model (sonnet/opus/haiku)
- `--client-id` - Client identifier
- Auto-resumes last session by default

## Customization

### Creating Custom Apps

The new architecture makes it easy to create custom apps:

```python
from textual.app import App, ComposeResult
from ksi_tui.components import MessageList, ConnectionStatus
from ksi_tui.themes import theme_manager

class MyApp(App):
    CSS = theme_manager.css  # Use KSI theme
    
    def compose(self) -> ComposeResult:
        yield MessageList()  # Use KSI components
        yield ConnectionStatus()
```

See `ksi_tui/examples/custom_app.py` for a complete example.

### Extending Components

All components are designed to be extended:

```python
from ksi_tui.components import MessageBubble

class CustomMessageBubble(MessageBubble):
    """Extended message bubble with custom features."""
    
    def on_click(self, event):
        # Add custom click behavior
        super().on_click(event)
        self.notify("Message clicked!")
```

## Troubleshooting

### Connection Issues

Both old and new interfaces connect to the same daemon:

```bash
# Check daemon status
./daemon_control.py status

# Restart if needed
./daemon_control.py restart
```

### Display Issues

The new interfaces require a modern terminal:
- Minimum 80x24 size (larger recommended)
- 256 color support (16.7M colors preferred)
- Unicode support

Recommended terminals:
- macOS: iTerm2, Kitty, Ghostty
- Linux: Alacritty, Kitty, GNOME Terminal
- Windows: Windows Terminal

### Performance

The new interfaces are more efficient:
- Virtual scrolling for long lists
- Debounced updates
- Background workers for async operations

If you experience lag:
1. Check terminal GPU acceleration
2. Reduce update interval: `--update-interval 2.0`
3. Clear event logs periodically: `Ctrl+C`

## Benefits of Migration

### Improved User Experience
- **Focused interfaces**: No mode confusion
- **Beautiful design**: Consistent Catppuccin theme
- **Smooth animations**: Modern feel
- **Better keyboard navigation**: Intuitive shortcuts

### Better Architecture
- **Reusable components**: Build your own apps
- **Clean services**: Easy to test and extend
- **Type safety**: Full type hints throughout
- **Async-first**: Better performance

### Future-Proof
- **Modular design**: Easy to add new features
- **Active development**: Regular improvements
- **Community-friendly**: Easy to contribute

## Getting Help

- Run with `F1` for built-in help
- Check `ksi_tui/README.md` for details
- See `ksi_tui/examples/` for code examples
- Report issues on GitHub

## Timeline

1. **Now**: ksi-chat and ksi-monitor are ready
2. **Soon**: ksi-history for conversation browsing
3. **Next**: ksi-agents for multi-agent coordination
4. **Future**: Plugin system for custom components

The old interfaces will remain available during the transition period, but new features will only be added to the new TUI system.