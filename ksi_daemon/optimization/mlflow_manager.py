"""MLflow tracking server management for KSI optimization service."""

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("mlflow_manager")

# MLflow server process
_mlflow_server_process: Optional[subprocess.Popen] = None
_mlflow_tracking_uri: Optional[str] = None


def get_mlflow_config() -> Dict[str, Any]:
    """Get MLflow configuration."""
    # Use KSI's standard database directory
    db_path = config.db_dir / "mlflow.db"
    artifacts_dir = config.db_dir / "mlflow_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "backend_store_uri": f"sqlite:///{db_path}",
        "default_artifact_root": str(artifacts_dir),
        "host": "127.0.0.1",
        "port": config.mlflow_port if hasattr(config, 'mlflow_port') else 5001,
        "workers": 2,
        "gunicorn_opts": "--timeout 60"
    }


async def start_mlflow_server() -> str:
    """Start MLflow tracking server if not already running."""
    global _mlflow_server_process, _mlflow_tracking_uri
    
    if _mlflow_server_process and _mlflow_server_process.poll() is None:
        logger.info("MLflow server already running")
        return _mlflow_tracking_uri
    
    mlflow_config = get_mlflow_config()
    tracking_uri = f"http://{mlflow_config['host']}:{mlflow_config['port']}"
    
    # Check if MLflow is already running on this port
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((mlflow_config['host'], mlflow_config['port']))
    sock.close()
    
    if result == 0:
        logger.info(f"MLflow server already running on port {mlflow_config['port']}")
        _mlflow_tracking_uri = tracking_uri
        return tracking_uri
    
    # Start MLflow server
    cmd = [
        "mlflow", "server",
        "--backend-store-uri", mlflow_config["backend_store_uri"],
        "--default-artifact-root", mlflow_config["default_artifact_root"],
        "--host", mlflow_config["host"],
        "--port", str(mlflow_config["port"]),
        "--workers", str(mlflow_config["workers"]),
        "--gunicorn-opts", mlflow_config["gunicorn_opts"]
    ]
    
    logger.info(f"Starting MLflow server on {tracking_uri}")
    
    try:
        # Start in background, suppress output to avoid log clutter
        _mlflow_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ
        )
        
        # Wait for server to start
        max_wait = 10  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((mlflow_config['host'], mlflow_config['port']))
            sock.close()
            
            if result == 0:
                logger.info(f"MLflow server started successfully on {tracking_uri}")
                _mlflow_tracking_uri = tracking_uri
                return tracking_uri
            
            await asyncio.sleep(0.5)
        
        # If we get here, server didn't start
        raise RuntimeError(f"MLflow server failed to start within {max_wait} seconds")
        
    except Exception as e:
        logger.error(f"Failed to start MLflow server: {e}")
        if _mlflow_server_process:
            _mlflow_server_process.terminate()
            _mlflow_server_process = None
        raise


async def stop_mlflow_server():
    """Stop MLflow tracking server."""
    global _mlflow_server_process
    
    if _mlflow_server_process and _mlflow_server_process.poll() is None:
        logger.info("Stopping MLflow server")
        _mlflow_server_process.terminate()
        
        # Wait for graceful shutdown
        try:
            _mlflow_server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("MLflow server didn't stop gracefully, forcing kill")
            _mlflow_server_process.kill()
            _mlflow_server_process.wait()
        
        _mlflow_server_process = None
        logger.info("MLflow server stopped")


def configure_dspy_autologging():
    """Configure DSPy autologging with MLflow."""
    try:
        import mlflow
        import mlflow.dspy
        
        # Set tracking URI
        if _mlflow_tracking_uri:
            mlflow.set_tracking_uri(_mlflow_tracking_uri)
            logger.info(f"MLflow tracking URI set to {_mlflow_tracking_uri}")
        
        # Enable DSPy autologging
        mlflow.dspy.autolog(
            log_compiles=True,  # Log optimization process
            log_evals=True,     # Log evaluation results
            log_traces_from_compile=True  # Log traces during optimization
        )
        
        # Set experiment name
        mlflow.set_experiment("ksi_optimizations")
        
        logger.info("DSPy autologging configured with MLflow")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure DSPy autologging: {e}")
        return False


