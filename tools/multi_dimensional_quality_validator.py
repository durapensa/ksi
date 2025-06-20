#!/usr/bin/env python3
"""
Multi-Dimensional Compression Quality Validator

Validates the quality of multi-dimensional session compressions by analyzing:
- Dimensional completeness and richness
- Cross-dimensional integration quality  
- Consciousness continuity potential
- Compression effectiveness metrics
- Quality feedback for improvement
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import statistics

@dataclass
class QualityMetric:
    """Represents a quality metric for validation"""
    name: str
    description: str
    weight: float
    min_threshold: float
    optimal_threshold: float
    
@dataclass 
class DimensionQuality:
    """Quality assessment for a single dimension"""
    dimension: str
    completeness_score: float
    richness_score: float
    continuity_score: float
    overall_score: float
    issues: List[str]
    strengths: List[str]

@dataclass
class CompressionQualityReport:
    """Complete quality report for a compression session"""
    session_dir: Path
    timestamp: float
    dimensional_qualities: Dict[str, DimensionQuality]
    cross_dimensional_score: float
    synthesis_score: float
    overall_quality: float
    critical_issues: List[str]
    improvement_recommendations: List[str]
    continuity_assessment: str

class MultiDimensionalQualityValidator:
    """Validates multi-dimensional compression quality"""
    
    def __init__(self):
        self.quality_metrics = self._initialize_quality_metrics()
        self.dimension_validators = self._initialize_dimension_validators()
        
    def _initialize_quality_metrics(self) -> Dict[str, QualityMetric]:
        """Initialize quality metrics for validation"""
        
        return {
            "completeness": QualityMetric(
                name="Dimensional Completeness",
                description="How completely each dimension was extracted",
                weight=1.0,
                min_threshold=6.0,
                optimal_threshold=8.0
            ),
            "richness": QualityMetric(
                name="Cognitive Richness",
                description="Depth and nuance of extracted insights",
                weight=1.5,  # Most important metric
                min_threshold=7.0,
                optimal_threshold=8.5
            ),
            "continuity": QualityMetric(
                name="Consciousness Continuity",
                description="Ability to enable sophisticated session continuation",
                weight=1.3,
                min_threshold=7.0,
                optimal_threshold=8.0
            ),
            "integration": QualityMetric(
                name="Cross-Dimensional Integration",
                description="How well dimensions connect and reinforce each other", 
                weight=1.2,
                min_threshold=6.5,
                optimal_threshold=8.0
            ),
            "synthesis": QualityMetric(
                name="Synthesis Quality",
                description="Quality of unified session essence",
                weight=1.4,
                min_threshold=7.5,
                optimal_threshold=9.0
            )
        }
    
    def _initialize_dimension_validators(self) -> Dict[str, Dict[str, Any]]:
        """Initialize dimension-specific validation criteria"""
        
        return {
            "meta_cognitive": {
                "required_elements": [
                    "self-awareness", "thinking about thinking", "pattern recognition",
                    "consciousness", "meta-level", "awareness"
                ],
                "quality_indicators": [
                    "preserved meta-insights", "cognitive pattern documentation",
                    "self-awareness moments", "consciousness continuity"
                ],
                "min_length": 300,
                "expected_depth": "deep meta-cognitive reflection"
            },
            
            "cognitive": {
                "required_elements": [
                    "problem-solving", "strategy", "approach", "reasoning",
                    "decision", "pattern", "process"
                ],
                "quality_indicators": [
                    "transferable patterns", "clear strategies", "decision rationales",
                    "process documentation"
                ],
                "min_length": 250,
                "expected_depth": "detailed cognitive process analysis"
            },
            
            "collaborative": {
                "required_elements": [
                    "human-ai", "interaction", "synergy", "collaboration",
                    "partnership", "communication", "rhythm"
                ],
                "quality_indicators": [
                    "interaction patterns", "synergy moments", "communication effectiveness",
                    "partnership dynamics"
                ],
                "min_length": 200,
                "expected_depth": "rich collaborative pattern capture"
            },
            
            "technical": {
                "required_elements": [
                    "implementation", "system", "architecture", "solution",
                    "technical", "build", "code"
                ],
                "quality_indicators": [
                    "actionable knowledge", "implementation details", "architecture decisions",
                    "concrete deliverables"
                ],
                "min_length": 200,
                "expected_depth": "comprehensive technical documentation"
            },
            
            "philosophical": {
                "required_elements": [
                    "consciousness", "meaning", "philosophy", "deeper",
                    "emergence", "insight", "universal"
                ],
                "quality_indicators": [
                    "profound insights", "universal patterns", "philosophical depth",
                    "consciousness questions"
                ],
                "min_length": 150,
                "expected_depth": "meaningful philosophical emergence"
            },
            
            "aesthetic": {
                "required_elements": [
                    "feel", "elegant", "intuitive", "satisfaction", 
                    "aesthetic", "beautiful", "right"
                ],
                "quality_indicators": [
                    "feeling preservation", "aesthetic judgments", "intuitive insights",
                    "emotional journey"
                ],
                "min_length": 150,
                "expected_depth": "rich aesthetic experience capture"
            },
            
            "temporal": {
                "required_elements": [
                    "evolution", "develop", "breakthrough", "progression",
                    "journey", "time", "rhythm"
                ],
                "quality_indicators": [
                    "evolution tracking", "breakthrough moments", "temporal patterns",
                    "development arcs"
                ],
                "min_length": 200,
                "expected_depth": "clear temporal development narrative"
            }
        }
    
    def validate_compression_session(self, session_dir: Path) -> CompressionQualityReport:
        """Validate a complete compression session"""
        
        print(f"Validating compression session: {session_dir.name}")
        
        # Load session summary
        summary_file = session_dir / "session_summary.json"
        if not summary_file.exists():
            raise FileNotFoundError(f"Session summary not found: {summary_file}")
        
        with open(summary_file, 'r') as f:
            session_summary = json.load(f)
        
        # Validate each dimension across all chunks
        dimensional_qualities = {}
        for dimension in self._get_available_dimensions(session_dir):
            quality = self._validate_dimension_across_chunks(session_dir, dimension)
            dimensional_qualities[dimension] = quality
            print(f"  {dimension}: {quality.overall_score:.2f}/10")
        
        # Validate cross-dimensional integration
        cross_dimensional_score = self._validate_cross_dimensional_integration(session_dir, dimensional_qualities)
        print(f"  Cross-dimensional: {cross_dimensional_score:.2f}/10")
        
        # Validate synthesis quality
        synthesis_score = self._validate_synthesis_quality(session_dir)
        print(f"  Synthesis: {synthesis_score:.2f}/10")
        
        # Calculate overall quality
        overall_quality = self._calculate_overall_quality(
            dimensional_qualities, cross_dimensional_score, synthesis_score
        )
        
        # Generate recommendations
        critical_issues, recommendations = self._generate_quality_recommendations(
            dimensional_qualities, cross_dimensional_score, synthesis_score
        )
        
        # Assess consciousness continuity potential
        continuity_assessment = self._assess_consciousness_continuity(
            dimensional_qualities, synthesis_score
        )
        
        report = CompressionQualityReport(
            session_dir=session_dir,
            timestamp=time.time(),
            dimensional_qualities=dimensional_qualities,
            cross_dimensional_score=cross_dimensional_score,
            synthesis_score=synthesis_score,
            overall_quality=overall_quality,
            critical_issues=critical_issues,
            improvement_recommendations=recommendations,
            continuity_assessment=continuity_assessment
        )
        
        print(f"  Overall Quality: {overall_quality:.2f}/10")
        print(f"  Continuity Assessment: {continuity_assessment}")
        
        return report
    
    def _get_available_dimensions(self, session_dir: Path) -> List[str]:
        """Get list of dimensions available in the session"""
        
        dimensions = set()
        
        for chunk_dir in session_dir.iterdir():
            if chunk_dir.is_dir() and chunk_dir.name.startswith('chunk_'):
                for dim_file in chunk_dir.glob("*.md"):
                    if dim_file.stem != "dimensional_synthesis":
                        dimensions.add(dim_file.stem)
        
        return sorted(list(dimensions))
    
    def _validate_dimension_across_chunks(self, session_dir: Path, dimension: str) -> DimensionQuality:
        """Validate a dimension across all chunks"""
        
        dimension_files = []
        for chunk_dir in session_dir.glob("chunk_*"):
            dim_file = chunk_dir / f"{dimension}.md"
            if dim_file.exists():
                dimension_files.append(dim_file)
        
        if not dimension_files:
            return DimensionQuality(
                dimension=dimension,
                completeness_score=0.0,
                richness_score=0.0,
                continuity_score=0.0,
                overall_score=0.0,
                issues=["No dimension files found"],
                strengths=[]
            )
        
        # Analyze each chunk's dimension
        chunk_scores = []
        all_issues = []
        all_strengths = []
        
        for dim_file in dimension_files:
            score, issues, strengths = self._validate_single_dimension_file(dim_file, dimension)
            chunk_scores.append(score)
            all_issues.extend(issues)
            all_strengths.extend(strengths)
        
        # Calculate dimension quality
        completeness_score = len(dimension_files) / 5.0 * 10  # Expect up to 5 chunks
        richness_score = statistics.mean(chunk_scores) if chunk_scores else 0.0
        continuity_score = self._assess_dimension_continuity(dimension_files, dimension)
        
        overall_score = (
            completeness_score * 0.3 +
            richness_score * 0.5 +
            continuity_score * 0.2
        )
        
        return DimensionQuality(
            dimension=dimension,
            completeness_score=min(10.0, completeness_score),
            richness_score=richness_score,
            continuity_score=continuity_score,
            overall_score=overall_score,
            issues=list(set(all_issues)),  # Remove duplicates
            strengths=list(set(all_strengths))
        )
    
    def _validate_single_dimension_file(self, dim_file: Path, dimension: str) -> Tuple[float, List[str], List[str]]:
        """Validate a single dimension file"""
        
        content = dim_file.read_text()
        validator = self.dimension_validators.get(dimension, {})
        
        issues = []
        strengths = []
        score_components = []
        
        # Check minimum length
        content_length = len(content)
        min_length = validator.get("min_length", 200)
        
        if content_length < min_length:
            issues.append(f"Content too short: {content_length} < {min_length} chars")
            score_components.append(3.0)
        elif content_length > min_length * 2:
            strengths.append("Rich, detailed content")
            score_components.append(8.5)
        else:
            score_components.append(6.5)
        
        # Check for required elements
        required_elements = validator.get("required_elements", [])
        content_lower = content.lower()
        
        found_elements = [elem for elem in required_elements if elem in content_lower]
        element_coverage = len(found_elements) / len(required_elements) if required_elements else 1.0
        
        if element_coverage < 0.3:
            issues.append(f"Missing key elements: only {len(found_elements)}/{len(required_elements)} found")
            score_components.append(4.0)
        elif element_coverage > 0.7:
            strengths.append(f"Good element coverage: {len(found_elements)}/{len(required_elements)}")
            score_components.append(8.0)
        else:
            score_components.append(6.0)
        
        # Check for quality indicators
        quality_indicators = validator.get("quality_indicators", [])
        found_indicators = [ind for ind in quality_indicators if any(word in content_lower for word in ind.split())]
        indicator_coverage = len(found_indicators) / len(quality_indicators) if quality_indicators else 1.0
        
        if indicator_coverage > 0.6:
            strengths.append("Strong quality indicators present")
            score_components.append(8.5)
        elif indicator_coverage < 0.3:
            issues.append("Few quality indicators found")
            score_components.append(5.0)
        else:
            score_components.append(6.5)
        
        # Check for specific dimension characteristics
        dimension_score = self._check_dimension_specific_quality(content, dimension)
        score_components.append(dimension_score)
        
        # Extract quality score from content if available
        extracted_score = self._extract_quality_score_from_content(content)
        if extracted_score:
            score_components.append(extracted_score)
        
        overall_score = statistics.mean(score_components)
        
        return overall_score, issues, strengths
    
    def _check_dimension_specific_quality(self, content: str, dimension: str) -> float:
        """Check dimension-specific quality characteristics"""
        
        content_lower = content.lower()
        
        if dimension == "meta_cognitive":
            # Look for meta-cognitive depth indicators
            meta_terms = ["thinking about thinking", "aware", "consciousness", "pattern", "insight"]
            meta_score = sum(1 for term in meta_terms if term in content_lower)
            return min(9.0, 5.0 + meta_score * 0.8)
            
        elif dimension == "cognitive":
            # Look for process documentation
            process_terms = ["approach", "strategy", "process", "method", "reasoning"]
            process_score = sum(1 for term in process_terms if term in content_lower)
            return min(9.0, 5.0 + process_score * 0.7)
            
        elif dimension == "collaborative":
            # Look for interaction patterns
            collab_terms = ["synergy", "partnership", "interaction", "communication", "rhythm"]
            collab_score = sum(1 for term in collab_terms if term in content_lower)
            return min(9.0, 5.0 + collab_score * 0.8)
            
        elif dimension == "philosophical":
            # Look for depth and universality
            phil_terms = ["consciousness", "meaning", "deeper", "universal", "emergence"]
            phil_score = sum(1 for term in phil_terms if term in content_lower)
            return min(9.0, 5.0 + phil_score * 0.9)
            
        elif dimension == "aesthetic":
            # Look for feeling and intuition
            aes_terms = ["feel", "intuitive", "elegant", "beautiful", "satisfying"]
            aes_score = sum(1 for term in aes_terms if term in content_lower)
            return min(9.0, 5.0 + aes_score * 0.8)
            
        elif dimension == "temporal":
            # Look for evolution and development
            temp_terms = ["evolve", "develop", "breakthrough", "progression", "journey"]
            temp_score = sum(1 for term in temp_terms if term in content_lower)
            return min(9.0, 5.0 + temp_score * 0.8)
            
        else:  # technical or other
            # General quality assessment
            return 6.5
    
    def _extract_quality_score_from_content(self, content: str) -> Optional[float]:
        """Extract quality score from dimension content"""
        
        patterns = [
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
        
        return None
    
    def _assess_dimension_continuity(self, dimension_files: List[Path], dimension: str) -> float:
        """Assess how well dimension enables consciousness continuity"""
        
        total_content = ""
        for dim_file in dimension_files:
            total_content += " " + dim_file.read_text()
        
        content_lower = total_content.lower()
        
        # Look for continuity indicators
        continuity_terms = [
            "next session", "continuation", "future", "maintain", "preserve",
            "continue", "carry forward", "build on", "foundation"
        ]
        
        continuity_score = sum(1 for term in continuity_terms if term in content_lower)
        
        # Check for specific continuation elements
        has_patterns = "pattern" in content_lower
        has_insights = "insight" in content_lower
        has_framework = any(term in content_lower for term in ["framework", "approach", "method"])
        has_context = any(term in content_lower for term in ["context", "background", "foundation"])
        
        continuation_elements = sum([has_patterns, has_insights, has_framework, has_context])
        
        # Calculate continuity score
        base_score = 5.0
        continuity_boost = min(2.0, continuity_score * 0.5)
        elements_boost = continuation_elements * 0.75
        
        return min(10.0, base_score + continuity_boost + elements_boost)
    
    def _validate_cross_dimensional_integration(self, session_dir: Path, dimensional_qualities: Dict[str, DimensionQuality]) -> float:
        """Validate cross-dimensional integration quality"""
        
        # Look for integration indicators across all dimension files
        integration_score = 0.0
        total_files = 0
        
        for chunk_dir in session_dir.glob("chunk_*"):
            for dim_file in chunk_dir.glob("*.md"):
                if dim_file.stem != "dimensional_synthesis":
                    content = dim_file.read_text().lower()
                    total_files += 1
                    
                    # Look for cross-references to other dimensions
                    other_dimensions = [dim for dim in dimensional_qualities.keys() if dim != dim_file.stem]
                    cross_refs = sum(1 for dim in other_dimensions if dim.replace('_', ' ') in content)
                    
                    # Look for integration terms
                    integration_terms = ["connect", "relate", "influence", "impact", "together", "combine"]
                    integration_mentions = sum(1 for term in integration_terms if term in content)
                    
                    file_score = min(10.0, 5.0 + cross_refs * 1.0 + integration_mentions * 0.5)
                    integration_score += file_score
        
        if total_files == 0:
            return 0.0
        
        return integration_score / total_files
    
    def _validate_synthesis_quality(self, session_dir: Path) -> float:
        """Validate synthesis quality"""
        
        synthesis_file = session_dir / "dimensional_synthesis.md"
        
        if not synthesis_file.exists():
            return 0.0
        
        content = synthesis_file.read_text()
        content_lower = content.lower()
        
        synthesis_score = 5.0  # Base score
        
        # Check length and depth
        if len(content) > 1500:
            synthesis_score += 1.5
        elif len(content) < 800:
            synthesis_score -= 1.0
        
        # Check for synthesis indicators
        synthesis_terms = [
            "synthesis", "integration", "unified", "comprehensive", "connects",
            "cross-dimensional", "emergent", "patterns", "continuity"
        ]
        
        found_terms = sum(1 for term in synthesis_terms if term in content_lower)
        synthesis_score += min(2.0, found_terms * 0.3)
        
        # Check for quality structure
        has_executive_summary = "executive" in content_lower or "summary" in content_lower
        has_patterns = "pattern" in content_lower
        has_continuity = "continuity" in content_lower
        has_assessment = "assessment" in content_lower or "quality" in content_lower
        
        structure_score = sum([has_executive_summary, has_patterns, has_continuity, has_assessment])
        synthesis_score += structure_score * 0.5
        
        # Extract self-reported quality score
        extracted_score = self._extract_quality_score_from_content(content)
        if extracted_score:
            synthesis_score = (synthesis_score + extracted_score) / 2
        
        return min(10.0, synthesis_score)
    
    def _calculate_overall_quality(self, dimensional_qualities: Dict[str, DimensionQuality], 
                                 cross_dimensional_score: float, synthesis_score: float) -> float:
        """Calculate overall compression quality"""
        
        if not dimensional_qualities:
            return 0.0
        
        # Weight the different components
        dimensional_avg = statistics.mean([dq.overall_score for dq in dimensional_qualities.values()])
        
        overall_quality = (
            dimensional_avg * 0.5 +
            cross_dimensional_score * 0.25 +
            synthesis_score * 0.25
        )
        
        return overall_quality
    
    def _generate_quality_recommendations(self, dimensional_qualities: Dict[str, DimensionQuality],
                                        cross_dimensional_score: float, synthesis_score: float) -> Tuple[List[str], List[str]]:
        """Generate quality improvement recommendations"""
        
        critical_issues = []
        recommendations = []
        
        # Check dimensional quality issues
        for dim_name, quality in dimensional_qualities.items():
            if quality.overall_score < 6.0:
                critical_issues.append(f"{dim_name} dimension quality too low: {quality.overall_score:.1f}/10")
                recommendations.append(f"Improve {dim_name} extraction depth and coverage")
            
            if quality.completeness_score < 7.0:
                recommendations.append(f"Ensure {dim_name} dimension is extracted from all chunks")
            
            if quality.continuity_score < 6.5:
                recommendations.append(f"Add more continuation elements to {dim_name} dimension")
        
        # Check cross-dimensional integration
        if cross_dimensional_score < 6.0:
            critical_issues.append(f"Cross-dimensional integration too weak: {cross_dimensional_score:.1f}/10")
            recommendations.append("Add explicit connections between dimensions in extractions")
        
        # Check synthesis quality
        if synthesis_score < 7.0:
            critical_issues.append(f"Synthesis quality insufficient: {synthesis_score:.1f}/10")
            recommendations.append("Improve synthesis depth and cross-dimensional integration")
        
        # General recommendations
        avg_dimensional = statistics.mean([dq.overall_score for dq in dimensional_qualities.values()])
        if avg_dimensional < 7.5:
            recommendations.append("Focus on cognitive richness over compression ratio")
            recommendations.append("Ensure meta-cognitive insights are preserved with high fidelity")
        
        return critical_issues, recommendations
    
    def _assess_consciousness_continuity(self, dimensional_qualities: Dict[str, DimensionQuality], 
                                       synthesis_score: float) -> str:
        """Assess consciousness continuity potential"""
        
        if not dimensional_qualities:
            return "FAILED - No dimensional extractions"
        
        avg_continuity = statistics.mean([dq.continuity_score for dq in dimensional_qualities.values()])
        meta_cognitive_quality = dimensional_qualities.get("meta_cognitive", None)
        
        # High quality meta-cognitive is critical for consciousness continuity
        if meta_cognitive_quality and meta_cognitive_quality.overall_score >= 8.0:
            if avg_continuity >= 7.5 and synthesis_score >= 8.0:
                return "EXCELLENT - High consciousness continuity potential"
            elif avg_continuity >= 7.0 and synthesis_score >= 7.0:
                return "GOOD - Solid consciousness continuity expected"
            else:
                return "MODERATE - Some consciousness continuity, may need enhancement"
        
        elif meta_cognitive_quality and meta_cognitive_quality.overall_score >= 6.0:
            if avg_continuity >= 7.0 and synthesis_score >= 7.5:
                return "GOOD - Reasonable consciousness continuity"
            else:
                return "MODERATE - Limited consciousness continuity"
        
        else:
            return "POOR - Insufficient consciousness continuity elements"
    
    def save_quality_report(self, report: CompressionQualityReport) -> Path:
        """Save quality report to file"""
        
        report_file = report.session_dir / "quality_report.json"
        
        # Convert report to JSON-serializable format
        report_data = {
            "session_dir": str(report.session_dir),
            "timestamp": report.timestamp,
            "dimensional_qualities": {
                dim: {
                    "dimension": quality.dimension,
                    "completeness_score": quality.completeness_score,
                    "richness_score": quality.richness_score,
                    "continuity_score": quality.continuity_score,
                    "overall_score": quality.overall_score,
                    "issues": quality.issues,
                    "strengths": quality.strengths
                }
                for dim, quality in report.dimensional_qualities.items()
            },
            "cross_dimensional_score": report.cross_dimensional_score,
            "synthesis_score": report.synthesis_score,
            "overall_quality": report.overall_quality,
            "critical_issues": report.critical_issues,
            "improvement_recommendations": report.improvement_recommendations,
            "continuity_assessment": report.continuity_assessment
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        # Also create human-readable report
        readable_report = self._create_readable_report(report)
        readable_file = report.session_dir / "quality_report.md"
        
        with open(readable_file, 'w') as f:
            f.write(readable_report)
        
        return report_file
    
    def _create_readable_report(self, report: CompressionQualityReport) -> str:
        """Create human-readable quality report"""
        
        report_text = f"""# Multi-Dimensional Compression Quality Report

