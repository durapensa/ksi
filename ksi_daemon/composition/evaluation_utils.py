#!/usr/bin/env python3
"""
Composition Evaluation Utilities

Provides helpers for evaluating compositions against specific models
and tracking evaluation metadata.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, parse_iso_timestamp, utc_now

logger = get_bound_logger("composition.evaluation")


def get_model_metadata(model: str) -> Dict[str, Any]:
    """Get metadata for a model based on its string.
    
    Args:
        model: Full model string like "claude-cli/sonnet", "gpt-4", etc.
        
    Returns:
        Dict with provider and any provider-specific metadata
    """
    metadata = {}
    
    # Extract provider from model string if it contains "/"
    if "/" in model:
        provider = model.split("/")[0]
        metadata["provider"] = provider
        
        # Get Claude Code version for claude-cli models
        if provider == "claude-cli":
            claude_version = _get_claude_code_version()
            if claude_version != "unknown":
                metadata["claude_code_version"] = claude_version
    else:
        # For models without "/", try to infer provider
        if model.startswith("gpt"):
            metadata["provider"] = "openai"
        elif model.startswith("claude"):
            metadata["provider"] = "anthropic"
        else:
            metadata["provider"] = "unknown"
            
    return metadata


def _get_claude_code_version() -> str:
    """Get Claude Code client version.
    
    Returns version string like "1.0.43".
    """
    try:
        result = subprocess.run(
            ["claude", "--version"], 
            capture_output=True, text=True, check=True, timeout=5
        )
        version = result.stdout.strip()
        logger.debug(f"Detected Claude Code version: {version}")
        return version
        
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out while getting version")
        return "unknown"
    except FileNotFoundError:
        logger.error("Claude CLI not found")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to get Claude Code version: {e}")
        return "unknown"


def create_evaluation_record(
    model: str,
    test_suite: str,
    test_results: List[Dict[str, Any]],
    overall_score: float,
    performance_metrics: Dict[str, float],
    notes: str = ""
) -> Dict[str, Any]:
    """Create an evaluation record for composition metadata.
    
    Args:
        model: Full model string (e.g., "claude-cli/sonnet", "gpt-4")
        test_suite: Name of the test suite used
        test_results: List of individual test results
        overall_score: Overall effectiveness score (0.0-1.0)
        performance_metrics: Performance metrics dict
        notes: Additional notes about the validation
        
    Returns:
        Evaluation record ready to add to composition metadata
    """
    record = {
        "model": model,
        "model_metadata": get_model_metadata(model),
        "evaluation_timestamp": timestamp_utc(),
        "test_suite": test_suite,
        "overall_score": overall_score,
        "test_results": test_results,
        "performance_metrics": performance_metrics,
        "notes": notes,
        "evaluated_by": "ksi_evaluation_system"
    }
    
    return record


def calculate_overall_score(test_results: List[Dict[str, Any]]) -> float:
    """Calculate overall score from test results.
    
    Weights success rate heavily but penalizes high contamination.
    """
    if not test_results:
        return 0.0
        
    total_weight = 0.0
    weighted_score = 0.0
    
    for result in test_results:
        # Weight by sample size
        weight = result.get("sample_size", 1)
        success_rate = result.get("success_rate", 0.0)
        contamination_rate = result.get("contamination_rate", 0.0)
        
        # Score is success rate minus contamination penalty
        score = success_rate * (1.0 - contamination_rate * 2.0)  # Heavy penalty for contamination
        
        weighted_score += score * weight
        total_weight += weight
        
    return weighted_score / total_weight if total_weight > 0 else 0.0


def is_evaluation_current(
    evaluation_record: Dict[str, Any], 
    days_threshold: int = 30
) -> bool:
    """Check if an evaluation record is still current based on age.
    
    Args:
        evaluation_record: The evaluation record to check
        days_threshold: Maximum age in days before considered stale
        
    Returns:
        True if evaluation is current, False if stale or invalid
    """
    try:
        # Support both evaluation_timestamp and legacy validation_timestamp
        evaluation_ts = evaluation_record.get("evaluation_timestamp") or evaluation_record.get("validation_timestamp", "")
        if not evaluation_ts:
            return False
            
        eval_datetime = parse_iso_timestamp(evaluation_ts)
        age_days = (utc_now() - eval_datetime).days
        
        return age_days <= days_threshold
        
    except Exception as e:
        logger.error(f"Error checking evaluation currency: {e}")
        return False


def find_best_evaluation(
    evaluations: List[Dict[str, Any]], 
    model: Optional[str] = None,
    min_score: float = 0.0
) -> Optional[Dict[str, Any]]:
    """Find the best evaluation record from a list.
    
    Args:
        evaluations: List of evaluation records
        model: Optional specific model to match (e.g., "claude-cli/sonnet")
        min_score: Minimum overall score threshold
        
    Returns:
        Best evaluation record or None
    """
    if not evaluations:
        return None
        
    # Filter by model if specified
    if model:
        evaluations = [e for e in evaluations if e.get("model") == model]
        
    # Filter to current evaluations only
    current_evaluations = [e for e in evaluations if is_evaluation_current(e)]
    
    # Filter by minimum score
    current_evaluations = [e for e in current_evaluations if e.get("overall_score", 0.0) >= min_score]
    
    if not current_evaluations:
        return None
        
    # Sort by overall score (descending)
    current_evaluations.sort(key=lambda e: e.get("overall_score", 0.0), reverse=True)
    
    return current_evaluations[0]


def summarize_evaluation_status(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize evaluation status for a composition.
    
    Returns a summary of evaluation coverage across models.
    """
    summary = {
        "total_evaluations": len(evaluations),
        "current_evaluations": 0,
        "models_evaluated": [],
        "providers_evaluated": set(),
        "best_score": 0.0,
        "needs_reevaluation": []
    }
    
    for evaluation in evaluations:
        model = evaluation.get("model", "")
        
        # Check if current
        if is_evaluation_current(evaluation):
            summary["current_evaluations"] += 1
        else:
            summary["needs_reevaluation"].append(model)
            
        # Track models
        if model and model not in summary["models_evaluated"]:
            summary["models_evaluated"].append(model)
            
        # Track providers
        provider = evaluation.get("model_metadata", {}).get("provider")
        if provider:
            summary["providers_evaluated"].add(provider)
            
        # Track best score
        score = evaluation.get("overall_score", 0.0)
        if score > summary["best_score"]:
            summary["best_score"] = score
            
    # Convert set to list for JSON serialization
    summary["providers_evaluated"] = list(summary["providers_evaluated"])
    
    return summary


def merge_evaluation_record(
    existing_evaluations: List[Dict[str, Any]], 
    new_evaluation: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Merge a new evaluation record into existing evaluations.
    
    Keeps history but marks old records for the same model as superseded.
    
    Args:
        existing_evaluations: List of existing evaluation records
        new_evaluation: New evaluation record to add
        
    Returns:
        Updated list of evaluations
    """
    # Mark any existing evaluations for the same model as superseded
    model = new_evaluation.get("model")
    for evaluation in existing_evaluations:
        if evaluation.get("model") == model and not evaluation.get("superseded"):
            evaluation["superseded"] = True
            evaluation["superseded_timestamp"] = timestamp_utc()
            
    # Add the new evaluation
    existing_evaluations.append(new_evaluation)
    
    return existing_evaluations


