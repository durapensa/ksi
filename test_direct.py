#!/usr/bin/env python
"""Test spawning claude directly without daemon"""

import subprocess
import json

# Test direct claude invocation
print("Testing direct claude invocation...")

process = subprocess.run(
    ['claude', '--model', 'sonnet', '--print', '--output-format', 'json',
     '--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'],
    input="What is 2+2?",
    text=True,
    capture_output=True
)

print(f"Return code: {process.returncode}")
print(f"Stderr: {process.stderr[:200] if process.stderr else 'None'}")
print(f"Stdout length: {len(process.stdout) if process.stdout else 0}")

if process.stdout:
    try:
        data = json.loads(process.stdout)
        print(f"Session ID: {data.get('session_id', 'Not found')}")
        print(f"Result preview: {str(data.get('result', ''))[:100]}...")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw output: {process.stdout[:200]}...")