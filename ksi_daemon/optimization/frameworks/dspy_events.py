"""DSPy Framework Adapter for KSI Optimization."""

import logging
from typing import Dict, Any, Optional, List, Callable
import dspy

from ksi_daemon.event_system import get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

from .dspy_adapter import DSPyMIPROAdapter
from .ksi_lm_adapter import KSIAgentLanguageModel

logger = get_bound_logger("dspy_framework")


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
            "exact_match": dspy.metrics.answer_exact_match,
            "f1": lambda ex, pred, trace=None: dspy.dsp.utils.F1(
                pred.answer if hasattr(pred, 'answer') else str(pred), 
                ex.answer
            ),
            "passage_match": dspy.metrics.answer_passage_match,
        }
    
    def _initialize_dspy(self):
        """Initialize DSPy with configured models."""
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
                
                self.dspy_models = {
                    "prompt_model": prompt_lm,
                    "task_model": task_lm
                }
                
                logger.info("DSPy initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize DSPy: {e}")
                self.dspy_models = None
        else:
            logger.info("DSPy models not configured - optimization features limited")
    
    @classmethod
    async def validate_setup(cls, raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate DSPy setup."""
        instance = cls()
        
        if instance.dspy_models is None:
            return {
                "valid": False,
                "reason": "DSPy models not configured",
                "required_config": [
                    "optimization_prompt_model",
                    "optimization_task_model"
                ]
            }
        
        # Test model availability
        try:
            test_pred = dspy.Predict("question -> answer")
            test_result = test_pred(question="test")
            return {
                "valid": True,
                "models": {
                    "prompt_model": str(instance.dspy_models.get("prompt_model", "none")),
                    "task_model": str(instance.dspy_models.get("task_model", "none"))
                }
            }
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Model test failed: {str(e)}"
            }
    
    async def optimize(self, target: str, signature: str, metric: str, **kwargs) -> Dict[str, Any]:
        """Run DSPy optimization on a component."""
        # Load target component
        router = get_router()
        target_response = await router.route({
            "event": "composition:get_component",
            "data": {"name": target}
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
            # Merge configs
            optimizer_config = {
                "auto": "medium",
                "num_candidates": 10,
                "max_bootstrapped_demos": 4,
                **config_overrides
            }
            
            adapter = DSPyMIPROAdapter(
                metric=metric_fn,
                prompt_model=self.dspy_models.get("prompt_model"),
                task_model=self.dspy_models.get("task_model"),
                config=optimizer_config
            )
            
            # Run optimization
            result = await adapter.optimize_component(
                component_name=target,
                component_content=component_content,
                trainset=trainset,
                valset=valset
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
        response = await router.route({
            "event": "composition:get_component",
            "data": {"name": signature_component, "type": "signature"}
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
        response = await router.route({
            "event": "composition:get_component",
            "data": {"name": metric, "type": "metric"}
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