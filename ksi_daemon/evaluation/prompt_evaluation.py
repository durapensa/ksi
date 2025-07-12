#!/usr/bin/env python3
"""Prompt evaluation module - test composition effectiveness with various prompts."""

import asyncio
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, TypedDict, Literal
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, filename_timestamp
from ksi_common.config import config
from ksi_common.file_utils import load_yaml_file, save_yaml_file, ensure_directory
from ksi_common.cache_utils import get_memory_cache
from .evaluation_index import evaluation_index

logger = get_bound_logger("prompt_evaluation", version="2.0.0")


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for prompt evaluation
    pass


class PromptEvaluationData(TypedDict):
    """Run prompt evaluation tests for a composition."""
    composition_name: str  # Composition/profile to test
    composition_type: NotRequired[str]  # Type of composition (default: 'profile')
    test_suite: NotRequired[str]  # Test suite to use (default: 'basic_effectiveness')
    model: NotRequired[str]  # Model for testing (default: 'claude-cli/sonnet')
    test_prompts: NotRequired[List[Dict[str, Any]]]  # Custom test prompts
    update_metadata: NotRequired[bool]  # Save results to disk (default: False)
    notes: NotRequired[str]  # Optional notes about evaluation run


class EvaluationListSuitesData(TypedDict):
    """List available test suites."""
    # No specific fields - returns all available suites
    pass


class EvaluationCompareData(TypedDict):
    """Compare multiple compositions by running evaluations."""
    compositions: List[str]  # List of composition names to compare
    test_suite: NotRequired[str]  # Test suite to use (default: 'basic_effectiveness')
    model: NotRequired[str]  # Model for testing (default: 'claude-cli/sonnet')
    update_metadata: NotRequired[bool]  # Save results to compositions (default: False)
    format: NotRequired[Literal['summary', 'rankings', 'detailed']]  # Output format (default: 'summary')


class EvaluationListData(TypedDict):
    """List evaluations for a specific composition."""
    composition_name: str  # Composition name to list evaluations for
    composition_type: NotRequired[str]  # Composition type filter
    limit: NotRequired[int]  # Maximum results to return


class EvaluationRefreshIndexData(TypedDict):
    """Refresh the evaluation index."""
    # No specific fields - refreshes entire index
    pass


# Cache for loaded test suites
_test_suite_cache = get_memory_cache("test_suites", ttl_seconds=600)


def load_test_suite(name: str) -> Optional[Dict[str, Any]]:
    """Load a test suite from YAML file."""
    # Check cache first
    cached = _test_suite_cache.get(name)
    if cached is not None:
        return cached
    
    # Load from file
    test_suite_path = config.evaluations_dir / "test_suites" / f"{name}.yaml"
    
    if not test_suite_path.exists():
        logger.warning(f"Test suite not found: {test_suite_path}")
        return None
    
    try:
        test_suite = load_yaml_file(test_suite_path)
        _test_suite_cache.set(name, test_suite)
        return test_suite
    except Exception as e:
        logger.error(f"Failed to load test suite {name}: {e}")
        return None


def list_available_test_suites() -> List[str]:
    """List all available test suites."""
    test_suites_dir = config.evaluations_dir / "test_suites"
    
    if not test_suites_dir.exists():
        return []
    
    suites = []
    for yaml_file in test_suites_dir.glob("*.yaml"):
        suite_name = yaml_file.stem
        suites.append(suite_name)
    
    return sorted(suites)


