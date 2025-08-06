"""KSI Optimization Module - Automated prompt and component optimization."""

from ksi_daemon.optimization.frameworks.base_optimizer import BaseOptimizer, OptimizationResult
from ksi_daemon.optimization.frameworks.dspy_mipro_adapter import DSPyMIPROAdapter
from ksi_daemon.optimization.frameworks.dspy_simba_adapter import DSPySIMBAAdapter

# Import integrated optimization events  
from ksi_daemon.optimization import integrated_optimization_events

__all__ = [
    "BaseOptimizer", 
    "OptimizationResult",
    "DSPyMIPROAdapter",
    "DSPySIMBAAdapter"
]