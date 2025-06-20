#!/usr/bin/env python3
"""
Extract seed prompt from session handoff
"""

import json
from pathlib import Path

def extract_seed():
    handoff_file = Path("autonomous_experiments/session_handoff.json")
    
    if not handoff_file.exists():
        print("❌ No handoff file found")
        return
    
    with open(handoff_file, 'r') as f:
        handoff_data = json.load(f)
    
    seed_prompt = handoff_data.get("new_session_seed", "")
    
    if not seed_prompt:
        print("❌ No seed prompt in handoff")
        return
    
    # Save to file
    seed_file = Path("autonomous_experiments/session_seed.txt")
    seed_file.write_text(seed_prompt)
    
    print(f"✅ Extracted seed prompt to: {seed_file}")
    print(f"Size: {len(seed_prompt)} characters ({len(seed_prompt)/1024:.1f}KB)")
    print(f"\nTo use: python3 chat.py --new --prompt {seed_file}")

if __name__ == "__main__":
    extract_seed()