#!/usr/bin/env python3
"""
Minimal test hook to verify Claude Code hooks are working.
This hook should ALWAYS produce output to verify it's being called.
"""

import sys
import json
import os
from datetime import datetime

# Always write to a log file as proof of execution
log_file = "/tmp/claude_hook_test.log"
timestamp = datetime.now().isoformat()

# Log that we started
with open(log_file, "a") as f:
    f.write(f"\n{'='*60}\n")
    f.write(f"Hook executed at: {timestamp}\n")
    f.write(f"Working directory: {os.getcwd()}\n")
    f.write(f"Python executable: {sys.executable}\n")
    f.write(f"Python version: {sys.version}\n")

# Try to read stdin
stdin_data = "No stdin data"
try:
    raw_input = sys.stdin.read()
    if raw_input:
        stdin_data = raw_input
        # Try to parse as JSON
        try:
            parsed = json.loads(raw_input)
            tool_name = parsed.get("tool_name", "unknown")
            with open(log_file, "a") as f:
                f.write(f"Tool name: {tool_name}\n")
                f.write(f"Full data: {json.dumps(parsed, indent=2)}\n")
        except:
            with open(log_file, "a") as f:
                f.write(f"Raw stdin (not JSON): {raw_input[:200]}\n")
except Exception as e:
    with open(log_file, "a") as f:
        f.write(f"Error reading stdin: {e}\n")

# ALWAYS print something to stdout so we can see it in Claude Code
print(f"[TEST HOOK] Executed at {timestamp[:19]} - Check /tmp/claude_hook_test.log")

# Exit successfully
sys.exit(0)