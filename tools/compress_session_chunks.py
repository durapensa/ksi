#!/usr/bin/env python3
"""
Session Compression Agent Spawner

Spawns autonomous agents to compress session chunks and combine results.
"""

import sys
from pathlib import Path
import json
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from claude_modules.autonomous_researcher import AutonomousResearcher
from prompts.composer import PromptComposer

class SessionCompressor:
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
    
    def compress_chunk(self, chunk_file: Path) -> str:
        """Compress a single chunk using autonomous agent"""
        chunk_number = chunk_file.stem.replace("chunk_", "")
        output_filename = f"compressed_chunk_{chunk_number}.md"
        
        # Read the chunk content (which contains the compression prompt)
        chunk_content = chunk_file.read_text()
        
        print(f"[SessionCompressor] Compressing {chunk_file.name}")
        
        # Spawn autonomous agent with compression task
        session_id = self.researcher.spawn_independent_claude(
            experiment_name=f"compress_chunk_{chunk_number}",
            custom_prompt=chunk_content
        )
        
        if session_id:
            print(f"[SessionCompressor] Launched compression agent for chunk {chunk_number} -> {session_id}")
            return session_id
        else:
            print(f"[SessionCompressor] Failed to spawn agent for chunk {chunk_number}")
            return None
    
    def compress_all_chunks(self):
        """Compress all chunks using autonomous agents"""
        chunks = self.find_chunks()
        
        if not chunks:
            print("No chunks found to compress")
            return []
            
        print(f"Found {len(chunks)} chunks to compress")
        
        compression_sessions = []
        for chunk_file in chunks:
            session_id = self.compress_chunk(chunk_file)
            if session_id:
                compression_sessions.append({
                    "chunk_file": str(chunk_file),
                    "session_id": session_id,
                    "chunk_number": chunk_file.stem.replace("chunk_", "")
                })
                
            # Brief delay between spawns
            time.sleep(1)
            
        # Save session tracking
        tracking_file = self.output_dir / "compression_sessions.json"
        with open(tracking_file, 'w') as f:
            json.dump(compression_sessions, f, indent=2)
            
        print(f"[SessionCompressor] Launched {len(compression_sessions)} compression agents")
        print(f"[SessionCompressor] Session tracking saved to {tracking_file}")
        
        return compression_sessions
    
    def create_essence_combiner_prompt(self, compression_sessions: list) -> str:
        """Create prompt for final essence combination"""
        
        chunk_references = []
        for session in compression_sessions:
            chunk_num = session["chunk_number"]
            chunk_references.append(f"- Compressed chunk {chunk_num}: autonomous_experiments/session_essence/compressed_chunk_{chunk_num}.md")
        
        prompt = f"""You are a session essence synthesizer. Your task is to combine compressed session chunks into a unified session essence document.

## Your Mission
Read all compressed session chunks and create a comprehensive but concise session essence that captures the complete technical journey and outcomes.

## Input Files
{chr(10).join(chunk_references)}

## Synthesis Requirements

### 1. Unified Technical Narrative
Combine all chunks into a coherent story of what was accomplished technically.

### 2. Comprehensive Architecture Overview  
Consolidate architectural decisions and system designs across all chunks.

### 3. Complete Implementation Details
Merge all technical implementation details into organized sections.

### 4. Key Insights and Patterns
Extract overarching insights and patterns that emerged across the session.

### 5. Future Continuation Context
Provide essential context for future engineering sessions to continue this work.

## Output Structure

```markdown
# Session Essence: [Session Topic]

## Executive Summary
- [Key accomplishments in 3-4 bullet points]

## Technical Architecture
- [Complete system architecture and design decisions]

## Implementation Details
- [All essential technical details organized by system/component]

## Integration and Testing
- [How systems work together and verification of functionality]

## Key Insights and Patterns
- [Important discoveries and methodological insights]

## Future Work Context
- [Essential context for continuing this work in future sessions]

## Reference Information
- [File paths, commands, configurations, and other reference data]
```

## Quality Standards
- **Complete**: Covers all significant technical work from all chunks
- **Organized**: Clear structure for quick navigation and reference
- **Actionable**: Provides sufficient detail for future work continuation
- **Concise**: Eliminates redundancy while preserving substance

Final output: autonomous_experiments/session_essence/session_essence.md"""

        return prompt
    
    def create_final_essence(self, compression_sessions: list):
        """Create final unified session essence"""
        if not compression_sessions:
            print("No compression sessions to combine")
            return
            
        essence_prompt = self.create_essence_combiner_prompt(compression_sessions)
        
        print("[SessionCompressor] Creating final session essence")
        
        session_id = self.researcher.spawn_independent_claude(
            experiment_name="session_essence_synthesis",
            custom_prompt=essence_prompt
        )
        
        if session_id:
            print(f"[SessionCompressor] Launched essence synthesis agent -> {session_id}")
            
            # Update tracking with essence synthesis
            tracking_file = self.output_dir / "compression_sessions.json"
            if tracking_file.exists():
                with open(tracking_file, 'r') as f:
                    data = json.load(f)
                data["essence_synthesis_session"] = session_id
                with open(tracking_file, 'w') as f:
                    json.dump(data, f, indent=2)
        else:
            print("[SessionCompressor] Failed to spawn essence synthesis agent")

def main():
    print("=== Session Compression System ===")
    
    compressor = SessionCompressor()
    
    # Compress all chunks
    compression_sessions = compressor.compress_all_chunks()
    
    if compression_sessions:
        print(f"\nCompression agents launched. Allow time for processing...")
        print(f"Monitor progress with: ./tools/monitor_autonomous.py")
        
        # Wait a moment then launch essence synthesis
        print("\nWaiting 10 seconds before launching essence synthesis...")
        time.sleep(10)
        
        compressor.create_final_essence(compression_sessions)
        
        print("\n=== Compression Pipeline Complete ===")
        print("Agents working on:")
        print("1. Individual chunk compression")
        print("2. Final essence synthesis")
        print(f"\nFinal result will be: autonomous_experiments/session_essence/session_essence.md")
    else:
        print("No compression sessions launched")

if __name__ == "__main__":
    main()