# Textual Chat Interface

A rich TUI (Terminal User Interface) chat application for Claude using the Textual framework.

## Installation

First, install Textual:
```bash
pip3 install textual
```

## Features

- **Rich TUI Interface**: Modern terminal interface with panels and styling
- **Session Management**: Resume previous sessions or start new ones
- **Conversation Browser**: Browse and replay past conversations (Ctrl+B)
- **Profile Support**: Automatically composes prompts using agent profiles
- **Command Support**: Built-in commands for common operations
- **Input History**: Navigate previous messages with up/down arrows
- **Interactive UI**: Send button, proper focus management

## Usage

### Basic Usage
```bash
# Start with default settings (resume last session)
python3 chat_textual.py

# Start a new session
python3 chat_textual.py --new

# Resume specific session
python3 chat_textual.py --resume SESSION_ID

# Start with initial prompt from file
python3 chat_textual.py --prompt initial_prompt.txt
```

### Keyboard Shortcuts

- `Ctrl+Q` - Quit the application
- `Ctrl+N` - Start a new session
- `Ctrl+B` - Browse/replay past conversations
- `Ctrl+L` - Clear conversation display
- `F1` - Show help
- `Escape` - Close conversation browser (when open)
- `Up/Down` - Navigate input history

### Commands

Type these in the input field:

- `/help` - Show help information
- `/clear` - Clear the conversation display
- `/new` - Start a new session

## Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│ 🤖 Claude Chat (Textual) - Press F1 for help            │
├──────────────────┬──────────────────────────────────────┤
│  Past Sessions   │                                      │
│  (Ctrl+B)        │      Conversation Area               │
│                  │                                      │
│  [Hidden by      │                                      │
│   default]       │                                      │
│                  ├──────────────────────────────────────┤
│                  │ [Input field................] [Send] │
├──────────────────┴──────────────────────────────────────┤
│ Session: xxx | Mode: chat/replay | Tokens: x | Cost: $x │
└─────────────────────────────────────────────────────────┘
```

## Differences from chat.py

- **Visual Interface**: Rich TUI instead of simple command line
- **Real-time Updates**: See metrics and tool calls as they happen
- **Better Session Visibility**: Always see current session ID and mode
- **Enhanced Input**: Multi-line support and better editing
- **Profile Integration**: Uses ksi-developer profile for better context

## Profile System

The chat interface uses agent profiles to enhance prompts automatically:

1. **Default Profile**: `ksi-developer` - Specialized for KSI project development
2. **Profile Location**: `agent_profiles/` directory
3. **How it works**:
   - Your message becomes the `{task}` in the profile template
   - Recent conversation history provides `{context}`
   - The composed prompt is sent to Claude

Example with ksi-developer profile:
- You type: "Add error handling to the daemon"
- Profile composes: Full prompt with KSI context, your task, and conversation history
- Claude receives: Enhanced prompt with all necessary context

To use a different profile:
```bash
python3 chat_textual.py --profile researcher
```

## Multi-Agent Mode (Coming Soon)

The interface is designed to support joining multi-agent conversations:
- List active conversations
- Join as a participant
- See other agents in the conversation
- Shared context awareness

## Troubleshooting

If you see "ModuleNotFoundError: No module named 'textual'":
```bash
pip3 install textual
```

If the daemon doesn't start automatically:
```bash
python3 daemon.py
```

## Development

The application is built with:
- Textual for the TUI framework
- Asyncio for daemon communication
- Same daemon protocol as chat.py