#!/usr/bin/env python3
"""Test Claude directly with different approaches"""

import subprocess
import tempfile
import os

# Test 1: Simple prompt without -p
print("Test 1: Simple echo without -p flag")
result = subprocess.run(
    ['/Users/dp/.claude/local/claude', '-c', 'echo "Hello from Claude"'],
    capture_output=True,
    text=True
)
print(f"Exit code: {result.returncode}")
print(f"Output: {result.stdout}")
print(f"Error: {result.stderr}")
print("-" * 50)

# Test 2: With -p flag and prompt file
print("\nTest 2: With -p flag and prompt file")
prompt_content = 'Please respond with exactly this JSON: {"event": "test", "data": {"status": "working"}}'
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
    f.write(prompt_content)
    prompt_file = f.name

try:
    result = subprocess.run(
        ['/Users/dp/.claude/local/claude', '-p', prompt_file],
        capture_output=True,
        text=True,
        timeout=30
    )
    print(f"Exit code: {result.returncode}")
    print(f"Output length: {len(result.stdout)}")
    print(f"First 200 chars: {result.stdout[:200]}")
    if result.stderr:
        print(f"Error: {result.stderr}")
finally:
    os.unlink(prompt_file)
print("-" * 50)

# Test 3: Direct prompt without file
print("\nTest 3: Direct prompt")
result = subprocess.run(
    ['/Users/dp/.claude/local/claude'],
    input='Respond with this JSON: {"event": "test", "data": {"value": 42}}',
    capture_output=True,
    text=True,
    timeout=30
)
print(f"Exit code: {result.returncode}")
print(f"Output: {result.stdout}")
if result.stderr:
    print(f"Error: {result.stderr}")