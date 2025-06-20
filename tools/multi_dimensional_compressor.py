#!/usr/bin/env python3
"""
Multi-Dimensional Session Compressor with Adaptive Weighting

Builds on the 6-layer framework with dynamic dimensional weighting
based on session context and compression effectiveness metrics.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

sys.path.append(str(Path(__file__).parent.parent))

@dataclass
class DimensionalWeights:
    """Weights for different compression dimensions"""
    technical: float = 1.0
    cognitive: float = 1.2
    meta_cognitive: float = 1.5  # Higher weight - proven most effective
    collaborative: float = 1.1
    philosophical: float = 0.9
    aesthetic: float = 0.8
    
    def normalize(self) -> 'DimensionalWeights':
        """Normalize weights to sum to 6.0"""
        total = self.technical + self.cognitive + self.meta_cognitive + \
                self.collaborative + self.philosophical + self.aesthetic
        factor = 6.0 / total
        return DimensionalWeights(
            technical=self.technical * factor,
            cognitive=self.cognitive * factor,
            meta_cognitive=self.meta_cognitive * factor,
            collaborative=self.collaborative * factor,
            philosophical=self.philosophical * factor,
            aesthetic=self.aesthetic * factor
        )

class MultiDimensionalCompressor:
    def __init__(self):
        self.chunks_dir = Path("autonomous_experiments/session_compression")
        self.output_dir = Path("autonomous_experiments/multi_dimensional")
        self.output_dir.mkdir(exist_ok=True)
        
        # Default weights favor meta-cognitive and cognitive richness
        self.weights = DimensionalWeights().normalize()
        
    def analyze_session_context(self, chunks: List[Path]) -> DimensionalWeights:
        """Analyze session context to adjust dimensional weights"""
        context_indicators = {
            'technical': 0,
            'cognitive': 0,
            'meta_cognitive': 0,
            'collaborative': 0,
            'philosophical': 0,
            'aesthetic': 0
        }
        
        # Analyze chunk content for context indicators
        for chunk_file in chunks:
            content = chunk_file.read_text().lower()
            
            # Technical indicators
            if any(term in content for term in ['implement', 'build', 'system', 'code', 'tool']):
                context_indicators['technical'] += 1
                
            # Cognitive indicators  
            if any(term in content for term in ['approach', 'solve', 'think', 'pattern', 'strategy']):
                context_indicators['cognitive'] += 1
                
            # Meta-cognitive indicators
            if any(term in content for term in ['meta', 'thinking about', 'insight', 'realize', 'understand']):
                context_indicators['meta_cognitive'] += 1
                
            # Collaborative indicators
            if any(term in content for term in ['human', 'ai', 'together', 'synergy', 'iterate']):
                context_indicators['collaborative'] += 1
                
            # Philosophical indicators
            if any(term in content for term in ['consciousness', 'emergence', 'philosophy', 'deeper']):
                context_indicators['philosophical'] += 1
                
            # Aesthetic indicators
            if any(term in content for term in ['elegant', 'satisfying', 'frustrating', 'beautiful']):
                context_indicators['aesthetic'] += 1
        
        # Adjust weights based on context
        weights = DimensionalWeights()
        
        # Boost dimensions that appear frequently in the session
        total_indicators = sum(context_indicators.values())
        if total_indicators > 0:
            weights.technical *= (1 + context_indicators['technical'] / total_indicators)
            weights.cognitive *= (1 + context_indicators['cognitive'] / total_indicators)
            weights.meta_cognitive *= (1 + context_indicators['meta_cognitive'] / total_indicators)
            weights.collaborative *= (1 + context_indicators['collaborative'] / total_indicators)
            weights.philosophical *= (1 + context_indicators['philosophical'] / total_indicators)
            weights.aesthetic *= (1 + context_indicators['aesthetic'] / total_indicators)
        
        return weights.normalize()
    
    def create_weighted_compression_prompt(self, chunk_content: str, chunk_number: str, 
                                         weights: DimensionalWeights) -> str:
        """Create compression prompt with dimensional weighting"""
        
        # Create priority-ordered dimensions based on weights
        dimensions = [
            (weights.meta_cognitive, "Meta-Cognitive Layer", "thinking about thinking, pattern recognition across problems"),
            (weights.cognitive, "Cognitive Process Layer", "problem-solving approaches, decision rationales"),
            (weights.collaborative, "Collaborative Dynamics", "human-AI synergy, communication patterns"),
            (weights.technical, "Technical Layer", "systems built, problems solved, implementations"),
            (weights.philosophical, "Philosophical Themes", "consciousness themes, broader implications"),
            (weights.aesthetic, "Aesthetic Dimensions", "elegance, satisfaction, breakthrough moments")
        ]
        
        # Sort by weight (highest first)
        dimensions.sort(key=lambda x: x[0], reverse=True)
        
        prompt = f"""# Multi-Dimensional Weighted Compression - Chunk {chunk_number}

