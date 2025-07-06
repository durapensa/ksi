#!/usr/bin/env python3
"""Diagnostic hook that properly handles stdin JSON input."""
import sys
import json
import os
from datetime import datetime

# Log file for diagnostics
log_file = "/Users/dp/projects/ksi/experiments/hook_diagnostic.log"

# Always write timestamp
with open(log_file, "a") as f:
    f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Hook invoked!\n")
    
    try:
        # Read JSON from stdin - this is the expected format
        hook_data = json.load(sys.stdin)
        f.write(f"Received hook data:\n{json.dumps(hook_data, indent=2)}\n")
        
        # Extract expected fields according to docs
        session_id = hook_data.get("session_id", "missing")
        transcript_path = hook_data.get("transcript_path", "missing")
        tool_name = hook_data.get("tool_name", "missing")
        tool_input = hook_data.get("tool_input", {})
        
        f.write(f"\nParsed data:\n")
        f.write(f"- Session ID: {session_id}\n")
        f.write(f"- Transcript: {transcript_path}\n")
        f.write(f"- Tool Name: {tool_name}\n")
        f.write(f"- Tool Input Keys: {list(tool_input.keys()) if isinstance(tool_input, dict) else 'not a dict'}\n")
        
    except json.JSONDecodeError as e:
        f.write(f"JSON decode error: {e}\n")
        f.write(f"Raw stdin: {sys.stdin.read()}\n")
    except Exception as e:
        f.write(f"Unexpected error: {type(e).__name__}: {e}\n")
    
    f.write("-" * 60 + "\n")

# Try to output to Claude (might not appear in conversation)
print(f"\n--- KSI Hook Diagnostic ---")
print(f"Hook triggered at {datetime.now().strftime('%H:%M:%S')}")
print(f"Check {log_file} for details")
print("---\n")

# Exit successfully
sys.exit(0)