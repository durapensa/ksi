#!/usr/bin/env python3
"""Prompt iteration and testing framework for systematic prompt improvement."""

import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from typing_extensions import NotRequired, Required
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now, timestamp_utc, filename_timestamp
from ksi_common.file_utils import save_yaml_file, load_yaml_file, ensure_directory
# Removed event_format_linter import - BREAKING CHANGE: Direct TypedDict access
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler
from .completion_utils import send_completion_and_wait
from .evaluators import create_evaluator

logger = get_bound_logger("prompt_iteration")


# TypedDict definitions for event handlers

class IteratePromptData(TypedDict):
    """Run prompt iteration testing on a specific test."""
    test_file: Required[str]  # Path to iteration test YAML file
    composition_name: NotRequired[str]  # Composition to test with (default: 'base-single-agent')
    model: NotRequired[str]  # Model to use (default: 'claude-cli/sonnet')
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class PromptPatternsData(TypedDict):
    """Analyze iteration results to extract successful prompt patterns."""
    test_name: NotRequired[str]  # Optional specific test to analyze
    min_success_rate: NotRequired[float]  # Minimum success rate to consider (default: 0.7)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@dataclass
class PromptVariation:
    """A single prompt variation to test."""
    version: str
    prompt: str
    hypothesis: Optional[str] = None  # Why we think this might work better
    tags: List[str] = field(default_factory=list)  # Technique tags


@dataclass
class IterationResult:
    """Result of testing a prompt variation."""
    version: str
    success: bool
    score: float
    response: str
    response_time: float
    evaluator_scores: List[Dict[str, Any]]
    timestamp: datetime = field(default_factory=utc_now)


@dataclass
class PromptIterationTest:
    """A complete prompt iteration test configuration."""
    test_name: str
    base_prompt: str
    evaluators: List[Dict[str, Any]]
    success_threshold: float
    variations: List[PromptVariation]
    failure_analysis: Optional[Dict[str, Any]] = None
    results: List[IterationResult] = field(default_factory=list)


