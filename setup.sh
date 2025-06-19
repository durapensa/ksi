#!/bin/bash
# Setup script for Claude daemon

echo "Setting up Claude Process Daemon..."

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "✓ uv is already installed"
fi

# Pin Python 3.13
echo "Setting up Python 3.13 with uv..."
uv python pin 3.13
uv python install 3.13
echo "✓ Python 3.13 configured"

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
    echo "⚠️  Claude CLI not found. Please install from https://claude.ai/code"
    exit 1
else
    echo "✓ Claude CLI is installed"
fi

# Create directories
mkdir -p claude_modules sockets claude_logs
echo "✓ Created required directories"

# Make scripts executable
chmod +x daemon.py chat.py
echo "✓ Made scripts executable"

echo ""
echo "Setup complete! You can now run:"
echo "  uv run python chat.py"
echo ""
echo "This will start the daemon and let you chat with Claude."