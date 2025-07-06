#!/usr/bin/env python3
"""
Find the current Claude conversation session ID.
Based on find_sid.sh logic.
"""

import os
import glob
from pathlib import Path

def find_conversation_session_id():
    """Find the current conversation session ID."""
    
    # Get current directory and encode it
    cwd = os.getcwd()
    encoded_path = cwd.replace('/', '-')
    
    # Build path to conversation files
    claude_projects_dir = os.path.expanduser(f"~/.claude/projects/{encoded_path}")
    
    print(f"Current directory: {cwd}")
    print(f"Encoded path: {encoded_path}")
    print(f"Looking in: {claude_projects_dir}")
    
    # Find all .jsonl files
    pattern = os.path.join(claude_projects_dir, "*.jsonl")
    files = glob.glob(pattern)
    
    if not files:
        print(f"\n❌ No conversation files found in {claude_projects_dir}")
        return None
    
    # Get the most recent file
    latest_file = max(files, key=os.path.getmtime)
    
    # Extract session ID from filename
    session_id = Path(latest_file).stem
    
    print(f"\n✓ Found conversation file: {os.path.basename(latest_file)}")
    print(f"✓ Session ID: {session_id}")
    
    # Show file age
    import time
    file_age = time.time() - os.path.getmtime(latest_file)
    if file_age < 3600:
        print(f"  Age: {int(file_age/60)} minutes")
    else:
        print(f"  Age: {file_age/3600:.1f} hours")
    
    return session_id

if __name__ == "__main__":
    session_id = find_conversation_session_id()
    
    if session_id:
        print(f"\nExport for shell use:")
        print(f"export CLAUDE_SESSION_ID='{session_id}'")
    else:
        import sys
        sys.exit(1)