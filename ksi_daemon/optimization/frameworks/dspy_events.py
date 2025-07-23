"""DSPy Framework Adapter for KSI Optimization."""

import logging
from typing import Dict, Any, Optional, List, Callable
import dspy

from ksi_daemon.event_system import get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

from .dspy_adapter import DSPyMIPROAdapter
from .litellm_dspy_adapter import KSILiteLLMDSPyAdapter, configure_dspy_with_litellm
from ..mlflow_manager import configure_dspy_autologging

logger = get_bound_logger("dspy_framework")

# Module-level tracking of active optimizers
_active_optimizers: Dict[str, Any] = {}


def get_active_optimizer(opt_id: str) -> Optional[Any]:
    """Get active optimizer by ID from module-level tracking."""
    return _active_optimizers.get(opt_id)


class DSPyFramework:
    """DSPy framework adapter for KSI optimization service."""
    
    def __init__(self):
        self.dspy_models = None
        self.metric_registry = self._initialize_metrics()
        self._initialize_dspy()
    
    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get framework information."""
        return {
            "available": True,
            "description": "DSPy framework for programming—not prompting—language models",
            "version": dspy.__version__ if hasattr(dspy, '__version__') else "unknown",
            "capabilities": {
                "signatures": ["InputField", "OutputField", "typed fields"],
                "predictors": ["Predict", "ChainOfThought", "ReAct", "ProgramOfThought", "Refine"],
                "optimizers": ["MIPROv2", "BootstrapFewShot", "COPRO", "BetterTogether"],
                "retrieval": ["25+ vector stores", "hybrid search", "metadata filtering"],
                "evaluation": ["metrics", "parallel eval", "HTML reports"]
            }
        }
    
    def _initialize_metrics(self) -> Dict[str, Callable]:
        """Initialize built-in DSPy metrics."""
        return {
            "exact_match": self._exact_match_metric,
            "confidence_calibration": self._confidence_calibration_metric,
            "text_analysis_quality": self._text_analysis_quality_metric,
        }
    
    def _exact_match_metric(self, example, prediction, trace=None) -> float:
        """Simple exact match metric."""
        if hasattr(prediction, 'answer') and hasattr(example, 'answer'):
            return 1.0 if prediction.answer.strip().lower() == example.answer.strip().lower() else 0.0
        return 0.5  # Default for non-answer tasks
    
    def _confidence_calibration_metric(self, example, prediction, trace=None) -> float:
        """Confidence calibration metric for text analysis."""
        if not hasattr(prediction, 'confidence'):
            return 0.0
        
        confidence = float(prediction.confidence)
        # Simple quality assessment based on response completeness
        quality = 0.5
        if hasattr(prediction, 'insights') and len(str(prediction.insights)) > 50:
            quality += 0.25
        if hasattr(prediction, 'recommendations') and len(str(prediction.recommendations)) > 50:
            quality += 0.25
        
        # Score based on how close confidence is to actual quality
        calibration_error = abs(confidence - quality)
        return max(0.0, 1.0 - calibration_error)
    
    def _text_analysis_quality_metric(self, example, prediction, trace=None) -> float:
        """Multi-factor text analysis quality metric."""
        scores = []
        
        # Factor 1: Response completeness
        if hasattr(prediction, 'insights'):
            insight_length = len(str(prediction.insights))
            scores.append(min(1.0, insight_length / 100))  # Target ~100 chars
        
        if hasattr(prediction, 'recommendations'):
            rec_length = len(str(prediction.recommendations))
            scores.append(min(1.0, rec_length / 100))  # Target ~100 chars
        
        # Factor 2: Confidence appropriateness
        if hasattr(prediction, 'confidence'):
            confidence = float(prediction.confidence)
            # Penalize overconfidence (> 0.9) or underconfidence (< 0.3)
            if 0.3 <= confidence <= 0.9:
                scores.append(1.0)
            else:
                scores.append(0.5)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _initialize_dspy(self):
        """Initialize DSPy with direct LiteLLM integration."""
        if config.optimization_prompt_model and config.optimization_task_model:
            try:
                # Use direct LiteLLM integration for optimization
                # This bypasses agent overhead and provides simpler, faster completions
                models = configure_dspy_with_litellm(
                    prompt_model=config.optimization_prompt_model,
                    task_model=config.optimization_task_model,
                    sandbox_dir=config.sandbox_dir if hasattr(config, 'sandbox_dir') else None
                )
                
                self.dspy_models = models
                logger.info(
                    "DSPy initialized with direct LiteLLM",
                    prompt_model=config.optimization_prompt_model,
                    task_model=config.optimization_task_model
                )
                
                # Configure MLflow autologging for DSPy
                if configure_dspy_autologging():
                    logger.info("MLflow autologging enabled for DSPy")
                else:
                    logger.warning("MLflow autologging could not be enabled")
                    
            except Exception as e:
                logger.error(f"Failed to initialize DSPy: {e}")
                self.dspy_models = None
        else:
            logger.info("DSPy models not configured - optimization features limited")
    
    def get_active_optimizer(self, opt_id: str) -> Optional[Any]:
        """Get active optimizer by ID."""
        return _active_optimizers.get(opt_id)
    
    def register_optimizer(self, opt_id: str, optimizer: Any):
        """Register an active optimizer."""
        _active_optimizers[opt_id] = optimizer
        logger.debug(f"Registered optimizer {opt_id}")
    
    def unregister_optimizer(self, opt_id: str):
        """Unregister an optimizer when complete."""
        if opt_id in _active_optimizers:
            del _active_optimizers[opt_id]
            logger.debug(f"Unregistered optimizer {opt_id}")
    
    @classmethod
    async def validate_setup(cls, raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate DSPy setup."""
        instance = cls()
        
        if instance.dspy_models is None:
            return event_response_builder({
                "valid": False,
                "reason": "DSPy models not configured",
                "required_config": [
                    "optimization_prompt_model",
                    "optimization_task_model"
                ]
            }, context=context)
        
        # Test model availability with simple check
        try:
            # Just verify models are configured properly
            return event_response_builder({
                "valid": True,
                "models": {
                    "prompt_model": str(instance.dspy_models.get("prompt_model", "none")),
                    "task_model": str(instance.dspy_models.get("task_model", "none"))
                },
                "adapter": "litellm"
            }, context=context)
        except Exception as e:
            return event_response_builder({
                "valid": False,
                "reason": f"Model test failed: {str(e)}"
            }, context=context)
    
    async def optimize(self, target: str, signature: str, metric: str, **kwargs) -> Dict[str, Any]:
        """Run DSPy optimization on a component."""
        # Extract optimization ID for progress tracking
        opt_id = kwargs.get("optimization_id")
        
        # Load target component
        router = get_router()
        target_response = await router.emit_first("composition:get_component", {
            "name": target
        })
        
        if target_response.get("status") != "success":
            raise ValueError(f"Failed to load target component: {target}")
        
        component_content = target_response.get("content", "")
        
        # Load metric
        metric_fn = await self._load_metric(metric)
        
        # Get training data
        trainset = kwargs.get("trainset", [])
        valset = kwargs.get("valset", [])
        optimizer_type = kwargs.get("optimizer", "mipro")
        config_overrides = kwargs.get("config", {})
        
        if optimizer_type == "mipro":
            # Use auto mode by default (recommended by DSPy source analysis)
            optimizer_config = {
                "auto": config_overrides.get("auto", "light"),  # "light", "medium", or "heavy"
                "max_bootstrapped_demos": config_overrides.get("max_bootstrapped_demos", 4),
                "max_labeled_demos": config_overrides.get("max_labeled_demos", 4),
                "init_temperature": config_overrides.get("init_temperature", 0.7),
                "verbose": config_overrides.get("verbose", True),
                **{k: v for k, v in config_overrides.items() if k not in ['auto', 'max_bootstrapped_demos', 'max_labeled_demos', 'init_temperature', 'verbose']}
            }
            
            adapter = DSPyMIPROAdapter(
                metric=metric_fn,
                prompt_model=self.dspy_models.get("prompt_model"),
                task_model=self.dspy_models.get("task_model"),
                config=optimizer_config,
                framework=self  # Pass framework reference for optimizer tracking
            )
            
            # Run optimization
            result = await adapter.optimize_component(
                component_name=target,
                component_content=component_content,
                trainset=trainset,
                valset=valset,
                opt_id=opt_id
            )
            
            return {
                "status": "success",
                "optimization_result": result
            }
        
        raise ValueError(f"Unknown optimizer: {optimizer_type}")
    
    async def evaluate(self, metric_component: str, metric_info: Dict[str, Any], 
                      data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Evaluate using DSPy metric."""
        # Load metric function
        metric_name = metric_info.get("metric_function", "exact_match")
        
        if metric_name in self.metric_registry:
            metric_fn = self.metric_registry[metric_name]
        else:
            # Try to load custom metric
            metric_fn = await self._load_custom_metric(metric_component, metric_info)
        
        example = data.get("example", {})
        prediction = data.get("prediction", {})
        
        try:
            # Create DSPy Example and Prediction objects
            dspy_example = dspy.Example(**example)
            dspy_prediction = dspy.Prediction(**prediction)
            
            # Run metric
            score = metric_fn(dspy_example, dspy_prediction)
            
            return {
                "status": "success",
                "metric": metric_name,
                "score": float(score) if isinstance(score, bool) else score,
                "example": example,
                "prediction": prediction
            }
        except Exception as e:
            logger.error(f"Metric evaluation failed: {e}")
            raise
    
    async def bootstrap(self, signature: str, **kwargs) -> Dict[str, Any]:
        """Bootstrap examples using DSPy."""
        # Load signature component
        if signature:
            sig_info = await self._load_signature(signature)
            signature_str = sig_info.get("signature", "input -> output")
        else:
            signature_str = kwargs.get("signature_str", "input -> output")
        
        program_type = kwargs.get("program_type", "predict")
        unlabeled_inputs = kwargs.get("unlabeled_inputs", [])
        metric = kwargs.get("metric", "exact_match")
        max_examples = kwargs.get("max_examples", 10)
        
        # Get metric function
        metric_fn = await self._load_metric(metric)
        
        try:
            # Create base program
            if program_type == "predict":
                program = dspy.Predict(signature_str)
            elif program_type == "chain_of_thought":
                program = dspy.ChainOfThought(signature_str)
            else:
                program = dspy.Predict(signature_str)
            
            # Use BootstrapFewShot
            bootstrap = dspy.BootstrapFewShot(
                metric=metric_fn,
                max_bootstrapped_demos=max_examples
            )
            
            # Create unlabeled examples
            unlabeled_examples = [
                dspy.Example(**inp).with_inputs(*inp.keys()) 
                for inp in unlabeled_inputs
            ]
            
            # Compile to generate examples
            compiled_program = bootstrap.compile(
                program, 
                trainset=unlabeled_examples
            )
            
            # Extract bootstrapped examples
            bootstrapped = []
            for demo in compiled_program.demos:
                bootstrapped.append(demo.toDict())
            
            return {
                "status": "success",
                "bootstrapped_examples": bootstrapped,
                "count": len(bootstrapped)
            }
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
            raise
    
    @classmethod
    async def format_examples(cls, raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format examples for DSPy."""
        examples = raw_data.get("examples", [])
        signature = raw_data.get("signature")
        
        formatted_examples = []
        
        for ex in examples:
            # Create DSPy Example
            dspy_ex = dspy.Example(**ex)
            
            # If signature provided, mark inputs/outputs
            if signature:
                input_fields = signature.get("inputs", [])
                output_fields = signature.get("outputs", [])
                
                # Mark fields
                dspy_ex = dspy_ex.with_inputs(*input_fields)
                if output_fields:
                    existing_outputs = [f for f in output_fields if f in ex]
                    if existing_outputs:
                        dspy_ex = dspy_ex.with_outputs(*existing_outputs)
            
            formatted_examples.append(dspy_ex.toDict())
        
        return {
            "formatted_examples": formatted_examples,
            "count": len(formatted_examples),
            "format": "dspy"
        }
    
    async def _load_signature(self, signature_component: str) -> Dict[str, Any]:
        """Load a signature component."""
        router = get_router()
        response = await router.emit_first("composition:get_component", {
            "name": signature_component
        })
        
        if response.get("status") != "success":
            raise ValueError(f"Failed to load signature: {signature_component}")
        
        return response.get("metadata", {})
    
    async def _load_metric(self, metric: str) -> Callable:
        """Load a metric function."""
        if metric in self.metric_registry:
            return self.metric_registry[metric]
        
        # Try to load as component
        router = get_router()
        response = await router.emit_first("composition:get_component", {
            "name": metric
        })
        
        if response.get("status") == "success":
            metric_info = response.get("metadata", {})
            return await self._load_custom_metric(metric, metric_info)
        
        # Default to exact match
        return self.metric_registry["exact_match"]
    
    async def _load_custom_metric(self, metric_name: str, metric_info: Dict[str, Any]) -> Callable:
        """Load a custom metric from component."""
        metric_type = metric_info.get("metric_type", "programmatic")
        
        if metric_type == "programmatic":
            # Load programmatic metric
            metric_code = metric_info.get("metric_code")
            if metric_code:
                # Execute metric code (be careful in production!)
                local_vars = {}
                exec(metric_code, {"dspy": dspy}, local_vars)
                if "metric" in local_vars:
                    return local_vars["metric"]
        
        # Default metric
        return self.metric_registry["exact_match"]
    
    @classmethod
    async def cleanup(cls):
        """Clean up DSPy resources on shutdown."""
        # Clear all active optimizers
        global _active_optimizers
        logger.info(f"Clearing {len(_active_optimizers)} active DSPy optimizers")
        _active_optimizers.clear()