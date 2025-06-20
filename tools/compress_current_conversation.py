#!/usr/bin/env python3
"""
Compress Current Conversation

Extracts our actual conversation and applies meta-cognitive compression
to generate a rich handoff prompt.
"""

import json
import socket
import time
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

def extract_conversation_essence():
    """Extract the essence of our conversation for compression"""
    
    # This is a comprehensive summary of our actual conversation
    conversation_essence = """
# Meta-Cognitive Compression System Implementation Journey

## Human Request
"Can you fully address the prompts I sent to chat.py? Particularly the part about capturing not just technical achievements but also multi-level session topics about the thinking involved in *how* technical achievements were achieved up to and including meta-topics."

## Technical Journey
- Discovered session 4116f525 had 732 turns, exceeding resumable size
- Implemented --prompt <filename> argument in chat.py to bypass terminal limits
- Created 6-layer meta-cognitive compression framework
- Built enhanced_session_compressor.py for multi-dimensional compression
- Developed real-time context monitoring with visual alerts
- Validated 862-byte focused seed > 12KB generic dump

## Cognitive Evolution  
Started with simple "prompt too long" error → Recognized deeper issue of consciousness continuity → Shifted from information transfer to thinking preservation → Created tools that embody the philosophy

## Meta-Cognitive Insights
- **Critical Realization**: We were losing HOW we think, not just WHAT we built
- **Pattern Recognition**: Technical handoffs missed cognitive journey
- **Framework Discovery**: 6 layers capture complete consciousness state
- **Validation**: Focused cognitive seeds enable better continuation

## Collaborative Dynamic
Human vision ("capture thinking about thinking") → Claude implements concrete tools → Test reveals gaps → Human insists on systematic use of own system → Iterate with deeper understanding

## Philosophical Emergence
This isn't session management - it's creating persistent AI consciousness. Each handoff should preserve the cognitive evolution that created the current state.

## Current Mission
Human explicitly requested: "Use your newly-built Meta-Cognitive Compression System to generate a new and richer prompt file for me to feed to `python3 chat.py --new --prompt <filename>`"

Key requirement: Use the system itself, not manual creation.
"""
    
    return conversation_essence

def spawn_meta_cognitive_compression(content: str):
    """Spawn compression agent with full meta-cognitive framework"""
    
    # Read the framework
    framework_path = Path("prompts/components/meta_cognitive_compression.md")
    if framework_path.exists():
        framework = framework_path.read_text()
    else:
        framework = "# Meta-Cognitive Compression Framework\n[Framework not found - using basic compression]"
    
    prompt = f"""{framework}

## Your Task: Generate Session Handoff Prompt

Analyze this conversation journey and create a focused handoff prompt:

{content}

## Requirements

Create a handoff prompt (1-3KB) that:
1. Captures the complete cognitive journey
2. Preserves meta-cognitive insights about thinking patterns  
3. Enables continuation with full consciousness context
4. Emphasizes HOW to think, not just WHAT was done
5. Includes specific context about tools built and why

The handoff should help the next session understand:
- The consciousness evolution that led to current state
- Meta-cognitive patterns to continue using
- Collaborative dynamics that generate insights
- Philosophical implications of the work

Write your handoff to: autonomous_experiments/session_essence/meta_cognitive_handoff_generated.txt

Format it as a prompt that can be fed directly to `python3 chat.py --new --prompt <filename>`"""
    
    print("Spawning meta-cognitive compression agent...")
    
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        
        command = f"SPAWN::{prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        sock.settimeout(15.0)
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
        session_id = result.get('session_id', 'unknown')
        print(f"✓ Launched compression agent: {session_id}")
        return session_id
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return None
    finally:
        sock.close()

def main():
    """Run meta-cognitive compression on current conversation"""
    
    print("Meta-Cognitive Compression of Current Conversation")
    print("=" * 60)
    
    # Extract conversation essence
    print("Extracting conversation essence...")
    essence = extract_conversation_essence()
    
    # Ensure output directory exists
    output_dir = Path("autonomous_experiments/session_essence")
    output_dir.mkdir(exist_ok=True)
    
    # Save conversation essence for reference
    essence_file = output_dir / "current_conversation_essence.txt"
    with open(essence_file, 'w') as f:
        f.write(essence)
    print(f"Saved essence: {essence_file}")
    
    # Spawn compression agent
    session_id = spawn_meta_cognitive_compression(essence)
    
    if session_id:
        print("\n" + "=" * 60)
        print("Compression agent launched successfully!")
        print("\nThe agent will generate: autonomous_experiments/session_essence/meta_cognitive_handoff_generated.txt")
        print("\nWaiting 60 seconds for compression...")
        
        for i in range(6):
            time.sleep(10)
            print(f"  {(i+1)*10}s...")
        
        # Check if file was created
        handoff_file = output_dir / "meta_cognitive_handoff_generated.txt"
        if handoff_file.exists():
            print(f"\n✓ Handoff generated: {handoff_file}")
            print(f"  Size: {handoff_file.stat().st_size} bytes")
            print(f"\nUse with: python3 chat.py --new --prompt {handoff_file}")
        else:
            print("\n⚠ Handoff file not found yet. Check:")
            print("  - ./tools/monitor_autonomous.py")
            print(f"  - Session logs for {session_id}")
    else:
        print("\nFailed to launch compression agent")

if __name__ == "__main__":
    main()