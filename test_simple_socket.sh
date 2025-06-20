#!/bin/bash
# Simple test for socket communication

echo "Testing simple socket communication..."

# Test 1: With newline (should work now)
echo "Test 1: Sending SPAWN:test-newline with newline"
echo "SPAWN:test-newline" | nc -U sockets/claude_daemon.sock &
NC_PID=$!

# Wait up to 5 seconds for response
sleep 5

# Check if nc is still running
if kill -0 $NC_PID 2>/dev/null; then
    echo "FAILED: Command still hanging after 5 seconds"
    kill $NC_PID
else
    echo "SUCCESS: Command completed"
fi

echo
echo "Test 2: Using socat with newline"
echo "SPAWN:test-socat" | socat - UNIX-CONNECT:sockets/claude_daemon.sock

echo
echo "Done testing!"