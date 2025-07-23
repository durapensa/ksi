"""KSI Optimization Module - Automated prompt and component optimization."""

from ksi_daemon.optimization.frameworks.base_optimizer import BaseOptimizer, OptimizationResult
from ksi_daemon.optimization.frameworks.dspy_adapter import DSPyMIPROAdapter

# Import evaluation service to register event handlers
from ksi_daemon.optimization import evaluation_service

__all__ = [
    "BaseOptimizer", 
    "OptimizationResult",
    "DSPyMIPROAdapter",
    "evaluation_service"
]