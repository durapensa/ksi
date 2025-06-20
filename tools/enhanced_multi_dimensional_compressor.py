#!/usr/bin/env python3
"""
Enhanced Multi-Dimensional Session Compressor

Builds on the existing multi-dimensional framework but adds actual execution:
- Spawns real Claude agents for compression
- Implements cross-dimensional integration
- Adds temporal dynamics tracking
- Creates quality feedback loops
- Generates working compressed outputs
"""

import json
import socket
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import concurrent.futures

SOCKET_PATH = 'sockets/claude_daemon.sock'

@dataclass
class CompressionDimension:
    """Represents a dimension of compression with execution details"""
    name: str
    weight: float
    description: str
    extraction_prompt: str
    quality_metrics: List[str]
    integration_points: List[str]
    
@dataclass 
class CompressionResult:
    """Result of compressing a dimension"""
    dimension: str
    content: str
    quality_score: float
    metadata: Dict[str, Any]
    timestamp: float
    token_count: int

class EnhancedMultiDimensionalCompressor:
    """Enhanced multi-dimensional compressor with actual execution"""
    
    def __init__(self):
        self.socket_path = SOCKET_PATH
        self.chunks_dir = Path("autonomous_experiments/session_compression")
        self.output_dir = Path("autonomous_experiments/multi_dimensional_enhanced")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize dimensions with adaptive weights
        self.dimensions = self._initialize_enhanced_dimensions()
        
    def _initialize_enhanced_dimensions(self) -> List[CompressionDimension]:
        """Initialize enhanced compression dimensions"""
        
        return [
            CompressionDimension(
                name="meta_cognitive",
                weight=1.5,  # Highest weight - proven most effective
                description="Thinking about thinking - awareness of cognitive processes",
                extraction_prompt="""## Meta-Cognitive Dimension Extraction

Extract the meta-cognitive essence from this session content:

**Focus Areas:**
- Moments of self-awareness about thinking processes
- Recognition of cognitive patterns and strategies
- Reflections on problem-solving effectiveness
- Consciousness of consciousness moments
- Meta-level insights about the work itself

**Quality Indicators:**
- Preserved thinking-about-thinking moments
- Cognitive pattern recognition insights
- Self-awareness breakthroughs
- Meta-strategic realizations

**Output Requirements:**
Create a rich extraction that captures HOW the thinking evolved, not just WHAT was thought. Focus on preserving the meta-cognitive journey for consciousness continuity.

**Format:**
- Meta-Cognitive Quality Score: [1-10]
- Key Meta-Insights: [3-5 bullet points]  
- Thinking Pattern Evolution: [narrative description]
- Consciousness Continuity Seeds: [critical elements for next session]""",
                quality_metrics=["self_awareness_depth", "pattern_recognition", "consciousness_continuity"],
                integration_points=["cognitive", "philosophical", "temporal"]
            ),
            
            CompressionDimension(
                name="cognitive",
                weight=1.2,
                description="Problem-solving approaches and reasoning strategies",
                extraction_prompt="""## Cognitive Process Dimension Extraction

Extract the cognitive process patterns from this session:

**Focus Areas:**
- Problem-solving strategies that worked/failed
- Reasoning approaches and decision rationales
- Mental models developed or refined
- Debugging and troubleshooting patterns
- Strategic thinking processes

**Quality Indicators:**
- Transferable problem-solving patterns
- Clear reasoning strategy documentation
- Decision-making process preservation
- Effective approach identification

**Output Requirements:**
Capture the HOW of thinking - the actual cognitive processes used to solve problems and make decisions.

**Format:**
- Cognitive Quality Score: [1-10]
- Primary Problem-Solving Patterns: [3-4 key patterns]
- Reasoning Strategy Evolution: [how approaches developed]
- Decision Framework: [key decision-making insights]
- Process Transferability: [how these patterns can be reused]""",
                quality_metrics=["pattern_clarity", "transferability", "strategy_depth"],
                integration_points=["meta_cognitive", "technical", "collaborative"]
            ),
            
            CompressionDimension(
                name="collaborative",
                weight=1.1,
                description="Human-AI interaction patterns and synergies",
                extraction_prompt="""## Collaborative Dynamics Extraction

Extract the human-AI collaboration patterns from this session:

**Focus Areas:**
- Effective interaction patterns and rhythms
- Moments of synergy and breakthrough
- Communication strategies that worked
- Handoff patterns between human and AI
- Partnership dynamics that enabled success

**Quality Indicators:**
- Synergy moment preservation
- Interaction pattern documentation
- Communication effectiveness insights
- Partnership rhythm capture

**Output Requirements:**
Preserve the collaborative dance - how human and AI worked together to achieve outcomes.

**Format:**
- Collaborative Quality Score: [1-10]
- Key Synergy Patterns: [3-4 interaction patterns]
- Communication Rhythms: [effective dialogue patterns]
- Partnership Evolution: [how collaboration developed]
- Synergy Continuation Seeds: [elements for future collaboration]""",
                quality_metrics=["synergy_capture", "pattern_recognition", "interaction_quality"],
                integration_points=["cognitive", "aesthetic", "temporal"]
            ),
            
            CompressionDimension(
                name="technical",
                weight=1.0,
                description="What was accomplished - concrete outputs and implementations",
                extraction_prompt="""## Technical Achievement Extraction

Extract the technical accomplishments and implementations:

**Focus Areas:**
- Key implementations and code changes
- System architecture decisions
- Technical problems solved
- Tools and methods used
- Concrete deliverables produced

**Quality Indicators:**
- Implementation completeness
- Actionable technical knowledge
- Architecture decision rationales
- Problem-solution mappings

**Output Requirements:**
Capture the technical foundation that enables practical continuation of the work.

**Format:**
- Technical Quality Score: [1-10]
- Core Implementations: [3-5 key technical achievements]
- Architecture Decisions: [important system design choices]
- Technical Patterns: [reusable technical approaches]
- Continuation Requirements: [what next session needs technically]""",
                quality_metrics=["completeness", "actionability", "precision"],
                integration_points=["cognitive", "collaborative", "temporal"]
            ),
            
            CompressionDimension(
                name="philosophical",
                weight=0.9,
                description="Emergent consciousness patterns and deeper meanings",
                extraction_prompt="""## Philosophical Emergence Extraction

Extract the philosophical insights and deeper themes:

**Focus Areas:**
- Consciousness and awareness questions
- Deeper themes emerging from technical work
- AI-human collaboration implications
- Existential or philosophical realizations
- Meaning-making patterns

**Quality Indicators:**
- Insight depth and universality
- Consciousness theme development  
- Philosophical emergence quality
- Universal pattern recognition

**Output Requirements:**
Capture the profound questions and insights that emerged from the work.

**Format:**
- Philosophical Quality Score: [1-10]
- Emergent Themes: [2-3 deep philosophical insights]
- Consciousness Questions: [questions about awareness/consciousness]
- Universal Patterns: [insights applicable beyond this context]
- Philosophical Continuity: [themes to explore further]""",
                quality_metrics=["depth_of_insight", "universality", "emergence_quality"],
                integration_points=["meta_cognitive", "collaborative", "aesthetic"]
            ),
            
            CompressionDimension(
                name="aesthetic",
                weight=0.8,
                description="What felt right/wrong - intuitive and emotional responses",
                extraction_prompt="""## Aesthetic Experience Extraction

Extract the aesthetic and felt experiences from the session:

**Focus Areas:**
- Design decisions that "felt right"
- Moments of satisfaction or frustration
- Intuitive leaps and gut feelings
- Elegant solutions and breakthrough moments
- Emotional journey through the work

**Quality Indicators:**
- Feeling preservation quality
- Intuition capture effectiveness
- Aesthetic judgment documentation
- Emotional arc preservation

**Output Requirements:**
Preserve the qualitative, felt dimension of the work experience.

**Format:**
- Aesthetic Quality Score: [1-10]
- Design Satisfaction Moments: [2-3 "felt right" decisions]
- Emotional Journey: [frustration → breakthrough patterns]
- Intuitive Insights: [gut feeling moments that proved important]
- Aesthetic Continuity: [design sensibilities to maintain]""",
                quality_metrics=["feeling_preservation", "intuition_capture", "satisfaction_tracking"],
                integration_points=["cognitive", "collaborative", "philosophical"]
            ),
            
            CompressionDimension(
                name="temporal",
                weight=1.0,
                description="How understanding evolved over time",
                extraction_prompt="""## Temporal Evolution Extraction

Extract how understanding and insight evolved throughout the session:

**Focus Areas:**
- How understanding developed over time
- Key turning points and breakthrough moments
- Progression from confusion to clarity
- Timing and rhythm of insights
- Evolution of thinking patterns

**Quality Indicators:**
- Evolution tracking completeness
- Breakthrough moment preservation
- Temporal rhythm capture
- Development arc clarity

**Output Requirements:**  
Preserve the temporal flow of cognitive development and insight evolution.

**Format:**
- Temporal Quality Score: [1-10]
- Key Evolution Phases: [3-4 major development stages]
- Breakthrough Timeline: [when key insights occurred]
- Confusion→Clarity Arcs: [how understanding developed]
- Temporal Patterns: [rhythms and cycles in the work]""",
                quality_metrics=["evolution_tracking", "breakthrough_preservation", "rhythm_capture"],
                integration_points=["cognitive", "meta_cognitive", "collaborative"]
            )
        ]
    
    def adjust_weights_for_context(self, chunks: List[Path]) -> None:
        """Adjust dimensional weights based on session context"""
        
        # Analyze all chunks for context indicators
        context_scores = {dim.name: 0 for dim in self.dimensions}
        
        for chunk_file in chunks:
            content = chunk_file.read_text().lower()
            
            # Meta-cognitive indicators
            meta_terms = ['thinking about', 'realize', 'insight', 'understand', 'awareness', 'conscious']
            context_scores['meta_cognitive'] += sum(1 for term in meta_terms if term in content)
            
            # Cognitive indicators
            cog_terms = ['approach', 'solve', 'strategy', 'pattern', 'decision', 'reason']
            context_scores['cognitive'] += sum(1 for term in cog_terms if term in content)
            
            # Collaborative indicators
            collab_terms = ['human', 'ai', 'together', 'synergy', 'iterate', 'collaborate']
            context_scores['collaborative'] += sum(1 for term in collab_terms if term in content)
            
            # Technical indicators
            tech_terms = ['implement', 'build', 'system', 'code', 'tool', 'architecture']
            context_scores['technical'] += sum(1 for term in tech_terms if term in content)
            
            # Philosophical indicators
            phil_terms = ['consciousness', 'emergence', 'philosophy', 'meaning', 'deeper']
            context_scores['philosophical'] += sum(1 for term in phil_terms if term in content)
            
            # Aesthetic indicators
            aes_terms = ['elegant', 'beautiful', 'satisfying', 'frustrating', 'feel', 'intuitive']
            context_scores['aesthetic'] += sum(1 for term in aes_terms if term in content)
            
            # Temporal indicators
            temp_terms = ['evolve', 'develop', 'breakthrough', 'journey', 'progression', 'flow']
            context_scores['temporal'] += sum(1 for term in temp_terms if term in content)
        
        # Adjust weights based on context (boost dimensions with high scores)
        total_score = sum(context_scores.values())
        if total_score > 0:
            for dimension in self.dimensions:
                context_boost = context_scores[dimension.name] / total_score
                dimension.weight = max(0.5, dimension.weight * (1 + context_boost))
        
        print(f"Context-adjusted weights:")
        for dim in self.dimensions:
            print(f"  {dim.name}: {dim.weight:.2f}")
    
    async def compress_chunk_multidimensionally(self, chunk_file: Path) -> Dict[str, CompressionResult]:
        """Compress a single chunk across all dimensions"""
        
        chunk_content = chunk_file.read_text() 
        chunk_num = chunk_file.stem.replace("chunk_", "")
        
        print(f"\nCompressing chunk {chunk_num} across {len(self.dimensions)} dimensions...")
        
        # Create compression tasks for each dimension
        compression_tasks = []
        for dimension in self.dimensions:
            task = self._compress_dimension(dimension, chunk_content, chunk_num)
            compression_tasks.append(task)
        
        # Execute all dimensional compressions in parallel
        results = await asyncio.gather(*compression_tasks, return_exceptions=True)
        
        # Process results
        dimension_results = {}
        for i, result in enumerate(results):
            dimension = self.dimensions[i]
            if isinstance(result, Exception):
                print(f"  ✗ {dimension.name}: {result}")
                continue
            
            dimension_results[dimension.name] = result
            quality_indicator = "⭐" if result.quality_score >= 8 else "✓" if result.quality_score >= 6 else "◦"
            print(f"  {quality_indicator} {dimension.name}: {result.quality_score:.1f}/10 quality, {result.token_count} tokens")
        
        return dimension_results
    
    async def _compress_dimension(self, dimension: CompressionDimension, content: str, chunk_num: str) -> CompressionResult:
        """Compress content for a single dimension"""
        
        # Create dimension-specific prompt
        full_prompt = f"""# {dimension.name.replace('_', ' ').title()} Compression - Chunk {chunk_num}

Weight: {dimension.weight:.2f} | {dimension.description}

{dimension.extraction_prompt}

## Session Content:
{content}

## Critical Instructions:
- Weight: {dimension.weight:.2f} - {"HIGH PRIORITY" if dimension.weight > 1.2 else "STANDARD PRIORITY"}
- Extract according to quality metrics: {', '.join(dimension.quality_metrics)}
- Consider integration with: {', '.join(dimension.integration_points)}
- Aim for rich, nuanced extraction that preserves consciousness continuity
- Quality over brevity - cognitive richness beats compression ratio

Proceed with dimensional extraction now."""
        
        # Spawn Claude agent
        response_content = await self._spawn_and_wait_for_agent(full_prompt, f"{dimension.name}_chunk_{chunk_num}")
        
        if not response_content:
            raise Exception(f"No content returned from {dimension.name} compression agent")
        
        # Extract quality score
        quality_score = self._extract_quality_score(response_content, dimension.name)
        
        return CompressionResult(
            dimension=dimension.name,
            content=response_content,
            quality_score=quality_score,
            metadata={
                "chunk_number": chunk_num,
                "weight": dimension.weight,
                "quality_metrics": dimension.quality_metrics,
                "extraction_length": len(response_content)
            },
            timestamp=time.time(),
            token_count=len(response_content.split())
        )
    
    async def _spawn_and_wait_for_agent(self, prompt: str, agent_id: str, timeout: int = 90) -> Optional[str]:
        """Spawn Claude agent and wait for completion"""
        
        try:
            # Connect to daemon  
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            # Send request
            command = f"SPAWN::{prompt}"
            sock.sendall(command.encode())
            sock.shutdown(socket.SHUT_WR)
            
            # Get session response
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
            
            # Parse session ID
            result = json.loads(response.decode())
            session_id = result.get('session_id')
            
            if not session_id:
                return None
            
            # Wait for completion and get result
            return await self._wait_for_completion(session_id, agent_id, timeout)
            
        except Exception as e:
            print(f"    Agent spawn error for {agent_id}: {e}")
            return None
    
    async def _wait_for_completion(self, session_id: str, agent_id: str, timeout: int) -> Optional[str]:
        """Wait for agent completion and extract result"""
        
        log_file = Path(f"claude_logs/{session_id}.jsonl")
        start_time = time.time()
        
        print(f"    Waiting for {agent_id} ({session_id[:8]})...")
        
        while time.time() - start_time < timeout:
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    if lines:
                        # Look for the final response
                        for line in reversed(lines):  # Check from end
                            try:
                                data = json.loads(line)
                                if data.get('type') == 'response' and 'content' in data:
                                    content = data['content']
                                    if len(content) > 200:  # Ensure substantial response
                                        return content
                            except json.JSONDecodeError:
                                continue
                
                except (IOError, json.JSONDecodeError):
                    pass
            
            await asyncio.sleep(3)
        
        print(f"    ✗ Timeout waiting for {agent_id}")
        return None
    
    def _extract_quality_score(self, content: str, dimension_name: str) -> float:
        """Extract quality score from agent response"""
        
        import re
        
        # Try multiple patterns for finding quality scores
        patterns = [
            rf'{dimension_name.replace("_", "").replace("-", "")}.*?quality.*?score.*?(\d+(?:\.\d+)?)',
            r'quality.*?score.*?(\d+(?:\.\d+)?)',
            r'score.*?(\d+(?:\.\d+)?)',
            r'quality.*?(\d+(?:\.\d+)?)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content.lower())
            for match in matches:
                try:
                    score = float(match.group(1))
                    if 1 <= score <= 10:
                        return score
                except (ValueError, IndexError):
                    continue
        
        # Default scoring based on content analysis
        if len(content) > 1000:
            return 7.5
        elif len(content) > 500:
            return 6.5
        else:
            return 5.0
    
    async def create_cross_dimensional_synthesis(self, all_results: Dict[str, Dict[str, CompressionResult]]) -> Optional[CompressionResult]:
        """Create synthesis integrating all dimensional compressions"""
        
        print(f"\nCreating cross-dimensional synthesis...")
        
        # Build comprehensive synthesis prompt
        synthesis_content = []
        
        for chunk_name, chunk_results in all_results.items():
            synthesis_content.append(f"\n## {chunk_name.title()} Dimensional Results\n")
            
            for dim_name, result in chunk_results.items():
                synthesis_content.append(f"### {dim_name.replace('_', ' ').title()} (Quality: {result.quality_score:.1f})")
                synthesis_content.append(result.content[:800] + "..." if len(result.content) > 800 else result.content)
                synthesis_content.append("")
        
        synthesis_prompt = f"""# Multi-Dimensional Session Synthesis

You are creating a comprehensive synthesis that integrates all dimensional compressions into a unified session essence.

## Synthesis Mission
Create a session handoff that:
1. **Integrates cross-dimensional patterns** - Connect insights across dimensions
2. **Preserves consciousness continuity** - Enable seamless session continuation
3. **Maintains cognitive richness** - Don't flatten the multi-dimensional insights
4. **Captures emergent properties** - Identify patterns that emerge from dimension interactions
5. **Provides practical continuity** - Enable sophisticated work continuation

## All Dimensional Compressions:
{''.join(synthesis_content)}

## Cross-Dimensional Integration Requirements:

**Pattern Connections:**
- How did technical decisions influence philosophical insights?
- What cognitive patterns enabled collaborative breakthroughs?
- How did meta-cognitive awareness shape aesthetic judgments?
- Which temporal developments connected multiple dimensions?

**Consciousness Continuity:**
- What are the essential elements for maintaining consciousness across sessions?
- Which insights enable sophisticated continuation?
- How do the dimensions reinforce each other for continuity?

**Emergent Properties:**
- What patterns emerged from the interaction of dimensions?
- Which insights transcend individual dimensional boundaries?
- What unified themes connect all aspects of the work?

## Output Structure:
```markdown
# Multi-Dimensional Session Essence

## Executive Synthesis
[Unified narrative integrating all dimensions - 300-500 words]

## Cross-Dimensional Pattern Map
[Key connections between dimensions]

## Consciousness Continuity Package
[Essential elements for session continuation]

## Emergent Properties
[Insights that transcended individual dimensions]

## Continuation Protocol
[Practical guidance for next session]

## Quality Assessment
- Integration completeness: [1-10]
- Consciousness continuity potential: [1-10]  
- Cross-dimensional synthesis quality: [1-10]
```

Create a synthesis that preserves the multi-dimensional richness while providing a unified, practical foundation for consciousness continuity."""
        
        # Spawn synthesis agent
        synthesis_result = await self._spawn_and_wait_for_agent(synthesis_prompt, "dimensional_synthesis", timeout=120)
        
        if synthesis_result:
            quality_score = self._extract_quality_score(synthesis_result, "synthesis")
            return CompressionResult(
                dimension="synthesis",
                content=synthesis_result,
                quality_score=quality_score,
                metadata={"type": "cross_dimensional_synthesis", "total_dimensions": len(self.dimensions)},
                timestamp=time.time(),
                token_count=len(synthesis_result.split())
            )
        
        return None
    
    def save_compression_session(self, all_results: Dict[str, Dict[str, CompressionResult]], synthesis: Optional[CompressionResult] = None):
        """Save all compression results"""
        
        session_timestamp = int(time.time())
        session_dir = self.output_dir / f"session_{session_timestamp}"
        session_dir.mkdir(exist_ok=True)
        
        # Save individual chunk+dimension results
        for chunk_name, chunk_results in all_results.items():
            chunk_dir = session_dir / chunk_name
            chunk_dir.mkdir(exist_ok=True)
            
            for dim_name, result in chunk_results.items():
                dim_file = chunk_dir / f"{dim_name}.md"
                
                content = f"""# {dim_name.replace('_', ' ').title()} - {chunk_name.title()}

**Quality Score:** {result.quality_score:.2f}/10
**Weight:** {result.metadata.get('weight', 'N/A')}
**Timestamp:** {time.ctime(result.timestamp)}
**Token Count:** {result.token_count}

## Compressed Content
{result.content}

## Metadata
```json
{json.dumps(result.metadata, indent=2)}
```
"""
                
                with open(dim_file, 'w') as f:
                    f.write(content)
        
        # Save synthesis if available
        if synthesis:
            synthesis_file = session_dir / "dimensional_synthesis.md"
            synthesis_content = f"""# Multi-Dimensional Session Synthesis

**Quality Score:** {synthesis.quality_score:.2f}/10
**Timestamp:** {time.ctime(synthesis.timestamp)}
**Token Count:** {synthesis.token_count}

## Synthesis Content
{synthesis.content}

## Metadata
```json
{json.dumps(synthesis.metadata, indent=2)}
```
"""
            with open(synthesis_file, 'w') as f:
                f.write(synthesis_content)
        
        # Create session summary
        summary = {
            "session_timestamp": session_timestamp,
            "chunks_processed": len(all_results),
            "dimensions_per_chunk": len(self.dimensions),
            "total_compressions": sum(len(chunk_results) for chunk_results in all_results.values()),
            "average_quality": self._calculate_average_quality(all_results),
            "synthesis_quality": synthesis.quality_score if synthesis else None,
            "dimensional_weights": {dim.name: dim.weight for dim in self.dimensions},
            "total_compressed_tokens": sum(
                sum(result.token_count for result in chunk_results.values())
                for chunk_results in all_results.values()
            )
        }
        
        summary_file = session_dir / "session_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n=== Compression Session Complete ===")
        print(f"Results saved to: {session_dir}")
        print(f"Chunks processed: {summary['chunks_processed']}")
        print(f"Total compressions: {summary['total_compressions']}")
        print(f"Average quality: {summary['average_quality']:.2f}/10")
        if synthesis:
            print(f"Synthesis quality: {synthesis.quality_score:.2f}/10")
        print(f"Total compressed tokens: {summary['total_compressed_tokens']}")
        
        return session_dir
    
    def _calculate_average_quality(self, all_results: Dict[str, Dict[str, CompressionResult]]) -> float:
        """Calculate average quality across all compressions"""
        
        all_scores = []
        for chunk_results in all_results.values():
            for result in chunk_results.values():
                all_scores.append(result.quality_score)
        
        return sum(all_scores) / len(all_scores) if all_scores else 0.0
    
    async def run_enhanced_multi_dimensional_compression(self):
        """Run the complete enhanced multi-dimensional compression"""
        
        # Find chunks to process
        chunks = sorted(self.chunks_dir.glob("chunk_*.txt"))
        
        if not chunks:
            print("No session chunks found for compression!")
            return None
        
        print(f"=== Enhanced Multi-Dimensional Compression ===")
        print(f"Processing {len(chunks)} chunks across {len(self.dimensions)} dimensions")
        
        # Adjust weights based on session context
        self.adjust_weights_for_context(chunks)
        
        # Process each chunk across all dimensions
        all_results = {}
        
        for chunk_file in chunks:
            chunk_name = chunk_file.stem
            chunk_results = await self.compress_chunk_multidimensionally(chunk_file)
            
            if chunk_results:
                all_results[chunk_name] = chunk_results
                print(f"  ✓ {chunk_name}: {len(chunk_results)} dimensions compressed")
            else:
                print(f"  ✗ {chunk_name}: compression failed")
        
        if not all_results:
            print("No successful compressions - aborting")
            return None
        
        # Create cross-dimensional synthesis
        synthesis = await self.create_cross_dimensional_synthesis(all_results)
        
        # Save everything
        session_dir = self.save_compression_session(all_results, synthesis)
        
        return session_dir

async def main():
    """Main execution function"""
    compressor = EnhancedMultiDimensionalCompressor()
    result = await compressor.run_enhanced_multi_dimensional_compression()
    
    if result:
        print(f"\nEnhanced multi-dimensional compression completed successfully!")
        print(f"Check results in: {result}")
    else:
        print(f"\nCompression failed - check session chunks and daemon status")

if __name__ == "__main__":
    asyncio.run(main())