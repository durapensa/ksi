#!/bin/bash
# Wrapper script to run KSI monitor with correct session ID

# Find session ID using the shell script
CLAUDE_SESSION_ID=$(./experiments/find_sid.sh)

if [ -z "$CLAUDE_SESSION_ID" ]; then
    echo "❌ No session ID found"
    exit 1
fi

echo "✓ Found session ID: $CLAUDE_SESSION_ID"

# Export for Python script
export CLAUDE_SESSION_ID

# Run the monitor (pass script name as argument)
if [ -z "$1" ]; then
    echo "Usage: $0 <monitor_script.py>"
    echo "Example: $0 experiments/ksi_simple_completion_monitor.py"
    exit 1
fi

python "$1"