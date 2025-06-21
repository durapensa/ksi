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
- **Two Conversation Browsers**: 
  - Past Sessions (Ctrl+B): Browse and replay completed conversations
  - Active Sessions (Ctrl+A): View and join ongoing multi-agent conversations
- **Profile Support**: Automatically composes prompts using agent profiles
- **Multi-Agent Support**: View and join active conversations with `/join`
- **Command Support**: Built-in commands for common operations
- **Input History**: Navigate previous messages with up/down arrows
- **Interactive UI**: Send button, proper focus management
- **Message Bus Integration**: Properly displays inter-agent messages

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
- `Ctrl+A` - Browse active conversations
- `Ctrl+L` - Clear conversation display
- `Ctrl+E` - Export selected conversation to markdown (when browsing past)
- `F1` - Show help
- `Escape` - Close conversation browser (when open)
- `Up/Down` - Navigate input history

### Commands

Type these in the input field:

- `/help` - Show help information
- `/clear` - Clear the conversation display
- `/new` - Start a new session
- `/join <conversation_id>` - Join an active multi-agent conversation

## Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 Claude Chat - F1: Help | Ctrl+B: Past | Ctrl+A: Active      │
├──────────────────┬──────────────────┬──────────────────────────┤
│ 📚 Past Sessions │ 🔴 Active Convos │                          │
│   (Ctrl+B)       │   (Ctrl+A)       │   Conversation Area      │
│                  │                  │                          │
│ [Hidden by       │ [Hidden by       │                          │
│  default]        │  default]        │                          │
│                  │                  ├──────────────────────────┤
│                  │                  │ [Input.........] [Send]  │
├──────────────────┴──────────────────┴──────────────────────────┤
│ Session: xxx | Mode: chat/replay/multi | Conv: xxx | Tokens: x │
└─────────────────────────────────────────────────────────────────┘
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

## Export Feature

Export any conversation to a markdown file:

1. Press `Ctrl+B` to open the past conversations browser
2. Click on any conversation to select it
3. Press `Ctrl+E` to export
4. A notification will show the export location

Exported files are saved to the `exports/` directory with timestamps:
- Format: `conversation_<session_id>_<timestamp>.md`
- Includes timestamps, sender names, and full message content
- Special formatting for inter-agent messages

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