# Quick Start: Textual Chat Interface

## 1. Install Textual

```bash
pip3 install textual
```

## 2. Run the Chat Interface

```bash
python3 chat_textual.py
```

## 3. Key Features to Try

### Browse Past Conversations
- Press `Ctrl+B` to open the conversation browser
- Click on any past session to replay it
- Press `Escape` or `Ctrl+B` again to close

### Start Fresh
- Press `Ctrl+N` for a new session
- Your messages are automatically enhanced with the ksi-developer profile

### Navigate Input History
- Use `Up`/`Down` arrows to navigate through previous messages

### Get Help
- Press `F1` to see all available commands and shortcuts

## 4. What's Different from chat.py

1. **Rich UI**: See your conversation in a proper interface with formatting
2. **Session Browser**: Browse and replay any past conversation
3. **Profile Integration**: Your prompts are automatically enhanced with KSI project context
4. **Interactive**: Click the Send button or press Enter to send messages
5. **Status Bar**: Always see your session ID, mode, tokens used, and cost

## 5. Profile System

The ksi-developer profile is automatically applied to your messages:
- You type simple prompts
- The system adds KSI project context
- Claude gets the full context it needs

## Troubleshooting

If you see "ModuleNotFoundError: No module named 'textual'":
```bash
pip3 install textual
```

If the interface looks weird:
- Make sure your terminal is at least 80x24 characters
- Try a different terminal emulator if needed

## Next Steps

- Try browsing your past conversations with `Ctrl+B`
- Start a new session with `Ctrl+N`
- The interface will automatically resume your last session by default