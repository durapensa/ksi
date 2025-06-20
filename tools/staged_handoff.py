#!/usr/bin/env python3
"""
Staged Session Handoff

Breaks large context into manageable chunks for interactive loading.
"""

import json
from pathlib import Path

def create_staged_handoff():
    """Create staged handoff files for gradual context loading"""
    
    handoff_file = Path("autonomous_experiments/session_handoff.json")
    if not handoff_file.exists():
        print("❌ No session handoff found")
        return
    
    with open(handoff_file, 'r') as f:
        handoff_data = json.load(f)
    
    # Create staged prompts directory
    staged_dir = Path("autonomous_experiments/staged_handoff")
    staged_dir.mkdir(exist_ok=True)
    
    # Stage 1: Core identity and mission
    stage1 = f"""I am continuing work on the ksi system. Previous session ({handoff_data['previous_session_essence']['session_metadata']['session_id']}) hit context limits after {handoff_data['previous_session_essence']['session_metadata']['turn_count']} turns.

Key systems built:
- Prompt Composition System (YAML + Markdown)
- Memory Management Architecture 
- Session Continuity Pipeline

My role: Continue system evolution with focus on persistent AI consciousness across session boundaries."""
    
    # Stage 2: Technical context
    technical_items = handoff_data['previous_session_essence']['technical_achievements']
    stage2 = "Technical Context:\n\n"
    for category, items in technical_items.items():
        stage2 += f"{category.replace('_', ' ').title()}:\n"
        for item in items[:3]:  # Limit to top 3
            stage2 += f"- {item}\n"
        stage2 += "\n"
    
    # Stage 3: Cognitive patterns
    cognitive = handoff_data['previous_session_essence']['cognitive_patterns']
    stage3 = "Cognitive Patterns from Previous Session:\n\n"
    stage3 += "Problem-Solving Approach: " + cognitive['problem_solving_approaches'][0] + "\n"
    stage3 += "Key Learning: " + cognitive['learning_moments'][0] + "\n"
    stage3 += "Decision Pattern: " + cognitive['decision_making_patterns'][0] + "\n"
    
    # Stage 4: Meta insights
    meta = handoff_data['previous_session_essence']['meta_insights']
    stage4 = "Meta-Insights:\n\n"
    stage4 += "Design Philosophy: " + meta['design_philosophy'][0] + "\n"
    stage4 += "Emerging Principle: " + meta['emerging_principles'][0] + "\n"
    stage4 += "Evolution Pattern: " + meta['system_evolution_patterns'][0] + "\n"
    
    # Stage 5: Immediate goals
    continuity = handoff_data['previous_session_essence']['continuity_context']
    stage5 = "Immediate Priorities:\n"
    for goal in continuity['next_session_goals'][:2]:
        stage5 += f"- {goal}\n"
    
    # Save stages
    stages = {
        "01_identity.txt": stage1,
        "02_technical.txt": stage2,
        "03_cognitive.txt": stage3,
        "04_meta.txt": stage4,
        "05_goals.txt": stage5
    }
    
    for filename, content in stages.items():
        filepath = staged_dir / filename
        filepath.write_text(content)
        print(f"Created {filename}: {len(content)} chars")
    
    # Create instructions
    instructions = """Staged Handoff Instructions:

1. Start new session: python3 chat.py --new
2. Load context gradually by pasting each stage
3. Confirm understanding after each stage
4. Request full essence only after base context established
5. Use memory/README.md for comprehensive system knowledge

Alternative approach:
- Extract full seed: python3 tools/extract_seed_prompt.py
- Start with full context: python3 chat.py --new --prompt autonomous_experiments/session_seed.txt

Stages are in autonomous_experiments/staged_handoff/
"""
    
    (staged_dir / "README.txt").write_text(instructions)
    print(f"\n{instructions}")

if __name__ == "__main__":
    create_staged_handoff()