class PromptIterationEngine:
    """Engine for systematic prompt iteration and improvement."""
    
    def __init__(self):
        self.iterations_dir = config.evaluations_dir / "prompt_iterations"
        self.iterations_dir = ensure_directory(self.iterations_dir)
        self.results_dir = config.evaluations_dir / "iteration_results"
        self.results_dir = ensure_directory(self.results_dir)
        
    async def run_iteration_test(
        self,
        test_config: PromptIterationTest,
        composition_name: str,
        model: str = "claude-cli/sonnet"
    ) -> Dict[str, Any]:
        """Run all variations of a prompt test."""
        results = []
        
        # Test base prompt first
        base_result = await self._test_single_prompt(
            prompt=test_config.base_prompt,
            evaluators=test_config.evaluators,
            composition_name=composition_name,
            model=model,
            version="base"
        )
        results.append(base_result)
        
        # Test each variation
        for variation in test_config.variations:
            result = await self._test_single_prompt(
                prompt=variation.prompt,
                evaluators=test_config.evaluators,
                composition_name=composition_name,
                model=model,
                version=variation.version
            )
            results.append(result)
        
        # Analyze results
        analysis = self._analyze_results(results, test_config)
        
        # Save results
        self._save_iteration_results(test_config.test_name, results, analysis)
        
        return {
            "test_name": test_config.test_name,
            "total_variations": len(test_config.variations) + 1,
            "results": results,
            "analysis": analysis
        }
    
    async def _test_single_prompt(
        self,
        prompt: str,
        evaluators: List[Dict[str, Any]],
        composition_name: str,
        model: str,
        version: str
    ) -> IterationResult:
        """Test a single prompt variation."""
        # Get response from model
        start_time = asyncio.get_event_loop().time()
        
        result = await send_completion_and_wait(
            prompt=prompt,
            model=model,
            agent_config={
                'composition': composition_name,
                'temperature': 0.0  # For consistent testing
            }
        )
        
        response_time = asyncio.get_event_loop().time() - start_time
        
        if result.get('status') != 'completed':
            return IterationResult(
                version=version,
                success=False,
                score=0.0,
                response=result.get('error', 'Failed to get response'),
                response_time=response_time,
                evaluator_scores=[]
            )
        
        response_text = result.get('response', '')
        
        # Run evaluators
        evaluator_scores = []
        total_weight = 0
        weighted_score = 0
        
        for eval_config in evaluators:
            eval_type = eval_config.get('type')
            weight = eval_config.get('weight', 1.0)
            
            evaluator = create_evaluator(eval_type)
            if evaluator:
                score = await evaluator.evaluate(response_text, eval_config)
                evaluator_scores.append({
                    'type': eval_type,
                    'score': score,
                    'weight': weight,
                    'config': eval_config
                })
                weighted_score += score * weight
                total_weight += weight
        
        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        return IterationResult(
            version=version,
            success=final_score >= 0.7,  # Default threshold
            score=final_score,
            response=response_text[:200] + '...' if len(response_text) > 200 else response_text,
            response_time=response_time,
            evaluator_scores=evaluator_scores
        )
    
    def _analyze_results(
        self, 
        results: List[IterationResult], 
        test_config: PromptIterationTest
    ) -> Dict[str, Any]:
        """Analyze iteration results to identify patterns."""
        successful_versions = [r for r in results if r.success]
        failed_versions = [r for r in results if not r.success]
        
        # Identify best performing version
        best_version = max(results, key=lambda r: r.score)
        
        # Extract technique patterns from successful prompts
        technique_patterns = self._extract_technique_patterns(
            successful_versions, 
            test_config.variations
        )
        
        return {
            "success_rate": len(successful_versions) / len(results),
            "best_version": {
                "version": best_version.version,
                "score": best_version.score,
                "response": best_version.response
            },
            "successful_versions": [r.version for r in successful_versions],
            "failed_versions": [r.version for r in failed_versions],
            "technique_patterns": technique_patterns,
            "improvement_over_base": best_version.score - results[0].score if results else 0
        }
    
    def _extract_technique_patterns(
        self,
        successful_results: List[IterationResult],
        variations: List[PromptVariation]
    ) -> Dict[str, Any]:
        """Extract common patterns from successful prompts."""
        # Map versions to variations for tag analysis
        version_to_variation = {v.version: v for v in variations}
        
        # Count technique tags in successful prompts
        technique_counts = {}
        for result in successful_results:
            if result.version in version_to_variation:
                variation = version_to_variation[result.version]
                for tag in variation.tags:
                    technique_counts[tag] = technique_counts.get(tag, 0) + 1
        
        return {
            "successful_techniques": technique_counts,
            "most_effective": max(technique_counts.items(), key=lambda x: x[1])[0] 
                if technique_counts else None
        }
    
    def _save_iteration_results(
        self,
        test_name: str,
        results: List[IterationResult],
        analysis: Dict[str, Any]
    ):
        """Save iteration results to file."""
        timestamp = filename_timestamp()
        filename = f"{test_name}_iteration_{timestamp}.yaml"
        filepath = self.results_dir / filename
        
        data = {
            "test_name": test_name,
            "timestamp": timestamp_utc(),
            "results": [
                {
                    "version": r.version,
                    "success": r.success,
                    "score": r.score,
                    "response": r.response,
                    "response_time": r.response_time,
                    "evaluator_scores": r.evaluator_scores
                }
                for r in results
            ],
            "analysis": analysis
        }
        
        save_yaml_file(filepath, data)
        
        logger.info(f"Saved iteration results to {filename}")


