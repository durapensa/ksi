#!/usr/bin/env python3
"""
Compression Quality Validator

Validates the quality and completeness of multi-dimensional session compression.
Checks for missing dimensions, insufficient depth, and integration opportunities.
"""

import json
import socket
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

SOCKET_PATH = 'sockets/claude_daemon.sock'

@dataclass
class QualityMetric:
    """Quality metric for compression validation"""
    name: str
    description: str
    weight: float
    score: float = 0.0
    details: str = ""

@dataclass
class ValidationResult:
    """Results from quality validation"""
    overall_score: float
    metrics: List[QualityMetric]
    recommendations: List[str]
    missing_dimensions: List[str]
    synthesis_quality: float
    timestamp: float

class CompressionQualityValidator:
    """Validates multi-dimensional compression quality"""
    
    def __init__(self):
        self.expected_dimensions = [
            "technical", "cognitive", "metacognitive", 
            "collaborative", "philosophical", "aesthetic"
        ]
        self.quality_metrics = self._init_quality_metrics()
    
    def _init_quality_metrics(self) -> List[QualityMetric]:
        """Initialize quality metrics"""
        return [
            QualityMetric(
                name="dimension_completeness",
                description="All expected dimensions are present",
                weight=0.20
            ),
            QualityMetric(
                name="depth_adequacy", 
                description="Each dimension has sufficient depth and detail",
                weight=0.15
            ),
            QualityMetric(
                name="integration_quality",
                description="Connections between dimensions are captured",
                weight=0.15
            ),
            QualityMetric(
                name="cognitive_fidelity",
                description="Thinking processes are accurately represented",
                weight=0.15
            ),
            QualityMetric(
                name="actionable_insights",
                description="Contains reusable patterns and guidelines",
                weight=0.10
            ),
            QualityMetric(
                name="future_continuity",
                description="Enables effective session continuation",
                weight=0.10
            ),
            QualityMetric(
                name="meta_cognitive_richness",
                description="Captures thinking about thinking effectively",
                weight=0.10
            ),
            QualityMetric(
                name="synthesis_coherence", 
                description="Multi-dimensional synthesis is coherent and integrated",
                weight=0.05
            )
        ]
    
    def validate_compression(self, results_dir: Path = None) -> ValidationResult:
        """Validate compression quality"""
        
        if results_dir is None:
            results_dir = Path("autonomous_experiments/compression_results")
        
        print(f"Validating compression quality in: {results_dir}")
        print("=" * 60)
        
        if not results_dir.exists():
            print("❌ Results directory not found!")
            return self._create_failed_validation("Results directory missing")
        
        # Check dimension completeness
        dimension_files = self._check_dimension_files(results_dir)
        missing_dims = [d for d in self.expected_dimensions if d not in dimension_files]
        
        # Analyze each dimension
        dimension_analysis = {}
        for dim in self.expected_dimensions:
            if dim in dimension_files:
                analysis = self._analyze_dimension_file(dimension_files[dim])
                dimension_analysis[dim] = analysis
                print(f"📊 {dim.title()}: {analysis['score']:.1f}/10")
        
        # Check synthesis quality
        synthesis_file = results_dir / "multidimensional_synthesis.md"
        synthesis_quality = self._analyze_synthesis(synthesis_file) if synthesis_file.exists() else 0.0
        
        # Calculate scores
        self._calculate_metric_scores(dimension_analysis, missing_dims, synthesis_quality)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(dimension_analysis, missing_dims)
        
        # Calculate overall score
        overall_score = sum(m.score * m.weight for m in self.quality_metrics)
        
        result = ValidationResult(
            overall_score=overall_score,
            metrics=self.quality_metrics,
            recommendations=recommendations,
            missing_dimensions=missing_dims,
            synthesis_quality=synthesis_quality,
            timestamp=datetime.now().timestamp()
        )
        
        self._print_validation_report(result)
        self._save_validation_results(result, results_dir)
        
        return result
    
    def _check_dimension_files(self, results_dir: Path) -> Dict[str, Path]:
        """Check which dimension files exist"""
        
        dimension_files = {}
        
        for dim in self.expected_dimensions:
            expected_file = results_dir / f"{dim}_dimension.md"
            if expected_file.exists():
                dimension_files[dim] = expected_file
        
        return dimension_files
    
    def _analyze_dimension_file(self, file_path: Path) -> Dict:
        """Analyze the quality of a dimension file"""
        
        try:
            content = file_path.read_text()
            
            analysis = {
                'file': str(file_path),
                'length': len(content),
                'sections': content.count('#'),
                'score': 0.0,
                'issues': []
            }
            
            # Basic content checks
            if len(content) < 500:
                analysis['issues'].append("Content too brief")
                analysis['score'] -= 2.0
            
            if analysis['sections'] < 3:
                analysis['issues'].append("Insufficient structure")
                analysis['score'] -= 1.0
            
            # Check for key indicators
            if 'pattern' in content.lower():
                analysis['score'] += 1.0
            if 'insight' in content.lower():
                analysis['score'] += 1.0
            if 'approach' in content.lower():
                analysis['score'] += 1.0
            if 'why' in content.lower():
                analysis['score'] += 0.5
            if 'because' in content.lower():
                analysis['score'] += 0.5
            
            # Normalize score to 0-10
            analysis['score'] = max(0, min(10, analysis['score'] + 5))
            
            return analysis
        
        except Exception as e:
            return {
                'file': str(file_path),
                'length': 0,
                'sections': 0,
                'score': 0.0,
                'issues': [f"Failed to read: {e}"]
            }
    
    def _analyze_synthesis(self, synthesis_file: Path) -> float:
        """Analyze synthesis quality"""
        
        if not synthesis_file.exists():
            return 0.0
        
        try:
            content = synthesis_file.read_text()
            
            score = 5.0  # Base score
            
            # Check for integration indicators
            if 'dimension' in content.lower():
                score += 1.0
            if 'synthesis' in content.lower():
                score += 1.0
            if 'integration' in content.lower():
                score += 1.0
            if 'connection' in content.lower():
                score += 0.5
            if 'pattern' in content.lower():
                score += 0.5
            
            # Check length
            if len(content) > 2000:
                score += 1.0
            
            return min(10.0, score)
        
        except:
            return 0.0
    
    def _calculate_metric_scores(self, dimension_analysis: Dict, missing_dims: List[str], synthesis_quality: float):
        """Calculate scores for each quality metric"""
        
        # Dimension completeness
        completeness_score = (len(self.expected_dimensions) - len(missing_dims)) / len(self.expected_dimensions) * 10
        self.quality_metrics[0].score = completeness_score
        self.quality_metrics[0].details = f"{len(missing_dims)} missing dimensions"
        
        # Depth adequacy
        if dimension_analysis:
            avg_depth = sum(a['score'] for a in dimension_analysis.values()) / len(dimension_analysis)
            self.quality_metrics[1].score = avg_depth
            self.quality_metrics[1].details = f"Average depth score: {avg_depth:.1f}/10"
        
        # Integration quality (based on synthesis)
        self.quality_metrics[2].score = synthesis_quality
        self.quality_metrics[2].details = f"Synthesis quality: {synthesis_quality:.1f}/10"
        
        # Cognitive fidelity (check for process indicators)
        cognitive_score = 5.0
        if 'cognitive' in dimension_analysis:
            if 'approach' in str(dimension_analysis['cognitive']).lower():
                cognitive_score += 1.0
            if 'process' in str(dimension_analysis['cognitive']).lower():
                cognitive_score += 1.0
        self.quality_metrics[3].score = min(10.0, cognitive_score)
        
        # Actionable insights
        actionable_score = 5.0
        for analysis in dimension_analysis.values():
            if 'pattern' in str(analysis).lower():
                actionable_score += 0.5
            if 'guideline' in str(analysis).lower():
                actionable_score += 0.5
        self.quality_metrics[4].score = min(10.0, actionable_score)
        
        # Future continuity
        continuity_score = synthesis_quality * 0.8  # Based on synthesis quality
        self.quality_metrics[5].score = continuity_score
        
        # Meta-cognitive richness
        meta_score = 5.0
        if 'metacognitive' in dimension_analysis:
            meta_score = dimension_analysis['metacognitive']['score']
        self.quality_metrics[6].score = meta_score
        
        # Synthesis coherence
        self.quality_metrics[7].score = synthesis_quality
    
    def _generate_recommendations(self, dimension_analysis: Dict, missing_dims: List[str]) -> List[str]:
        """Generate improvement recommendations"""
        
        recommendations = []
        
        if missing_dims:
            recommendations.append(f"Missing dimensions: {', '.join(missing_dims)}. Run compression for these dimensions.")
        
        for dim, analysis in dimension_analysis.items():
            if analysis['score'] < 6.0:
                recommendations.append(f"Improve {dim} dimension quality (current: {analysis['score']:.1f}/10)")
            
            if 'Content too brief' in analysis['issues']:
                recommendations.append(f"Expand {dim} dimension content - needs more depth")
        
        if not Path("autonomous_experiments/compression_results/multidimensional_synthesis.md").exists():
            recommendations.append("Create multi-dimensional synthesis to integrate all dimensions")
        
        low_scoring_metrics = [m for m in self.quality_metrics if m.score < 6.0]
        for metric in low_scoring_metrics:
            recommendations.append(f"Improve {metric.name}: {metric.description}")
        
        return recommendations
    
    def _print_validation_report(self, result: ValidationResult):
        """Print validation report"""
        
        print("\n" + "=" * 60)
        print("COMPRESSION QUALITY VALIDATION REPORT")
        print("=" * 60)
        
        print(f"\n📊 Overall Score: {result.overall_score:.1f}/10")
        
        if result.overall_score >= 8.0:
            print("🟢 Excellent compression quality")
        elif result.overall_score >= 6.0:
            print("🟡 Good compression quality with room for improvement")
        else:
            print("🔴 Compression quality needs significant improvement")
        
        print(f"\n📈 Quality Metrics:")
        for metric in result.metrics:
            status = "✅" if metric.score >= 7.0 else "⚠️" if metric.score >= 5.0 else "❌"
            print(f"  {status} {metric.name}: {metric.score:.1f}/10 ({metric.description})")
            if metric.details:
                print(f"      {metric.details}")
        
        if result.missing_dimensions:
            print(f"\n❌ Missing Dimensions: {', '.join(result.missing_dimensions)}")
        
        if result.recommendations:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")
        
        print(f"\n🔗 Synthesis Quality: {result.synthesis_quality:.1f}/10")
    
    def _save_validation_results(self, result: ValidationResult, results_dir: Path):
        """Save validation results"""
        
        validation_file = results_dir / "quality_validation.json"
        
        validation_data = {
            "timestamp": result.timestamp,
            "overall_score": result.overall_score,
            "metrics": [
                {
                    "name": m.name,
                    "description": m.description, 
                    "weight": m.weight,
                    "score": m.score,
                    "details": m.details
                }
                for m in result.metrics
            ],
            "recommendations": result.recommendations,
            "missing_dimensions": result.missing_dimensions,
            "synthesis_quality": result.synthesis_quality
        }
        
        with open(validation_file, 'w') as f:
            json.dump(validation_data, f, indent=2)
        
        print(f"\n💾 Validation results saved: {validation_file}")
    
    def _create_failed_validation(self, reason: str) -> ValidationResult:
        """Create a failed validation result"""
        
        return ValidationResult(
            overall_score=0.0,
            metrics=self.quality_metrics,
            recommendations=[f"Fix critical issue: {reason}"],
            missing_dimensions=self.expected_dimensions,
            synthesis_quality=0.0,
            timestamp=datetime.now().timestamp()
        )

