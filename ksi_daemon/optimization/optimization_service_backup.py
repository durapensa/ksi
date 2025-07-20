"""KSI Optimization Service - DSPy integration for systematic optimization."""

import logging
import json
from typing import Dict, Any, Optional, List, Union, Callable
import dspy
from pathlib import Path

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Import DSPy adapters
from .frameworks.dspy_adapter import DSPyMIPROAdapter
from .frameworks.ksi_lm_adapter import KSIAgentLanguageModel

logger = get_bound_logger("optimization_service")

# DSPy models configured on startup
dspy_models: Optional[Dict[str, Any]] = None

# Metric registry for custom metrics
metric_registry: Dict[str, Callable] = {
    # Built-in DSPy metrics
    "exact_match": dspy.metrics.answer_exact_match,
    "f1": lambda ex, pred, trace=None: dspy.dsp.utils.F1(pred.answer if hasattr(pred, 'answer') else str(pred), ex.answer),
    "passage_match": dspy.metrics.answer_passage_match,
}


@event_handler("optimization:get_framework_info")
async def handle_get_framework_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about available optimization frameworks."""
    
    framework = raw_data.get("framework", "all")
    
    frameworks_info = {
        "dspy": {
            "available": dspy_models is not None,
            "description": "DSPy framework for programming—not prompting—language models",
            "version": dspy.__version__ if hasattr(dspy, '__version__') else "unknown",
            "capabilities": {
                "signatures": ["InputField", "OutputField", "typed fields"],
                "predictors": ["Predict", "ChainOfThought", "ReAct", "ProgramOfThought", "Refine"],
                "optimizers": ["MIPROv2", "BootstrapFewShot", "COPRO", "BetterTogether"],
                "retrieval": ["25+ vector stores", "hybrid search", "metadata filtering"],
                "evaluation": ["metrics", "parallel eval", "HTML reports"]
            },
            "configured_models": {
                "prompt_model": config.optimization_prompt_model,
                "task_model": config.optimization_task_model
            } if dspy_models else None
        }
    }
    
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
    
    if framework == "dspy":
        if dspy_models is None:
            return event_response_builder({
                "valid": False,
                "reason": "DSPy models not configured",
                "required_config": [
                    "optimization_prompt_model",
                    "optimization_task_model"
                ]
            }, context=context)
        
        # Test model availability
        try:
            test_pred = dspy.Predict("question -> answer")
            test_result = test_pred(question="test")
            return event_response_builder({
                "valid": True,
                "models": {
                    "prompt_model": str(dspy_models.get("prompt_model", "none")),
                    "task_model": str(dspy_models.get("task_model", "none"))
                }
            }, context=context)
        except Exception as e:
            return event_response_builder({
                "valid": False,
                "reason": f"Model test failed: {str(e)}"
            }, context=context)
    
    return error_response(f"Unknown framework: {framework}", context=context)


@event_handler("optimization:format_examples")
async def handle_format_examples(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format training data for optimization frameworks."""
    
    examples = raw_data.get("examples", [])
    format_type = raw_data.get("format", "dspy")
    signature = raw_data.get("signature")  # Optional signature spec
    
    if format_type == "dspy":
        formatted_examples = []
        
        for ex in examples:
            # Create DSPy Example with all fields
            dspy_ex = dspy.Example(**ex)
            
            # If signature provided, mark inputs/outputs
            if signature:
                input_fields = signature.get("inputs", [])
                output_fields = signature.get("outputs", [])
                
                # Mark fields
                dspy_ex = dspy_ex.with_inputs(*input_fields)
                if output_fields:
                    # Only mark outputs if they exist in the example
                    existing_outputs = [f for f in output_fields if f in ex]
                    if existing_outputs:
                        dspy_ex = dspy_ex.with_outputs(*existing_outputs)
            
            formatted_examples.append(dspy_ex.toDict())
        
        return event_response_builder({
            "formatted_examples": formatted_examples,
            "count": len(formatted_examples),
            "format": "dspy"
        }, context=context)
    
    return error_response(f"Unknown format: {format_type}", context=context)


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


# ============= NEW DSPy Core Events =============

