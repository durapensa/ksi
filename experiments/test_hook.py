#!/usr/bin/env python3
"""Simple test hook to verify hook mechanism works."""
import sys
import json

# Read hook input
try:
    hook_data = json.load(sys.stdin)
    tool_name = hook_data.get("tool_name", "unknown")
except:
    tool_name = "error_reading"

# Output message
print(f"\n[TEST HOOK] Tool '{tool_name}' was used!\n")

# Exit successfully
sys.exit(0)