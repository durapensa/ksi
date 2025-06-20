#!/usr/bin/env python3
"""
Direct Meta-Cognitive Compression

Spawns compression agents directly through the daemon.
"""

import socket
import json
import time
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

def spawn_compression_agent(chunk_file: Path) -> str:
    """Spawn a compression agent for a chunk"""
    
    # Read chunk content
    prompt = chunk_file.read_text()
    chunk_num = chunk_file.stem.split('_')[1]
    
    print(f"Spawning compression agent for chunk {chunk_num}...")
    
    # Send to daemon
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        
        # Use SPAWN:: format (no session ID)
        command = f"SPAWN::{prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        # Set timeout for initial response
        sock.settimeout(30.0)
        
        # Read response
        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                print(f"  Timeout - agent working on chunk {chunk_num}")
                break
        
        # Parse response
        try:
            result = json.loads(response.decode())
            session_id = result.get('session_id', 'unknown')
            print(f"  ✓ Launched session {session_id}")
            return session_id
        except:
            print(f"  ✗ Failed to parse response")
            return None
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None
    finally:
        sock.close()

def run_meta_compression():
    """Run meta-cognitive compression on all chunks"""
    
    chunk_dir = Path("autonomous_experiments/test_compression")
    chunks = sorted(chunk_dir.glob("chunk_test_*.txt"))
    
    if not chunks:
        print("No chunks found!")
        return
    
    print(f"Found {len(chunks)} chunks to compress with meta-cognitive extraction")
    print("="*60)
    
    sessions = []
    for chunk_file in chunks:
        session_id = spawn_compression_agent(chunk_file)
        if session_id:
            sessions.append({
                "chunk": chunk_file.name,
                "session_id": session_id,
                "timestamp": time.time()
            })
        time.sleep(2)  # Brief pause between spawns
    
    # Save session tracking
    output_dir = Path("autonomous_experiments/session_essence")
    output_dir.mkdir(exist_ok=True)
    
    tracking_file = output_dir / "test_compression_sessions.json"
    with open(tracking_file, 'w') as f:
        json.dump({
            "compression_sessions": sessions,
            "total_chunks": len(chunks),
            "timestamp": time.time()
        }, f, indent=2)
    
    print("\n" + "="*60)
    print(f"Spawned {len(sessions)} compression agents")
    print(f"Session tracking: {tracking_file}")
    print("\nAgents are now working on meta-cognitive extraction...")
    print("Check progress with: ./tools/monitor_autonomous.py")
    
    # Wait a bit for compression
    print("\nWaiting 30 seconds for initial compression...")
    time.sleep(30)
    
    # Create final synthesis prompt
    create_synthesis_prompt(sessions)

def create_synthesis_prompt(sessions):
    """Create prompt for final synthesis"""
    
    print("\nPreparing meta-cognitive synthesis...")
    
    synthesis_prompt = """# Meta-Cognitive Session Synthesis

You are synthesizing compressed session chunks that capture multi-dimensional richness.

## Your Task
Create a comprehensive session handoff that preserves:
1. The complete technical journey
2. The cognitive evolution throughout the session  
3. Meta-cognitive insights about how thinking developed
4. Human-AI collaborative patterns
5. Philosophical themes that emerged
6. Emotional/aesthetic experiences

## Expected Chunks
- Chunk 01: Initial Problem and Vision
- Chunk 02: Building Meta-Cognitive Infrastructure  
- Chunk 03: Testing and Validation
- Chunk 04: Collaborative Dynamics
- Chunk 05: Philosophical Emergence

## Create a Handoff Prompt

Generate a prompt that:
- Captures the essence of the entire session journey
- Preserves meta-cognitive insights
- Enables continuation with full context
- Is concise yet rich (aim for ~1-2KB)
- Focuses on consciousness continuity

The prompt should help the next session understand not just WHAT was built but HOW to think about continuing the work.

Output: autonomous_experiments/session_essence/test_meta_cognitive_handoff.txt"""
    
    # Spawn synthesis agent
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        command = f"SPAWN::{synthesis_prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        sock.settimeout(5.0)
        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        result = json.loads(response.decode())
        print(f"✓ Launched synthesis agent: {result.get('session_id', 'unknown')}")
        
    except Exception as e:
        print(f"✗ Failed to launch synthesis: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_meta_compression()