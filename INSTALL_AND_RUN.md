# Installing and Running the Textual Chat Interface

## Quick Install & Run

```bash
# Install Textual (required)
pip3 install textual

# Run the chat interface
python3 chat_textual.py
```

## If pip3 install fails

Try one of these alternatives:

```bash
# Option 1: Use brew's pip
/opt/homebrew/bin/pip3 install textual

# Option 2: Use Python directly
/opt/homebrew/bin/python3 -m pip install textual

# Option 3: Install with --user flag
pip3 install --user textual
```

## Verify Installation

```bash
python3 -c "import textual; print(f'Textual {textual.__version__} installed successfully')"
```

## Run the Chat Interface

Once Textual is installed:

```bash
python3 chat_textual.py
```

### First Time Usage

1. The interface will start and load the ksi-developer profile
2. It will try to resume your last session (or start a new one)
3. Type your message and press Enter or click Send
4. Press Ctrl+B to browse past conversations
5. Press F1 for help on all commands

### Features to Try

- **Browse Sessions**: Ctrl+B opens a sidebar with your conversation history
- **Replay Mode**: Click any past session to replay it
- **New Session**: Ctrl+N starts fresh
- **Smart Prompts**: Your messages are automatically enhanced with KSI project context

## Troubleshooting

If you see permission errors:
```bash
# Use sudo (macOS may require this)
sudo pip3 install textual
```

If you see SSL certificate errors:
```bash
# Bypass SSL temporarily
pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org textual
```

If the interface looks broken:
- Make sure your terminal window is at least 80 columns wide
- Try maximizing your terminal window
- Some terminals work better than others (Terminal.app, iTerm2, Ghostty all work well)