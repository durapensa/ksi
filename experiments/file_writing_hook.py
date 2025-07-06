#!/usr/bin/env python3
"""Hook that writes to a file for verification."""
import sys
import json
from datetime import datetime

# Read hook input
try:
    hook_data = json.load(sys.stdin)
    tool_name = hook_data.get("tool_name", "unknown")
    session_id = hook_data.get("session_id", "unknown")
except:
    tool_name = "error"
    session_id = "error"

# Write to log file
with open("/Users/dp/projects/ksi/experiments/hook_log.txt", "a") as f:
    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Tool: {tool_name}, Session: {session_id}\n")

# Also try to output to Claude
print(f"\n[HOOK] Tool '{tool_name}' executed\n")

sys.exit(0)