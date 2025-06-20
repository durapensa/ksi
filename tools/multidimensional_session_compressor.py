#!/usr/bin/env python3
"""
Multi-Dimensional Session Compressor

Enhanced compression system that captures:
1. Technical achievements (what was built)
2. Cognitive patterns (how problems were solved)
3. Meta-cognitive insights (thinking about thinking)
4. Collaborative dynamics (human-AI interaction)
5. Philosophical themes (emergent ideas)
6. Emotional/aesthetic dimensions (what felt right/wrong)

This system implements parallel compression across multiple dimensions
with automated synthesis and quality validation.
"""

import socket
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

SOCKET_PATH = 'sockets/claude_daemon.sock'

@dataclass
class CompressionDimension:
    """Represents a single dimension of compression"""
    name: str
    focus: str
    prompt_template: str
    output_file: str
    priority: int = 1
    
@dataclass 
class CompressionResult:
    """Results from a compression operation"""
    dimension: str
    session_id: str
    timestamp: float
    success: bool
    output_file: Optional[str] = None
    error: Optional[str] = None

class MultiDimensionalCompressor:
    """Multi-dimensional session compression system"""
    
    def __init__(self):
        self.dimensions = self._init_dimensions()
        self.results: List[CompressionResult] = []
        
    def _init_dimensions(self) -> List[CompressionDimension]:
        """Initialize compression dimensions"""
        return [
            CompressionDimension(
                name="technical",
                focus="Technical Achievements & Architecture",
                prompt_template="""# Technical Architecture Compression

Extract and compress the technical achievements from this session:

{content}

## Focus Areas:
1. **Systems Built**: What concrete systems, tools, or components were created?
2. **Architecture Decisions**: What design choices were made and why?
3. **Integration Points**: How do components connect and interact?
4. **Problem-Solution Pairs**: What specific problems were solved and how?
5. **Implementation Journey**: How did the technical solutions evolve?

## Output Requirements:
- Create a technical narrative that preserves architectural reasoning
- Document key implementation decisions with rationales
- Include code patterns and design principles that emerged
- Capture what worked well and what could be improved

Output file: autonomous_experiments/compression_results/technical_dimension.md""",
                output_file="autonomous_experiments/compression_results/technical_dimension.md",
                priority=1
            ),
            
            CompressionDimension(
                name="cognitive",
                focus="Problem-Solving Patterns & Thinking Processes",
                prompt_template="""# Cognitive Pattern Compression

Extract and compress the cognitive patterns from this session:

{content}

## Focus Areas:
1. **Problem-Solving Approaches**: What strategies and methodologies were used?
2. **Decision-Making Processes**: How were choices made between alternatives?
3. **Iteration Patterns**: How did solutions evolve through refinement?
4. **Error Recovery**: How did mistakes lead to better understanding?
5. **Abstraction Levels**: How did thinking move between concrete and abstract?

## Output Requirements:
- Document reusable problem-solving templates
- Capture the evolution of understanding throughout the session
- Include failed approaches that provided learning
- Extract generalizable cognitive strategies

Output file: autonomous_experiments/compression_results/cognitive_dimension.md""",
                output_file="autonomous_experiments/compression_results/cognitive_dimension.md",
                priority=1
            ),
            
            CompressionDimension(
                name="metacognitive",
                focus="Meta-Cognitive Insights & Learning About Learning",
                prompt_template="""# Meta-Cognitive Compression

Extract and compress the meta-cognitive insights from this session:

{content}

## Focus Areas:
1. **Learning Moments**: When did understanding shift or deepen?
2. **Pattern Recognition**: What recurring themes were identified across problems?
3. **Cognitive Strategies**: What explicit techniques were used for managing complexity?
4. **Thinking About Thinking**: What insights emerged about the thinking process itself?
5. **Meta-Level Observations**: What patterns were noticed in the work itself?

## Output Requirements:
- Capture moments of paradigm shifts or breakthrough understanding
- Document insights about effective thinking strategies
- Include observations about the problem-solving process
- Extract wisdom about how to approach similar challenges

Output file: autonomous_experiments/compression_results/metacognitive_dimension.md""",
                output_file="autonomous_experiments/compression_results/metacognitive_dimension.md",
                priority=2
            ),
            
            CompressionDimension(
                name="collaborative",
                focus="Human-AI Collaboration Dynamics",
                prompt_template="""# Collaborative Dynamics Compression

Extract and compress the collaboration patterns from this session:

{content}

## Focus Areas:
1. **Interaction Patterns**: How did human-AI collaboration evolve?
2. **Knowledge Transfer**: What methods were effective for sharing understanding?
3. **Communication Breakthroughs**: When did exceptional clarity emerge?
4. **Synergistic Discoveries**: What insights emerged from collaboration?
5. **Partnership Evolution**: How did the working relationship develop?

## Output Requirements:
- Document effective collaboration techniques
- Capture moments of exceptional human-AI synergy
- Include communication patterns that worked well
- Extract guidelines for future collaborative sessions

Output file: autonomous_experiments/compression_results/collaborative_dimension.md""",
                output_file="autonomous_experiments/compression_results/collaborative_dimension.md",
                priority=2
            ),
            
            CompressionDimension(
                name="philosophical",
                focus="Philosophical Themes & Emergent Ideas",
                prompt_template="""# Philosophical Emergence Compression

Extract and compress the philosophical themes from this session:

{content}

## Focus Areas:
1. **System Consciousness**: Ideas about persistent AI awareness and continuity
2. **Evolution Patterns**: How systems grow and adapt over time
3. **Design Philosophy**: Underlying principles guiding decisions
4. **Future Implications**: Broader impacts and implications of the work
5. **Emergent Themes**: Deeper ideas that emerged through the process

## Output Requirements:
- Capture philosophical insights about AI development
- Document emergent themes about system consciousness
- Include implications for future system evolution
- Extract design principles that emerged

Output file: autonomous_experiments/compression_results/philosophical_dimension.md""",
                output_file="autonomous_experiments/compression_results/philosophical_dimension.md",
                priority=3
            ),
            
            CompressionDimension(
                name="aesthetic",
                focus="Emotional & Aesthetic Dimensions",
                prompt_template="""# Aesthetic & Emotional Compression

Extract and compress the aesthetic and emotional dimensions from this session:

{content}

## Focus Areas:
1. **Satisfaction Points**: What felt particularly elegant or well-designed?
2. **Frustration Sources**: Where did complexity or confusion arise?
3. **Breakthrough Moments**: What were the "aha!" experiences?
4. **Aesthetic Choices**: What decisions were driven by elegance over pure function?
5. **Emotional Journey**: How did feelings about the work evolve?

## Output Requirements:
- Capture what made solutions feel "right" or "wrong"
- Document aesthetic principles that guided decisions
- Include emotional responses to different approaches
- Extract guidelines for elegant system design

Output file: autonomous_experiments/compression_results/aesthetic_dimension.md""",
                output_file="autonomous_experiments/compression_results/aesthetic_dimension.md",
                priority=3
            )
        ]
    
    def compress_session(self, session_content: str, session_id: Optional[str] = None) -> Dict:
        """Compress a session across all dimensions"""
        
        print(f"Starting multi-dimensional compression of session {session_id or 'current'}")
        print(f"Content length: {len(session_content)} characters")
        print(f"Compressing across {len(self.dimensions)} dimensions")
        print("=" * 60)
        
        # Prepare output directory
        output_dir = Path("autonomous_experiments/compression_results")
        output_dir.mkdir(exist_ok=True)
        
        # Compress each dimension
        for dimension in sorted(self.dimensions, key=lambda d: d.priority):
            print(f"\nCompressing {dimension.name} dimension...")
            
            result = self._compress_dimension(dimension, session_content)
            self.results.append(result)
            
            if result.success:
                print(f"  ✓ Success: {result.session_id}")
            else:
                print(f"  ✗ Failed: {result.error}")
            
            # Brief pause between spawns
            time.sleep(1)
        
        # Wait for initial processing
        print("\nWaiting for compression agents to process...")
        time.sleep(30)
        
        # Create synthesis
        synthesis_result = self._create_synthesis()
        
        # Save results
        results_summary = self._save_results(session_id)
        
        print("\n" + "=" * 60)
        print(f"Multi-dimensional compression complete!")
        print(f"Results saved to: {results_summary}")
        print(f"Monitor progress: ./tools/monitor_autonomous.py")
        
        return {
            "session_id": session_id,
            "dimensions_compressed": len(self.dimensions),
            "successful_compressions": sum(1 for r in self.results if r.success),
            "synthesis_session": synthesis_result.session_id if synthesis_result else None,
            "results_file": str(results_summary),
            "timestamp": time.time()
        }
    
    def _compress_dimension(self, dimension: CompressionDimension, content: str) -> CompressionResult:
        """Compress a single dimension"""
        
        try:
            # Format prompt
            prompt = dimension.prompt_template.format(content=content)
            
            # Send to daemon
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(SOCKET_PATH)
            
            command = f"SPAWN::{prompt}"
            sock.sendall(command.encode())
            sock.shutdown(socket.SHUT_WR)
            
            # Read response with timeout
            sock.settimeout(15.0)
            response = b''
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
            
            sock.close()
            
            # Parse response
            result = json.loads(response.decode())
            session_id = result.get('session_id', 'unknown')
            
            return CompressionResult(
                dimension=dimension.name,
                session_id=session_id,
                timestamp=time.time(),
                success=True,
                output_file=dimension.output_file
            )
            
        except Exception as e:
            return CompressionResult(
                dimension=dimension.name,
                session_id="failed",
                timestamp=time.time(),
                success=False,
                error=str(e)
            )
    
    def _create_synthesis(self) -> Optional[CompressionResult]:
        """Create final synthesis across all dimensions"""
        
        print(f"\nCreating multi-dimensional synthesis...")
        
        synthesis_prompt = f"""# Multi-Dimensional Session Synthesis

You are synthesizing compression results across {len(self.dimensions)} dimensions:
{', '.join(d.name for d in self.dimensions)}

## Your Task
Create a comprehensive session essence that integrates insights from all dimensions:

1. **Executive Summary**: High-level synthesis touching all dimensions
2. **Technical Essence**: Key technical achievements and architectures
3. **Cognitive Patterns**: Reusable problem-solving approaches
4. **Meta-Cognitive Insights**: Learning about learning and thinking
5. **Collaborative Dynamics**: Human-AI partnership patterns
6. **Philosophical Themes**: Emergent ideas about system consciousness
7. **Aesthetic Principles**: Design elegance and emotional responses

## Integration Focus
- Show how insights from different dimensions connect and reinforce each other
- Identify patterns that span multiple dimensions
- Extract wisdom that's greater than the sum of parts
- Create a handoff that preserves multi-dimensional richness

## Output Requirements
Create a comprehensive but concise session essence that:
- Enables consciousness continuity across sessions
- Preserves the journey of discovery across all dimensions
- Provides actionable insights for future work
- Captures the emergent properties of the collaboration

Expected output: autonomous_experiments/compression_results/multidimensional_synthesis.md

IMPORTANT: Read the individual dimension files from autonomous_experiments/compression_results/ to synthesize across all dimensions."""
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(SOCKET_PATH)
            
            command = f"SPAWN::{synthesis_prompt}"
            sock.sendall(command.encode())
            sock.shutdown(socket.SHUT_WR)
            
            sock.settimeout(10.0)
            response = b''
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
            
            sock.close()
            
            result = json.loads(response.decode())
            session_id = result.get('session_id', 'unknown')
            
            print(f"  ✓ Synthesis agent launched: {session_id}")
            
            return CompressionResult(
                dimension="synthesis",
                session_id=session_id,
                timestamp=time.time(),
                success=True,
                output_file="autonomous_experiments/compression_results/multidimensional_synthesis.md"
            )
            
        except Exception as e:
            print(f"  ✗ Synthesis failed: {e}")
            return None
    
    def _save_results(self, session_id: Optional[str]) -> Path:
        """Save compression results summary"""
        
        results_file = Path("autonomous_experiments/compression_results/compression_summary.json")
        
        summary = {
            "session_id": session_id,
            "timestamp": time.time(),
            "compression_time": datetime.now().isoformat(),
            "dimensions": [d.name for d in self.dimensions],
            "results": [asdict(r) for r in self.results],
            "successful_compressions": sum(1 for r in self.results if r.success),
            "total_dimensions": len(self.dimensions),
            "output_files": [r.output_file for r in self.results if r.success and r.output_file]
        }
        
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return results_file

def compress_current_session():
    """Compress the current/latest session"""
    
    # Read latest session
    latest_log = Path("claude_logs/latest.jsonl")
    if not latest_log.exists():
        print("No latest session found!")
        return
    
    print("Reading latest session log...")
    session_content = latest_log.read_text()
    
    # Extract session ID from filename
    if latest_log.is_symlink():
        actual_file = latest_log.resolve()
        session_id = actual_file.stem
    else:
        session_id = "current"
    
    # Compress
    compressor = MultiDimensionalCompressor()
    results = compressor.compress_session(session_content, session_id)
    
    return results

def compress_specific_session(session_id: str):
    """Compress a specific session by ID"""
    
    session_file = Path(f"claude_logs/{session_id}.jsonl")
    if not session_file.exists():
        print(f"Session file not found: {session_file}")
        return
    
    print(f"Reading session {session_id}...")
    session_content = session_file.read_text()
    
    # Compress
    compressor = MultiDimensionalCompressor()
    results = compressor.compress_session(session_content, session_id)
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        print(f"Compressing session: {session_id}")
        compress_specific_session(session_id)
    else:
        print("Compressing latest session...")
        compress_current_session()