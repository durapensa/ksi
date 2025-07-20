"""KSI Optimization Service - Framework-agnostic optimization integration."""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.async_operations import (
    start_operation, update_operation_status, complete_operation,
    fail_operation, create_background_task, build_progress_event,
    build_result_event, build_error_event
)
from .mlflow_manager import (
    start_mlflow_server, stop_mlflow_server, get_mlflow_ui_url,
    get_active_optimization_runs, get_optimization_progress
)

logger = get_bound_logger("optimization_service")

# Framework registry
optimization_frameworks: Dict[str, Any] = {}

# Track if MLflow has been initialized
_mlflow_initialized = False


def register_framework(name: str, adapter_class: Any):
    """Register an optimization framework adapter."""
    optimization_frameworks[name] = adapter_class
    logger.info(f"Registered optimization framework: {name}")


@event_handler("optimization:get_framework_info")
async def handle_get_framework_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about available optimization frameworks."""
    
    framework = raw_data.get("framework", "all")
    
    frameworks_info = {}
    for name, adapter_class in optimization_frameworks.items():
        if hasattr(adapter_class, 'get_info'):
            frameworks_info[name] = adapter_class.get_info()
        else:
            frameworks_info[name] = {"available": True, "description": f"{name} framework"}
    
    if framework == "all":
        return event_response_builder({"frameworks": frameworks_info}, context=context)
    elif framework in frameworks_info:
        return event_response_builder(frameworks_info[framework], context=context)
    else:
        return error_response(f"Unknown framework: {framework}", context=context)


@event_handler("optimization:validate_setup")
async def handle_validate_setup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate that optimization setup is ready."""
    
    framework = raw_data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return event_response_builder({
            "valid": False,
            "reason": f"Framework {framework} not registered"
        }, context=context)
    
    adapter_class = optimization_frameworks[framework]
    if hasattr(adapter_class, 'validate_setup'):
        return await adapter_class.validate_setup(raw_data, context)
    
    return event_response_builder({"valid": True}, context=context)


