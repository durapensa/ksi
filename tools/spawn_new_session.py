#!/usr/bin/env python3
"""
Spawn New Orchestrator Session

Starts a new chat.py session with comprehensive context from session handoff.
"""

import json
import subprocess
import tempfile
from pathlib import Path

def spawn_new_session():
    """Spawn a new chat.py session with handoff context"""
    
    # Read the session handoff
    handoff_file = Path("autonomous_experiments/session_handoff.json")
    if not handoff_file.exists():
        print("❌ No session handoff found. Run session orchestrator first:")
        print("python3 tools/session_orchestrator.py --prepare-handoff")
        return False
    
    with open(handoff_file, 'r') as f:
        handoff_data = json.load(f)
    
    # Extract the new session seed prompt
    seed_prompt = handoff_data.get("new_session_seed", "")
    
    if not seed_prompt:
        print("❌ No seed prompt found in handoff data")
        return False
    
    # Create a temporary file with the seed prompt
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(seed_prompt)
        seed_file = f.name
    
    print("=== Spawning New Orchestrator Session ===")
    print(f"Session ID from handoff: {handoff_data.get('previous_session_essence', {}).get('session_metadata', {}).get('session_id', 'unknown')}")
    print(f"Context preserved: {len(seed_prompt)} characters")
    print(f"Seed file: {seed_file}")
    print()
    print("Starting new chat.py session with context...")
    print()
    
    # Start chat.py with the seed prompt as initial input
    try:
        # Use cat to pipe the seed prompt into chat.py
        result = subprocess.run([
            "sh", "-c", f"cat '{seed_file}' | python3 chat.py"
        ], cwd=".")
        
        # Clean up temp file
        Path(seed_file).unlink()
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Failed to spawn new session: {e}")
        Path(seed_file).unlink()
        return False

def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Spawn new orchestrator session with handoff context")
    parser.add_argument("--show-seed", action="store_true", help="Show the seed prompt instead of spawning")
    
    args = parser.parse_args()
    
    if args.show_seed:
        # Show the seed prompt
        handoff_file = Path("autonomous_experiments/session_handoff.json")
        if not handoff_file.exists():
            print("❌ No session handoff found")
            return
            
        with open(handoff_file, 'r') as f:
            handoff_data = json.load(f)
        
        seed_prompt = handoff_data.get("new_session_seed", "")
        print("=== New Session Seed Prompt ===")
        print(seed_prompt)
        print(f"\n=== Seed length: {len(seed_prompt)} characters ===")
    else:
        # Spawn new session
        success = spawn_new_session()
        if success:
            print("✅ New session spawned successfully")
        else:
            print("❌ Failed to spawn new session")

if __name__ == "__main__":
    main()