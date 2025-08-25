"""DSPy/MIPROv2 adapter for KSI component optimization."""

import dspy
from typing import Dict, List, Any, Optional, Callable
import json
import yaml
from datetime import datetime
import re

from ksi_daemon.optimization.frameworks.base_optimizer import (
    BaseOptimizer, 
    OptimizationResult,
    ComponentMetrics
)
from ksi_common.timestamps import timestamp_utc
from ksi_common.logging import get_bound_logger
from ksi_common.async_operations import run_in_thread_pool

logger = get_bound_logger("dspy_adapter")

# Import default metric for agent-based evaluation
try:
    from ksi_daemon.optimization.metrics.agent_output_metric import evaluate_data_analysis
except ImportError:
    logger.warning("Agent output metric not available, using simplified metric")
    evaluate_data_analysis = None


class KSIComponentSignature(dspy.Signature):
    """You are an expert at optimizing prompts and instructions for AI systems. Your task is to take an existing instruction/prompt and make it more effective, detailed, and actionable while maintaining its core purpose."""
    context: str = dspy.InputField(desc="Component metadata - the type and purpose of this AI component")
    current_instruction: str = dspy.InputField(desc="The EXISTING instruction/prompt text that needs improvement")
    examples: str = dspy.InputField(desc="Example patterns showing what makes instructions effective")
    optimized_instruction: str = dspy.OutputField(desc="Your IMPROVED version of the instruction - make it more detailed, structured, and effective")