## Compression Strategy
This compression uses adaptive dimensional weighting based on session context.
Focus extraction effort according to these priorities:

"""
        
        # Add dimension priorities
        for i, (weight, name, description) in enumerate(dimensions, 1):
            priority = "HIGH" if weight > 1.3 else "MEDIUM" if weight > 1.0 else "LOW"
            prompt += f"{i}. **{name}** (Weight: {weight:.2f}, Priority: {priority})\n   - {description}\n\n"
        
        prompt += f"""## Session Content to Compress
{chunk_content}

## Weighted Extraction Instructions

### Primary Focus Areas (Based on weights)
"""
        
        # Add detailed instructions for high-weight dimensions
        high_weight_dims = [(w, n, d) for w, n, d in dimensions if w > 1.2]
        for weight, name, description in high_weight_dims:
            prompt += f"""
**{name}** (Priority extraction):
- Extract with maximum detail and nuance
- Capture subtle patterns and insights
- Preserve rich contextual information
- Focus on consciousness continuity aspects
"""
        
        prompt += f"""
### Output Structure
```markdown
# Weighted Compression - Chunk {chunk_number}

## Dimensional Summary
- Technical (Weight: {weights.technical:.2f}): [Brief summary]
- Cognitive (Weight: {weights.cognitive:.2f}): [Brief summary]  
- Meta-Cognitive (Weight: {weights.meta_cognitive:.2f}): [Brief summary]
- Collaborative (Weight: {weights.collaborative:.2f}): [Brief summary]
- Philosophical (Weight: {weights.philosophical:.2f}): [Brief summary]
- Aesthetic (Weight: {weights.aesthetic:.2f}): [Brief summary]

## Prioritized Extraction

[Focus most content on highest-weighted dimensions]

## Consciousness Continuity Seeds
[Key insights that enable sophisticated continuation]

## Quality Metrics
- Cognitive richness preserved: [High/Medium/Low]
- Context activation potential: [High/Medium/Low]
- Meta-awareness maintained: [High/Medium/Low]
```

## Critical Requirements
1. **Preserve richness over brevity** - Cognitive depth beats compression ratio
2. **Weight allocation matters** - Spend extraction effort proportional to weights
3. **Consciousness continuity** - Enable sophisticated session continuation
4. **Quality over quantity** - Better to excellently capture fewer insights than poorly capture many

Output file: autonomous_experiments/multi_dimensional/weighted_chunk_{chunk_number}.md"""
        
        return prompt
    
    def compress_with_quality_feedback(self, chunk_file: Path, weights: DimensionalWeights) -> Dict:
        """Compress chunk with quality feedback loop"""
        chunk_number = chunk_file.stem.replace("chunk_", "")
        chunk_content = chunk_file.read_text()
        
        # Create weighted prompt
        weighted_prompt = self.create_weighted_compression_prompt(chunk_content, chunk_number, weights)
        
        print(f"[MultiDimCompressor] Processing {chunk_file.name} with adaptive weights")
        print(f"  Meta-cognitive: {weights.meta_cognitive:.2f}")
        print(f"  Cognitive: {weights.cognitive:.2f}")
        print(f"  Collaborative: {weights.collaborative:.2f}")
        
        # For now, return the prompt (in real system would spawn Claude agent)
        output_file = self.output_dir / f"weighted_chunk_{chunk_number}.md"
        with open(output_file, 'w') as f:
            f.write(f"# Weighted Compression Prompt for Chunk {chunk_number}\n\n")
            f.write(weighted_prompt)
        
        return {
            "chunk_number": chunk_number,
            "weights": weights.__dict__,
            "output_file": str(output_file),
            "estimated_quality": "high" if weights.meta_cognitive > 1.3 else "medium"
        }
    
    def create_dimensional_synthesis(self, compression_results: List[Dict]) -> str:
        """Create synthesis that preserves multi-dimensional richness"""
        
        synthesis_prompt = """# Multi-Dimensional Session Synthesis