def validate_latest_compression():
    """Validate the latest compression results"""
    
    validator = CompressionQualityValidator()
    result = validator.validate_compression()
    
    return result

def generate_improvement_agent(validation_result: ValidationResult):
    """Generate an agent to improve compression based on validation"""
    
    if not validation_result.recommendations:
        print("No improvements needed!")
        return
    
    improvement_prompt = f"""# Compression Quality Improvement

The multi-dimensional session compression has been validated with a score of {validation_result.overall_score:.1f}/10.

## Issues to Address:
{chr(10).join(f'- {rec}' for rec in validation_result.recommendations)}

## Missing Dimensions:
{', '.join(validation_result.missing_dimensions) if validation_result.missing_dimensions else 'None'}

## Your Task:
1. Address each recommendation systematically
2. Improve low-scoring dimensions
3. Create missing dimensions if needed
4. Enhance the multi-dimensional synthesis
5. Focus on integration between dimensions

## Quality Standards:
- Each dimension should score 7.0+ for depth and insight
- Synthesis should integrate insights across all dimensions
- Content should preserve cognitive journey, not just outcomes
- Include actionable patterns for future sessions

Output improvements to: autonomous_experiments/compression_results/

IMPORTANT: Read existing dimension files first to understand current state, then enhance them."""
    
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        
        command = f"SPAWN::{improvement_prompt}"
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
        
        print(f"🚀 Improvement agent launched: {session_id}")
        print("Monitor progress: ./tools/monitor_autonomous.py")
        
    except Exception as e:
        print(f"❌ Failed to launch improvement agent: {e}")

if __name__ == "__main__":
    import sys
    
    result = validate_latest_compression()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--improve":
        print("\n🔧 Launching improvement agent...")
        generate_improvement_agent(result)