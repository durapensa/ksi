"""KSI Optimization Service - Framework-agnostic optimization integration."""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("optimization_service")

# Framework registry
optimization_frameworks: Dict[str, Any] = {}


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
    adapter = adapter_class()
    
    # Run optimization
    result = await adapter.optimize(
        target=target,
        signature=signature,
        metric=metric,
        **raw_data
    )
    
    return event_response_builder(result, context=context)


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


# Initialize on import
initialize_frameworks()