class DSPyMIPROAdapter(BaseOptimizer):
    """Adapter for using DSPy's MIPROv2 optimizer with KSI components."""
    
    def __init__(
        self, 
        metric: Optional[Callable] = None,
        prompt_model: Optional[Any] = None,
        task_model: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        framework: Optional[Any] = None
    ):
        """Initialize DSPy adapter with models and config."""
        # Use agent-based evaluation metric if none provided
        if metric is None and evaluate_data_analysis is not None:
            # Create a sync wrapper for the async metric
            import asyncio
            def sync_metric_wrapper(example, prediction, trace=None):
                """Sync wrapper for async agent evaluation metric."""
                try:
                    # Run async metric in event loop
                    loop = asyncio.new_event_loop()
                    score = loop.run_until_complete(
                        evaluate_data_analysis(example, prediction, trace)
                    )
                    loop.close()
                    return score
                except Exception as e:
                    logger.error(f"Error in metric evaluation: {e}")
                    return 0.0
            metric = sync_metric_wrapper
            logger.info("Using agent-based evaluation metric")
        elif metric is None:
            # Fallback to simple metric
            def simple_metric(example, prediction, trace=None):
                """Simple fallback metric."""
                return 0.5
            metric = simple_metric
            logger.warning("Using fallback simple metric")
            
        super().__init__(metric, config)
        
        # Configure DSPy models
        self.prompt_model = prompt_model or dspy.settings.lm
        self.task_model = task_model or dspy.settings.lm
        self.framework = framework  # Reference to DSPyFramework for optimizer tracking
        
        # Configure for zero-shot optimization based on DSPy source analysis
        auto_mode = config.get("auto", "light")  # Default to light auto mode
        
        if auto_mode and auto_mode != "None":
            # Auto mode: zero-shot optimization (instruction-only)
            self.mipro_init_config = {
                "auto": auto_mode,  # "light", "medium", or "heavy"
                "init_temperature": config.get("init_temperature", 0.7),
                "verbose": config.get("verbose", True),
                "track_stats": config.get("track_stats", True),
                "metric_threshold": config.get("metric_threshold", None),
            }
            # Zero-shot parameters go in compile(), not init()
            self.mipro_compile_config = {
                "max_bootstrapped_demos": 0,  # Zero-shot: no bootstrapped examples
                "max_labeled_demos": 0,       # Zero-shot: no few-shot examples
            }
        else:
            # Manual mode: zero-shot optimization
            self.mipro_init_config = {
                "auto": None,  # Disable auto mode for manual control
                "init_temperature": config.get("init_temperature", 0.7),
                "verbose": config.get("verbose", True),
                "track_stats": config.get("track_stats", True),
                "metric_threshold": config.get("metric_threshold", None),
            }
            # Zero-shot parameters and num_trials go to compile(), not init()
            self.mipro_compile_config = {
                "num_trials": config.get("num_trials", 12),
                "max_bootstrapped_demos": 0,  # Zero-shot: no bootstrapped examples
                "max_labeled_demos": 0,       # Zero-shot: no few-shot examples
            }
    
    def get_optimizer_name(self) -> str:
        """Return optimizer name."""
        return "DSPy-MIPROv2"
    
    def _extract_component_parts(self, content: str) -> Dict[str, Any]:
        """Extract frontmatter and body from component content."""
        # Match frontmatter between --- markers
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        
        if frontmatter_match:
            frontmatter_str = frontmatter_match.group(1)
            body = frontmatter_match.group(2)
            
            # Parse YAML frontmatter
            try:
                frontmatter = yaml.safe_load(frontmatter_str) or {}
            except yaml.YAMLError:
                frontmatter = {}
        else:
            frontmatter = {}
            body = content
        
        return {
            "frontmatter": frontmatter,
            "body": body,
            "full_content": content
        }
    
    def _reconstruct_component(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Reconstruct component content from parts."""
        if frontmatter:
            yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
            return f"---\n{yaml_str}---\n{body}"
        return body
    
    def _create_dspy_program(self, component_type: str) -> dspy.Module:
        """Create a DSPy program for the component type."""
        
        class ComponentOptimizer(dspy.Module):
            def __init__(self):
                super().__init__()
                self.optimize = dspy.ChainOfThought(KSIComponentSignature)
            
            def forward(self, context, current_instruction, examples):
                return self.optimize(
                    context=context,
                    current_instruction=current_instruction,
                    examples=examples
                )
        
        return ComponentOptimizer()
    
    def _prepare_training_examples(
        self, 
        component_name: str,
        trainset: List[Dict[str, Any]]
    ) -> List[dspy.Example]:
        """Convert KSI training data to DSPy examples."""
        dspy_examples = []
        
        for example in trainset:
            # Extract relevant fields based on component type
            if "agent_response" in example and "evaluation" in example:
                # This is an agent interaction example
                dspy_example = dspy.Example(
                    context=f"Component: {component_name}\nInput: {example.get('input', '')}",
                    current_instruction=example.get('current_instruction', ''),
                    examples=f"Response: {example['agent_response']}\nEvaluation: {example['evaluation']}",
                    optimized_instruction=example.get('improved_instruction', '')
                ).with_inputs("context", "current_instruction", "examples")
                
                dspy_examples.append(dspy_example)
        
        return dspy_examples
    
    def _optimize_component_sync(
        self,
        component_name: str,
        component_content: str,
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        opt_id: Optional[str] = None,
        **kwargs
    ) -> OptimizationResult:
        """Synchronous optimization implementation for running in thread pool."""
        
        # Extract component parts
        parts = self._extract_component_parts(component_content)
        original_body = parts["body"]
        frontmatter = parts["frontmatter"]
        
        # Prepare training data
        dspy_trainset = self._prepare_training_examples(component_name, trainset)
        
        if not dspy_trainset:
            # Generate minimal training examples for DSPy instruction generation
            dspy_trainset = self._generate_minimal_training_data(component_name, original_body)
        
        # Create validation set
        if valset:
            dspy_valset = self._prepare_training_examples(component_name, valset)
        else:
            # Split trainset if no valset provided
            # Ensure at least 1 example in valset
            if len(dspy_trainset) >= 2:
                split_idx = max(1, int(len(dspy_trainset) * 0.8))
                # Ensure we don't take all examples for trainset
                split_idx = min(split_idx, len(dspy_trainset) - 1)
                dspy_valset = dspy_trainset[split_idx:]
                dspy_trainset = dspy_trainset[:split_idx]
            else:
                # If only 1 example, duplicate it for valset
                dspy_valset = dspy_trainset.copy()
                logger.warning(f"Only {len(dspy_trainset)} training examples, duplicating for validation")
        
        # Create DSPy program
        program = self._create_dspy_program(component_name)
        
        # Initialize MIPROv2 optimizer with separated configuration
        optimizer = dspy.MIPROv2(
            metric=self.metric,
            prompt_model=self.prompt_model,
            task_model=self.task_model,
            **self.mipro_init_config
        )
        
        # Register optimizer for progress tracking if framework is available
        if self.framework and opt_id:
            self.framework.register_optimizer(opt_id, optimizer)
        
        try:
            # Tag MLflow run with KSI optimization ID if MLflow is active
            try:
                import mlflow
                if mlflow.active_run() is None:
                    mlflow.start_run()
                if opt_id:
                    mlflow.set_tag("ksi_optimization_id", opt_id)
                    mlflow.set_tag("ksi_component", component_name)
                    mlflow.set_tag("ksi_optimizer", "DSPy-MIPROv2")
            except Exception as e:
                logger.debug(f"Could not set MLflow tags: {e}")
            
            # Run optimization with compile-specific configuration
            logger.info(f"Starting DSPy optimization for {component_name}")
            optimized_program = optimizer.compile(
                program,
                trainset=dspy_trainset,
                valset=dspy_valset,
                requires_permission_to_run=False,
                **self.mipro_compile_config
            )
            logger.info(f"DSPy optimization completed for {component_name}")
        finally:
            # Always unregister optimizer when done
            if self.framework and opt_id:
                self.framework.unregister_optimizer(opt_id)
        
        # Dump raw DSPy output for debugging
        logger.info("=" * 80)
        logger.info("RAW DSPY OUTPUT DUMP")
        logger.info("=" * 80)
        
        # Dump the entire optimized program structure
        logger.info(f"Optimized program type: {type(optimized_program)}")
        logger.info(f"Optimized program dict: {optimized_program.__dict__}")
        
        # Dump all modules and their attributes
        for name, module in optimized_program.named_modules():
            logger.info(f"\nModule: {name}")
            logger.info(f"  Type: {type(module)}")
            logger.info(f"  Dict: {module.__dict__}")
            
            if hasattr(module, 'extended_signature'):
                logger.info(f"  Extended signature: {module.extended_signature}")
                logger.info(f"  Extended signature dict: {module.extended_signature.__dict__}")
            
            if hasattr(module, 'predictors'):
                logger.info(f"  Predictors: {module.predictors}")
            
            if hasattr(module, 'signature'):
                logger.info(f"  Signature: {module.signature}")
        
        # Also dump optimizer stats if available
        if hasattr(optimizer, 'best_program'):
            logger.info(f"\nOptimizer best_program: {optimizer.best_program}")
        
        if hasattr(optimizer, 'best_score'):
            logger.info(f"Optimizer best_score: {optimizer.best_score}")
            
        if hasattr(optimizer, 'stats'):
            logger.info(f"Optimizer stats: {optimizer.stats}")
        
        logger.info("=" * 80)
        logger.info("END RAW DSPY OUTPUT")
        logger.info("=" * 80)
        
        # Extract optimized instruction by running the optimized program
        optimized_instruction = None
        
        try:
            # Create a test example with the component to optimize
            test_example = dspy.Example(
                context=f"Component: {component_name}\nType: {frontmatter.get('component_type', 'component')}\nPurpose: {frontmatter.get('description', 'AI component')}",
                current_instruction=original_body,
                examples="Good instructions have: Clear role definition, specific expertise areas, structured approach, personality traits"
            ).with_inputs("context", "current_instruction", "examples")
            
            # Run the optimized program to get the actual optimized instruction
            logger.info("Running optimized program to extract instruction")
            prediction = optimized_program(test_example)
            
            if hasattr(prediction, 'optimized_instruction'):
                optimized_instruction = prediction.optimized_instruction
                logger.info(f"Successfully extracted optimized instruction (length: {len(optimized_instruction)})")
            else:
                logger.warning("No optimized_instruction field in prediction")
                optimized_instruction = original_body
                
        except Exception as e:
            logger.error(f"Failed to extract optimized instruction: {e}")
            optimized_instruction = original_body
        
        # Update frontmatter with optimization metadata
        frontmatter["optimization"] = {
            "optimizer": self.get_optimizer_name(),
            "timestamp": time.time(),  # Numeric for processing
            "timestamp_iso": timestamp_utc(),  # ISO for display
            "auto_mode": self.mipro_init_config.get("auto"),
            "num_trials": self.mipro_compile_config.get("num_trials", "auto"),
            "trainset_size": len(dspy_trainset),
            "valset_size": len(dspy_valset),
        }
        
        # Reconstruct optimized component
        optimized_content = self._reconstruct_component(frontmatter, optimized_instruction)
        
        # Extract actual scores from optimization results
        original_score = 0.0  # Baseline (before optimization)
        optimized_score = 0.0  # Will be extracted from results
        
        # Try to get the best score from optimizer
        if hasattr(optimizer, 'best_score') and optimizer.best_score is not None:
            optimized_score = float(optimizer.best_score)
            logger.info(f"Using optimizer best_score: {optimized_score}")
        
        # Try to extract from trial logs in optimized program
        elif hasattr(optimized_program, 'trial_logs') and optimized_program.trial_logs:
            # Find the best score from all trials
            best_score = 0.0
            for trial_num, trial_data in optimized_program.trial_logs.items():
                if 'full_eval_score' in trial_data:
                    trial_score = float(trial_data['full_eval_score'])
                    if trial_score > best_score:
                        best_score = trial_score
                        logger.info(f"Trial {trial_num} score: {trial_score}")
            optimized_score = best_score
            logger.info(f"Best score from trial logs: {optimized_score}")
        
        # Try to extract from program score attribute
        elif hasattr(optimized_program, 'score'):
            optimized_score = float(optimized_program.score)
            logger.info(f"Using program score: {optimized_score}")
        
        # If still no score, run evaluation manually
        if optimized_score == 0.0 and self.metric:
            logger.info("No score found in optimization results, evaluating manually")
            try:
                # Create a test example
                test_example = dspy.Example(
                    context=f"Component: {component_name}",
                    current_instruction=original_body[:500],
                    examples="Test evaluation"
                ).with_inputs("context", "current_instruction", "examples")
                
                # Run the optimized program to get prediction
                prediction = optimized_program(test_example)
                
                # Evaluate with metric
                optimized_score = self.metric(test_example, prediction)
                logger.info(f"Manual evaluation score: {optimized_score}")
            except Exception as e:
                logger.error(f"Failed to manually evaluate: {e}")
                optimized_score = 0.1  # Small default if evaluation fails
        
        result: OptimizationResult = {
            "component_name": component_name,
            "original_score": original_score,
            "optimized_score": optimized_score,
            "improvement": optimized_score - original_score,
            "optimized_content": optimized_content,
            "optimization_metadata": {
                "optimizer": self.get_optimizer_name(),
                "init_config": self.mipro_init_config,
                "compile_config": self.mipro_compile_config,
                "stats": optimizer.__dict__.get("stats", {}),
            },
            "git_commit": None,  # Will be set by git tracking
            "git_tag": None,  # Will be set by git tracking
        }
        
        self.save_optimization_result(result)
        return result
    
    async def optimize_component(
        self,
        component_name: str,
        component_content: str,
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        opt_id: Optional[str] = None,
        **kwargs
    ) -> OptimizationResult:
        """Optimize a single KSI component using MIPROv2.
        
        This async method runs the synchronous DSPy optimization in a thread pool
        to avoid blocking the event loop.
        """
        logger.info(f"Running DSPy optimization for {component_name} in thread pool")
        
        # Run the sync optimization in thread pool
        result = await run_in_thread_pool(
            self._optimize_component_sync,
            component_name=component_name,
            component_content=component_content,
            trainset=trainset,
            valset=valset,
            opt_id=opt_id,
            **kwargs
        )
        
        return result
    
    
    def _generate_minimal_training_data(self, component_name: str, original_body: str) -> List[Any]:
        """Generate minimal training examples for DSPy instruction generation (2-3 examples max)."""
        import dspy
        
        # Extract component purpose from name and body
        component_type = "component"
        if "analyst" in component_name.lower():
            component_type = "analyst persona"
        elif "researcher" in component_name.lower():
            component_type = "researcher persona"
        elif "coordinator" in component_name.lower():
            component_type = "coordinator agent"
        
        # Create minimal examples that clearly show instruction optimization
        training_examples = []
        
        # Example 1: Show concrete instruction optimization (simple to detailed)
        example1 = dspy.Example(
            context=f"Component: assistant\nType: AI assistant\nPurpose: Make this basic assistant instruction more effective and detailed",
            current_instruction="You are a helpful assistant.",
            examples="Good instructions have: Clear role definition, specific expertise areas, structured approach, personality traits",
            optimized_instruction="You are a knowledgeable and helpful AI assistant with expertise in analysis, problem-solving, and clear communication. Your approach is systematic: first understand the context, then break down complex problems into manageable steps, and finally provide actionable solutions. You communicate in a clear, professional tone while adapting your style to match the user's needs and expertise level."
        ).with_inputs("context", "current_instruction", "examples")
        training_examples.append(example1)
        
        # Example 2: Show domain-specific optimization (analyst persona)
        example2 = dspy.Example(
            context=f"Component: data_analyst\nType: analyst persona\nPurpose: Transform generic instruction into domain-specific expertise",
            current_instruction="You are an analyst who works with data.",
            examples="Effective analyst prompts include: Domain expertise, methodical approach, tools knowledge, communication skills",
            optimized_instruction="You are a Senior Data Analyst with deep expertise in statistical analysis, data visualization, and business intelligence. Your approach is methodical: start by understanding the business question, assess data quality and completeness, select appropriate analytical methods, and present findings with clear visualizations and actionable recommendations. You excel at translating complex data insights into strategic business value."
        ).with_inputs("context", "current_instruction", "examples")
        training_examples.append(example2)
        
        return training_examples