@event_handler("optimization:optimize")
async def handle_optimize(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run optimization on a component using specified framework."""
    
    # Ensure MLflow is initialized
    await _ensure_mlflow_initialized()
    
    framework = raw_data.get("framework", "dspy")
    target = raw_data.get("target")  # Component to optimize
    signature = raw_data.get("signature")  # Signature component name
    metric = raw_data.get("metric")  # Metric component name
    
    if not target:
        return error_response("target component required", context=context)
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    # Load framework adapter
    adapter_class = optimization_frameworks[framework]
    
    # Parse config if it's a string
    config_data = raw_data.get("config", {})
    if isinstance(config_data, str):
        import json
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            return error_response(f"Invalid JSON in config parameter: {config_data}", context=context)
    
    # Create adapter (different constructors for different frameworks)
    if framework == "dspy":
        adapter = adapter_class()  # DSPyFramework takes no args
    else:
        adapter = adapter_class(metric=None, config=config_data)
    
    # Run optimization - filter out duplicate parameters
    kwargs = {k: v for k, v in raw_data.items() if k not in ['target', 'signature', 'metric', 'framework', 'config']}
    result = await adapter.optimize(
        target=target,
        signature=signature,
        metric=metric,
        **kwargs
    )
    
    return event_response_builder(result, context=context)


@event_handler("optimization:async")
async def handle_async_optimization(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start async optimization with background processing."""
    
    # Ensure MLflow is initialized
    await _ensure_mlflow_initialized()
    
    # Extract parameters
    framework = raw_data.get("framework", "dspy")
    target = raw_data.get("target")
    
    if not target:
        return error_response("target component required", context=context)
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    # Start operation tracking
    opt_id = start_operation(
        operation_type="optimization",
        service_name="optimization",
        metadata={
            "component": target,
            "framework": framework,
            "signature": raw_data.get("signature"),
            "metric": raw_data.get("metric")
        }
    )
    
    # Create background task for optimization
    task = create_background_task(
        opt_id,
        run_optimization(opt_id, raw_data, context)
    )
    
    return event_response_builder({
        "optimization_id": opt_id,
        "status": "started",
        "framework": framework,
        "component": target
    }, context)


async def run_optimization(opt_id: str, data: Dict[str, Any], context: Optional[Dict[str, Any]]):
    """Run optimization in background with progress updates."""
    router = get_router()
    
    try:
        # Update status to initializing
        update_operation_status(opt_id, "initializing")
        
        # Emit progress event
        await router.emit("optimization:progress", build_progress_event(
            opt_id, "initializing", "optimization"
        ))
        
        # Get framework
        framework_name = data.get("framework", "dspy")
        adapter_class = optimization_frameworks[framework_name]
        
        # Parse config if needed
        config_data = data.get("config", {})
        if isinstance(config_data, str):
            import json
            config_data = json.loads(config_data)
        
        # Create adapter
        if framework_name == "dspy":
            adapter = adapter_class()
        else:
            adapter = adapter_class(metric=None, config=config_data)
        
        # Update status to optimizing
        update_operation_status(opt_id, "optimizing")
        await router.emit("optimization:progress", build_progress_event(
            opt_id, "optimizing", "optimization", 
            framework=framework_name
        ))
        
        # Run optimization - pass opt_id for progress tracking
        kwargs = {k: v for k, v in data.items() if k not in ['target', 'signature', 'metric', 'framework', 'config']}
        result = await adapter.optimize(
            target=data.get("target"),
            signature=data.get("signature"),
            metric=data.get("metric"),
            optimization_id=opt_id,  # Pass opt_id for progress tracking
            **kwargs
        )
        
        # Complete operation
        complete_operation(opt_id, result)
        
        # Emit result event
        await router.emit("optimization:result", build_result_event(
            opt_id, result, "optimization"
        ))
        
    except Exception as e:
        logger.error(f"Optimization {opt_id} failed: {e}", exc_info=True)
        
        # Mark as failed
        fail_operation(opt_id, str(e), type(e).__name__)
        
        # Emit error event
        await router.emit("optimization:error", build_error_event(
            opt_id, str(e), "optimization",
            error_type=type(e).__name__
        ))


@event_handler("optimization:status")
async def handle_optimization_status(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get status of optimization operations with rich progress information."""
    
    from ksi_common.async_operations import get_operation_status, get_active_operations_summary
    
    # Check for specific optimization ID
    opt_id = raw_data.get("optimization_id")
    if opt_id:
        # Get basic status
        status = get_operation_status(opt_id)
        if not status:
            return error_response(f"Optimization {opt_id} not found", context)
        
        # Parameters for what to include
        include_scores = raw_data.get("include_scores", True)
        include_instructions = raw_data.get("include_instructions", False)  # Default false - could be large
        include_stats = raw_data.get("include_stats", True)
        include_activity = raw_data.get("include_activity", True)
        
        # Enhance with DSPy state if available
        if status.get("status") == "optimizing":
            framework_name = status.get("metadata", {}).get("framework")
            
            if framework_name == "dspy":
                # Get DSPy-specific progress
                dspy_progress = await get_dspy_optimization_progress(
                    opt_id,
                    include_scores=include_scores,
                    include_instructions=include_instructions,
                    include_stats=include_stats
                )
                status["progress"] = dspy_progress
            
            # Add LLM activity regardless of framework
            if include_activity:
                status["activity"] = await get_optimization_activity(opt_id, status["started_at"])
            
            # Try to get MLflow data if available
            mlflow_data = await get_mlflow_optimization_data(opt_id)
            if mlflow_data:
                status["mlflow"] = mlflow_data
        
        return event_response_builder(status, context)
    
    # Return summary of all optimizations
    summary = get_active_operations_summary(
        service_name="optimization",
        operation_type="optimization"
    )
    
    # Add MLflow tracking info
    mlflow_runs = await get_active_optimization_runs()
    
    response_data = {
        "active_optimizations": summary["total"],
        "by_status": summary.get("by_status", {}),
        "frameworks": {name: {"available": True} for name in optimization_frameworks.keys()}
    }
    
    # Add MLflow data if available
    if "error" not in mlflow_runs:
        response_data["mlflow"] = {
            "active_runs": mlflow_runs.get("active_runs", 0),
            "ui_url": get_mlflow_ui_url()
        }
    
    return event_response_builder(response_data, context)


@event_handler("optimization:cancel")
async def handle_cancel_optimization(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Cancel an active optimization."""
    
    from ksi_common.async_operations import cancel_operation
    
    opt_id = raw_data.get("optimization_id")
    if not opt_id:
        return error_response("optimization_id required", context)
    
    success = await cancel_operation(opt_id)
    if success:
        return event_response_builder({
            "optimization_id": opt_id,
            "status": "cancelled"
        }, context)
    else:
        return error_response(f"Optimization {opt_id} not found or already completed", context)


@event_handler("optimization:evaluate")
async def handle_evaluate(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate a prediction using specified metric."""
    
    metric_component = raw_data.get("metric")  # Metric component name
    data = raw_data.get("data", {})
    
    if not metric_component:
        return error_response("metric component required", context=context)
    
    # Load metric component to determine type
    from ksi_daemon.composition import composition_service
    router = get_router()
    
    metric_response = await router.route({
        "event": "composition:get_component",
        "data": {"name": metric_component, "type": "metric"}
    })
    
    if metric_response.get("status") != "success":
        return error_response(f"Failed to load metric component: {metric_component}", context=context)
    
    metric_info = metric_response.get("metadata", {})
    metric_type = metric_info.get("metric_type", "programmatic")
    
    # Route to appropriate framework
    if metric_type == "programmatic":
        framework = metric_info.get("framework", "dspy")
    elif metric_type == "llm_judge":
        framework = "judge"
    else:
        framework = raw_data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return error_response(f"Framework {framework} not available for metric type {metric_type}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    adapter = adapter_class()
    
    result = await adapter.evaluate(metric_component, metric_info, data, **raw_data)
    return event_response_builder(result, context=context)


@event_handler("optimization:bootstrap")
async def handle_bootstrap(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Bootstrap training examples using specified framework."""
    
    framework = raw_data.get("framework", "dspy")
    signature = raw_data.get("signature")  # Signature component name
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    adapter = adapter_class()
    
    if hasattr(adapter, 'bootstrap'):
        result = await adapter.bootstrap(signature=signature, **raw_data)
        return event_response_builder(result, context=context)
    
    return error_response(f"Framework {framework} does not support bootstrapping", context=context)


@event_handler("optimization:compare")
async def handle_compare(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compare multiple optimization techniques."""
    
    techniques = raw_data.get("techniques", ["dspy", "judge"])
    target = raw_data.get("target")
    metric = raw_data.get("metric")
    
    if not target:
        return error_response("target component required", context=context)
    
    results = {}
    
    for technique in techniques:
        if technique not in optimization_frameworks:
            results[technique] = {"error": f"Framework {technique} not available"}
            continue
        
        # Run optimization with each technique
        adapter_class = optimization_frameworks[technique]
        adapter = adapter_class()
        
        try:
            result = await adapter.optimize(
                target=target,
                metric=metric,
                **raw_data
            )
            results[technique] = result
        except Exception as e:
            logger.error(f"Optimization with {technique} failed: {e}")
            results[technique] = {"error": str(e)}
    
    # Compare results
    comparison = {
        "techniques": techniques,
        "results": results,
        "recommendation": _recommend_technique(results)
    }
    
    return event_response_builder(comparison, context=context)


@event_handler("optimization:format_examples")
async def handle_format_examples(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format training data for optimization frameworks."""
    
    framework = raw_data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    if hasattr(adapter_class, 'format_examples'):
        return await adapter_class.format_examples(raw_data, context)
    
    # Default formatting
    examples = raw_data.get("examples", [])
    return event_response_builder({
        "formatted_examples": examples,
        "count": len(examples),
        "format": framework
    }, context=context)


@event_handler("optimization:get_git_info")
async def handle_get_git_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get git-based optimization tracking information."""
    
    from .git_tracking.optimization_tracker import OptimizationTracker
    
    component_name = raw_data.get("component_name")
    list_experiments = raw_data.get("list_experiments", False)
    
    tracker = OptimizationTracker()
    
    if list_experiments and component_name:
        experiments = tracker.list_experiments(component_name)
        return event_response_builder({
            "component": component_name,
            "experiments": experiments
        }, context=context)
    
    # Get current status
    return event_response_builder({
        "git_enabled": tracker.is_git_enabled(),
        "repo_path": str(tracker.repo_path) if tracker.repo else None,
        "current_branch": tracker.get_current_branch() if tracker.repo else None
    }, context=context)


def _recommend_technique(results: Dict[str, Any]) -> str:
    """Recommend the best optimization technique based on results."""
    # Simple heuristic - can be made more sophisticated
    best_score = -1
    best_technique = None
    
    for technique, result in results.items():
        if "error" in result:
            continue
        
        score = result.get("optimized_score", result.get("improvement", 0))
        if score > best_score:
            best_score = score
            best_technique = technique
    
    return best_technique or "manual"


async def get_dspy_optimization_progress(
    opt_id: str,
    include_scores: bool = True,
    include_instructions: bool = False,
    include_stats: bool = True
) -> Dict[str, Any]:
    """Extract progress from active DSPy optimizer."""
    
    # Import the module-level function
    try:
        from .frameworks.dspy_events import get_active_optimizer
    except ImportError:
        return {"status": "framework_not_available"}
    
    # Get optimizer from module-level tracking
    optimizer = get_active_optimizer(opt_id)
    if not optimizer:
        return {"status": "optimizer_not_accessible"}
    
    progress = {}
    
    # Extract from optimizer's internal state
    optimizer_dict = optimizer.__dict__
    
    # Trial Progress - MIPROv2 tracks trials internally
    # Look for trial-related attributes
    total_calls = optimizer_dict.get("total_calls", 0)
    prompt_model_calls = optimizer_dict.get("prompt_model_total_calls", 0)
    
    # Estimate trials based on evaluation calls (heuristic)
    # In MIPROv2, each trial involves evaluations
    if hasattr(optimizer, 'num_trials'):
        num_trials = getattr(optimizer, 'num_trials', 12)
        # Rough estimate: trials completed based on total calls
        if total_calls > 0:
            # This is an approximation - actual trial count may vary
            trials_completed = min(total_calls // 10, num_trials)  # Assume ~10 calls per trial
        else:
            trials_completed = 0
            
        progress["trial_progress"] = {
            "completed": trials_completed,
            "total": num_trials,
            "percentage": int((trials_completed / num_trials) * 100) if num_trials > 0 else 0,
            "total_evaluation_calls": total_calls,
            "prompt_model_calls": prompt_model_calls
        }
    
    # Scores - Extract from score_data if available
    if include_scores:
        score_data = optimizer_dict.get("score_data", [])
        if score_data:
            # Extract scores from score_data list
            scores = [entry.get("score", 0) for entry in score_data if "score" in entry]
            if scores:
                progress["scores"] = {
                    "best": max(scores),
                    "current": scores[-1],
                    "history": scores[-5:] if len(scores) > 5 else scores,  # Last 5 scores
                    "evaluations": len(scores)
                }
    
    # Instructions (be careful with size)
    if include_instructions:
        # MIPROv2 doesn't directly expose current instructions during optimization
        # Would need to extract from trial_logs if available
        trial_logs = optimizer_dict.get("trial_logs", {})
        if trial_logs:
            # Get latest trial's instructions if available
            latest_trial = max(trial_logs.keys()) if trial_logs else None
            if latest_trial and "program" in trial_logs[latest_trial]:
                progress["instructions"] = {
                    "trial": latest_trial,
                    "note": "Full instruction extraction requires program introspection"
                }
    
    # Statistics
    if include_stats:
        progress["statistics"] = {
            "max_bootstrapped_demos": optimizer_dict.get("max_bootstrapped_demos", 0),
            "max_labeled_demos": optimizer_dict.get("max_labeled_demos", 0),
            "init_temperature": optimizer_dict.get("init_temperature", 0.7),
            "auto_mode": optimizer_dict.get("auto", "light"),
            "num_candidates": optimizer_dict.get("num_candidates", 10),
            "track_stats": optimizer_dict.get("track_stats", True),
            "optimization_stage": "running" if total_calls > 0 else "initializing"
        }
    
    return progress


async def get_optimization_activity(opt_id: str, started_at: str) -> Dict[str, Any]:
    """Get optimization activity based on trial progress."""
    import time
    from ksi_common.timestamps import parse_iso_timestamp
    
    # Try to get optimizer for real-time stats
    try:
        from .frameworks.dspy_events import get_active_optimizer
        optimizer = get_active_optimizer(opt_id)
        
        if optimizer:
            # Get current stats from optimizer
            total_calls = getattr(optimizer, "total_calls", 0)
            prompt_model_calls = getattr(optimizer, "prompt_model_total_calls", 0)
            
            # Calculate time since start
            if isinstance(started_at, str):
                dt = parse_iso_timestamp(started_at)
                start_timestamp = dt.timestamp()
            else:
                start_timestamp = started_at
            
            elapsed_time = time.time() - start_timestamp
            
            # Calculate rates
            calls_per_minute = (total_calls / elapsed_time * 60) if elapsed_time > 0 else 0
            
            return {
                "total_evaluation_calls": total_calls,
                "prompt_optimization_calls": prompt_model_calls,
                "elapsed_seconds": round(elapsed_time, 1),
                "calls_per_minute": round(calls_per_minute, 1),
                "status": "active" if calls_per_minute > 0.5 else "idle",
                "optimizer_active": True
            }
    except Exception as e:
        logger.debug(f"Could not get optimizer stats: {e}")
    
    # Fallback: no real-time stats available
    return {
        "status": "optimizer_stats_unavailable",
        "note": "Real-time statistics require active optimizer tracking"
    }


async def get_mlflow_optimization_data(opt_id: str) -> Optional[Dict[str, Any]]:
    """Get MLflow tracking data for an optimization."""
    try:
        # Search for MLflow run with matching optimization ID
        # This assumes we tag MLflow runs with the KSI optimization ID
        import mlflow
        
        runs = mlflow.search_runs(
            filter_string=f"tags.ksi_optimization_id = '{opt_id}'",
            max_results=1
        )
        
        if not runs.empty:
            run_id = runs.iloc[0]["run_id"]
            return await get_optimization_progress(run_id)
        
        return None
    except Exception as e:
        logger.debug(f"Could not get MLflow data for {opt_id}: {e}")
        return None


async def _ensure_mlflow_initialized():
    """Ensure MLflow is initialized before optimization."""
    global _mlflow_initialized
    
    if not _mlflow_initialized:
        try:
            tracking_uri = await start_mlflow_server()
            logger.info(f"MLflow tracking server started at {tracking_uri}")
            _mlflow_initialized = True
        except Exception as e:
            logger.warning(f"Could not start MLflow server: {e}")
            # Continue without MLflow - it's optional


# Initialize frameworks on module load
def initialize_frameworks():
    """Initialize and register optimization frameworks."""
    try:
        # Register DSPy framework if available
        from .frameworks.dspy_events import DSPyFramework
        register_framework("dspy", DSPyFramework)
        logger.info("DSPy framework registered")
    except ImportError:
        logger.info("DSPy framework not available")
    
    try:
        # Register LLM Judge framework if available
        from .frameworks.judge_events import JudgeFramework
        register_framework("judge", JudgeFramework)
        logger.info("Judge framework registered")
    except ImportError:
        logger.info("Judge framework not available")
    
    try:
        # Register hybrid framework if available
        from .frameworks.hybrid_events import HybridFramework
        register_framework("hybrid", HybridFramework)
        logger.info("Hybrid framework registered")
    except ImportError:
        logger.info("Hybrid framework not available")


async def initialize_optimization_service():
    """Initialize optimization service with MLflow."""
    # Initialize frameworks
    initialize_frameworks()
    
    # Start MLflow server
    try:
        tracking_uri = await start_mlflow_server()
        logger.info(f"MLflow tracking server started at {tracking_uri}")
    except Exception as e:
        logger.warning(f"Could not start MLflow server: {e}")


# Initialize on import (sync part)
initialize_frameworks()

# Note: Async initialization (MLflow server) must be called from event system startup


@event_handler("optimization:initialize")
async def handle_optimization_initialize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize optimization service including MLflow."""
    try:
        await initialize_optimization_service()
        return event_response_builder({
            "status": "initialized",
            "mlflow_ui": get_mlflow_ui_url()
        })
    except Exception as e:
        logger.error(f"Failed to initialize optimization service: {e}")
        return error_response(str(e))


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up optimization resources on shutdown."""
    from ksi_common.async_operations import shutdown_thread_pool, cancel_operation
    
    logger.info("Optimization service shutting down")
    
    # Cancel all active optimizations
    from ksi_common.async_operations import active_operations
    
    for opt_id, op_data in list(active_operations.items()):
        if (op_data.get("service") == "optimization" and 
            op_data.get("status") in ["queued", "initializing", "optimizing"]):
            logger.info(f"Cancelling active optimization {opt_id}")
            await cancel_operation(opt_id)
    
    # Clean up framework resources
    dspy_framework = optimization_frameworks.get("dspy")
    if dspy_framework and hasattr(dspy_framework, "cleanup"):
        await dspy_framework.cleanup()
    
    # Shutdown thread pool
    shutdown_thread_pool()
    
    # Stop MLflow server
    await stop_mlflow_server()
    
    logger.info("Optimization service shutdown complete")