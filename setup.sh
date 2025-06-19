#!/bin/bash
# Setup script for Claude daemon

echo "Setting up Claude Process Daemon..."

# Check for socat
if ! command -v socat &> /dev/null; then
    echo "Installing socat..."
    brew install socat
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

# Create claude_modules directory
mkdir -p claude_modules
echo "✓ Created claude_modules/ directory"

# Make scripts executable
chmod +x daemon.py chat.py
echo "✓ Made scripts executable"

echo ""
echo "Setup complete! You can now run:"
echo "  python3 chat.py"
echo ""
echo "This will start the daemon and let you chat with Claude."