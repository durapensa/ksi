#!/usr/bin/env python3
"""Generate some KSI activity to test the hook monitor."""

import socket
import json

def send_command(cmd):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("var/run/daemon.sock")
    sock.sendall(json.dumps(cmd).encode() + b'\n')
    response = sock.recv(4096).decode()
    sock.close()
    return json.loads(response)

# Create an entity
print("Creating test entity...")
result = send_command({
    "event": "state:entity:create",
    "data": {
        "id": "test_monitor_entity",
        "type": "test",
        "properties": {"name": "Hook Monitor Test"}
    }
})
print(f"Created: {result['data']['id']}")

# Spawn an agent
print("\nSpawning test agent...")
result = send_command({
    "event": "agent:spawn",
    "data": {
        "profile": "base_single_agent",
        "agent_id": "hook_test_agent"
    }
})
print(f"Spawned: {result['data']['agent_id']}")

print("\nActivity generated! The next tool use should show these events.")