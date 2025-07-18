"""Base optimizer interface for KSI component optimization."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, TypedDict
from datetime import datetime
import json


class OptimizationResult(TypedDict):
    """Result from an optimization run."""
    component_name: str
    original_score: float
    optimized_score: float
    improvement: float
    optimized_content: str
    optimization_metadata: Dict[str, Any]
    git_commit: Optional[str]
    git_tag: Optional[str]


class ComponentMetrics(TypedDict):
    """Metrics collected for a component."""
    component_name: str
    metric_name: str
    value: float
    timestamp: str
    context: Optional[Dict[str, Any]]


class BaseOptimizer(ABC):
    """Abstract base class for component optimizers."""
    
    def __init__(self, metric: Callable, config: Optional[Dict[str, Any]] = None):
        """Initialize optimizer with a metric function and optional config."""
        self.metric = metric
        self.config = config or {}
        self.optimization_history: List[OptimizationResult] = []
    
    @abstractmethod
    async def optimize_component(
        self,
        component_name: str,
        component_content: str,
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> OptimizationResult:
        """Optimize a single component.
        
        Args:
            component_name: Name/path of the component (e.g., "personas/negotiator")
            component_content: Current component content (markdown with frontmatter)
            trainset: Training examples for optimization
            valset: Validation set for evaluation (if None, split from trainset)
            **kwargs: Additional optimizer-specific parameters
            
        Returns:
            OptimizationResult with optimized content and metadata
        """
        pass
    
    @abstractmethod
    async def optimize_orchestration(
        self,
        orchestration_pattern: str,
        components: Dict[str, str],
        trainset: List[Dict[str, Any]],
        valset: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, OptimizationResult]:
        """Optimize all components in an orchestration jointly.
        
        Args:
            orchestration_pattern: Name of the orchestration pattern
            components: Dict mapping component names to their content
            trainset: Training examples for optimization
            valset: Validation set for evaluation
            **kwargs: Additional optimizer-specific parameters
            
        Returns:
            Dict mapping component names to their optimization results
        """
        pass
    
    def save_optimization_result(self, result: OptimizationResult) -> None:
        """Save optimization result to history."""
        self.optimization_history.append(result)
    
    def get_optimization_history(
        self, 
        component_name: Optional[str] = None
    ) -> List[OptimizationResult]:
        """Get optimization history, optionally filtered by component."""
        if component_name:
            return [r for r in self.optimization_history if r["component_name"] == component_name]
        return self.optimization_history
    
    @abstractmethod
    def get_optimizer_name(self) -> str:
        """Return the name of this optimizer (e.g., 'MIPROv2', 'TextGrad')."""
        pass