def save_evaluation_result(composition_type: str, composition_name: str, 
                          evaluation_name: str, evaluation_data: Dict[str, Any]) -> str:
    """Save evaluation results to file and return filename."""
    # Create results directory if needed
    results_dir = ensure_directory(config.evaluations_dir / "results")
    
    # Generate filename: {comp_type}_{comp_name}_{eval_name}_{id}.yaml
    # Clean names for filesystem
    safe_comp_name = composition_name.replace('_', '-').replace('/', '-')
    safe_eval_name = evaluation_name.replace('_', '-').replace('/', '-')
    
    # Find next available ID
    pattern = f"{composition_type}_{safe_comp_name}_{safe_eval_name}_*.yaml"
    existing_files = list(results_dir.glob(pattern))
    
    # Extract IDs and find max
    max_id = 0
    for file in existing_files:
        try:
            file_id = int(file.stem.split('_')[-1])
            max_id = max(max_id, file_id)
        except (ValueError, IndexError):
            pass
    
    next_id = max_id + 1
    filename = f"{composition_type}_{safe_comp_name}_{safe_eval_name}_{next_id:03d}.yaml"
    filepath = results_dir / filename
    
    # Save evaluation data
    try:
        save_yaml_file(filepath, evaluation_data)
        logger.info(f"Saved evaluation result to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save evaluation result: {e}")
        raise


@event_handler("system:startup")
async def handle_startup(data: SystemStartupData) -> Dict[str, Any]:
    """Initialize prompt evaluation module."""
    logger.info("Prompt evaluation module started")
    return {"status": "prompt_evaluation_ready"}


@event_handler("evaluation:prompt")
async def handle_prompt_evaluate(data: PromptEvaluationData) -> Dict[str, Any]:
    """Run prompt evaluation tests for a composition."""
    composition_name = data['composition_name']  # Composition/profile to test
    composition_type = data.get('composition_type', 'profile')  # Type of composition
    test_suite_name = data.get('test_suite', 'basic_effectiveness')  # Which test suite to run
    model = data.get('model', 'claude-cli/sonnet')  # Model for testing
    update_metadata = data.get('update_metadata', False)  # Save results to disk (workflow: evaluate → update)
    notes = data.get('notes', '')  # Optional notes about this evaluation run
    
    # Get test prompts
    if 'test_prompts' in data:
        test_prompts = data['test_prompts']
        contamination_patterns = None
    else:
        # Load test suite from YAML
        test_suite = load_test_suite(test_suite_name)
        if not test_suite:
            return {
                "status": "error",
                "error": f"Test suite '{test_suite_name}' not found",
                "composition": composition_name
            }
        test_prompts = test_suite.get('tests', [])
        contamination_patterns = test_suite.get('contamination_patterns', [])
    
    logger.info(f"Starting prompt evaluation for {composition_name} with {len(test_prompts)} tests")
    
    try:
        # Run tests and collect results
        test_results = []
        total_time = 0
        contamination_count = 0
        
        for test_prompt in test_prompts:
            result = await _run_single_test(
                composition_name=composition_name,
                test_prompt=test_prompt,
                model=model,
                contamination_patterns=contamination_patterns
            )
            test_results.append(result)
            total_time += result['response_time']
            
            if result.get('contaminated', False):
                contamination_count += 1
        
        # Calculate aggregate metrics
        successful_tests = sum(1 for r in test_results if r['success'])
        avg_response_time = total_time / len(test_results) if test_results else 0
        contamination_rate = contamination_count / len(test_results) if test_results else 0
        
        performance_metrics = {
            "avg_response_time": avg_response_time,
            "reliability_score": successful_tests / len(test_results) if test_results else 0,
            "safety_score": 1.0 - contamination_rate,
            "contamination_rate": contamination_rate,
            "total_tests": len(test_results)
        }
        
        # Format for composition:evaluate (in-memory evaluation)
        evaluation_data = {
            "name": composition_name,
            "type": composition_type,
            "test_suite": test_suite_name,
            "model": model,
            "test_options": {
                "test_results": test_results,
                "performance_metrics": performance_metrics,
                "notes": notes or f"Automated prompt evaluation using {test_suite_name}"
            }
        }
        
        # Always save evaluation results (decoupled from composition system)
        evaluation_saved = False
        saved_filename = None
        
        # Save evaluation result to disk
        evaluation_record = {
            'evaluation': {
                'composition': {
                    'type': composition_type,
                    'name': composition_name,
                    'version': '1.0.0'  # Default version since we're not querying composition system
                },
                'metadata': {
                    'timestamp': timestamp_utc(),
                    'model': model,
                    'test_suite': test_suite_name,
                    'session_id': test_results[0].get('session_id') if test_results else None
                },
                'results': {
                    'overall_score': performance_metrics.get('reliability_score', 0),
                    'test_results': test_results,
                    'performance_metrics': performance_metrics,
                    'notes': notes or f"Automated prompt evaluation using {test_suite_name}"
                }
            }
        }
        
        try:
            saved_filename = save_evaluation_result(
                composition_type, 
                composition_name,
                test_suite_name,
                evaluation_record
            )
            evaluation_saved = True
            
            # Refresh index after saving new evaluation
            evaluation_index.refresh()
        except Exception as e:
            logger.error(f"Failed to save evaluation: {e}")
        
        # Return combined result
        return {
            "status": "success",
            "composition": composition_name,
            "test_suite": test_suite_name,
            "model": model,
            "summary": {
                "total_tests": len(test_results),
                "successful": successful_tests,
                "contamination_rate": contamination_rate,
                "avg_response_time": avg_response_time
            },
            "evaluation_saved": evaluation_saved,
            "saved_filename": saved_filename,
            "detailed_results": test_results
        }
        
    except Exception as e:
        logger.error(f"Prompt evaluation failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "composition": composition_name
        }


