#!/usr/bin/env python3
"""
Direct test of Claude CLI provider to verify subprocess spawning.
"""

import asyncio
import sys
import time
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_provider_directly():
    """Test the provider directly and monitor subprocesses."""
    
    print("Testing Claude CLI provider directly...")
    
    # Import and create provider
    from ksi_daemon.plugins.completion.claude_cli_litellm_provider import ClaudeCLIProvider
    provider = ClaudeCLIProvider()
    
    # Monitor subprocesses before
    print("\nBefore starting completion:")
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    claude_processes_before = [line for line in result.stdout.split('\n') if 'claude' in line and 'grep' not in line]
    print(f"Found {len(claude_processes_before)} claude processes")
    for proc in claude_processes_before:
        print(f"  {proc}")
    
    # Start completion and monitor in parallel
    print("\nStarting completion...")
    
    async def monitor_processes():
        """Monitor processes while completion runs."""
        for i in range(10):  # Monitor for 10 seconds
            await asyncio.sleep(1)
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            claude_processes = [line for line in result.stdout.split('\n') if 'claude' in line and 'grep' not in line]
            new_processes = [p for p in claude_processes if p not in claude_processes_before]
            if new_processes:
                print(f"Second {i+1}: Found {len(new_processes)} new claude processes:")
                for proc in new_processes:
                    print(f"  NEW: {proc}")
            else:
                print(f"Second {i+1}: No new claude processes")
    
    # Run completion and monitoring concurrently
    try:
        completion_task = asyncio.create_task(
            provider.acompletion(
                messages=[{"role": "user", "content": "Say hello"}],
                model="claude-cli/sonnet"
            )
        )
        
        monitor_task = asyncio.create_task(monitor_processes())
        
        # Wait for completion or 5 seconds, whichever comes first
        done, pending = await asyncio.wait(
            [completion_task, monitor_task], 
            timeout=10, 
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Check results
        if completion_task in done:
            result = completion_task.result()
            print(f"\nCompletion finished successfully")
            print(f"Response type: {type(result)}")
            if hasattr(result, 'choices'):
                print(f"Response content: {result.choices[0].message.content[:100]}...")
        else:
            print("\nCompletion didn't finish in time")
            
    except Exception as e:
        print(f"Error during completion: {e}")
        import traceback
        traceback.print_exc()
    
    # Check final state
    print("\nAfter completion:")
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    claude_processes_after = [line for line in result.stdout.split('\n') if 'claude' in line and 'grep' not in line]
    print(f"Found {len(claude_processes_after)} claude processes")
    for proc in claude_processes_after:
        print(f"  {proc}")

if __name__ == "__main__":
    asyncio.run(test_provider_directly())