"""DSPy/SIMBA adapter for KSI component runtime optimization."""

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

logger = get_bound_logger("dspy_simba_adapter")


class KSIComponentSignature(dspy.Signature):
    """You are an expert at iteratively improving prompts based on recent performance feedback. Your task is to take an existing instruction/prompt and make small, targeted improvements based on the mini-batch results."""
    context: str = dspy.InputField(desc="Component metadata - the type and purpose of this AI component")
    current_instruction: str = dspy.InputField(desc="The CURRENT instruction/prompt that needs incremental improvement")
    performance_feedback: str = dspy.InputField(desc="Recent performance data from mini-batch showing what worked and what didn't")
    improved_instruction: str = dspy.OutputField(desc="Your INCREMENTALLY IMPROVED version - make small targeted changes based on the feedback")


class DSPySIMBAAdapter(BaseOptimizer):
    """Adapter for using DSPy's SIMBA optimizer for runtime component adaptation."""
    
    def __init__(
        self, 
        metric: Optional[Callable] = None,
        prompt_model: Optional[Any] = None,
        task_model: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        framework: Optional[Any] = None
    ):
        """Initialize SIMBA adapter with models and config."""
        super().__init__(metric, config)
        
        # Configure DSPy models
        self.prompt_model = prompt_model or dspy.settings.lm
        self.task_model = task_model or dspy.settings.lm
        self.framework = framework  # Reference to DSPyFramework for optimizer tracking
        
        # SIMBA-specific configuration
        self.simba_config = {
            "max_steps": config.get("max_steps", 4),  # Default: 4 optimization steps
            "num_candidates": config.get("num_candidates", 4),  # Candidates per step
            "max_demos": config.get("max_demos", 2),  # Max few-shot demos
            "mini_batch_size": config.get("mini_batch_size", 8),  # Mini-batch size
            "exploration_temperature": config.get("exploration_temperature", 0.7),
            "verbose": config.get("verbose", True),
            "track_stats": config.get("track_stats", True),
        }
        
        logger.info(f"Initialized SIMBA adapter with config: {self.simba_config}")
    
    def get_optimizer_name(self) -> str:
        """Return optimizer name."""
        return "DSPy-SIMBA"
    
    def _extract_component_parts(self, content: str) -> Dict[str, Any]:
        """Extract frontmatter and body from component content."""
        # Match frontmatter between --- markers
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        
        if frontmatter_match:
            frontmatter_str = frontmatter_match.group(1)
            body = frontmatter_match.group(2).strip()
            
            # Parse frontmatter as YAML
            try:
                frontmatter = yaml.safe_load(frontmatter_str) or {}
            except yaml.YAMLError:
                frontmatter = {}
        else:
            # No frontmatter, entire content is body
            frontmatter = {}
            body = content.strip()
        
        return {
            "frontmatter": frontmatter,
            "body": body
        }
    
    def _reconstruct_component(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Reconstruct component content from parts."""
        if frontmatter:
            # Convert frontmatter to YAML
            frontmatter_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)
            return f"---\n{frontmatter_str}---\n\n{body}"
        else:
            return body
    
    def _create_dspy_program(self, component_name: str) -> dspy.Module:
        """Create a DSPy program for component optimization."""
        
        class ComponentOptimizer(dspy.Module):
            def __init__(self):
                super().__init__()
                self.optimizer = dspy.ChainOfThought(KSIComponentSignature)
            
            def forward(self, context, current_instruction, performance_feedback):
                return self.optimizer(
                    context=context,
                    current_instruction=current_instruction,
                    performance_feedback=performance_feedback
                )
        
        return ComponentOptimizer()
    
    def _create_mini_batch_dataset(
        self, 
        component_name: str,
        recent_interactions: List[Dict[str, Any]]
    ) -> List[dspy.Example]:
        """Create mini-batch dataset from recent interactions."""
        dspy_examples = []
        
        for interaction in recent_interactions[-self.simba_config["mini_batch_size"]:]:
            # Extract performance feedback
            performance = interaction.get("performance", {})
            feedback = f"Score: {performance.get('score', 0.0)}, "
            feedback += f"Success: {performance.get('success', False)}, "
            feedback += f"Issues: {performance.get('issues', 'None')}"
            
            example = dspy.Example(
                context=f"Component: {component_name}, Type: {interaction.get('type', 'agent')}",
                current_instruction=interaction.get("prompt", "")[:1000],  # Truncate for context
                performance_feedback=feedback,
                improved_instruction=interaction.get("ideal_response", "")  # If available
            )
            
            # Only use inputs for SIMBA (not outputs, as we're learning incrementally)
            example = example.with_inputs("context", "current_instruction", "performance_feedback")
            dspy_examples.append(example)
        
        return dspy_examples
    
    def optimize_sync(
        self,
        component_name: str,
        component_content: str,
        recent_interactions: List[Dict[str, Any]],
        **kwargs
    ) -> OptimizationResult:
        """Optimize component using SIMBA based on recent performance."""
        
        # Extract current component parts
        parts = self._extract_component_parts(component_content)
        frontmatter = parts["frontmatter"]
        original_body = parts["body"]
        
        # Create mini-batch dataset
        mini_batch = self._create_mini_batch_dataset(component_name, recent_interactions)
        
        if not mini_batch:
            logger.warning(f"No recent interactions for {component_name}, skipping optimization")
            return {
                "component_name": component_name,
                "original_score": 0.0,
                "optimized_score": 0.0,
                "improvement": 0.0,
                "optimized_content": component_content,
                "optimization_metadata": {
                    "optimizer": self.get_optimizer_name(),
                    "reason": "No recent interactions"
                }
            }
        
        # Create program
        program = self._create_dspy_program(component_name)
        
        # Initialize SIMBA optimizer
        optimizer = dspy.SIMBA(
            metric=self.metric,
            max_steps=self.simba_config["max_steps"],
            num_candidates=self.simba_config["num_candidates"],
            max_demos=self.simba_config["max_demos"],
            init_temperature=self.simba_config["exploration_temperature"],
            verbose=self.simba_config["verbose"],
            track_stats=self.simba_config["track_stats"]
        )
        
        # Track optimization in framework if available
        if self.framework:
            self.framework.track_optimization_run(
                optimizer_name=self.get_optimizer_name(),
                component=component_name,
                config=self.simba_config
            )
        
        # Run SIMBA optimization
        logger.info(f"Starting SIMBA optimization for {component_name}")
        logger.info(f"Mini-batch size: {len(mini_batch)}")
        
        optimized_program = optimizer.compile(
            program,
            trainset=mini_batch,
            save_path=None  # Don't save intermediate results
        )
        
        # Extract optimized instruction
        optimized_instruction = original_body  # Default fallback
        
        # Try to get the improved instruction from the last mini-batch evaluation
        if mini_batch:
            try:
                # Create a test example with recent performance
                last_interaction = recent_interactions[-1] if recent_interactions else {}
                test_feedback = f"Recent performance: {last_interaction.get('performance', {})}"
                
                test_example = dspy.Example(
                    context=f"Component: {component_name}",
                    current_instruction=original_body[:1000],
                    performance_feedback=test_feedback
                ).with_inputs("context", "current_instruction", "performance_feedback")
                
                # Get improved instruction
                prediction = optimized_program(test_example)
                if hasattr(prediction, 'improved_instruction'):
                    optimized_instruction = prediction.improved_instruction
                    logger.info("Successfully extracted improved instruction from SIMBA")
            except Exception as e:
                logger.error(f"Failed to extract optimized instruction: {e}")
        
        # Calculate improvement scores
        original_score = 0.0
        optimized_score = 0.0
        
        # Get scores from SIMBA if available
        if hasattr(optimizer, 'score_history') and optimizer.score_history:
            # SIMBA tracks score improvements over steps
            original_score = optimizer.score_history[0] if optimizer.score_history else 0.0
            optimized_score = optimizer.score_history[-1] if optimizer.score_history else 0.0
            logger.info(f"SIMBA score progression: {optimizer.score_history}")
        
        # Update frontmatter with optimization metadata
        frontmatter["optimization"] = frontmatter.get("optimization", {})
        frontmatter["optimization"]["last_simba_update"] = {
            "timestamp": timestamp_utc(),
            "mini_batch_size": len(mini_batch),
            "steps": self.simba_config["max_steps"],
            "score_improvement": optimized_score - original_score
        }
        
        # Reconstruct optimized component
        optimized_content = self._reconstruct_component(frontmatter, optimized_instruction)
        
        result: OptimizationResult = {
            "component_name": component_name,
            "original_score": original_score,
            "optimized_score": optimized_score,
            "improvement": optimized_score - original_score,
            "optimized_content": optimized_content,
            "optimization_metadata": {
                "optimizer": self.get_optimizer_name(),
                "config": self.simba_config,
                "mini_batch_size": len(mini_batch),
                "score_history": getattr(optimizer, 'score_history', [])
            },
            "git_commit": None,  # Will be set by git tracking if enabled
            "git_tag": None,
        }
        
        self.save_optimization_result(result)
        return result
    
    async def optimize_component(
        self,
        component_name: str,
        component_content: str,
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> OptimizationResult:
        """Optimize a single component using SIMBA (trainset contains recent interactions)."""
        # For SIMBA, trainset contains recent interactions rather than traditional training examples
        recent_interactions = trainset
        
        logger.info(f"Running SIMBA component optimization for {component_name}")
        
        # Run sync optimization in thread pool
        result = await run_in_thread_pool(
            self.optimize_sync,
            component_name,
            component_content,
            recent_interactions,
            **kwargs
        )
        
        return result
    
    async def optimize_orchestration(
        self,
        orchestration_pattern: str,
        components: Dict[str, str],
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, OptimizationResult]:
        """Optimize all components in an orchestration using SIMBA."""
        results = {}
        
        # For now, optimize each component independently using recent interactions
        # Future: implement joint optimization considering component interactions
        for component_name, component_content in components.items():
            # Filter interactions relevant to this component
            component_interactions = [
                interaction for interaction in trainset
                if interaction.get("component") == component_name
            ]
            
            if not component_interactions:
                # Use full trainset if no component-specific interactions
                component_interactions = trainset
            
            try:
                result = await self.optimize_component(
                    component_name=component_name,
                    component_content=component_content,
                    trainset=component_interactions,
                    valset=valset,
                    **kwargs
                )
                results[component_name] = result
            except Exception as e:
                logger.error(f"Failed to optimize component {component_name}: {e}")
                # Create error result
                results[component_name] = {
                    "component_name": component_name,
                    "original_score": 0.0,
                    "optimized_score": 0.0,
                    "improvement": 0.0,
                    "optimized_content": component_content,
                    "optimization_metadata": {
                        "optimizer": self.get_optimizer_name(),
                        "error": str(e)
                    },
                    "git_commit": None,
                    "git_tag": None,
                }
        
        return results
    
    async def optimize(
        self,
        component_name: str,
        component_content: str,
        recent_interactions: List[Dict[str, Any]],
        **kwargs
    ) -> OptimizationResult:
        """Async wrapper for SIMBA optimization (legacy interface)."""
        logger.info(f"Running SIMBA optimization for {component_name} in thread pool")
        
        # Run sync optimization in thread pool
        result = await run_in_thread_pool(
            self.optimize_sync,
            component_name,
            component_content,
            recent_interactions,
            **kwargs
        )
        
        return result
    
    def optimize_pipeline(
        self,
        components: Dict[str, str],
        interactions_per_component: Dict[str, List[Dict[str, Any]]],
        **kwargs
    ) -> Dict[str, OptimizationResult]:
        """Optimize multiple components based on their recent interactions."""
        results = {}
        
        for component_name, component_content in components.items():
            recent_interactions = interactions_per_component.get(component_name, [])
            
            try:
                result = self.optimize_sync(
                    component_name,
                    component_content,
                    recent_interactions,
                    **kwargs
                )
                results[component_name] = result
                logger.info(f"SIMBA optimization for {component_name}: improvement={result['improvement']:.3f}")
            except Exception as e:
                logger.error(f"Failed to optimize {component_name}: {e}")
                results[component_name] = {
                    "component_name": component_name,
                    "original_score": 0.0,
                    "optimized_score": 0.0,
                    "improvement": 0.0,
                    "optimized_content": component_content,
                    "optimization_metadata": {
                        "optimizer": self.get_optimizer_name(),
                        "error": str(e)
                    }
                }
        
        return results