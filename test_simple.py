#!/usr/bin/env python3
"""Simple test of daemon spawning claude"""

import subprocess
import time

# Start daemon directly
print("Starting daemon...")
daemon = subprocess.Popen(['uv', 'run', 'python', 'daemon.py'])
time.sleep(2)

print("\nRunning simple test prompt through chat.py...")
result = subprocess.run(
    ['uv', 'run', 'python', 'chat.py'],
    input='hello claude\nexit\n',
    text=True,
    capture_output=True
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)

# Kill daemon
daemon.terminate()
daemon.wait()

print("\nCheck logs:")
subprocess.run(['ls', '-la', 'claude_logs/'], check=False)