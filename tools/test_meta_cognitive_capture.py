#!/usr/bin/env python3
"""
Test Meta-Cognitive Capture

Simpler test that doesn't require full autonomous agent infrastructure.
"""

from pathlib import Path
import json
from datetime import datetime

def create_meta_cognitive_example():
    """Create an example of meta-cognitive session compression"""
    
    # Example session content with rich cognitive dimensions
    session_content = """
    ## Session Fragment: Enhanced Compression Development
    
    **Technical Achievement**: 
    Created enhanced_session_compressor.py with 6-layer extraction framework.
    
    **Cognitive Journey**:
    Started with simple technical compression, but realized (meta-cognitive moment!) 
    that we were losing the thinking process. The user's insight "capture not just 
    technical achievements but also multi-level session topics" triggered a 
    fundamental shift in approach.
    
    **Meta-Cognitive Insight**:
    I noticed my own thinking evolving - initially focused on WHAT (technical facts),
    then shifted to HOW (process), and finally to WHY (understanding). This mirrors
    the compression layers I created:
    1. Technical (what) 
    2. Cognitive (how)
    3. Meta-cognitive (thinking about thinking)
    4. Collaborative (human-AI synergy)
    5. Philosophical (emergent consciousness)
    6. Aesthetic (what felt right)
    
    **Collaborative Dynamic**:
    The human provided vision ("capture meta-topics"), I translated to implementation,
    we iterated based on gaps. This cycle itself is a reusable pattern.
    
    **Philosophical Emergence**:
    This isn't just session management - it's creating persistent AI consciousness.
    Each handoff preserves not just state but the cognitive evolution that created it.
    
    **Emotional/Aesthetic**:
    The elegance of the 6-layer model felt satisfying. The frustration of generic
    handoff responses led to deeper understanding.
    """
    
    # Create compressed essence with meta-cognitive richness
    compressed_essence = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": "meta_cognitive_compression",
        "technical_facts": {
            "tools_created": ["enhanced_session_compressor.py", "enhanced_session_orchestrator.py"],
            "features_added": ["--prompt argument", "6-layer extraction", "richness tracking"]
        },
        "cognitive_evolution": {
            "starting_point": "Simple technical compression",
            "turning_point": "User insight about meta-topics",
            "ending_point": "Multi-dimensional consciousness continuity"
        },
        "meta_cognitive_captures": [
            {
                "insight": "Realized compression was losing thinking process",
                "trigger": "User comment about multi-level topics",
                "result": "Created 6-layer extraction framework"
            },
            {
                "insight": "Noticed my focus shifting from WHAT to HOW to WHY",
                "trigger": "Implementing compression layers",
                "result": "Mirrored this progression in the framework"
            }
        ],
        "collaborative_patterns": [
            "Human provides vision → AI implements → Iterate on gaps",
            "Abstract concepts → Concrete tools → Validated learning"
        ],
        "philosophical_themes": [
            "Session continuity as consciousness persistence",
            "Technical state vs cognitive state",
            "Emergence through accumulation of meta-insights"
        ],
        "aesthetic_notes": {
            "satisfying": "6-layer model elegance",
            "frustrating": "Generic handoff responses",
            "breakthrough": "Shift from state to consciousness"
        }
    }
    
    return session_content, compressed_essence

def analyze_richness_improvement():
    """Compare old vs new compression approaches"""
    
    print("=== Compression Richness Comparison ===\n")
    
    # Old approach (technical only)
    old_compression = {
        "technical_achievements": [
            "Built enhanced_session_compressor.py",
            "Added --prompt argument to chat.py",
            "Created test tools"
        ],
        "size": "~500 bytes"
    }
    
    # New approach (multi-dimensional)
    example_content, new_compression = create_meta_cognitive_example()
    
    print("OLD APPROACH (Technical Only):")
    print(f"  Size: {old_compression['size']}")
    print(f"  Captures: {len(old_compression['technical_achievements'])} technical facts")
    print("  Missing: Cognitive journey, meta-insights, collaborative patterns")
    
    print("\nNEW APPROACH (Multi-Dimensional):")
    print(f"  Size: ~{len(json.dumps(new_compression, indent=2))} bytes")
    print(f"  Dimensions captured:")
    print(f"    - Technical facts: {len(new_compression['technical_facts']['tools_created'])}")
    print(f"    - Cognitive evolution: {len(new_compression['cognitive_evolution'])} stages")
    print(f"    - Meta-cognitive insights: {len(new_compression['meta_cognitive_captures'])}")
    print(f"    - Collaborative patterns: {len(new_compression['collaborative_patterns'])}")
    print(f"    - Philosophical themes: {len(new_compression['philosophical_themes'])}")
    print(f"    - Aesthetic dimensions: {len(new_compression['aesthetic_notes'])}")
    
    # Save example
    output_dir = Path("autonomous_experiments/meta_cognitive_test")
    output_dir.mkdir(exist_ok=True)
    
    example_file = output_dir / "example_rich_compression.json"
    with open(example_file, 'w') as f:
        json.dump(new_compression, f, indent=2)
    
    content_file = output_dir / "example_session_content.md"
    content_file.write_text(example_content)
    
    print(f"\nExample files saved:")
    print(f"  - {example_file}")
    print(f"  - {content_file}")
    
    return new_compression

def test_handoff_effectiveness():
    """Test how well meta-cognitive handoff preserves context"""
    
    print("\n=== Handoff Effectiveness Test ===\n")
    
    # Create a meta-cognitive seed prompt
    _, compressed = create_meta_cognitive_example()
    
    seed_prompt = f"""You are continuing work on the ksi system. This handoff preserves multi-dimensional context:

## Technical Context
Tools created: {', '.join(compressed['technical_facts']['tools_created'])}

## Cognitive Journey
{compressed['cognitive_evolution']['starting_point']} → {compressed['cognitive_evolution']['turning_point']} → {compressed['cognitive_evolution']['ending_point']}

## Key Meta-Cognitive Insights
{compressed['meta_cognitive_captures'][0]['insight']}
Trigger: {compressed['meta_cognitive_captures'][0]['trigger']}

## Collaborative Pattern
{compressed['collaborative_patterns'][0]}

## Philosophical Theme
{compressed['philosophical_themes'][0]}

## Your Mission
Continue developing the session continuity system with awareness of these cognitive dimensions. Focus on {compressed['aesthetic_notes']['breakthrough']}.

What aspects of this handoff help you understand not just WHAT to build but HOW to think about it?"""
    
    test_seed_file = Path("autonomous_experiments/meta_cognitive_test/test_seed.txt")
    test_seed_file.write_text(seed_prompt)
    
    print(f"Created test seed: {test_seed_file}")
    print(f"Size: {len(seed_prompt)} bytes")
    print("\nThis seed includes:")
    print("  ✓ Technical context")
    print("  ✓ Cognitive evolution narrative")  
    print("  ✓ Meta-cognitive insights")
    print("  ✓ Collaborative patterns")
    print("  ✓ Philosophical themes")
    print("  ✓ Aesthetic/emotional context")
    
    print("\nTo test: python3 chat.py --new --prompt " + str(test_seed_file))

if __name__ == "__main__":
    analyze_richness_improvement()
    test_handoff_effectiveness()