"""KSI Optimization Service - Framework-agnostic optimization integration."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.async_operations import (
    start_operation, update_operation_status, complete_operation,
    fail_operation, create_background_task, build_progress_event,
    build_result_event, build_error_event
)
from ksi_common.process_utils import get_process_manager, ProcessExecutionError
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


async def _capture_optimization_state(opt_id: str, state: str, data: Dict[str, Any], context: Optional[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None):
    """Capture optimization state snapshot for introspection."""
    try:
        from ksi_daemon.core.context_manager import get_context_manager
        cm = get_context_manager()
        
        # Create a context for this optimization state
        optimization_context = await cm.create_context(
            event_id=f"optimization_state_{opt_id}_{state}_{int(timestamp_utc().timestamp())}",
            timestamp=timestamp_utc().timestamp(),
            optimization_id=opt_id,
            state=state
        )
        
        # Serialize optimization state
        optimization_snapshot = {
            "optimization_id": opt_id,
            "state": state,
            "framework": data.get("framework", "dspy"),
            "target": data.get("target"),
            "signature": data.get("signature"),
            "metric": data.get("metric"),
            "config": data.get("config", {}),
            "timestamp": timestamp_utc(),
            "metadata": metadata or {}
        }
        
        # Store the optimization snapshot
        optimization_event = {
            "event_id": optimization_context["_event_id"],
            "event_name": "optimization:state_snapshot",
            "timestamp": optimization_context["_event_timestamp"],
            "data": optimization_snapshot
        }
        
        context_ref = await cm.store_event_with_context(optimization_event)
        logger.debug(f"Captured optimization state {state} for {opt_id} as context {context_ref}")
        
    except Exception as e:
        logger.warning(f"Failed to capture optimization state for {opt_id}: {e}")


@event_handler("optimization:get_framework_info")
async def handle_get_framework_info(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about available optimization frameworks."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    framework = data.get("framework", "all")
    
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
async def handle_validate_setup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate that optimization setup is ready."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    framework = data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return event_response_builder({
            "valid": False,
            "reason": f"Framework {framework} not registered"
        }, context=context)
    
    adapter_class = optimization_frameworks[framework]
    if hasattr(adapter_class, 'validate_setup'):
        return await adapter_class.validate_setup(data, context)
    
    return event_response_builder({"valid": True}, context=context)


@event_handler("optimization:optimize")
async def handle_optimize(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run optimization on a component using specified framework."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    # Ensure MLflow is initialized
    await _ensure_mlflow_initialized()
    
    framework = data.get("framework", "dspy")
    target = data.get("target")  # Component to optimize
    signature = data.get("signature")  # Signature component name
    metric = data.get("metric")  # Metric component name
    
    if not target:
        return error_response("target component required", context=context)
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    # Load framework adapter
    adapter_class = optimization_frameworks[framework]
    
    # Parse config if it's a string
    config_data = data.get("config", {})
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
    kwargs = {k: v for k, v in data.items() if k not in ['target', 'signature', 'metric', 'framework', 'config']}
    result = await adapter.optimize(
        target=target,
        signature=signature,
        metric=metric,
        **kwargs
    )
    
    return event_response_builder(result, context=context)


@event_handler("optimization:async")
async def handle_async_optimization(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start async optimization with background processing."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    # Ensure MLflow is initialized
    await _ensure_mlflow_initialized()
    
    # Extract parameters
    framework = data.get("framework", "dspy")
    target = data.get("target")
    
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
            "signature": data.get("signature"),
            "metric": data.get("metric")
        }
    )
    
    # Create background task for subprocess-based optimization
    task = create_background_task(
        opt_id,
        run_optimization_subprocess(opt_id, data, context)
    )
    
    return event_response_builder({
        "optimization_id": opt_id,
        "status": "started",
        "framework": framework,
        "component": target
    }, context)


async def run_optimization_subprocess(opt_id: str, data: Dict[str, Any], context: Optional[Dict[str, Any]]):
    """Run optimization in subprocess with proper cancellation support."""
    router = get_router()
    process_manager = get_process_manager()
    
    try:
        # Update status to initializing
        update_operation_status(opt_id, "initializing")
        
        # Capture optimization state for introspection
        await _capture_optimization_state(opt_id, "initializing", data, context)
        
        # Emit progress event
        await router.emit("optimization:progress", build_progress_event(
            opt_id, "initializing", "optimization"
        ))
        
        # Load component content before starting subprocess
        target = data.get("target")
        
        # Get component content from composition service
        component_response = await router.emit_first("composition:get_component", {
            "name": target
        })
        
        if component_response.get("status") != "success":
            raise ValueError(f"Failed to load component {target}: {component_response}")
        
        component_content = component_response.get("content", "")
        
        # Prepare subprocess configuration
        framework_name = data.get("framework", "dspy")
        config_data = data.get("config", {})
        
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        
        # Create temporary files for component content and result
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(component_content)
            component_file = f.name
        
        # Create result file path
        with tempfile.NamedTemporaryFile(mode='w', suffix='_result.json', delete=False) as f:
            result_file = f.name
        
        # Build command for subprocess
        cmd = [
            "python", 
            str(Path(__file__).parent.parent.parent / "ksi_optimize_component.py"),
            "--opt-id", opt_id,
            "--component", target,
            "--component-file", component_file,
            "--result-file", result_file,
            "--config", json.dumps(config_data)
        ]
        
        # Add optional parameters
        if data.get("signature"):
            cmd.extend(["--signature", data.get("signature")])
        if data.get("metric"):
            cmd.extend(["--metric", data.get("metric")])
        
        # Update status to optimizing
        update_operation_status(opt_id, "optimizing")
        
        # Capture optimization state for introspection
        await _capture_optimization_state(opt_id, "optimizing", data, context, {"component_content": component_content})
        
        await router.emit("optimization:progress", build_progress_event(
            opt_id, "optimizing", "optimization", 
            framework=framework_name,
            subprocess=True
        ))
        
        logger.info(f"Starting optimization subprocess for {opt_id}")
        
        # Run optimization in subprocess
        returncode, stdout, stderr = await process_manager.run_subprocess(
            cmd=cmd,
            process_id=opt_id,
            working_dir=Path(__file__).parent.parent.parent,  # KSI root
            timeout=1800,  # 30 minutes max
            progress_timeout=600  # 10 minutes without output
        )
        
        logger.info(f"Optimization subprocess {opt_id} completed with code {returncode}")
        
        if returncode == 0:
            # Success - read specific result file and update component
            try:
                # Read result from the known file path
                with open(result_file, 'r') as f:
                    result_data = json.load(f)
                
                # Update component with optimized content
                update_response = await router.emit_first("composition:update_component", {
                    "name": result_data["component_name"],
                    "content": result_data["optimized_content"],
                    "metadata": result_data["metadata"]
                })
                
                if update_response.get("status") == "success":
                    logger.info(f"Updated component {result_data['component_name']} with optimized content")
                    
                    result = {
                        "status": "completed", 
                        "subprocess_completed": True,
                        "component_updated": True,
                        "component_name": result_data["component_name"],
                        "improvement": result_data.get("improvement", 0)
                    }
                    complete_operation(opt_id, result)
                    
                    # Capture optimization completion state for introspection
                    await _capture_optimization_state(opt_id, "completed", data, context, {"result": result, "improvement": result_data.get("improvement", 0)})
                    
                    await router.emit("optimization:result", build_result_event(
                        opt_id, result, "optimization"
                    ))
                else:
                    raise ValueError(f"Failed to update component: {update_response}")
                    
            except Exception as e:
                error_msg = f"Failed to process subprocess result: {e}"
                logger.error(error_msg)
                fail_operation(opt_id, error_msg, "ResultProcessingError")
                
                # Capture optimization error state for introspection
                await _capture_optimization_state(opt_id, "failed", data, context, {"error": error_msg, "error_type": "ResultProcessingError"})
                
                await router.emit("optimization:error", build_error_event(
                    opt_id, error_msg, "optimization",
                    error_type="ResultProcessingError"
                ))
        
        # Clean up temporary files
        try:
            Path(component_file).unlink()
        except Exception as e:
            logger.warning(f"Could not clean up component file {component_file}: {e}")
        
        try:
            Path(result_file).unlink()
        except Exception as e:
            logger.warning(f"Could not clean up result file {result_file}: {e}")
        else:
            # Subprocess failed
            error_msg = f"Optimization subprocess failed with code {returncode}"
            if stderr:
                error_msg += f": {stderr[:500]}"
            
            fail_operation(opt_id, error_msg, "SubprocessError")
            
            # Capture optimization error state for introspection
            await _capture_optimization_state(opt_id, "failed", data, context, {"error": error_msg, "error_type": "SubprocessError", "returncode": returncode})
            
            await router.emit("optimization:error", build_error_event(
                opt_id, error_msg, "optimization",
                error_type="SubprocessError",
                returncode=returncode,
                stderr=stderr[:1000] if stderr else None
            ))
        
    except ProcessExecutionError as e:
        logger.error(f"Optimization {opt_id} subprocess failed: {e}")
        
        fail_operation(opt_id, str(e), "ProcessExecutionError")
        
        await router.emit("optimization:error", build_error_event(
            opt_id, str(e), "optimization",
            error_type="ProcessExecutionError",
            returncode=e.returncode,
            stderr=e.stderr[:1000] if e.stderr else None
        ))
        
    except asyncio.CancelledError:
        logger.info(f"Optimization {opt_id} was cancelled")
        
        # Update status
        update_operation_status(opt_id, "cancelled")
        
        # Emit cancellation event
        await router.emit("optimization:cancelled", {
            "optimization_id": opt_id,
            "timestamp": timestamp_utc()
        })
        
        raise
        
    except Exception as e:
        logger.error(f"Optimization {opt_id} failed: {e}", exc_info=True)
        
        fail_operation(opt_id, str(e), type(e).__name__)
        
        await router.emit("optimization:error", build_error_event(
            opt_id, str(e), "optimization",
            error_type=type(e).__name__
        ))


@event_handler("optimization:list")
async def handle_optimization_list(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get list of active optimizations."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    from ksi_common.async_operations import get_active_operations_summary
    
    try:
        # Get active optimizations using the async_operations utilities
        summary = get_active_operations_summary(
            service_name="optimization",
            operation_type="optimization"
        )
        
        active_optimizations = []
        
        # Extract active optimizations from the summary
        if summary.get("active_operations"):
            for opt_id, opt_data in summary["active_operations"].items():
                if opt_data.get("status") in ["pending", "optimizing"]:
                    optimization_info = {
                        "optimization_id": opt_id,
                        "status": opt_data.get("status"),
                        "started_at": opt_data.get("started_at"),
                        "component": opt_data.get("metadata", {}).get("component"),
                        "framework": opt_data.get("metadata", {}).get("framework")
                    }
                    active_optimizations.append(optimization_info)
        
        return event_response_builder({
            "optimizations": active_optimizations,
            "total_active": len(active_optimizations)
        }, context=context)
        
    except Exception as e:
        logger.error(f"Error getting optimization list: {e}")
        return error_response(f"Failed to get optimization list: {e}", context)


@event_handler("optimization:status")
async def handle_optimization_status(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get status of optimization operations with rich progress information."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    logger.info(f"Handling optimization:status request: {data}")
    from ksi_common.async_operations import get_operation_status, get_active_operations_summary
    
    # Check for specific optimization ID
    opt_id = data.get("optimization_id")
    if opt_id:
        # Get basic status
        status = get_operation_status(opt_id)
        if not status:
            return error_response(f"Optimization {opt_id} not found", context)
        
        # Parameters for what to include
        include_scores = data.get("include_scores", True)
        include_instructions = data.get("include_instructions", False)  # Default false - could be large
        include_stats = data.get("include_stats", True)
        include_activity = data.get("include_activity", True)
        
        # Get MLflow data for progress tracking (replaces DSPy internal state)
        logger.info(f"Checking status for MLflow data: {status.get('status')}")
        if status.get("status") in ["optimizing", "completed", "failed"]:
            logger.info(f"Status matches, calling get_mlflow_optimization_data for {opt_id}")
            mlflow_data = await get_mlflow_optimization_data(opt_id)
            if mlflow_data:
                status["mlflow"] = mlflow_data
                
                # Extract trial progress from MLflow if available
                if "metrics" in mlflow_data:
                    metrics = mlflow_data["metrics"]
                    status["progress"] = {
                        "trial_progress": {
                            "current_score": metrics.get("score"),
                            "best_score": metrics.get("best_score"),
                            "trials_completed": int(metrics.get("trial", 0))
                        }
                    }
                
                # Extract activity from MLflow history
                if include_activity and "metric_history" in mlflow_data:
                    history = mlflow_data["metric_history"]
                    trial_history = history.get("trial", [])
                    
                    if trial_history:
                        latest_time = trial_history[-1].get("timestamp", 0)
                        start_time = trial_history[0].get("timestamp", 0)
                        elapsed = (latest_time - start_time) / 1000  # Convert to seconds
                        
                        status["activity"] = {
                            "total_trials": len(trial_history),
                            "elapsed_seconds": round(elapsed, 1),
                            "trials_per_minute": round(len(trial_history) / (elapsed / 60), 1) if elapsed > 0 else 0,
                            "status": "active" if latest_time > (time.time() * 1000 - 30000) else "idle"  # Active if trial in last 30s
                        }
                    else:
                        # Fallback to subprocess-based activity
                        process_manager = get_process_manager()
                        active_processes = process_manager.get_active_processes()
                        
                        if opt_id in active_processes:
                            process_info = active_processes[opt_id]
                            status["activity"] = {
                                "subprocess_running": process_info["running"],
                                "subprocess_pid": process_info["pid"],
                                "status": "active" if process_info["running"] else "idle"
                            }
        
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
        mlflow_data = {
            "active_runs": mlflow_runs.get("active_runs", 0),
            "ui_url": get_mlflow_ui_url()
        }
        
        # Include run details if any
        if mlflow_runs.get("runs"):
            mlflow_data["runs"] = []
            for run in mlflow_runs["runs"]:
                run_summary = {
                    "ksi_optimization_id": run.get("ksi_optimization_id"),
                    "run_id": run.get("run_id"),
                    "status": run.get("status"),
                    "start_time": run.get("start_time")
                }
                
                # Add key metrics if available
                metrics = run.get("metrics", {})
                if metrics:
                    # Look for common optimization metrics
                    key_metrics = {}
                    for metric_name in ["score", "best_score", "trial", "iteration"]:
                        if metric_name in metrics:
                            key_metrics[metric_name] = metrics[metric_name]
                    if key_metrics:
                        run_summary["metrics"] = key_metrics
                
                mlflow_data["runs"].append(run_summary)
        
        response_data["mlflow"] = mlflow_data
    
    return event_response_builder(response_data, context)


@event_handler("optimization:cancel")
async def handle_cancel_optimization(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Cancel an active optimization."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    from ksi_common.async_operations import cancel_operation
    
    opt_id = data.get("optimization_id")
    if not opt_id:
        return error_response("optimization_id required", context)
    
    # Cancel the async operation (background task)
    async_cancelled = await cancel_operation(opt_id)
    
    # Also cancel the subprocess if it's running
    process_manager = get_process_manager()
    subprocess_cancelled = await process_manager.cancel_process(opt_id)
    
    if async_cancelled or subprocess_cancelled:
        logger.info(f"Cancelled optimization {opt_id} (async: {async_cancelled}, subprocess: {subprocess_cancelled})")
        return event_response_builder({
            "optimization_id": opt_id,
            "status": "cancelled",
            "async_cancelled": async_cancelled,
            "subprocess_cancelled": subprocess_cancelled
        }, context)
    else:
        return error_response(f"Optimization {opt_id} not found or already completed", context)


@event_handler("optimization:evaluate")
async def handle_evaluate(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate a prediction using specified metric."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    metric_component = data.get("metric")  # Metric component name
    eval_data = data.get("data", {})
    
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
        framework = data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return error_response(f"Framework {framework} not available for metric type {metric_type}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    adapter = adapter_class()
    
    result = await adapter.evaluate(metric_component, metric_info, eval_data, **data)
    return event_response_builder(result, context=context)


@event_handler("optimization:bootstrap")
async def handle_bootstrap(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Bootstrap training examples using specified framework."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    framework = data.get("framework", "dspy")
    signature = data.get("signature")  # Signature component name
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    adapter = adapter_class()
    
    if hasattr(adapter, 'bootstrap'):
        result = await adapter.bootstrap(signature=signature, **data)
        return event_response_builder(result, context=context)
    
    return error_response(f"Framework {framework} does not support bootstrapping", context=context)


@event_handler("optimization:compare")
async def handle_compare(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compare multiple optimization techniques."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    techniques = data.get("techniques", ["dspy", "judge"])
    target = data.get("target")
    metric = data.get("metric")
    
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
                **data
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
async def handle_format_examples(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format training data for optimization frameworks."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    framework = data.get("framework", "dspy")
    
    if framework not in optimization_frameworks:
        return error_response(f"Unknown framework: {framework}", context=context)
    
    adapter_class = optimization_frameworks[framework]
    if hasattr(adapter_class, 'format_examples'):
        return await adapter_class.format_examples(data, context)
    
    # Default formatting
    examples = data.get("examples", [])
    return event_response_builder({
        "formatted_examples": examples,
        "count": len(examples),
        "format": framework
    }, context=context)


@event_handler("optimization:get_git_info")
async def handle_get_git_info(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get git-based optimization tracking information."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    from .git_tracking.optimization_tracker import OptimizationTracker
    
    component_name = data.get("component_name")
    list_experiments = data.get("list_experiments", False)
    
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


# Removed get_dspy_optimization_progress - now using MLflow data instead


# Removed get_optimization_activity - now using MLflow data and subprocess info


async def get_mlflow_optimization_data(opt_id: str) -> Optional[Dict[str, Any]]:
    """Get MLflow tracking data for an optimization."""
    logger.info(f"Fetching MLflow data for optimization {opt_id}")
    try:
        # Search for MLflow run with matching optimization ID
        # This assumes we tag MLflow runs with the KSI optimization ID
        import mlflow
        
        # Set tracking URI to KSI's MLflow server
        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        
        runs = mlflow.search_runs(
            experiment_names=["ksi_optimizations"],
            filter_string=f"tags.ksi_optimization_id = '{opt_id}'",
            max_results=1
        )
        
        if not runs.empty:
            run_id = runs.iloc[0]["run_id"]
            return await get_optimization_progress(run_id)
        
        return None
    except Exception as e:
        logger.info(f"Could not get MLflow data for {opt_id}: {e}")
        return None


time = __import__('time')  # Import time module for activity calculations


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
    from ksi_common.async_operations import cancel_operation, active_operations
    
    logger.info("Optimization service shutting down")
    
    # Cancel all active optimization subprocesses
    process_manager = get_process_manager()
    
    for opt_id, op_data in list(active_operations.items()):
        if (op_data.get("service") == "optimization" and 
            op_data.get("status") in ["queued", "initializing", "optimizing"]):
            logger.info(f"Cancelling active optimization subprocess {opt_id}")
            # Cancel the async operation tracking
            await cancel_operation(opt_id)
            # Cancel the actual subprocess
            await process_manager.cancel_process(opt_id)
    
    # Clean up all remaining processes
    await process_manager.cleanup_all_processes()
    
    # Stop MLflow server
    await stop_mlflow_server()
    
    logger.info("Optimization service shutdown complete - all subprocesses terminated")


@event_handler("optimization:introspect")
async def handle_optimization_introspection(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Provide deep introspection into optimization runs using context history."""
    
    opt_id = data.get("optimization_id")
    if not opt_id:
        return error_response("optimization_id required", context=context)
    
    try:
        from ksi_daemon.core.context_manager import get_context_manager
        cm = get_context_manager()
        
        # Get current optimization status from async operations
        from ksi_common.async_operations import get_active_operations_summary
        summary = get_active_operations_summary(
            service_name="optimization",
            operation_type="optimization"
        )
        
        optimization_data = summary.get("active_operations", {}).get(opt_id) or \
                          summary.get("completed_operations", {}).get(opt_id) or \
                          summary.get("failed_operations", {}).get(opt_id)
        
        if not optimization_data:
            return error_response(f"Optimization {opt_id} not found", context=context)
        
        # Enhanced introspection data
        introspection_result = {
            "optimization_id": opt_id,
            "current_status": optimization_data.get("status"),
            "started_at": optimization_data.get("started_at"),
            "completed_at": optimization_data.get("completed_at"),
            "duration": optimization_data.get("duration"),
            "metadata": optimization_data.get("metadata", {}),
            "framework": optimization_data.get("metadata", {}).get("framework"),
            "target_component": optimization_data.get("metadata", {}).get("component"),
            "context_snapshots": []  # Will be populated when context query is implemented
        }
        
        # Add error information if available
        if optimization_data.get("status") == "failed":
            introspection_result["error"] = optimization_data.get("error")
            introspection_result["error_type"] = optimization_data.get("error_type")
        
        # Add result information if completed
        if optimization_data.get("status") == "completed":
            introspection_result["result"] = optimization_data.get("result")
        
        return event_response_builder(introspection_result, context=context)
        
    except Exception as e:
        logger.error(f"Error during optimization introspection: {e}")
        return error_response(f"Introspection failed: {str(e)}", context=context)


