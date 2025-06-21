#!/usr/bin/env python3
"""
Controlled test of natural tool communication with SPAWN_AGENT
Only spawns one agent, tests it, then cleans up before proceeding
"""

import asyncio
import json
import time
import sys
from pathlib import Path

# Import orchestrator functionality instead of duplicating
sys.path.insert(0, str(Path(__file__).parent.parent))
from orchestrate_v2 import MultiClaudeOrchestrator

async def check_agent_count(orchestrator):
    """Check how many agents are currently active"""
    result = await orchestrator._send_daemon_command("GET_AGENTS")
    if result and 'agents' in result:
        return len(result['agents'])
    return 0

async def wait_for_agent_registration(orchestrator, expected_count=1, timeout=5):
    """Wait for agent to register with daemon"""
    for i in range(timeout):
        count = await check_agent_count(orchestrator)
        if count >= expected_count:
            return True
        await asyncio.sleep(1)
    return False

async def cleanup_all_agents():
    """Clean up any running agents"""
    import subprocess
    subprocess.run(['pkill', '-f', 'agent_process.py'], capture_output=True)
    await asyncio.sleep(2)  # Give time for cleanup

async def test_single_agent_natural_tools():
    """Test one agent with natural tool communication"""
    print("Testing Single Agent Natural Tool Communication")
    print("=" * 60)
    
    # Use orchestrator for daemon communication
    orchestrator = MultiClaudeOrchestrator()
    
    # 1. Verify clean state
    initial_count = await check_agent_count(orchestrator)
    if initial_count > 0:
        print(f"⚠ Found {initial_count} existing agents - cleaning up first")
        await cleanup_all_agents()
        initial_count = await check_agent_count(orchestrator)
        print(f"✓ Clean state: {initial_count} agents")
    
    # 2. Spawn ONE agent with tool access
    print("\n1. Spawning tool_tester agent...")
    spawn_result = await orchestrator._send_daemon_command("SPAWN_AGENT:tool_tester:Ready for tool testing::")
    
    if not spawn_result or 'process_id' not in spawn_result:
        print(f"✗ Failed to spawn agent: {spawn_result}")
        return False
    
    process_id = spawn_result['process_id']
    print(f"✓ Spawned agent (process {process_id})")
    
    # 3. Wait for registration and get actual agent ID
    print("\n2. Waiting for agent registration...")
    if not await wait_for_agent_registration(orchestrator):
        print("✗ Agent failed to register")
        return False
    
    # Get the actual registered agent ID
    agents_result = await orchestrator._send_daemon_command("GET_AGENTS")
    if agents_result and 'agents' in agents_result:
        active_agents = agents_result['agents']
        if active_agents:
            # Get the first (and should be only) agent
            agent_id = list(active_agents.keys())[0]
            print(f"✓ Agent registered with ID: {agent_id}")
        else:
            print("✗ No agents found after spawn")
            return False
    else:
        print("✗ Could not get agent list")
        return False
    
    # Give agent extra time to fully initialize
    await asyncio.sleep(3)
    print("✓ Agent stabilized")
    
    # 4. Send direct message to agent
    print(f"\n3. Sending direct message to {agent_id}...")
    direct_message = {
        'to': agent_id,
        'content': 'Please create a file at tests/agent_demo.txt with content "Natural tool test successful" and then read it back to verify. Naturally mention what tools you\'re using.',
        'conversation_id': 'tool_test_001',
        'from': 'test_controller'
    }
    
    command = f"PUBLISH:test_controller:DIRECT_MESSAGE:{json.dumps(direct_message)}"
    pub_result = await orchestrator._send_daemon_command(command)
    print(f"✓ Direct message sent: {pub_result}")
    
    # 5. Wait longer for completion
    print("\n4. Waiting for task completion...")
    await asyncio.sleep(10)
    
    # 6. Check results
    print("\n5. Checking results...")
    test_file = Path('tests/agent_demo.txt')
    if test_file.exists():
        content = test_file.read_text()
        print(f"✓ File created: {content}")
        test_file.unlink()  # cleanup
    else:
        print("? File not created")
    
    # 7. Check shared state for agent communication
    print("\n6. Checking agent communication...")
    shared_dir = Path('shared_state')
    if shared_dir.exists():
        recent_files = sorted(shared_dir.glob('*.json'), 
                            key=lambda x: x.stat().st_mtime, reverse=True)[:3]
        
        for file in recent_files:
            try:
                with open(file) as f:
                    data = json.load(f)
                    if isinstance(data, str) and any(word in data.lower() 
                                                   for word in ['tool', 'file', 'read', 'write', 'create']):
                        print(f"✓ Found tool communication: {data[:100]}...")
                        break
            except:
                pass
    
    # 8. MANDATORY CLEANUP
    print("\n7. Cleaning up...")
    import subprocess
    subprocess.run(['pkill', '-f', 'agent_process.py'], capture_output=True)
    await asyncio.sleep(2)
    
    final_count = await check_agent_count(orchestrator)
    print(f"✓ Cleanup complete (agents remaining: {final_count})")
    
    return True

async def main():
    """Run controlled test"""
    # Check daemon first using orchestrator
    orchestrator = MultiClaudeOrchestrator()
    if not await orchestrator.ensure_daemon_running():
        print("✗ Daemon not running. Start with: ./daemon_control.sh start")
        return
    
    print("✓ Daemon is healthy\n")
    
    # Run test
    success = await test_single_agent_natural_tools()
    
    if success:
        print("\n✓ Test completed successfully")
    else:
        print("\n✗ Test failed")

if __name__ == '__main__':
    asyncio.run(main())