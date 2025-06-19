#!/bin/bash
# Test the daemon-centric chat system

echo "Testing daemon-centric architecture..."
echo

# Test with a simple prompt
echo "Hello Claude! Can you see this message?" | python3 chat.py

echo
echo "Check for logs:"
ls -la claude_logs/

echo
echo "Latest log content:"
if [ -f claude_logs/latest.jsonl ]; then
    echo "First few lines of latest.jsonl:"
    head -5 claude_logs/latest.jsonl
fi