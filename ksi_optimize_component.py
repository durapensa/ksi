#!/usr/bin/env python3
"""Standalone script for running DSPy component optimization in subprocess."""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

# Add KSI modules to path
ksi_root = Path(__file__).parent
sys.path.insert(0, str(ksi_root))

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.optimization.frameworks.dspy_adapter import DSPyMIPROAdapter
from ksi_daemon.optimization.frameworks.litellm_dspy_adapter import configure_dspy_with_litellm

logger = get_bound_logger("optimize_component")


def load_component_from_file(component_file: str) -> str:
    """Load component content from file."""
    try:
        with open(component_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Failed to load component from file {component_file}: {e}")


def save_optimized_content_to_file(component_name: str, content: str, metadata: dict, result_file: str, improvement: float = 0.0):
    """Save optimized component content to the specified result file."""
    import json
    
    result_data = {
        "component_name": component_name,
        "optimized_content": content,
        "metadata": metadata,
        "improvement": improvement
    }
    
    with open(result_file, 'w') as f:
        json.dump(result_data, f, indent=2)
    
    logger.info(f"Saved optimization result to {result_file}")
    return result_file


def configure_mlflow(opt_id: str, component_name: str):
    """Configure MLflow for this optimization run."""
    try:
        import mlflow
        import mlflow.dspy
        
        # Set tracking URI to KSI MLflow server
        mlflow.set_tracking_uri("http://127.0.0.1:5001")
        
        # Set experiment
        mlflow.set_experiment("ksi_optimizations")
        
        # Start run with KSI tags
        mlflow.start_run()
        mlflow.set_tag("ksi_optimization_id", opt_id)
        mlflow.set_tag("ksi_component", component_name)
        mlflow.set_tag("ksi_optimizer", "DSPy-MIPROv2")
        mlflow.set_tag("ksi_subprocess", "true")
        
        # Enable DSPy autologging
        mlflow.dspy.autolog(
            log_compiles=True,
            log_evals=True,
            log_traces_from_compile=True
        )
        
        logger.info(f"MLflow configured for optimization {opt_id}")
        return True
        
    except Exception as e:
        logger.warning(f"Could not configure MLflow: {e}")
        return False


def log_progress(opt_id: str, status: str, **kwargs):
    """Log optimization progress (events will be handled by main process)."""
    logger.info(f"Optimization {opt_id} progress: {status}", **kwargs)


def create_minimal_metric():
    """Create a simple metric for optimization."""
    def simple_effectiveness_metric(example, prediction, trace=None):
        """Simple metric based on response completeness and structure."""
        if not hasattr(prediction, 'answer') and not hasattr(prediction, 'response'):
            return 0.0
        
        # Get response content
        response = getattr(prediction, 'answer', getattr(prediction, 'response', ''))
        response_str = str(response)
        
        score = 0.0
        
        # Length-based scoring (reasonable response length)
        if 50 <= len(response_str) <= 500:
            score += 0.4
        elif len(response_str) > 20:
            score += 0.2
        
        # Structure scoring (contains JSON-like structure)
        if '{' in response_str and '}' in response_str:
            score += 0.3
        
        # Completeness scoring (not truncated)
        if not response_str.endswith('...'):
            score += 0.3
        
        return min(1.0, score)
    
    return simple_effectiveness_metric


async def run_optimization(args):
    """Run the DSPy optimization."""
    opt_id = args.opt_id
    component_name = args.component
    config_data = json.loads(args.config)
    
    logger.info(f"Starting optimization {opt_id} for {component_name}")
    
    # Configure MLflow
    mlflow_enabled = configure_mlflow(opt_id, component_name)
    
    try:
        # Log initialization
        log_progress(opt_id, "loading_component")
        
        # Load component content from file
        if hasattr(args, 'component_file') and args.component_file:
            component_content = load_component_from_file(args.component_file)
            logger.info(f"Loaded component {component_name} from file")
        else:
            raise ValueError("Component file path required for subprocess optimization")
        
        # Configure DSPy
        log_progress(opt_id, "configuring_dspy")
        
        models = configure_dspy_with_litellm(
            prompt_model=config.optimization_prompt_model,
            task_model=config.optimization_task_model
        )
        
        # Create metric
        metric = create_minimal_metric()
        
        # Create adapter
        log_progress(opt_id, "initializing_optimizer")
        
        adapter = DSPyMIPROAdapter(
            metric=metric,
            prompt_model=models.get("prompt_model"),
            task_model=models.get("task_model"),
            config=config_data
        )
        
        # Prepare minimal training data (DSPy needs some examples)
        trainset = []  # Empty for zero-shot
        valset = []    # Empty for zero-shot
        
        # Run optimization
        log_progress(opt_id, "optimizing")
        
        result = await adapter.optimize_component(
            component_name=component_name,
            component_content=component_content,
            trainset=trainset,
            valset=valset,
            opt_id=opt_id
        )
        
        # Save optimized result to file
        log_progress(opt_id, "saving_result")
        
        optimization_metadata = {
            "optimization": {
                "optimizer": "DSPy-MIPROv2",
                "timestamp": timestamp_utc(),
                "opt_id": opt_id,
                "config": config_data,
                "mlflow_enabled": mlflow_enabled
            }
        }
        
        save_optimized_content_to_file(
            component_name, 
            result["optimized_content"], 
            optimization_metadata,
            args.result_file,
            result.get("improvement", 0.0)
        )
        
        # Log completion
        logger.info(f"Optimization {opt_id} completed successfully: {result.get('improvement', 0):.3f} improvement")
        
        logger.info(f"Optimization {opt_id} completed successfully")
        
        # End MLflow run
        if mlflow_enabled:
            try:
                import mlflow
                mlflow.end_run()
                logger.info("MLflow run ended")
            except Exception as e:
                logger.warning(f"Could not end MLflow run: {e}")
        
        return 0
        
    except Exception as e:
        error_msg = f"Optimization failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Error already logged above
        pass
        
        # End MLflow run with failed status
        if mlflow_enabled:
            try:
                import mlflow
                mlflow.end_run(status="FAILED")
            except Exception:
                pass
        
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run DSPy component optimization")
    parser.add_argument("--opt-id", required=True, help="Optimization ID")
    parser.add_argument("--component", required=True, help="Component name to optimize")
    parser.add_argument("--component-file", required=True, help="Path to component content file")
    parser.add_argument("--result-file", required=True, help="Path to write optimization result")
    parser.add_argument("--config", required=True, help="JSON configuration for optimizer")
    parser.add_argument("--signature", help="Signature component name")
    parser.add_argument("--metric", help="Metric component name")
    
    args = parser.parse_args()
    
    try:
        # Run async optimization
        return asyncio.run(run_optimization(args))
    except KeyboardInterrupt:
        logger.info("Optimization cancelled by user")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())