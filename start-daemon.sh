#!/bin/bash
# Start Claude Daemon

set -e

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found (.venv)"
    exit 1
fi

# Change to script directory and start daemon
cd "$(dirname "$0")"
source .venv/bin/activate
nohup python daemon.py > /dev/null 2>&1 &

echo "Daemon startup initiated"