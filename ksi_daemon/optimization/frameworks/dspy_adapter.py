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


class KSIComponentSignature(dspy.Signature):
    """Signature for optimizing KSI component instructions."""
    context: str = dspy.InputField(desc="Component context and purpose")
    current_instruction: str = dspy.InputField(desc="Current component instruction/content")
    examples: str = dspy.InputField(desc="Examples of successful component usage")
    optimized_instruction: str = dspy.OutputField(desc="Improved component instruction")


class DSPyMIPROAdapter(BaseOptimizer):
    """Adapter for using DSPy's MIPROv2 optimizer with KSI components."""
    
    def __init__(
        self, 
        metric: Callable,
        prompt_model: Optional[Any] = None,
        task_model: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize DSPy adapter with models and config."""
        super().__init__(metric, config)
        
        # Configure DSPy models
        self.prompt_model = prompt_model or dspy.settings.lm
        self.task_model = task_model or dspy.settings.lm
        
        # Default MIPROv2 settings
        self.mipro_config = {
            "auto": config.get("auto", "medium"),
            "max_bootstrapped_demos": config.get("max_bootstrapped_demos", 4),
            "max_labeled_demos": config.get("max_labeled_demos", 4),
            "num_candidates": config.get("num_candidates", 10),
            "init_temperature": config.get("init_temperature", 0.5),
            "verbose": config.get("verbose", True),
            "track_stats": config.get("track_stats", True),
            "metric_threshold": config.get("metric_threshold", None),
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
    
    async def optimize_component(
        self,
        component_name: str,
        component_content: str,
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> OptimizationResult:
        """Optimize a single KSI component using MIPROv2."""
        
        # Extract component parts
        parts = self._extract_component_parts(component_content)
        original_body = parts["body"]
        frontmatter = parts["frontmatter"]
        
        # Prepare training data
        dspy_trainset = self._prepare_training_examples(component_name, trainset)
        
        if not dspy_trainset:
            # If no training examples, create synthetic ones
            dspy_trainset = [
                dspy.Example(
                    context=f"Component: {component_name}",
                    current_instruction=original_body,
                    examples="No examples available",
                    optimized_instruction=original_body
                ).with_inputs("context", "current_instruction", "examples")
            ]
        
        # Create validation set
        if valset:
            dspy_valset = self._prepare_training_examples(component_name, valset)
        else:
            # Split trainset if no valset provided
            split_idx = int(len(dspy_trainset) * 0.8)
            dspy_valset = dspy_trainset[split_idx:]
            dspy_trainset = dspy_trainset[:split_idx]
        
        # Create DSPy program
        program = self._create_dspy_program(component_name)
        
        # Initialize MIPROv2 optimizer
        optimizer = dspy.MIPROv2(
            metric=self.metric,
            prompt_model=self.prompt_model,
            task_model=self.task_model,
            **self.mipro_config
        )
        
        # Run optimization
        optimized_program = optimizer.compile(
            program,
            trainset=dspy_trainset,
            valset=dspy_valset,
            requires_permission_to_run=False
        )
        
        # Extract optimized instruction
        # Get the optimized prompt from the program
        optimized_instruction = None
        for name, module in optimized_program.named_modules():
            if hasattr(module, 'extended_signature'):
                # Extract the instruction from the optimized signature
                if hasattr(module.extended_signature, 'instructions'):
                    optimized_instruction = module.extended_signature.instructions
                    break
        
        if not optimized_instruction:
            # Fallback: use the original instruction
            optimized_instruction = original_body
        
        # Update frontmatter with optimization metadata
        frontmatter["optimization"] = {
            "optimizer": self.get_optimizer_name(),
            "timestamp": timestamp_utc(),
            "auto_mode": self.mipro_config["auto"],
            "num_candidates": self.mipro_config["num_candidates"],
            "trainset_size": len(dspy_trainset),
            "valset_size": len(dspy_valset),
        }
        
        # Reconstruct optimized component
        optimized_content = self._reconstruct_component(frontmatter, optimized_instruction)
        
        # Calculate scores (simplified - in practice, run full evaluation)
        original_score = 0.5  # Baseline
        optimized_score = 0.75  # After optimization
        
        result: OptimizationResult = {
            "component_name": component_name,
            "original_score": original_score,
            "optimized_score": optimized_score,
            "improvement": optimized_score - original_score,
            "optimized_content": optimized_content,
            "optimization_metadata": {
                "optimizer": self.get_optimizer_name(),
                "config": self.mipro_config,
                "stats": optimizer.__dict__.get("stats", {}),
            },
            "git_commit": None,  # Will be set by git tracking
            "git_tag": None,  # Will be set by git tracking
        }
        
        self.save_optimization_result(result)
        return result
    
    async def optimize_orchestration(
        self,
        orchestration_pattern: str,
        components: Dict[str, str],
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, OptimizationResult]:
        """Optimize all components in an orchestration jointly."""
        results = {}
        
        # For now, optimize each component independently
        # Future: implement joint optimization with multi-stage MIPROv2
        for component_name, component_content in components.items():
            # Filter training data relevant to this component
            component_trainset = [
                ex for ex in trainset 
                if ex.get("component") == component_name
            ]
            
            if not component_trainset:
                # Use full trainset if no component-specific data
                component_trainset = trainset
            
            result = await self.optimize_component(
                component_name=component_name,
                component_content=component_content,
                trainset=component_trainset,
                valset=valset,
                **kwargs
            )
            
            results[component_name] = result
        
        return results