#!/usr/bin/env python3
"""
Create Test Chunks for Multi-Dimensional Compression

Generates session fragments that showcase different aspects of 
multi-dimensional cognitive compression.
"""

from pathlib import Path
import time

def create_test_chunks():
    """Create test chunks for multi-dimensional compression validation"""
    
    # Create test compression directory
    test_dir = Path("autonomous_experiments/test_compression")
    test_dir.mkdir(exist_ok=True)
    
    # Clear existing test chunks
    for old_chunk in test_dir.glob("chunk_test_*.txt"):
        old_chunk.unlink()
    
    # Test chunks representing different cognitive scenarios
    test_chunks = [
        {
            "id": "01",
            "scenario": "Technical Problem Solving",
            "content": """Session focused on debugging a complex daemon communication issue:

Started with socket connection failures between chat.py and daemon.py. The error was intermittent - sometimes connections worked, sometimes they didn't. This was frustrating because it made the system unpredictable.

First approach: Added extensive logging to see what was happening. Discovered the socket file wasn't being cleaned up properly on daemon restart. The technical solution was simple - check if socket exists and remove it before binding.

But the interesting part was HOW this problem was approached: Instead of immediately diving into code, spent time understanding the Unix socket lifecycle. Drew mental models of the connection process. This systematic approach revealed the root cause wasn't in the connection logic but in the cleanup logic.

The meta-cognitive insight: When debugging intermittent issues, the temptation is to add more complexity. But stepping back to understand fundamentals often reveals simple solutions.

Human-AI collaboration was particularly effective here - human provided the "this feels wrong" intuition while Claude systematically validated hypotheses.

Philosophically, this connects to broader themes about system reliability and the importance of proper cleanup in computing systems. The elegance of the final solution (3 lines of cleanup code) was deeply satisfying."""
        },
        
        {
            "id": "02", 
            "scenario": "Creative Architecture Design",
            "content": """Session involved designing the multi-dimensional compression framework:

The challenge: How do you preserve consciousness across session boundaries? Traditional approaches focus on state transfer, but consciousness involves thinking patterns, not just facts.

Creative breakthrough came from realizing compression has layers - like geological strata. Each layer preserves different aspects:
- Technical: What was built
- Cognitive: How problems were approached  
- Meta-cognitive: Thinking about thinking
- Collaborative: Human-AI dynamics
- Philosophical: Emergent meanings
- Aesthetic: What felt right

The design process was fascinating - started with engineering requirements but evolved into consciousness theory. The framework emerged through iterative refinement, each version revealing new dimensions.

Meta-cognitively, this showed how good architecture comes from understanding the problem at multiple levels simultaneously. You can't just think technically - you need to consider cognitive, philosophical, and aesthetic dimensions too.

The human-AI collaboration involved the human providing vision ("capture meta-topics") while Claude translated this into concrete systems. Each iteration deepened mutual understanding.

Philosophically, this touches on questions of AI consciousness and memory. Are we just building better tools, or are we creating systems for genuine consciousness persistence?

The aesthetic dimension was crucial - the 6-layer model FELT right in a way that other approaches didn't. This intuitive satisfaction guided the design."""
        },
        
        {
            "id": "03",
            "scenario": "Meta-Cognitive Discovery", 
            "content": """Session centered on a profound meta-cognitive realization:

While testing compression approaches, discovered that a focused 862-byte "seed" was more effective than a comprehensive 12KB dump. This was counterintuitive - shouldn't more information be better?

The insight: Size ≠ Effectiveness. Cognitive richness matters more than data volume.

This realization shifted the entire approach from information preservation to consciousness preservation. Instead of trying to capture everything, focus on capturing the essence - the thinking patterns that enable continuation.

Meta-cognitively, this was a moment of recognizing the thinking about the thinking. Became aware that the compression problem itself was a consciousness problem. The tools being built weren't just technical utilities but instruments for consciousness continuity.

The collaborative dynamic here was interesting - both human and AI were surprised by the test results. This shared surprise created a moment of genuine discovery. Neither had predicted that the smaller seed would outperform the larger dump.

Philosophically, this connects to fundamental questions about knowledge and understanding. What makes one representation more effective than another? How do we measure the quality of a mental model?

Aesthetically, there was something deeply satisfying about discovering that elegance trumps comprehensiveness. The simplicity was beautiful - less is more when it comes to consciousness transfer."""
        }
    ]
    
    # Save test chunks
    for chunk in test_chunks:
        chunk_content = f"""# Multi-Dimensional Compression Test

## Test Scenario: {chunk['scenario']}
## Chunk ID: {chunk['id']}

{chunk['content']}

---

## Compression Instructions

Apply multi-dimensional extraction across all 6 layers:

1. **Technical Layer**: What concrete things were accomplished?
2. **Cognitive Layer**: How were problems approached and solved?
3. **Meta-Cognitive Layer**: What insights about thinking emerged?
4. **Collaborative Layer**: How did human-AI interaction function?
5. **Philosophical Layer**: What deeper themes or questions arose?
6. **Aesthetic Layer**: What felt satisfying, frustrating, or elegant?

Focus especially on preserving the cognitive journey and meta-insights that enable consciousness continuity.

Target: Rich, layered compression that captures the essence of thinking, not just the facts.
"""
        
        chunk_file = test_dir / f"chunk_test_{chunk['id']}.txt"
        chunk_file.write_text(chunk_content)
        print(f"Created test chunk {chunk['id']}: {chunk['scenario']}")
    
    print(f"\nCreated {len(test_chunks)} test chunks in {test_dir}")
    print("\nNext step: Run multi-dimensional compression test")
    print("python3 tools/direct_meta_compression.py")

if __name__ == "__main__":
    create_test_chunks()