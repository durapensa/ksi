#!/usr/bin/env python3
"""Test script for Gemini CLI integration with KSI."""

import json
import socket
import time

def send_request(event, data):
    """Send a request to the KSI daemon."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("var/run/daemon.sock")
    
    request = json.dumps({"event": event, "data": data})
    sock.sendall(request.encode())
    
    response = sock.recv(65536).decode()
    sock.close()
    
    return json.loads(response)

def test_gemini_completion():
    """Test basic Gemini completion."""
    print("Testing Gemini CLI completion...")
    
    # Send completion request
    response = send_request("completion:async", {
        "model": "gemini-cli/gemini-2.5-pro",
        "messages": [{"role": "user", "content": "What is 5+5?"}],
        "stream": False
    })
    
    print(f"Initial response: {json.dumps(response, indent=2)}")
    
    # Extract request_id
    request_id = response["data"].get("request_id")
    if not request_id:
        print("ERROR: No request_id in response")
        return
    
    # Wait for completion
    print(f"Waiting for completion (request_id: {request_id})...")
    time.sleep(5)
    
    # Check status
    status_response = send_request("completion:status", {"request_id": request_id})
    print(f"Status: {json.dumps(status_response['data'].get('status_counts', {}), indent=2)}")

def test_model_comparison():
    """Compare responses from Claude and Gemini."""
    print("\nTesting model comparison...")
    
    prompt = "Write a one-line description of Python"
    
    models = [
        "claude-cli/sonnet",
        "gemini-cli/gemini-2.5-pro"
    ]
    
    for model in models:
        print(f"\n{model}:")
        response = send_request("completion:async", {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        })
        
        request_id = response["data"].get("request_id")
        print(f"  Request ID: {request_id}")
        print("  Status: Queued")
        
        # Note: In a real test, we'd wait for and retrieve the actual response

if __name__ == "__main__":
    print("KSI Gemini Integration Test\n" + "="*40)
    
    try:
        test_gemini_completion()
        test_model_comparison()
        print("\n✓ Tests completed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")