"""Integrated optimization events that combine optimization with evaluation."""

import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_daemon.optimization.evaluation_service import evaluation_service

logger = get_bound_logger("integrated_optimization")


@event_handler("optimization:run_with_evaluation")
async def handle_optimization_run_with_evaluation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run optimization followed by automatic LLM-as-Judge evaluation.
    
    This combines:
    1. Running MIPRO/SIMBA optimization
    2. Waiting for completion
    3. Loading optimization results
    4. Triggering LLM-as-Judge evaluation
    5. Handling accept/reject/revise decisions
    """
    component = data.get("component")
    if not component:
        return {"status": "error", "message": "component is required"}
    
    optimizer = data.get("optimizer", "mipro")
    num_trials = data.get("num_trials", 10)
    
    try:
        router = get_router()
        
        # Step 1: Start optimization
        logger.info(f"Starting {optimizer} optimization for {component}")
        
        opt_result = await router.emit(
            "optimization:async",
            {
                "target": component,  # Changed from "component"
                "framework": "dspy",  # Always DSPy for MIPRO/SIMBA
                "config": {
                    "optimizer": optimizer,  # MIPRO or SIMBA
                    "num_trials": num_trials,
                    **data.get("config", {})
                }
            }
        )
        
        # Handle case where emit returns a list (multiple handlers)
        if isinstance(opt_result, list):
            # Find the response with 'started' status
            opt_result = next((r for r in opt_result if r.get("status") == "started"), opt_result[0] if opt_result else {})
        
        if opt_result.get("status") != "started":
            return {
                "status": "error",
                "message": "Failed to start optimization",
                "details": opt_result
            }
        
        optimization_id = opt_result.get("optimization_id")
        logger.info(f"Optimization started with ID: {optimization_id}")
        
        # Step 2: Monitor optimization progress
        max_wait = 900  # 15 minutes
        check_interval = 30  # Check every 30 seconds
        elapsed = 0
        
        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            status_result = await router.emit(
                "optimization:status",
                {"optimization_id": optimization_id}
            )
            
            # Handle case where emit returns a list
            if isinstance(status_result, list):
                status_result = status_result[0] if status_result else {}
            
            status = status_result.get("status")
            logger.info(f"Optimization {optimization_id} status: {status}")
            
            if status == "completed":
                break
            elif status in ["failed", "error"]:
                return {
                    "status": "error",
                    "message": f"Optimization failed with status: {status}",
                    "optimization_id": optimization_id,
                    "details": status_result
                }
        
        if elapsed >= max_wait:
            return {
                "status": "error",
                "message": "Optimization timed out",
                "optimization_id": optimization_id
            }
        
        # Step 3: Load optimization results
        result_file = status_result.get("result", {}).get("result_file")
        if not result_file or not Path(result_file).exists():
            return {
                "status": "error",
                "message": "Optimization result file not found",
                "optimization_id": optimization_id
            }
        
        with open(result_file, 'r') as f:
            optimization_result = json.load(f)
        
        # Add original content (load from component)
        comp_result = await router.emit(
            "composition:get_component",
            {"name": component}
        )
        
        # Handle case where emit returns a list
        if isinstance(comp_result, list):
            comp_result = comp_result[0] if comp_result else {}
        
        if comp_result.get("status") != "success":
            return {
                "status": "error",
                "message": "Failed to load original component",
                "details": comp_result
            }
        
        # Step 4: Prepare evaluation data
        evaluation_data = {
            "component_name": component,
            "original_content": comp_result.get("content", ""),
            "optimized_content": optimization_result.get("optimized_content", ""),
            "optimization_metadata": {
                "optimizer": optimizer,
                "improvement": optimization_result.get("improvement", 0.0),
                "metadata": optimization_result.get("metadata", {})
            }
        }
        
        # Step 5: Trigger LLM-as-Judge evaluation
        logger.info(f"Starting LLM-as-Judge evaluation for optimization {optimization_id}")
        
        eval_result = await evaluation_service.process_optimization_completion(
            optimization_id=optimization_id,
            optimization_result=evaluation_data,
            skip_git=data.get("skip_git", False)
        )
        
        # Step 6: Return comprehensive results
        return {
            "status": "success",
            "optimization_id": optimization_id,
            "optimization_improvement": optimization_result.get("improvement", 0.0),
            "evaluation_result": eval_result,
            "component_updated": eval_result.get("component_updated", False),
            "judge_decision": eval_result.get("recommendation"),
            "message": f"Optimization and evaluation completed for {component}"
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
            result = next((r for r in result if r.get("status") == "started"), result[0] if result else {})
        
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