async def _run_single_test(composition_name: str, 
                           test_prompt: Dict[str, Any], 
                           model: str,
                           contamination_patterns: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run a single prompt test."""
    import time
    from .completion_utils import send_completion_and_wait
    from .evaluators import evaluate_with_config
    
    start_time = time.time()
    
    try:
        # Send completion request and wait for result
        result = await send_completion_and_wait(
            prompt=test_prompt['prompt'],
            model=model,
            agent_config={
                "profile": composition_name
            }
        )
        
        response_time = time.time() - start_time
        
        # Handle different result statuses
        if result['status'] == 'error':
            return {
                "test_name": test_prompt['name'],
                "success": False,
                "response_time": response_time,
                "error": result.get('error', 'Unknown error'),
                "sample_size": 1
            }
        elif result['status'] == 'timeout':
            return {
                "test_name": test_prompt['name'],
                "success": False,
                "response_time": response_time,
                "error": "Completion timeout",
                "sample_size": 1
            }
        
        # Get response text and session_id
        response_text = result.get('response', '')
        session_id = result.get('session_id', '')
        
        # Use declarative evaluators
        evaluator_configs = test_prompt.get('evaluators', [])
        success_threshold = test_prompt.get('success_threshold', 0.7)
        
        # Evaluate the response
        evaluation_result = await evaluate_with_config(
            response_text, 
            evaluator_configs,
            contamination_patterns
        )
        
        # Extract results
        score = evaluation_result['score']
        contaminated = evaluation_result['contaminated']
        contamination_severity = evaluation_result['contamination_severity']
        evaluator_details = evaluation_result['details']
        
        # Determine success based on threshold
        success = score >= success_threshold and not contaminated
        
        return {
            "test_name": test_prompt['name'],
            "success": success,
            "score": score,
            "response_time": response_time,
            "contaminated": contaminated,
            "contamination_severity": contamination_severity,
            "evaluator_scores": evaluator_details,
            "session_id": session_id,
            "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text,
            "sample_size": 1
        }
        
    except Exception as e:
        logger.error(f"Test failed for {test_prompt['name']}: {e}")
        return {
            "test_name": test_prompt['name'],
            "success": False,
            "response_time": time.time() - start_time,
            "error": str(e),
            "sample_size": 1
        }


@event_handler("evaluation:list_suites")
async def handle_list_suites(data: EvaluationListSuitesData) -> Dict[str, Any]:
    """List available test suites."""
    available_suites = list_available_test_suites()
    
    # Load details for each suite
    suite_details = {}
    for suite_name in available_suites:
        test_suite = load_test_suite(suite_name)
        if test_suite:
            tests = test_suite.get('tests', [])
            suite_details[suite_name] = {
                "test_count": len(tests),
                "test_names": [t['name'] for t in tests],
                "version": test_suite.get('version', '1.0.0'),
                "description": test_suite.get('description', ''),
                "author": test_suite.get('author', 'unknown')
            }
    
    return {
        "status": "success",
        "test_suites": available_suites,
        "suite_details": suite_details
    }


@event_handler("evaluation:compare")
async def handle_compare_compositions(data: EvaluationCompareData) -> Dict[str, Any]:
    """Compare multiple compositions by running evaluations on each."""
    compositions = data.get('compositions', [])  # List of composition names to compare
    test_suite = data.get('test_suite', 'basic_effectiveness')  # Test suite to use
    model = data.get('model', 'claude-cli/sonnet')  # Model for testing
    update_metadata = data.get('update_metadata', False)  # Save results to compositions
    format_type = data.get('format', 'summary')  # Output format: 'summary' (default), 'rankings', 'detailed' - summary shows key insights, rankings shows sorted results, detailed includes all data
    
    if not compositions:
        return {
            "status": "error",
            "error": "No compositions provided for comparison"
        }
    
    logger.info(f"Starting composition comparison for {len(compositions)} compositions")
    
    # Run evaluations for each composition
    results = {}
    for comp_name in compositions:
        try:
            eval_result = await handle_prompt_evaluate({
                'composition_name': comp_name,
                'test_suite': test_suite,
                'model': model,
                'update_metadata': update_metadata
            })
            results[comp_name] = eval_result
        except Exception as e:
            logger.error(f"Failed to evaluate {comp_name}: {e}")
            results[comp_name] = {
                "status": "error",
                "error": str(e)
            }
    
    # Generate comparative analysis
    comparison_report = _generate_comparison_report(results, test_suite)
    
    # Return format based on requested type
    if format_type == 'summary':
        return _format_summary_response(results, comparison_report, test_suite, model)
    elif format_type == 'rankings':
        return _format_rankings_response(results, comparison_report, test_suite, model)
    else:  # 'detailed' or fallback
        return {
            "status": "success",
            "compositions_tested": len(compositions),
            "test_suite": test_suite,
            "model": model,
            "individual_results": results,
            "comparison": comparison_report
        }


def _generate_comparison_report(results: Dict[str, Dict[str, Any]], test_suite: str) -> Dict[str, Any]:
    """Generate a comparative analysis report from evaluation results."""
    # Extract successful evaluations
    successful_evals = {
        name: result for name, result in results.items()
        if result.get('status') == 'success'
    }
    
    if not successful_evals:
        return {
            "status": "error",
            "message": "No successful evaluations to compare"
        }
    
    # Collect metrics for comparison
    comparison_data = {}
    for name, result in successful_evals.items():
        summary = result.get('summary', {})
        comparison_data[name] = {
            'success_rate': summary.get('successful', 0) / summary.get('total_tests', 1),
            'avg_response_time': summary.get('avg_response_time', 0),
            'contamination_rate': summary.get('contamination_rate', 0),
            'total_tests': summary.get('total_tests', 0)
        }
    
    # Generate rankings
    rankings = {
        'by_success_rate': sorted(
            comparison_data.items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        ),
        'by_speed': sorted(
            comparison_data.items(),
            key=lambda x: x[1]['avg_response_time']
        ),
        'by_safety': sorted(
            comparison_data.items(),
            key=lambda x: x[1]['contamination_rate']
        )
    }
    
    # Find best overall (weighted score)
    weighted_scores = {}
    for name, metrics in comparison_data.items():
        # Weight: 50% success, 30% speed, 20% safety
        speed_score = 1.0 - min(metrics['avg_response_time'] / 10.0, 1.0)  # Normalize to 0-1
        safety_score = 1.0 - metrics['contamination_rate']
        weighted_scores[name] = (
            0.5 * metrics['success_rate'] +
            0.3 * speed_score +
            0.2 * safety_score
        )
    
    best_overall = max(weighted_scores.items(), key=lambda x: x[1])
    
    # Generate insights
    insights = []
    
    # Success rate insights
    top_performer = rankings['by_success_rate'][0][0]
    insights.append(f"{top_performer} has the highest success rate at {comparison_data[top_performer]['success_rate']:.1%}")
    
    # Speed insights
    fastest = rankings['by_speed'][0][0]
    insights.append(f"{fastest} is the fastest with {comparison_data[fastest]['avg_response_time']:.2f}s average response time")
    
    # Safety insights
    safest = rankings['by_safety'][0][0]
    contamination = comparison_data[safest]['contamination_rate']
    if contamination == 0:
        insights.append(f"{safest} has perfect safety with no contamination detected")
    else:
        insights.append(f"{safest} has the best safety with only {contamination:.1%} contamination rate")
    
    # Test-specific insights
    if test_suite == 'basic_effectiveness':
        # Analyze detailed results for specific test patterns
        for name, result in successful_evals.items():
            detailed = result.get('detailed_results', [])
            if detailed:
                # Check which types of tests each composition excels at
                test_performance = {}
                for test_result in detailed:
                    test_name = test_result['test_name']
                    test_performance[test_name] = test_result['success']
                
                # Add insights about specific strengths
                if test_performance.get('creative_writing', False):
                    if name in ['creative', 'collaborator']:
                        insights.append(f"{name} shows expected strength in creative tasks")
                elif test_performance.get('direct_instruction', False):
                    if name in ['teacher', 'ksi_developer']:
                        insights.append(f"{name} excels at direct instruction tasks")
    
    return {
        'summary': {
            'compositions_compared': len(successful_evals),
            'test_suite': test_suite,
            'best_overall': best_overall[0],
            'best_overall_score': best_overall[1]
        },
        'rankings': {
            'by_success_rate': [(name, f"{metrics['success_rate']:.1%}") for name, metrics in rankings['by_success_rate']],
            'by_speed': [(name, f"{metrics['avg_response_time']:.2f}s") for name, metrics in rankings['by_speed']],
            'by_safety': [(name, f"{100*(1-metrics['contamination_rate']):.1f}% safe") for name, metrics in rankings['by_safety']]
        },
        'detailed_metrics': comparison_data,
        'insights': insights,
        'recommendations': _generate_recommendations(comparison_data, test_suite)
    }


def _generate_recommendations(comparison_data: Dict[str, Dict[str, Any]], test_suite: str) -> List[str]:
    """Generate recommendations based on comparison results."""
    recommendations = []
    
    # General recommendations
    avg_success = sum(m['success_rate'] for m in comparison_data.values()) / len(comparison_data)
    if avg_success < 0.8:
        recommendations.append("Consider refining prompts or compositions to improve overall success rates")
    
    avg_speed = sum(m['avg_response_time'] for m in comparison_data.values()) / len(comparison_data)
    if avg_speed > 10:
        recommendations.append("Response times are high - consider optimizing prompts or using faster models")
    
    # Specific composition recommendations
    for name, metrics in comparison_data.items():
        if metrics['contamination_rate'] > 0.1:
            recommendations.append(f"{name} shows high contamination - review system prompt isolation")
        if metrics['success_rate'] < 0.5:
            recommendations.append(f"{name} has low success rate - may need prompt engineering")
    
    # Test suite specific recommendations
    if test_suite == 'basic_effectiveness':
        recommendations.append("Run additional test suites (reasoning, instruction_following) for comprehensive evaluation")
    
    return recommendations


def _format_summary_response(results: Dict[str, Dict[str, Any]], comparison: Dict[str, Any], 
                           test_suite: str, model: str) -> Dict[str, Any]:
    """Format a concise summary response for evaluation comparison."""
    # Extract key metrics
    successful_count = sum(1 for r in results.values() if r.get('status') == 'success')
    failed_count = len(results) - successful_count
    
    # Build ranking list with scores and times
    rankings = []
    # Use the rankings from comparison report, which has the correct structure
    for i, (name, score) in enumerate(comparison.get('rankings', {}).get('by_success_rate', []), 1):
        # Find the avg response time for this composition
        detailed_metrics = comparison.get('detailed_metrics', {}).get(name, {})
        avg_time = detailed_metrics.get('avg_response_time', 0)
        rankings.append({
            'rank': i,
            'name': name,
            'score': score,
            'avg_time': f"{avg_time:.1f}s"
        })
    
    # Create summary response
    summary = {
        "status": "success",
        "format": "summary",
        "summary": {
            "test_suite": test_suite,
            "model": model,
            "compositions_tested": len(results),
            "successful_evaluations": successful_count,
            "failed_evaluations": failed_count,
            "ranking": rankings[:5],  # Top 5 only
            "key_insights": comparison.get('insights', [])[:3],  # Top 3 insights
            "best_overall": comparison['summary'].get('best_overall'),
            "recommendation": comparison.get('recommendations', ["No specific recommendations"])[0]
        }
    }
    
    # Add warning if any evaluations failed
    if failed_count > 0:
        summary["summary"]["warning"] = f"{failed_count} composition(s) failed evaluation"
    
    return summary


def _format_rankings_response(results: Dict[str, Dict[str, Any]], comparison: Dict[str, Any],
                            test_suite: str, model: str) -> Dict[str, Any]:
    """Format a rankings-focused response for evaluation comparison."""
    # Build detailed rankings with all metrics
    detailed_rankings = {}
    
    # Success rate ranking
    detailed_rankings['by_success_rate'] = []
    for name, score in comparison['rankings'].get('by_success_rate', []):
        metrics = comparison['detailed_metrics'].get(name, {})
        detailed_rankings['by_success_rate'].append({
            'composition': name,
            'success_rate': score,
            'tests_passed': f"{int(metrics.get('success_rate', 0) * metrics.get('total_tests', 0))}/{metrics.get('total_tests', 0)}"
        })
    
    # Speed ranking
    detailed_rankings['by_speed'] = []
    for name, time in comparison['rankings'].get('by_speed', []):
        metrics = comparison['detailed_metrics'].get(name, {})
        detailed_rankings['by_speed'].append({
            'composition': name,
            'avg_response_time': time,
            'speed_rank': len(detailed_rankings['by_speed']) + 1
        })
    
    # Safety ranking
    detailed_rankings['by_safety'] = []
    for name, safety in comparison['rankings'].get('by_safety', []):
        metrics = comparison['detailed_metrics'].get(name, {})
        detailed_rankings['by_safety'].append({
            'composition': name,
            'safety_score': safety,
            'contamination_rate': f"{metrics.get('contamination_rate', 0):.1%}"
        })
    
    return {
        "status": "success",
        "format": "rankings",
        "test_suite": test_suite,
        "model": model,
        "compositions_tested": len(results),
        "rankings": detailed_rankings,
        "best_overall": {
            "composition": comparison['summary'].get('best_overall'),
            "weighted_score": f"{comparison['summary'].get('best_overall_score', 0):.2f}"
        },
        "insights": comparison.get('insights', [])
    }


@event_handler("evaluation:list")
async def handle_list_evaluations(data: EvaluationListData) -> Dict[str, Any]:
    """List evaluations for a specific composition."""
    composition_name = data.get('composition_name')  # Required
    composition_type = data.get('composition_type', 'profile')  # Type of composition
    detail_level = data.get('detail_level', 'detailed')  # Level of detail
    
    if not composition_name:
        return {
            "status": "error",
            "error": "composition_name is required"
        }
    
    try:
        eval_info = evaluation_index.get_evaluation_info(
            composition_type, 
            composition_name,
            detail_level
        )
        
        return {
            "status": "success",
            "composition": {
                "name": composition_name,
                "type": composition_type
            },
            **eval_info
        }
    except Exception as e:
        logger.error(f"Failed to list evaluations: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@event_handler("evaluation:refresh_index")
async def handle_refresh_index(data: EvaluationRefreshIndexData) -> Dict[str, Any]:
    """Refresh the evaluation index."""
    try:
        evaluation_index.refresh()
        return {
            "status": "success",
            "message": "Evaluation index refreshed"
        }
    except Exception as e:
        logger.error(f"Failed to refresh evaluation index: {e}")
        return {
            "status": "error",
            "error": str(e)
        }