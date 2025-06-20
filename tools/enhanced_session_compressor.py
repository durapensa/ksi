#!/usr/bin/env python3
"""
Enhanced Session Compressor with Meta-Cognitive Capture

Compresses sessions with multi-dimensional extraction including:
- Technical achievements
- Cognitive patterns  
- Meta-cognitive insights
- Collaborative dynamics
- Philosophical emergence
"""

import sys
from pathlib import Path
import json
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from claude_modules.autonomous_researcher import AutonomousResearcher
from prompts.composer import PromptComposer

class EnhancedSessionCompressor:
    def __init__(self):
        self.researcher = AutonomousResearcher()
        self.composer = PromptComposer(base_path="prompts")
        self.chunks_dir = Path("autonomous_experiments/session_compression")
        self.output_dir = Path("autonomous_experiments/session_essence")
        self.output_dir.mkdir(exist_ok=True)
        
    def find_chunks(self):
        """Find all chunk files to process"""
        chunk_files = list(self.chunks_dir.glob("chunk_*.txt"))
        chunk_files.sort()
        return chunk_files
    
    def create_enhanced_chunk_prompt(self, chunk_content: str, chunk_number: str) -> str:
        """Create enhanced compression prompt with meta-cognitive focus"""
        
        prompt = f"""# Multi-Dimensional Session Compression Task

## Chunk Information
- Chunk Number: {chunk_number}
- Task: Extract multi-dimensional essence from this session chunk

## Session Content to Compress
{chunk_content}

## Extraction Requirements

You must analyze this session chunk across ALL of these dimensions:

### 1. Technical Layer
- What systems/tools/features were built or modified
- Specific problems solved and their solutions
- Architectural decisions and implementations

### 2. Cognitive Process Layer  
- How problems were approached and solved
- Decision-making rationales
- Iteration and refinement patterns

### 3. Meta-Cognitive Layer
- Insights about the thinking process itself
- Recognition of patterns across problems
- Explicit strategies for managing complexity
- Moments where understanding shifted

### 4. Collaborative Dynamics
- How human and AI built on each other's ideas
- Communication patterns that worked well
- Moments of synergistic discovery

### 5. Philosophical/Emergent Themes
- Ideas about system consciousness or evolution
- Broader implications of the work
- Design philosophy principles

### 6. Emotional/Aesthetic Dimensions
- What felt elegant or satisfying
- Sources of frustration or confusion
- "Aha!" moments and breakthroughs

## Output Format

Structure your compressed essence with these sections:

```markdown
# Session Chunk {chunk_number} - Multi-Dimensional Essence

## Technical Achievements
[Concrete things built/fixed/implemented]

## Cognitive Journey
[How thinking evolved, key problem-solving approaches]

## Meta-Cognitive Insights
[Observations about the thinking process, pattern recognition]

## Collaborative Dynamics
[How human-AI interaction created value]

## Emergent Themes
[Philosophical or systemic insights]

## Key Learning Moments
[Specific "aha!" moments or understanding shifts]
```

## Critical: Preserve Richness
- Don't just list technical facts
- Capture the narrative of discovery
- Include failed attempts that led to insights
- Preserve the "why" behind decisions
- Document moments of cognitive breakthrough

Your output file: autonomous_experiments/session_essence/enhanced_chunk_{chunk_number}.md"""
        
        return prompt
    
    def compress_chunk_enhanced(self, chunk_file: Path) -> str:
        """Compress a single chunk with enhanced meta-cognitive extraction"""
        chunk_number = chunk_file.stem.replace("chunk_", "")
        
        # Read the original chunk content
        chunk_content = chunk_file.read_text()
        
        # Create enhanced prompt
        enhanced_prompt = self.create_enhanced_chunk_prompt(chunk_content, chunk_number)
        
        print(f"[EnhancedCompressor] Compressing {chunk_file.name} with meta-cognitive extraction")
        
        # Spawn autonomous agent with enhanced compression task
        session_id = self.researcher.spawn_independent_claude(
            experiment_name=f"enhanced_compress_{chunk_number}",
            custom_prompt=enhanced_prompt
        )
        
        if session_id:
            print(f"[EnhancedCompressor] Launched enhanced compression for chunk {chunk_number} -> {session_id}")
            return session_id
        else:
            print(f"[EnhancedCompressor] Failed to spawn agent for chunk {chunk_number}")
            return None
    
    def create_meta_synthesis_prompt(self, compression_sessions: list) -> str:
        """Create synthesis prompt that preserves multi-dimensional richness"""
        
        chunk_references = []
        for session in compression_sessions:
            chunk_num = session["chunk_number"]
            chunk_references.append(f"- Enhanced chunk {chunk_num}: autonomous_experiments/session_essence/enhanced_chunk_{chunk_num}.md")
        
        prompt = f"""You are a meta-cognitive session synthesizer creating a unified essence from multi-dimensional compressions.

## Your Mission
Synthesize all compressed chunks into a cohesive narrative that preserves the complete cognitive landscape of the session.

## Input Files
{chr(10).join(chunk_references)}

## Synthesis Requirements

### 1. Preserve Multi-Dimensional Richness
- Technical achievements AND the thinking that created them
- Cognitive patterns AND meta-cognitive observations
- Concrete results AND philosophical implications

### 2. Create Narrative Coherence
- Tell the story of the session's cognitive journey
- Show how understanding evolved
- Connect insights across chunks

### 3. Extract Cumulative Wisdom
- Identify patterns that span multiple chunks
- Synthesize meta-level insights
- Capture emergent collaborative dynamics

### 4. Package for Continuity
- Create bridges for future sessions
- Preserve context for ongoing work
- Enable cumulative learning

## Output Structure

```markdown
# Session Essence: [Identify Core Theme]

## Multi-Dimensional Summary
- Technical: [Key systems/tools built]
- Cognitive: [Primary problem-solving patterns]
- Meta-Cognitive: [Insights about thinking process]
- Collaborative: [Human-AI synergy highlights]
- Philosophical: [Emergent themes]

## The Journey: Technical Narrative
[Story of what was built, including dead ends and redirections]

## The Process: Cognitive Evolution
[How understanding developed, key learning moments]

## The Insights: Meta-Cognitive Observations
[Patterns in thinking, effective strategies discovered]

## The Partnership: Collaborative Dynamics
[How human and AI co-created value]

## The Implications: Emergent Philosophy
[Broader themes about consciousness, evolution, design]

## Wisdom Extraction
[Reusable patterns and insights for future work]

## Continuity Context
[Essential information for session handoff]
```

## Quality Standards
- **Depth**: Capture insights at all levels, not just technical
- **Integration**: Show connections between layers
- **Narrative**: Tell a coherent story of discovery
- **Wisdom**: Extract generalizable insights
- **Continuity**: Enable seamless future sessions

Final output: autonomous_experiments/session_essence/meta_cognitive_essence.md"""
        
        return prompt
    
    def compress_all_enhanced(self):
        """Run enhanced compression on all chunks"""
        chunks = self.find_chunks()
        
        if not chunks:
            print("No chunks found to compress")
            return []
            
        print(f"Found {len(chunks)} chunks for enhanced compression")
        
        compression_sessions = []
        for chunk_file in chunks:
            session_id = self.compress_chunk_enhanced(chunk_file)
            if session_id:
                compression_sessions.append({
                    "chunk_file": str(chunk_file),
                    "session_id": session_id,
                    "chunk_number": chunk_file.stem.replace("chunk_", ""),
                    "type": "enhanced_meta_cognitive"
                })
                
            # Brief delay between spawns
            time.sleep(2)
            
        # Save enhanced session tracking
        tracking_file = self.output_dir / "enhanced_compression_sessions.json"
        with open(tracking_file, 'w') as f:
            json.dump(compression_sessions, f, indent=2)
            
        print(f"[EnhancedCompressor] Launched {len(compression_sessions)} enhanced compression agents")
        print(f"[EnhancedCompressor] Session tracking saved to {tracking_file}")
        
        return compression_sessions
    
    def create_meta_cognitive_synthesis(self, compression_sessions: list):
        """Create final synthesis preserving all dimensions"""
        if not compression_sessions:
            print("No compression sessions to synthesize")
            return
            
        synthesis_prompt = self.create_meta_synthesis_prompt(compression_sessions)
        
        print("[EnhancedCompressor] Creating meta-cognitive synthesis")
        
        session_id = self.researcher.spawn_independent_claude(
            experiment_name="meta_cognitive_synthesis",
            custom_prompt=synthesis_prompt
        )
        
        if session_id:
            print(f"[EnhancedCompressor] Launched meta-cognitive synthesis -> {session_id}")
            
            # Update tracking
            tracking_file = self.output_dir / "enhanced_compression_sessions.json"
            if tracking_file.exists():
                with open(tracking_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    data = {"compression_sessions": data}
                data["meta_synthesis_session"] = session_id
                with open(tracking_file, 'w') as f:
                    json.dump(data, f, indent=2)
        else:
            print("[EnhancedCompressor] Failed to spawn synthesis agent")

def main():
    print("=== Enhanced Session Compression System ===")
    print("Multi-dimensional extraction including meta-cognitive insights")
    print()
    
    compressor = EnhancedSessionCompressor()
    
    # Run enhanced compression
    compression_sessions = compressor.compress_all_enhanced()
    
    if compression_sessions:
        print(f"\nEnhanced compression agents launched.")
        print(f"These will capture:")
        print("- Technical achievements")
        print("- Cognitive patterns")
        print("- Meta-cognitive insights")
        print("- Collaborative dynamics")
        print("- Philosophical themes")
        print("- Emotional/aesthetic dimensions")
        
        print(f"\nMonitor progress: ./tools/monitor_autonomous.py")
        
        # Wait before synthesis
        print("\nWaiting 15 seconds before launching meta-cognitive synthesis...")
        time.sleep(15)
        
        compressor.create_meta_cognitive_synthesis(compression_sessions)
        
        print("\n=== Enhanced Compression Pipeline Active ===")
        print("Results will include:")
        print("1. Individual enhanced chunk compressions")
        print("2. Meta-cognitive synthesis")
        print(f"\nFinal result: autonomous_experiments/session_essence/meta_cognitive_essence.md")
    else:
        print("No compression sessions launched")

if __name__ == "__main__":
    main()