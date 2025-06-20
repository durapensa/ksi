#!/bin/bash
# Setup script for Claude daemon

echo "Setting up Claude Process Daemon..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "✓ Python dependencies installed"

# Check for socat
if ! command -v socat &> /dev/null; then
    echo "Installing socat..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install socat
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y socat || sudo yum install -y socat
    fi
else
    echo "✓ socat is already installed"
fi

# Check for claude CLI
if ! command -v claude &> /dev/null; then
    echo "⚠️  Claude CLI not found in PATH"
    echo "   Please install from https://claude.ai/code"
    echo "   Note: If claude is installed via npm/nvm, it may not be in the PATH"
    echo "   The daemon will still work if claude is accessible when running"
else
    echo "✓ Claude CLI is installed"
fi

# Create directories
mkdir -p claude_modules sockets claude_logs logs shared_state agent_profiles
echo "✓ Created required directories"

# Make scripts executable
chmod +x daemon.py chat.py orchestrate.py monitor_tui.py claude_node.py test_multi_claude.py
echo "✓ Made scripts executable"

echo ""
echo "Setup complete! You can now run:"
echo "  python3 chat.py              # Start chatting with Claude"
echo ""
echo "For multi-Claude conversations:"
echo "  python3 orchestrate.py 'Topic' --mode debate"
echo "  python3 monitor_tui.py       # In another terminal"
echo ""
echo "Note: Make sure to activate the virtual environment first:"
echo "  source .venv/bin/activate"