@event_handler("optimization:analyze_performance") 
async def handle_optimization_analysis(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze optimization performance patterns using context data."""
    
    framework = data.get("framework")
    component_pattern = data.get("component_pattern")  # Optional pattern to filter components
    
    try:
        from ksi_common.async_operations import get_active_operations_summary
        summary = get_active_operations_summary(
            service_name="optimization",
            operation_type="optimization"
        )
        
        # Aggregate performance data
        performance_analysis = {
            "framework_performance": {},
            "component_performance": {},
            "success_rate": 0,
            "average_duration": 0,
            "improvement_distribution": []
        }
        
        all_ops = {}
        all_ops.update(summary.get("completed_operations", {}))
        all_ops.update(summary.get("failed_operations", {}))
        
        completed_count = 0
        total_duration = 0
        framework_stats = {}
        component_stats = {}
        
        for opt_id, opt_data in all_ops.items():
            opt_framework = opt_data.get("metadata", {}).get("framework")
            opt_component = opt_data.get("metadata", {}).get("component")
            
            # Filter by framework if specified
            if framework and opt_framework != framework:
                continue
            
            # Filter by component pattern if specified
            if component_pattern and opt_component and component_pattern not in opt_component:
                continue
            
            # Update framework stats
            if opt_framework not in framework_stats:
                framework_stats[opt_framework] = {"total": 0, "completed": 0, "failed": 0, "avg_duration": 0}
            
            framework_stats[opt_framework]["total"] += 1
            if opt_data.get("status") == "completed":
                framework_stats[opt_framework]["completed"] += 1
                completed_count += 1
                
                if opt_data.get("duration"):
                    total_duration += opt_data["duration"]
                    framework_stats[opt_framework]["avg_duration"] += opt_data["duration"]
            else:
                framework_stats[opt_framework]["failed"] += 1
            
            # Update component stats
            if opt_component:
                if opt_component not in component_stats:
                    component_stats[opt_component] = {"total": 0, "completed": 0, "failed": 0}
                
                component_stats[opt_component]["total"] += 1
                if opt_data.get("status") == "completed":
                    component_stats[opt_component]["completed"] += 1
                else:
                    component_stats[opt_component]["failed"] += 1
        
        # Calculate averages
        for fw_name, fw_stats in framework_stats.items():
            if fw_stats["completed"] > 0:
                fw_stats["avg_duration"] = fw_stats["avg_duration"] / fw_stats["completed"]
                fw_stats["success_rate"] = fw_stats["completed"] / fw_stats["total"]
        
        performance_analysis["framework_performance"] = framework_stats
        performance_analysis["component_performance"] = component_stats
        performance_analysis["success_rate"] = completed_count / len(all_ops) if all_ops else 0
        performance_analysis["average_duration"] = total_duration / completed_count if completed_count > 0 else 0
        performance_analysis["total_optimizations"] = len(all_ops)
        
        return event_response_builder(performance_analysis, context=context)
        
    except Exception as e:
        logger.error(f"Error during optimization analysis: {e}")
        return error_response(f"Analysis failed: {str(e)}", context=context)