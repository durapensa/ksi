"""Integrated optimization events that combine optimization with evaluation."""

import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common.event_utils import extract_single_response
from ksi_daemon.optimization.evaluation_service import evaluation_service

logger = get_bound_logger("integrated_optimization")


@event_handler("optimization:run_with_evaluation")
async def handle_optimization_run_with_evaluation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Start optimization with automatic LLM-as-Judge evaluation on completion.
    
    This starts the optimization and returns immediately. A transformer
    handles the completion and triggers evaluation.
    """
    component = data.get("component")
    if not component:
        return {"status": "error", "message": "component is required"}
    
    optimizer = data.get("optimizer", "mipro")
    num_trials = data.get("num_trials", 10)
    skip_git = data.get("skip_git", False)
    
    try:
        router = get_router()
        
        # Start optimization with evaluation flag
        logger.info(f"Starting {optimizer} optimization for {component} with auto-evaluation")
        
        opt_result = await router.emit(
            "optimization:async",
            {
                "target": component,
                "framework": "dspy",
                "config": {
                    "optimizer": optimizer,
                    "num_trials": num_trials,
                    "auto_evaluate": True,  # Flag for transformer
                    "skip_git": skip_git,
                    **data.get("config", {})
                }
            }
        )
        
        # Handle case where emit returns a list
        if isinstance(opt_result, list):
            opt_result = next((r for r in opt_result if r.get("status") == "started"), extract_single_response(opt_result) or {})
        
        if opt_result.get("status") != "started":
            return {
                "status": "error",
                "message": "Failed to start optimization",
                "details": opt_result
            }
        
        optimization_id = opt_result.get("optimization_id")
        logger.info(f"Optimization started with ID: {optimization_id}")
        
        return {
            "status": "started",
            "optimization_id": optimization_id,
            "message": f"Started {optimizer} optimization for {component} with automatic evaluation on completion",
            "details": "The optimization will run in the background. LLM-as-Judge evaluation will trigger automatically upon completion."
        }
        
    except Exception as e:
        logger.error(f"Error in integrated optimization: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@event_handler("optimization:run_behavioral") 
async def handle_optimization_run_behavioral(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run optimization with behavioral testing metric.
    
    This uses the agent behavioral metric that spawns test agents
    to evaluate actual behavior rather than instruction text.
    """
    component = data.get("component")
    if not component:
        return {"status": "error", "message": "component is required"}
    
    optimizer = data.get("optimizer", "mipro")
    
    try:
        # Configure optimization to use behavioral metric
        config_with_metric = data.get("config", {})
        config_with_metric["metric"] = "behavioral"
        config_with_metric["metric_config"] = {
            "test_suite": data.get("test_suite", "behavioral_effectiveness"),
            "test_prompts": data.get("test_prompts", [])
        }
        
        # Run optimization with behavioral metric
        router = get_router()
        result = await router.emit(
            "optimization:async",
            {
                "target": component,
                "framework": "dspy",
                "config": config_with_metric
            }
        )
        
        # Handle case where emit returns a list
        if isinstance(result, list):
            result = next((r for r in result if r.get("status") == "started"), extract_single_response(result) or {})
        
        if result.get("status") == "started":
            return {
                "status": "success",
                "message": f"Started behavioral optimization for {component}",
                "optimization_id": result.get("optimization_id"),
                "details": "Using agent-in-the-loop behavioral evaluation"
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"Error starting behavioral optimization: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@event_handler("optimization:completed_with_evaluation")
async def handle_optimization_completed_with_evaluation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Handle optimization completion and trigger LLM-as-Judge evaluation.
    
    This is triggered by a transformer when an optimization with auto_evaluate completes.
    """
    logger.info(f"Received optimization:completed_with_evaluation data type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'NOT A DICT'}")
    
    optimization_id = data.get("optimization_id")
    if not optimization_id:
        return {"status": "error", "message": "optimization_id is required"}
    
    try:
        router = get_router()
        
        # Get data from the transformer result
        result = data.get("result", {})
        logger.info(f"Result type: {type(result)}, value: {result if not isinstance(result, dict) else 'dict with keys: ' + str(list(result.keys()))}")
        
        # Handle case where result might be a JSON string
        if isinstance(result, str):
            try:
                import json
                result = json.loads(result)
                logger.info(f"Parsed JSON string result to dict with keys: {list(result.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse result as JSON: {e}")
                return {"status": "error", "message": "Invalid JSON format from transformer"}
            
        opt_metadata = result.get("optimization_metadata", {}) if isinstance(result, dict) else {}
        opt_config = opt_metadata.get("config", {}) if isinstance(opt_metadata, dict) else {}
        
        # Check auto_evaluate flag
        if not opt_config.get("auto_evaluate"):
            return {"status": "skipped", "message": "Optimization not marked for auto-evaluation"}
        
        component = result.get("component_name")
        if not component:
            return {"status": "error", "message": "component_name not found in result"}
        
        skip_git = opt_config.get("skip_git", False)
        
        logger.info(f"Processing completed optimization {optimization_id} for evaluation")
        
        # Get optimization result from the status response
        status_result = await router.emit(
            "optimization:status",
            {"optimization_id": optimization_id}
        )
        
        if isinstance(status_result, list):
            status_result = extract_single_response(status_result) or {}
        
        # The result data should be in the status response
        if status_result.get("status") != "completed":
            return {
                "status": "error",
                "message": f"Optimization not completed: {status_result.get('status')}"
            }
        
        # Extract optimization result from status
        optimization_result = status_result.get("result", {})
        if not optimization_result:
            # Try to extract from the original result passed by transformer
            optimization_result = result
        
        # Get original component content
        comp_result_list = await router.emit(
            "composition:get_component",
            {"name": component}
        )
        comp_result = extract_single_response(comp_result_list)
        
        # Handle case where comp_result might be a string or unexpected format
        if isinstance(comp_result, str):
            logger.warning(f"Unexpected string response from composition:get_component: {comp_result[:100]}")
            comp_result = {"content": ""}
        elif not isinstance(comp_result, dict):
            logger.warning(f"Unexpected response type from composition:get_component: {type(comp_result)}")
            comp_result = {"content": ""}
        
        # Prepare evaluation data
        # The optimization result might be in different formats
        optimized_content = ""
        improvement = 0.0
        
        if isinstance(optimization_result, dict):
            # Try different possible field names
            optimized_content = optimization_result.get("optimized_content", 
                                 optimization_result.get("content", 
                                 optimization_result.get("result", "")))
            improvement = optimization_result.get("improvement", 
                          result.get("improvement", 0.0))
        
        # If no optimized content (0% improvement case), use original content
        original_content = comp_result.get("content", "")
        if not optimized_content and improvement == 0.0:
            logger.info(f"No optimized content found (0% improvement), using original content for evaluation")
            optimized_content = original_content
        
        evaluation_data = {
            "component_name": component,
            "original_content": original_content,
            "optimized_content": optimized_content,
            "optimization_metadata": {
                "optimizer": opt_metadata.get("optimizer", "unknown"),
                "improvement": improvement,
                "metadata": optimization_result if isinstance(optimization_result, dict) else {}
            }
        }
        
        # Trigger LLM-as-Judge evaluation
        logger.info(f"Starting LLM-as-Judge evaluation for optimization {optimization_id}")
        
        # Ensure evaluation service is initialized
        if evaluation_service.router is None:
            await evaluation_service.initialize(context)
        
        eval_result = await evaluation_service.process_optimization_completion(
            optimization_id=optimization_id,
            optimization_result=evaluation_data,
            skip_git=skip_git
        )
        
        return {
            "status": "success",
            "optimization_id": optimization_id,
            "evaluation_result": eval_result,
            "component_updated": eval_result.get("component_updated", False),
            "judge_decision": eval_result.get("recommendation"),
            "message": f"Evaluation completed for optimization {optimization_id}"
        }
        
    except Exception as e:
        logger.error(f"Error in optimization completion handler: {e}")
        return {
            "status": "error",
            "message": str(e)
        }