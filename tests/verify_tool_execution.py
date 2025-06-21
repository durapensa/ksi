#!/usr/bin/env python3
"""
Verify that Claude actually executes tools and we can log it
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def send_daemon_command(command: str) -> dict:
    """Send command to daemon and get response"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        if not command.endswith('\n'):
            command += '\n'
        writer.write(command.encode())
        await writer.drain()
        
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        if response:
            response_str = response.decode().strip()
            # Handle plain text responses like HEALTH_CHECK
            if response_str == 'HEALTHY':
                return {'status': 'healthy'}
            # Otherwise parse as JSON
            return json.loads(response_str)
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

async def test_file_creation():
    """Test that Claude actually creates a file using tools"""
    print("Testing Actual Tool Execution")
    print("=" * 50)
    
    # Define test file
    test_file = Path('tests/tool_test_output.txt')
    timestamp = time.time()
    
    # Remove file if it exists
    if test_file.exists():
        test_file.unlink()
        print(f"✓ Cleaned up existing test file")
    
    # Ask Claude to create the file
    prompt = f"""Please help me test tool usage by doing the following:

1. Use the Write tool to create a file at tests/tool_test_output.txt
2. In the file, write: "Tool test successful at timestamp {timestamp}"
3. Then use the Read tool to verify the file was created
4. Tell me what you found

Remember to signal each tool use with [TOOL_USE] before using it."""
    
    print(f"\nAsking Claude to create: {test_file}")
    command = f"SPAWN:sync:claude::sonnet:tool_verify:{prompt}"
    result = await send_daemon_command(command)
    
    if result and 'result' in result:
        print(f"\nClaude's response:")
        print("-" * 50)
        print(result['result'])
        print("-" * 50)
        
        # Check if file was created
        if test_file.exists():
            print(f"\n✓ SUCCESS: File was created at {test_file}")
            
            # Read the file
            with open(test_file) as f:
                content = f.read()
                print(f"✓ File content: {content}")
                
                # Verify content
                if str(timestamp) in content:
                    print("✓ Timestamp verified - Claude executed the Write tool!")
        else:
            print(f"\n✗ FAIL: File was not created at {test_file}")
            print("  Claude may not have tool access or didn't execute the tool")
        
        # Check for tool signals
        if '[TOOL_USE]' in result['result']:
            print("\n✓ Found [TOOL_USE] signals in response")
        else:
            print("\n⚠ No [TOOL_USE] signals found")
            
        # Check session stats
        if 'usage' in result:
            tool_use = result['usage'].get('server_tool_use', {})
            print(f"\nServer tool usage stats: {tool_use}")
            
        return result.get('session_id')
    else:
        print(f"\n✗ Error: {result}")
        return None

async def test_bash_execution():
    """Test Bash tool execution"""
    print("\n\nTesting Bash Tool Execution")
    print("=" * 50)
    
    # Create a marker file that Bash will modify
    marker_file = Path('tests/bash_marker.txt')
    marker_file.write_text("initial")
    
    prompt = """Please test the Bash tool:

1. [TOOL_USE] Run this command: echo "Bash tool worked at $(date)" > tests/bash_marker.txt
2. [TOOL_USE] Then run: cat tests/bash_marker.txt
3. Tell me what the file contains

Signal each tool use with [TOOL_USE]."""
    
    command = f"SPAWN:sync:claude::sonnet:bash_test:{prompt}"
    result = await send_daemon_command(command)
    
    if result and 'result' in result:
        print(f"\nClaude's response (first 500 chars):")
        print(result['result'][:500] + "...")
        
        # Check if file was modified
        new_content = marker_file.read_text()
        if "Bash tool worked" in new_content:
            print(f"\n✓ SUCCESS: Bash command executed!")
            print(f"✓ File now contains: {new_content.strip()}")
        else:
            print(f"\n✗ File still contains: {new_content}")

async def check_tool_logs(session_id: str):
    """Check if tools were logged"""
    print(f"\n\nChecking Tool Logs for session {session_id}")
    print("=" * 50)
    
    # Check tool usage log
    tool_log = Path('logs/tool_usage.jsonl')
    if tool_log.exists():
        found_session = False
        with open(tool_log) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get('session_id') == session_id:
                    found_session = True
                    print(f"✓ Found tool log entry:")
                    print(f"  Tools used: {entry['tool_count']}")
                    for tool in entry['tools_used']:
                        print(f"  - {tool['tool']}: {tool['description'][:60]}...")
        
        if not found_session:
            print("✗ No tool usage logged for this session")
    else:
        print("✗ Tool usage log file doesn't exist")

async def main():
    """Run verification tests"""
    # Check daemon
    result = await send_daemon_command("HEALTH_CHECK")
    if not result or (result.get('error') or result.get('status') != 'healthy'):
        print("✗ Daemon not running. Start with: ./daemon_control.sh start")
        return
    
    print("✓ Daemon is running\n")
    
    # Test file creation
    session_id = await test_file_creation()
    
    # Test bash execution
    await test_bash_execution()
    
    # Check logs
    if session_id:
        await check_tool_logs(session_id)
    
    # Cleanup
    for f in ['tests/tool_test_output.txt', 'tests/bash_marker.txt']:
        if Path(f).exists():
            Path(f).unlink()
    
    print("\n✓ Verification complete")

if __name__ == '__main__':
    asyncio.run(main())