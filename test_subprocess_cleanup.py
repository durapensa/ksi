#!/usr/bin/env python3
"""
Test script to validate Claude CLI provider subprocess cleanup.
Tests that cancellation properly kills subprocess and doesn't leave zombies.
"""

import asyncio
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_daemon.plugins.completion.claude_cli_litellm_provider import ClaudeCLIProvider

async def test_subprocess_cleanup():
    """Test that subprocess cleanup works on cancellation."""
    
    print("Testing Claude CLI provider subprocess cleanup...")
    
    provider = ClaudeCLIProvider()
    
    # Start a long-running completion
    print("Starting long completion request...")
    
    try:
        # Create a completion task that should take a while
        task = asyncio.create_task(
            provider.acompletion(
                messages=[{
                    "role": "user", 
                    "content": "Please write a very detailed 2000-word essay about the history of computing, taking your time to be thorough and comprehensive. Include many specific details and examples."
                }],
                model="claude-cli/sonnet",
                timeout=120  # 2 minute timeout
            )
        )
        
        # Let it run for a few seconds
        print("Letting completion run for 3 seconds...")
        await asyncio.sleep(3)
        
        # Check if any claude processes are running
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'claude'], capture_output=True, text=True)
        running_processes = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        print(f"Found {len(running_processes)} claude processes before cancellation")
        for pid in running_processes:
            if pid:
                print(f"  PID: {pid}")
        
        # Cancel the task
        print("Cancelling completion task...")
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            print("Task cancelled successfully")
        
        # Wait a moment for cleanup
        await asyncio.sleep(2)
        
        # Check if claude processes are still running
        result = subprocess.run(['pgrep', '-f', 'claude'], capture_output=True, text=True)
        remaining_processes = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        print(f"Found {len(remaining_processes)} claude processes after cancellation")
        for pid in remaining_processes:
            if pid:
                print(f"  Remaining PID: {pid}")
        
        # Check provider's active processes tracking
        print(f"Provider active processes: {len(provider.active_processes)}")
        for thread_id, process in provider.active_processes.items():
            print(f"  Thread {thread_id}: PID {process.pid if process else 'None'}")
        
        # Determine success
        if len(remaining_processes) == 0 or (len(remaining_processes) == 1 and not remaining_processes[0]):
            print("✓ SUCCESS: All claude processes cleaned up properly")
            return True
        else:
            print("✗ FAILURE: Claude processes still running after cancellation")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_subprocess_cleanup())
    sys.exit(0 if result else 1)