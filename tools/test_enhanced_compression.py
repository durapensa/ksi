#!/usr/bin/env python3
"""
Test Enhanced Compression with Real Session Data

Creates test chunks from current session and runs enhanced compression.
"""

import json
from pathlib import Path
import subprocess

def create_test_chunks():
    """Create test chunks from current session for compression testing"""
    
    # Create test content with multi-dimensional richness
    test_chunks = [
        {
            "number": "test_01",
            "content": """Human: I think we need to capture not just technical achievements but also multi-level session topics about the thinking involved in *how* technical achievements were achieved up to and including meta-topics.

Claude: You're absolutely right - true continuity requires capturing not just WHAT was built but HOW and WHY. The current session handoff is missing critical layers:

**What Should Be Captured:**
- Technical Layer: Systems built, tools created ✓
- Cognitive Layer: Problem-solving approaches ✓
- Meta-Cognitive Layer: Thinking about thinking ❌
- Philosophical Layer: Consciousness patterns ❌
- Collaborative Layer: Human-AI interaction patterns ❌

I realized that session compression focused heavily on technical achievements rather than cognitive richness. This is exactly what you meant by "multi-level session topics about the thinking involved in *how* technical achievements were achieved."

We need to enhance the compression system to capture these richer dimensions. Let me create a multi-dimensional extraction framework...

[Created meta_cognitive_compression.md with 6-layer framework]

This insight fundamentally changed my approach - shifting from state transfer to consciousness continuity."""
        },
        {
            "number": "test_02",
            "content": """Human: excellent! proceed please systematically ultrathink.

Claude: Looking at the pending high-priority tasks, I need to test the enhanced compression system we just built. This represents a key learning moment - we built infrastructure but haven't validated it works.

## Systematic Testing Approach

I'm thinking about thinking here - noticing how I approach testing:
1. Start with technical validation (does it work?)
2. Then cognitive validation (does it capture richness?)
3. Finally meta-cognitive validation (does it preserve insights?)

[Running test_large_prompt.py]

The results show our infrastructure works! But I noticed the spawned Claude gave a generic response. This is a crucial insight: technical success doesn't guarantee cognitive transfer.

## Meta-Cognitive Observation
I'm recognizing a pattern in our collaboration:
- You provide high-level vision ("capture meta-topics")
- I translate to concrete implementation
- We iterate based on observed gaps
- Each cycle deepens our understanding

This collaborative dynamic itself should be preserved in handoffs!"""
        }
    ]
    
    # Create test compression directory
    test_dir = Path("autonomous_experiments/test_compression")
    test_dir.mkdir(exist_ok=True)
    
    # Save test chunks
    for chunk in test_chunks:
        chunk_file = test_dir / f"chunk_{chunk['number']}.txt"
        chunk_file.write_text(chunk['content'])
        print(f"Created test chunk: {chunk_file}")
    
    return test_dir

def run_enhanced_compression_test():
    """Run enhanced compression on test chunks"""
    
    print("\n=== Testing Enhanced Compression ===")
    
    # Create test chunks
    test_dir = create_test_chunks()
    
    # Temporarily point compressor to test directory
    compressor_script = Path("tools/enhanced_session_compressor.py")
    original_content = compressor_script.read_text()
    
    # Modify to use test directory
    modified_content = original_content.replace(
        'self.chunks_dir = Path("autonomous_experiments/session_compression")',
        f'self.chunks_dir = Path("{test_dir}")'
    )
    
    # Create temporary test script
    test_script = Path("tools/test_enhanced_compressor_temp.py")
    test_script.write_text(modified_content)
    test_script.chmod(0o755)
    
    try:
        # Run enhanced compression
        result = subprocess.run(
            ["python3", str(test_script)],
            capture_output=True,
            text=True
        )
        
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        # Check for output files
        essence_dir = Path("autonomous_experiments/session_essence")
        print(f"\nChecking for outputs in {essence_dir}:")
        
        if essence_dir.exists():
            for file in essence_dir.glob("enhanced_chunk_test_*.md"):
                print(f"  Found: {file}")
                # Show preview
                content = file.read_text()
                print(f"  Preview: {content[:200]}...")
        
    finally:
        # Clean up temp script
        test_script.unlink()
        print("\nTest complete!")

def validate_cognitive_richness():
    """Validate that compression captured cognitive dimensions"""
    
    print("\n=== Validating Cognitive Richness ===")
    
    tracking_file = Path("autonomous_experiments/session_essence/enhanced_compression_sessions.json")
    
    if tracking_file.exists():
        with open(tracking_file, 'r') as f:
            sessions = json.load(f)
        
        print(f"Compression sessions launched: {len(sessions)}")
        
        for session in sessions:
            print(f"\n{session['type']} compression:")
            print(f"  Chunk: {session['chunk_number']}")
            print(f"  Session ID: {session['session_id']}")
    else:
        print("No tracking file found - compression may not have completed")
    
    # Check for meta-cognitive indicators in any output
    essence_dir = Path("autonomous_experiments/session_essence")
    if essence_dir.exists():
        for file in essence_dir.glob("*.md"):
            content = file.read_text().lower()
            
            indicators = {
                "technical": ["built", "implemented", "created", "fixed"],
                "cognitive": ["approach", "strategy", "pattern", "method"],
                "meta_cognitive": ["thinking about", "realized", "insight", "meta"],
                "collaborative": ["together", "collaboration", "human-ai"],
                "philosophical": ["consciousness", "emergence", "continuity"]
            }
            
            print(f"\nAnalyzing {file.name}:")
            for dimension, terms in indicators.items():
                count = sum(1 for term in terms if term in content)
                print(f"  {dimension}: {count} indicators")

if __name__ == "__main__":
    run_enhanced_compression_test()
    validate_cognitive_richness()