async def get_active_optimization_runs() -> Dict[str, Any]:
    """Get currently active optimization runs from MLflow by KSI optimization IDs."""
    try:
        import mlflow
        # Get currently active KSI optimizations via event system
        from ksi_daemon.core.event_emitter import get_event_emitter
        event_emitter = get_event_emitter()
        
        result = await event_emitter("optimization:list", {})
        
        # Extract active optimization IDs from the event response
        optimizations = result.get("optimizations", [])
        active_opt_ids = [
            opt.get("optimization_id") for opt in optimizations
            if opt.get("status") in ["pending", "optimizing"] and opt.get("optimization_id")
        ]
        
        if not active_opt_ids:
            return {"active_runs": 0, "runs": []}
        
        runs_data = []
        
        # Search MLflow for runs with each active KSI optimization ID
        for opt_id in active_opt_ids:
            try:
                # Search for MLflow runs tagged with this KSI optimization ID
                filter_string = f"tags.ksi_optimization_id = '{opt_id}'"
                runs = mlflow.search_runs(
                    experiment_names=["ksi_optimizations"],
                    filter_string=filter_string,
                    max_results=1,
                    order_by=["attributes.start_time DESC"]
                )
                
                if not runs.empty:
                    run = runs.iloc[0]
                    run_data = {
                        "run_id": run["run_id"],
                        "ksi_optimization_id": opt_id,
                        "status": run["status"],
                        "start_time": run["start_time"],
                        "metrics": {},
                        "params": {}
                    }
                    
                    # Extract metrics and params
                    for col in run.index:
                        if col.startswith("metrics."):
                            metric_name = col.replace("metrics.", "")
                            run_data["metrics"][metric_name] = run[col]
                        elif col.startswith("params."):
                            param_name = col.replace("params.", "")
                            run_data["params"][param_name] = run[col]
                    
                    runs_data.append(run_data)
                    
            except Exception as e:
                logger.debug(f"Could not find MLflow run for optimization {opt_id}: {e}")
                continue
        
        return {
            "active_runs": len(runs_data),
            "runs": runs_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get active optimization runs from MLflow: {e}")
        return {"error": str(e)}


async def get_optimization_progress(run_id: str) -> Dict[str, Any]:
    """Get detailed progress for a specific optimization run."""
    try:
        import mlflow
        from mlflow import MlflowClient
        
        # Set tracking URI to KSI's MLflow server
        mlflow.set_tracking_uri("http://127.0.0.1:5001")
        client = MlflowClient()
        
        # Get run details
        run = client.get_run(run_id)
        
        # Get metric history for key metrics
        metric_names = ["score", "trial", "best_score", "avg_score"]
        metric_history = {}
        
        for metric_name in metric_names:
            try:
                history = client.get_metric_history(run_id, metric_name)
                if history:
                    metric_history[metric_name] = [
                        {"step": m.step, "value": m.value, "timestamp": m.timestamp}
                        for m in history
                    ]
            except Exception:
                pass  # Metric might not exist
        
        return {
            "run_id": run_id,
            "status": run.info.status,
            "start_time": run.info.start_time,
            "end_time": run.info.end_time,
            "metrics": run.data.metrics,
            "params": run.data.params,
            "metric_history": metric_history,
            "tags": run.data.tags
        }
        
    except Exception as e:
        logger.error(f"Failed to get optimization progress: {e}")
        return {"error": str(e)}


def get_mlflow_ui_url() -> Optional[str]:
    """Get MLflow UI URL if server is running."""
    if _mlflow_tracking_uri:
        return _mlflow_tracking_uri
    return None