@event_handler("evaluation:iterate_prompt")
async def handle_iterate_prompt(data: IteratePromptData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run prompt iteration testing on a specific test.
    
    Parameters:
        test_file: Path to iteration test YAML file
        composition_name: Composition to test with
        model: Model to use (default: claude-cli/sonnet)
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    test_file = data.get('test_file')  # Path to iteration test YAML
    composition_name = data.get('composition_name', 'base-single-agent')
    model = data.get('model', 'claude-cli/sonnet')
    
    if not test_file:
        return {"status": "error", "error": "test_file parameter required"}
    
    # Load test configuration
    test_path = Path(test_file)
    if not test_path.is_absolute():
        test_path = config.evaluations_dir / "prompt_iterations" / test_file
    
    if not test_path.exists():
        return {"status": "error", "error": f"Test file not found: {test_path}"}
    
    test_data = load_yaml_file(test_path)
    
    # Parse into test configuration
    variations = []
    for var_data in test_data.get('variations', []):
        variations.append(PromptVariation(
            version=var_data['version'],
            prompt=var_data['prompt'],
            hypothesis=var_data.get('hypothesis'),
            tags=var_data.get('tags', [])
        ))
    
    test_config = PromptIterationTest(
        test_name=test_data['test_name'],
        base_prompt=test_data['base_prompt'],
        evaluators=test_data['evaluators'],
        success_threshold=test_data.get('success_threshold', 0.7),
        variations=variations,
        failure_analysis=test_data.get('failure_analysis')
    )
    
    # Run iteration testing
    engine = PromptIterationEngine()
    results = await engine.run_iteration_test(test_config, composition_name, model)
    
    return {
        "status": "success",
        **results
    }


@event_handler("evaluation:prompt_patterns")
async def handle_prompt_patterns(data: PromptPatternsData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Analyze all iteration results to extract successful prompt patterns.
    
    Parameters:
        test_name: Optional specific test to analyze
        min_success_rate: Minimum success rate to consider (default: 0.7)
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    test_name = data.get('test_name')
    min_success_rate = data.get('min_success_rate', 0.7)
    
    try:
        engine = PromptIterationEngine()
        results_dir = engine.results_dir
        
        # Load all or specific iteration results
        pattern_data = {
            "techniques": {},
            "successful_patterns": [],
            "improvement_techniques": []
        }
        
        for result_file in results_dir.glob("*_iteration_*.yaml"):
            try:
                result_data = load_yaml_file(result_file)
                
                if test_name and result_data['test_name'] != test_name:
                    continue
                
                analysis = result_data.get('analysis', {})
                if analysis.get('success_rate', 0) >= min_success_rate:
                    # Extract successful techniques
                    techniques = analysis.get('technique_patterns', {}).get('successful_techniques', {})
                    for technique, count in techniques.items():
                        pattern_data['techniques'][technique] = pattern_data['techniques'].get(technique, 0) + count
                    
                    # Track improvement patterns
                    if analysis.get('improvement_over_base', 0) > 0.1:
                        pattern_data['improvement_techniques'].append({
                            "test": result_data['test_name'],
                            "best_version": analysis['best_version']['version'],
                            "improvement": analysis['improvement_over_base']
                        })
            except Exception as e:
                logger.warning(f"Error processing result file {result_file}: {e}")
                continue
        
        # Sort techniques by effectiveness
        sorted_techniques = sorted(
            pattern_data['techniques'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return event_response_builder({
            "most_effective_techniques": sorted_techniques[:10],
            "total_tests_analyzed": len(pattern_data['improvement_techniques']),
            "average_improvement": sum(t['improvement'] for t in pattern_data['improvement_techniques']) / len(pattern_data['improvement_techniques'])
                if pattern_data['improvement_techniques'] else 0,
            "top_improvements": sorted(
                pattern_data['improvement_techniques'], 
                key=lambda x: x['improvement'], 
                reverse=True
            )[:5]
        }, context)
    except Exception as e:
        return error_response(f"Failed to analyze prompt patterns: {str(e)}", context)