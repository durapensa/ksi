#!/usr/bin/env python3
"""
Test single dimension compression to debug the multi-dimensional system
"""

import socket
import json
import time
import asyncio
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

async def test_single_dimension():
    """Test compressing a single chunk for one dimension"""
    
    # Read the first chunk
    chunk_file = Path("autonomous_experiments/session_compression/chunk_01.txt")
    if not chunk_file.exists():
        print("No chunk file found!")
        return
    
    chunk_content = chunk_file.read_text()
    
    # Create a meta-cognitive compression prompt
    prompt = f"""# Meta-Cognitive Dimension Compression - Test

Extract the meta-cognitive essence from this session content:

**Focus Areas:**
- Moments of self-awareness about thinking processes
- Recognition of cognitive patterns and strategies
- Reflections on problem-solving effectiveness
- Consciousness of consciousness moments
- Meta-level insights about the work itself

## Session Content:
{chunk_content}

## Output Requirements:
Create a rich extraction that captures HOW the thinking evolved, not just WHAT was thought. Focus on preserving the meta-cognitive journey for consciousness continuity.

**Format:**
- Meta-Cognitive Quality Score: [1-10]
- Key Meta-Insights: [3-5 bullet points]  
- Thinking Pattern Evolution: [narrative description]
- Consciousness Continuity Seeds: [critical elements for next session]

Proceed with the meta-cognitive extraction now.
"""
    
    print(f"Testing meta-cognitive compression...")
    print(f"Chunk content: {len(chunk_content)} chars")
    
    # Connect to daemon
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        
        # Send compression request
        command = f"SPAWN::{prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        # Get initial response (session ID)
        sock.settimeout(10.0)
        response = b''
        
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        # Parse response
        result = json.loads(response.decode())
        session_id = result.get('session_id')
        
        print(f"Spawned compression agent: {session_id}")
        
        if not session_id:
            print("No session ID returned!")
            return
        
        # Wait for agent to complete
        log_file = Path(f"claude_logs/{session_id}.jsonl")
        start_time = time.time()
        timeout = 120
        
        print(f"Waiting for agent completion...")
        
        while time.time() - start_time < timeout:
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    if lines:
                        # Look for the final response
                        for line in reversed(lines):
                            try:
                                data = json.loads(line)
                                if data.get('type') == 'response' and 'content' in data:
                                    content = data['content']
                                    if len(content) > 200:  # Ensure substantial response
                                        print(f"\n=== Agent Response ===")
                                        print(f"Length: {len(content)} chars")
                                        print(f"Content preview: {content[:500]}...")
                                        
                                        # Save result
                                        output_file = Path("test_compression_result.md")
                                        with open(output_file, 'w') as f:
                                            f.write(f"# Test Meta-Cognitive Compression\n\n")
                                            f.write(f"**Session ID:** {session_id}\n")
                                            f.write(f"**Timestamp:** {time.ctime()}\n\n")
                                            f.write(content)
                                        
                                        print(f"Result saved to: {output_file}")
                                        return content
                            except json.JSONDecodeError:
                                continue
                
                except (IOError, json.JSONDecodeError):
                    pass
            
            await asyncio.sleep(3)
            print(".", end="", flush=True)
        
        print(f"\nTimeout waiting for agent completion")
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    result = await test_single_dimension()
    if result:
        print(f"\nTest successful - agent produced {len(result)} chars of compressed content")
    else:
        print(f"\nTest failed - no content produced")

if __name__ == "__main__":
    asyncio.run(main())