@event_handler("optimization:optimize_component")
async def handle_optimize_component(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run DSPy optimization on a KSI component."""
    
    component_name = raw_data.get("component_name")
    component_content = raw_data.get("component_content")
    trainset = raw_data.get("trainset", [])
    valset = raw_data.get("valset", [])
    metric_name = raw_data.get("metric", "exact_match")
    optimizer_type = raw_data.get("optimizer", "mipro")
    config_overrides = raw_data.get("config", {})
    
    if not component_name or not component_content:
        return error_response("component_name and component_content required", context=context)
    
    # Get metric function
    if metric_name in metric_registry:
        metric_fn = metric_registry[metric_name]
    else:
        return error_response(f"Unknown metric: {metric_name}", context=context)
    
    # Create optimizer based on type
    if optimizer_type == "mipro":
        # Merge configs
        optimizer_config = {
            "auto": "medium",
            "num_candidates": 10,
            "max_bootstrapped_demos": 4,
            **config_overrides
        }
        
        adapter = DSPyMIPROAdapter(
            metric=metric_fn,
            prompt_model=dspy_models.get("prompt_model"),
            task_model=dspy_models.get("task_model"),
            config=optimizer_config
        )
        
        # Run optimization
        result = await adapter.optimize_component(
            component_name=component_name,
            component_content=component_content,
            trainset=trainset,
            valset=valset
        )
        
        return event_response_builder({
            "status": "success",
            "optimization_result": result
        }, context=context)
    
    return error_response(f"Unknown optimizer: {optimizer_type}", context=context)


@event_handler("optimization:run_dspy_program")
async def handle_run_dspy_program(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a DSPy program with given inputs."""
    
    program_type = raw_data.get("program_type", "predict")
    signature = raw_data.get("signature")
    inputs = raw_data.get("inputs", {})
    demos = raw_data.get("demos", [])
    
    if not signature:
        return error_response("signature required", context=context)
    
    try:
        # Create program based on type
        if program_type == "predict":
            program = dspy.Predict(signature)
        elif program_type == "chain_of_thought":
            program = dspy.ChainOfThought(signature)
        elif program_type == "program_of_thought":
            program = dspy.ProgramOfThought(signature)
        elif program_type == "react":
            program = dspy.ReAct(signature)
        elif program_type == "refine":
            program = dspy.Refine(signature)
        else:
            return error_response(f"Unknown program type: {program_type}", context=context)
        
        # Add demos if provided
        if demos:
            for demo in demos:
                program.demos.append(dspy.Example(**demo))
        
        # Execute program
        result = program(**inputs)
        
        # Convert result to dict
        if hasattr(result, 'toDict'):
            result_dict = result.toDict()
        else:
            result_dict = dict(result)
        
        return event_response_builder({
            "status": "success",
            "result": result_dict,
            "completions": result.completions if hasattr(result, 'completions') else None
        }, context=context)
        
    except Exception as e:
        logger.error(f"DSPy program execution failed: {e}")
        return error_response(str(e), context=context)


@event_handler("optimization:evaluate_with_metric")
async def handle_evaluate_with_metric(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate a prediction using a DSPy metric."""
    
    metric_name = raw_data.get("metric", "exact_match")
    example = raw_data.get("example", {})
    prediction = raw_data.get("prediction", {})
    
    # Get metric function
    if metric_name not in metric_registry:
        return error_response(f"Unknown metric: {metric_name}. Available: {list(metric_registry.keys())}", context=context)
    
    metric_fn = metric_registry[metric_name]
    
    try:
        # Create DSPy Example and Prediction objects
        dspy_example = dspy.Example(**example)
        dspy_prediction = dspy.Prediction(**prediction)
        
        # Run metric
        score = metric_fn(dspy_example, dspy_prediction)
        
        return event_response_builder({
            "status": "success",
            "metric": metric_name,
            "score": float(score) if isinstance(score, bool) else score,
            "example": example,
            "prediction": prediction
        }, context=context)
        
    except Exception as e:
        logger.error(f"Metric evaluation failed: {e}")
        return error_response(str(e), context=context)


@event_handler("optimization:bootstrap_examples")
async def handle_bootstrap_examples(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Bootstrap training examples using DSPy's bootstrapping."""
    
    program_type = raw_data.get("program_type", "predict")
    signature = raw_data.get("signature")
    unlabeled_inputs = raw_data.get("unlabeled_inputs", [])
    metric_name = raw_data.get("metric", "exact_match")
    max_examples = raw_data.get("max_examples", 10)
    
    if not signature or not unlabeled_inputs:
        return error_response("signature and unlabeled_inputs required", context=context)
    
    # Get metric
    metric_fn = metric_registry.get(metric_name)
    if not metric_fn:
        return error_response(f"Unknown metric: {metric_name}", context=context)
    
    try:
        # Create base program
        if program_type == "predict":
            program = dspy.Predict(signature)
        elif program_type == "chain_of_thought":
            program = dspy.ChainOfThought(signature)
        else:
            program = dspy.Predict(signature)  # Default
        
        # Use BootstrapFewShot for example generation
        bootstrap = dspy.BootstrapFewShot(
            metric=metric_fn,
            max_bootstrapped_demos=max_examples
        )
        
        # Create unlabeled examples
        unlabeled_examples = [dspy.Example(**inp).with_inputs(*inp.keys()) for inp in unlabeled_inputs]
        
        # Compile to generate examples
        compiled_program = bootstrap.compile(program, trainset=unlabeled_examples)
        
        # Extract bootstrapped examples
        bootstrapped = []
        for demo in compiled_program.demos:
            bootstrapped.append(demo.toDict())
        
        return event_response_builder({
            "status": "success",
            "bootstrapped_examples": bootstrapped,
            "count": len(bootstrapped)
        }, context=context)
        
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        return error_response(str(e), context=context)


@event_handler("optimization:register_metric")
async def handle_register_metric(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register a custom metric function."""
    
    metric_name = raw_data.get("metric_name")
    metric_code = raw_data.get("metric_code")
    metric_type = raw_data.get("metric_type", "custom")
    
    if not metric_name:
        return error_response("metric_name required", context=context)
    
    if metric_type == "llm_judge":
        # Create an LLM-based metric using DSPy
        judge_signature = raw_data.get("judge_signature", "example, prediction -> score")
        judge_instruction = raw_data.get("judge_instruction", "Rate the quality of the prediction.")
        
        def llm_judge_metric(example, pred, trace=None):
            judge = dspy.Predict(judge_signature)
            result = judge(example=str(example), prediction=str(pred))
            # Extract score - assumes judge returns a score field
            if hasattr(result, 'score'):
                try:
                    return float(result.score)
                except:
                    return 0.5  # Default middle score
            return 0.5
        
        metric_registry[metric_name] = llm_judge_metric
        
    elif metric_code:
        # Execute custom metric code (be careful with this in production!)
        # This is a simplified version - in production, use proper sandboxing
        try:
            exec(metric_code, {"dspy": dspy}, metric_registry)
            if metric_name not in metric_registry:
                return error_response("Metric code must define metric_registry[metric_name]", context=context)
        except Exception as e:
            return error_response(f"Failed to register metric: {e}", context=context)
    else:
        return error_response("Either metric_code or metric_type='llm_judge' required", context=context)
    
    return event_response_builder({
        "status": "success",
        "metric_name": metric_name,
        "registered_metrics": list(metric_registry.keys())
    }, context=context)


@event_handler("optimization:list_metrics")
async def handle_list_metrics(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List available metrics."""
    
    metrics_info = {
        "exact_match": {
            "description": "Checks if prediction exactly matches expected answer",
            "type": "binary",
            "expects": ["answer"]
        },
        "f1": {
            "description": "F1 score based on token overlap",
            "type": "score",
            "expects": ["answer"]
        },
        "passage_match": {
            "description": "Checks if answer appears in retrieved passages",
            "type": "binary",
            "expects": ["answer", "passages"]
        }
    }
    
    # Add custom metrics
    for name in metric_registry:
        if name not in metrics_info:
            metrics_info[name] = {
                "description": "Custom metric",
                "type": "custom"
            }
    
    return event_response_builder({
        "metrics": metrics_info,
        "count": len(metrics_info)
    }, context=context)


# Initialize DSPy on module load
def initialize_dspy():
    """Initialize DSPy with configured models."""
    global dspy_models
    
    if config.optimization_prompt_model and config.optimization_task_model:
        try:
            # Create KSI language model adapters
            prompt_lm = KSIAgentLanguageModel(
                model_name=config.optimization_prompt_model,
                agent_profile="optimization_prompt_agent"
            )
            task_lm = KSIAgentLanguageModel(
                model_name=config.optimization_task_model,
                agent_profile="optimization_task_agent"
            )
            
            # Configure DSPy
            dspy.settings.configure(lm=task_lm)
            
            dspy_models = {
                "prompt_model": prompt_lm,
                "task_model": task_lm
            }
            
            logger.info("DSPy initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DSPy: {e}")
            dspy_models = None
    else:
        logger.info("DSPy models not configured - optimization features disabled")


# Initialize on import
initialize_dspy()