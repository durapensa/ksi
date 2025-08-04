#!/usr/bin/env python3
"""Test script using same venv path structure as KSI hook monitor"""
import sys
import json

print(f"Python path: {sys.executable}", flush=True)
print(f"Working directory: {sys.path[0]}", flush=True)

# Try to output in same JSON format as KSI hook monitor
output = {
    "decision": "block",
    "reason": "Test venv hook working!"
}
print(json.dumps(output), flush=True)