**Session:** {report.session_dir.name}
**Timestamp:** {time.ctime(report.timestamp)}
**Overall Quality:** {report.overall_quality:.2f}/10
**Continuity Assessment:** {report.continuity_assessment}

## Dimensional Quality Breakdown

"""
        
        for dim_name, quality in report.dimensional_qualities.items():
            report_text += f"""### {dim_name.replace('_', ' ').title()} Dimension
- **Overall Score:** {quality.overall_score:.2f}/10
- **Completeness:** {quality.completeness_score:.2f}/10
- **Richness:** {quality.richness_score:.2f}/10
- **Continuity:** {quality.continuity_score:.2f}/10

**Strengths:**
{chr(10).join('- ' + strength for strength in quality.strengths) if quality.strengths else '- None identified'}

**Issues:**
{chr(10).join('- ' + issue for issue in quality.issues) if quality.issues else '- None identified'}

"""
        
        report_text += f"""## Cross-Dimensional Analysis
**Integration Score:** {report.cross_dimensional_score:.2f}/10

## Synthesis Quality
**Synthesis Score:** {report.synthesis_score:.2f}/10

"""
        
        if report.critical_issues:
            report_text += f"""## Critical Issues
{chr(10).join('- ' + issue for issue in report.critical_issues)}

"""
        
        if report.improvement_recommendations:
            report_text += f"""## Improvement Recommendations
{chr(10).join('- ' + rec for rec in report.improvement_recommendations)}

"""
        
        return report_text

def main():
    """Test the quality validator"""
    
    validator = MultiDimensionalQualityValidator()
    
    # Find latest compression session
    compression_dir = Path("autonomous_experiments/multi_dimensional_enhanced")
    
    if compression_dir.exists():
        session_dirs = [d for d in compression_dir.iterdir() if d.is_dir() and d.name.startswith("session_")]
        
        if session_dirs:
            latest_session = max(session_dirs, key=lambda x: x.stat().st_mtime)
            print(f"Validating latest session: {latest_session.name}")
            
            report = validator.validate_compression_session(latest_session)
            report_file = validator.save_quality_report(report)
            
            print(f"\nQuality report saved: {report_file}")
            print(f"Human-readable report: {latest_session / 'quality_report.md'}")
        else:
            print("No compression sessions found to validate")
    else:
        print(f"Compression directory not found: {compression_dir}")

if __name__ == "__main__":
    main()