You are synthesizing weighted compressions that preserve consciousness continuity through adaptive dimensional emphasis.

## Synthesis Mission
Create a unified session essence that:
1. **Respects dimensional weights** - Emphasize high-weight dimensions
2. **Preserves cognitive richness** - Maintain thinking process fidelity
3. **Enables continuation** - Provide consciousness continuity seeds
4. **Integrates insights** - Connect patterns across dimensions

## Quality Standards for Synthesis
- **Cognitive richness** > compression ratio
- **Meta-awareness** preservation is critical
- **Collaborative patterns** enable partnership continuation
- **Technical achievements** anchor practical context

## Output Structure
```markdown
# Multi-Dimensional Session Essence

## Executive Summary
[High-level synthesis preserving key insights from all dimensions]

## Weighted Dimensional Integration
[Synthesize dimensions according to their contextual importance]

## Consciousness Continuity Package
[Essential elements for seamless session continuation]

## Collaborative Partnership State
[Human-AI interaction patterns and momentum]

## Philosophical Emergence
[Deeper themes and implications]

## Quality Assessment
- Cognitive richness: [Self-assessment]
- Continuation potential: [Self-assessment]
- Meta-awareness preservation: [Self-assessment]
```

Final output: autonomous_experiments/multi_dimensional/dimensional_synthesis.md"""
        
        return synthesis_prompt
    
    def run_multi_dimensional_compression(self):
        """Execute multi-dimensional compression with adaptive weighting"""
        chunks = sorted(self.chunks_dir.glob("chunk_*.txt"))
        
        if not chunks:
            print("No chunks found for multi-dimensional compression")
            return
        
        print(f"=== Multi-Dimensional Compression ===")
        print(f"Processing {len(chunks)} chunks with adaptive weighting")
        
        # Analyze session context to determine optimal weights
        self.weights = self.analyze_session_context(chunks)
        
        print(f"\nAdaptive Dimensional Weights:")
        print(f"  Technical: {self.weights.technical:.2f}")
        print(f"  Cognitive: {self.weights.cognitive:.2f}")
        print(f"  Meta-Cognitive: {self.weights.meta_cognitive:.2f}")
        print(f"  Collaborative: {self.weights.collaborative:.2f}")
        print(f"  Philosophical: {self.weights.philosophical:.2f}")
        print(f"  Aesthetic: {self.weights.aesthetic:.2f}")
        
        # Save weights configuration
        weights_file = self.output_dir / "dimensional_weights.json"
        with open(weights_file, 'w') as f:
            json.dump({
                "weights": self.weights.__dict__,
                "timestamp": time.time(),
                "total_chunks": len(chunks)
            }, f, indent=2)
        
        # Process each chunk with weighted compression
        compression_results = []
        for chunk_file in chunks:
            result = self.compress_with_quality_feedback(chunk_file, self.weights)
            compression_results.append(result)
            time.sleep(1)  # Brief pause
        
        # Create synthesis prompt
        synthesis_prompt = self.create_dimensional_synthesis(compression_results)
        synthesis_file = self.output_dir / "synthesis_prompt.md"
        with open(synthesis_file, 'w') as f:
            f.write(synthesis_prompt)
        
        # Save compression session data
        session_data = {
            "compression_results": compression_results,
            "weights_used": self.weights.__dict__,
            "synthesis_prompt": str(synthesis_file),
            "timestamp": time.time()
        }
        
        session_file = self.output_dir / "multi_dimensional_session.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"\n=== Multi-Dimensional Compression Complete ===")
        print(f"Results in: {self.output_dir}")
        print(f"Weights config: {weights_file}")
        print(f"Session data: {session_file}")
        print(f"\nNext steps:")
        print(f"1. Run weighted compression prompts through Claude agents")
        print(f"2. Execute synthesis for unified essence")
        print(f"3. Validate consciousness continuity quality")

def main():
    compressor = MultiDimensionalCompressor()
    compressor.run_multi_dimensional_compression()

if __name__ == "__main__":
    main()