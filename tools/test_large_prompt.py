#!/usr/bin/env python3
"""
Test Large Prompt Through Daemon

Tests if we can send large prompts without --resume.
"""

import json
import socket
import time
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

def test_prompt_size(size_kb):
    """Test sending a prompt of specific size"""
    
    # Generate test prompt
    base_text = "This is a test prompt to check size limits. "
    repeat_count = (size_kb * 1024) // len(base_text)
    test_prompt = base_text * repeat_count
    actual_size = len(test_prompt)
    
    print(f"\nTesting {size_kb}KB prompt (actual: {actual_size} bytes)...")
    
    # Send to daemon
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        command = f"SPAWN::{test_prompt}"
        
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        # Read response
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        # Parse response
        result = json.loads(response.decode())
        
        if 'error' in result:
            print(f"❌ Failed: {result['error']}")
            return False
        else:
            print(f"✅ Success! Session: {result.get('session_id', 'unknown')}")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        sock.close()

def test_handoff_prompt():
    """Test the actual handoff prompt"""
    handoff_file = Path("autonomous_experiments/session_handoff.json")
    
    if not handoff_file.exists():
        print("❌ No handoff file found")
        return False
    
    with open(handoff_file, 'r') as f:
        handoff_data = json.load(f)
    
    seed_prompt = handoff_data.get("new_session_seed", "")
    size_kb = len(seed_prompt) / 1024
    
    print(f"\nTesting actual handoff prompt ({size_kb:.1f}KB)...")
    
    # Send to daemon
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        command = f"SPAWN::{seed_prompt}"
        
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        # Read response with timeout
        sock.settimeout(30.0)  # 30 second timeout
        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                print("⏱️  Timeout waiting for response")
                break
        
        # Parse response
        try:
            result = json.loads(response.decode())
            
            if 'error' in result:
                print(f"❌ Failed: {result['error']}")
                if 'stderr' in result:
                    print(f"Stderr: {result['stderr']}")
                return False
            else:
                print(f"✅ Success! Session: {result.get('session_id', 'unknown')}")
                print(f"Response length: {len(result.get('result', ''))}")
                return True
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response: {response[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        sock.close()

def main():
    """Run tests"""
    print("Testing Large Prompt Sizes Through Daemon")
    print("=" * 50)
    
    # Test increasing sizes
    sizes = [1, 5, 10, 12, 15]
    results = {}
    
    for size in sizes:
        results[size] = test_prompt_size(size)
        time.sleep(2)  # Give daemon a break
    
    # Summary
    print("\nSummary:")
    for size, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {size}KB: {'SUCCESS' if success else 'FAILED'}")
    
    # Test actual handoff
    print("\n" + "=" * 50)
    handoff_success = test_handoff_prompt()
    
    if handoff_success:
        print("\n🎉 Handoff prompt works! You can use:")
        print("python3 tools/extract_seed_prompt.py  # First extract the seed")
        print("python3 chat.py --new --prompt autonomous_experiments/session_seed.txt")

if __name__ == "__main__":
    main()