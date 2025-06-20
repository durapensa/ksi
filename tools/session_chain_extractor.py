#!/usr/bin/env python3
"""
Session Chain Extractor for Claude Logs

Traces conversation sessions backward from current session to build complete chain.
Extracts Claude result portions for compression and essence generation.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse

class SessionChainExtractor:
    def __init__(self, logs_dir: str = "claude_logs"):
        self.logs_dir = Path(logs_dir)
        self.sessions = {}  # session_id -> session_data
        self.session_chain = []  # ordered list of sessions in conversation
        
    def load_session_logs(self):
        """Load all session log files"""
        print("Loading session logs...")
        
        for log_file in self.logs_dir.glob("*.jsonl"):
            if log_file.name == "latest.jsonl":
                continue
                
            session_id = log_file.stem
            session_data = {
                "session_id": session_id,
                "file": log_file,
                "entries": [],
                "start_time": None,
                "end_time": None,
                "human_messages": 0,
                "claude_responses": 0
            }
            
            # Parse JSONL entries
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line.strip())
                            session_data["entries"].append(entry)
                            
                            # Track message types and times
                            if entry.get("type") == "human":
                                session_data["human_messages"] += 1
                                if not session_data["start_time"]:
                                    session_data["start_time"] = entry.get("timestamp")
                            elif entry.get("type") == "claude":
                                session_data["claude_responses"] += 1
                                session_data["end_time"] = entry.get("timestamp")
                                
            except Exception as e:
                print(f"Error loading {log_file}: {e}")
                continue
                
            self.sessions[session_id] = session_data
            
        print(f"Loaded {len(self.sessions)} sessions")
        
    def find_current_session(self) -> Optional[str]:
        """Find the current session ID from latest.jsonl symlink"""
        latest_link = self.logs_dir / "latest.jsonl"
        if latest_link.exists() and latest_link.is_symlink():
            target = latest_link.readlink()
            return target.stem
        return None
    
    def trace_session_chain(self, start_session_id: str) -> List[str]:
        """Trace conversation chain backward from start session"""
        print(f"Tracing session chain from {start_session_id}")
        
        chain = []
        current_session = start_session_id
        
        while current_session and current_session in self.sessions:
            chain.append(current_session)
            print(f"Added session {current_session} to chain")
            
            # Look for previous session by analyzing context patterns
            # Claude sessions with high cache_read_input_tokens likely resumed from previous session
            session_data = self.sessions[current_session]
            
            # Check for large cache reads indicating resumed session
            for entry in session_data["entries"]:
                if entry.get("type") == "claude" and "usage" in entry:
                    cache_read = entry["usage"].get("cache_read_input_tokens", 0)
                    cache_create = entry["usage"].get("cache_creation_input_tokens", 0)
                    
                    # If cache_read >> cache_create, this was likely resumed
                    if cache_read > cache_create * 2:
                        # Find previous session by timestamp proximity
                        prev_session = self.find_previous_session_by_time(session_data["start_time"])
                        if prev_session and prev_session not in chain:
                            current_session = prev_session
                            break
                    
            else:
                # No clear previous session found
                break
                
        print(f"Session chain: {' -> '.join(reversed(chain))}")
        return list(reversed(chain))  # Return chronological order
    
    def find_previous_session_by_time(self, current_start_time: str) -> Optional[str]:
        """Find session that ended just before current session started"""
        if not current_start_time:
            return None
            
        current_time = datetime.fromisoformat(current_start_time.replace('Z', '+00:00'))
        
        # Find sessions that ended before current session started
        candidates = []
        for session_id, data in self.sessions.items():
            if data["end_time"]:
                end_time = datetime.fromisoformat(data["end_time"].replace('Z', '+00:00'))
                if end_time < current_time:
                    time_diff = (current_time - end_time).total_seconds()
                    candidates.append((session_id, time_diff, data))
        
        # Return session that ended closest to current session start
        if candidates:
            candidates.sort(key=lambda x: x[1])  # Sort by time difference
            closest_session = candidates[0]
            if closest_session[1] < 3600:  # Within 1 hour
                return closest_session[0]
                
        return None
    
    def extract_claude_results(self, session_chain: List[str]) -> List[Dict]:
        """Extract Claude result portions from session chain"""
        print("Extracting Claude results from session chain...")
        
        results = []
        for session_id in session_chain:
            session_data = self.sessions[session_id]
            
            for entry in session_data["entries"]:
                if entry.get("type") == "claude" and "result" in entry:
                    results.append({
                        "session_id": session_id,
                        "timestamp": entry.get("timestamp"),
                        "result": entry["result"],
                        "duration_ms": entry.get("duration_ms", 0),
                        "cost_usd": entry.get("total_cost_usd", 0),
                        "num_turns": entry.get("num_turns", 0)
                    })
                    
        print(f"Extracted {len(results)} Claude results")
        return results
    
    def chunk_results(self, results: List[Dict], max_chunk_size: int = 50000) -> List[List[Dict]]:
        """Chunk results into manageable sizes for compression"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for result in results:
            result_size = len(result["result"])
            
            if current_size + result_size > max_chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [result]
                current_size = result_size
            else:
                current_chunk.append(result)
                current_size += result_size
                
        if current_chunk:
            chunks.append(current_chunk)
            
        print(f"Created {len(chunks)} chunks for compression")
        return chunks
    
    def generate_compression_prompt(self, chunk: List[Dict], chunk_index: int) -> str:
        """Generate prompt for compressing a chunk of Claude results"""
        
        # Combine all results in chunk
        combined_text = ""
        for i, result in enumerate(chunk):
            combined_text += f"\n--- Response {i+1} (Session: {result['session_id'][:8]}, Turns: {result['num_turns']}) ---\n"
            combined_text += result["result"]
            combined_text += "\n"
        
        prompt = f"""You are a session essence extractor. Your task is to compress and summarize Claude responses while preserving all important technical information, decisions, and outcomes.

CHUNK {chunk_index + 1}: This contains {len(chunk)} Claude responses from a system engineering conversation about building prompt composition systems and memory management.

SOURCE RESPONSES:
{combined_text}

COMPRESSION REQUIREMENTS:
1. **Preserve Technical Details**: Keep all specific implementation details, file paths, code snippets, architectural decisions
2. **Preserve Outcomes**: What was built, what worked, what didn't work
3. **Preserve Context**: Key insights and reasoning behind decisions  
4. **Remove Redundancy**: Eliminate repetitive explanations and verbose language
5. **Maintain Chronology**: Keep the logical flow of development

OUTPUT FORMAT:
## Chunk {chunk_index + 1} Summary

### Key Accomplishments
- [Specific technical achievements]

### Technical Details  
- [Implementation specifics, file structures, code patterns]

### Architectural Decisions
- [Key design choices and rationale]

### Outcomes and Results
- [What was successfully built and tested]

### Critical Context
- [Important insights for future sessions]

Focus on creating a compressed but comprehensive technical summary that would allow another engineer to understand what was accomplished and continue the work."""

        return prompt
    
    def save_chunks_for_compression(self, chunks: List[List[Dict]], output_dir: str = "autonomous_experiments/session_compression"):
        """Save chunks as individual files for agent compression"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Clear existing chunk files
        for f in output_path.glob("chunk_*.txt"):
            f.unlink()
            
        for i, chunk in enumerate(chunks):
            prompt = self.generate_compression_prompt(chunk, i)
            
            chunk_file = output_path / f"chunk_{i+1:02d}.txt"
            with open(chunk_file, 'w') as f:
                f.write(prompt)
                
        print(f"Saved {len(chunks)} chunks to {output_dir}")
        return output_path

def main():
    parser = argparse.ArgumentParser(description="Extract and prepare session chain for compression")
    parser.add_argument("--logs-dir", default="claude_logs", help="Directory containing claude logs")
    parser.add_argument("--output-dir", default="autonomous_experiments/session_compression", 
                       help="Directory to save chunks for compression")
    parser.add_argument("--chunk-size", type=int, default=50000, 
                       help="Maximum characters per chunk")
    
    args = parser.parse_args()
    
    extractor = SessionChainExtractor(args.logs_dir)
    
    # Load all sessions
    extractor.load_session_logs()
    
    # Find current session
    current_session = extractor.find_current_session()
    if not current_session:
        print("Could not find current session")
        return
        
    print(f"Current session: {current_session}")
    
    # Trace session chain
    session_chain = extractor.trace_session_chain(current_session)
    
    if not session_chain:
        print("Could not build session chain")
        return
    
    # Extract Claude results
    results = extractor.extract_claude_results(session_chain)
    
    if not results:
        print("No Claude results found in session chain")
        return
    
    # Chunk results
    chunks = extractor.chunk_results(results, args.chunk_size)
    
    # Save chunks for compression
    output_path = extractor.save_chunks_for_compression(chunks, args.output_dir)
    
    print(f"\nSession chain extraction complete!")
    print(f"Sessions in chain: {len(session_chain)}")
    print(f"Claude responses: {len(results)}")
    print(f"Compression chunks: {len(chunks)}")
    print(f"Chunks saved to: {output_path}")
    print(f"\nNext: Run compression agents on chunks in {output_path}")

if __name__ == "__main__":
    main()