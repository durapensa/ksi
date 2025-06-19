#!/usr/bin/env python3
"""
Test script to demonstrate the daemon functionality
"""

import subprocess
import time
import os
import signal
from client import ClaudeClient

def test_daemon():
    """Run a series of tests on the daemon"""
    print("Starting daemon test suite...\n")
    
    # Start the daemon in the background
    daemon_process = subprocess.Popen(['python3', 'daemon.py'])
    time.sleep(1)  # Give daemon time to start
    
    try:
        # Create client
        client = ClaudeClient()
        client.connect()
        print("✓ Connected to daemon")
        
        # Test ping
        result = client.ping()
        assert result['success'] and result.get('pong')
        print("✓ Ping successful")
        
        # Test loading module
        result = client.load_module('example')
        assert result['success']
        print(f"✓ Loaded module 'example' with functions: {result['functions']}")
        
        # Test calling a function
        result = client.call_function('example', 'hello', ['Claude'])
        assert result['success']
        print(f"✓ Called hello function: {result['result']}")
        
        # Test system info
        result = client.call_function('example', 'system_info')
        assert result['success']
        print(f"✓ Got system info: platform={result['result']['platform']}")
        
        # Test spawning a process
        result = client.spawn_process(['echo', 'Hello from spawned process'])
        assert result['success']
        process_id = result['process_id']
        print(f"✓ Spawned process with ID: {process_id}")
        
        # Wait a bit for process to complete
        time.sleep(0.5)
        
        # Check process info
        result = client.get_process_info(process_id)
        assert result['success']
        print(f"✓ Process info: status={result['info']['status']}")
        
        # List all processes
        result = client.list_processes()
        assert result['success']
        print(f"✓ Listed {len(result['processes'])} processes")
        
        # Test module listing
        result = client.list_modules()
        assert result['success']
        print(f"✓ Loaded modules: {list(result['modules'].keys())}")
        
        # Test hot reload by modifying the module
        print("\nTesting hot reload...")
        
        # Add a new function to the module
        with open('claude_modules/example.py', 'a') as f:
            # Ensure there's a newline before the new function
            f.write("\n\ndef new_function():\n    return \"This function was added during runtime!\"\n")
        
        # Reload the module
        result = client.load_module('example')
        if not result['success']:
            print(f"Module reload failed: {result}")
        assert result['success'], f"Module reload failed: {result}"
        assert 'new_function' in result['functions'], f"new_function not found in: {result['functions']}"
        print("✓ Module reloaded with new function")
        
        # Call the new function
        result = client.call_function('example', 'new_function')
        assert result['success']
        print(f"✓ Called new function: {result['result']}")
        
        print("\nAll tests passed! ✨")
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        raise
    finally:
        # Clean up
        print("\nShutting down daemon...")
        try:
            client.shutdown()
            client.disconnect()
        except:
            pass
        
        # Ensure daemon process is terminated
        daemon_process.terminate()
        daemon_process.wait()
        
        # Clean up socket file
        if os.path.exists('/tmp/claude_daemon.sock'):
            os.unlink('/tmp/claude_daemon.sock')

if __name__ == '__main__':
    test_daemon()