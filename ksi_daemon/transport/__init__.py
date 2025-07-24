"""
KSI daemon transport layer.

Provides pluggable transport mechanisms for client connections.
"""

from typing import Dict, Any, List
import asyncio
import importlib
import logging

from ksi_common.config import config
from ksi_common.task_management import create_tracked_task

logger = logging.getLogger(__name__)

# Active transport tasks
transport_tasks: List[asyncio.Task] = []


async def start_transports() -> None:
    """Start all configured transports."""
    enabled = config.enabled_transports
    logger.info(f"Starting transports: {enabled}")
    
    # Map transport names to module names
    transport_modules = {
        "unix": "unix_socket",
        "websocket": "websocket"
    }
    
    for transport_name in enabled:
        try:
            # Get actual module name
            module_name = transport_modules.get(transport_name, transport_name)
            
            # Import transport module dynamically
            module = importlib.import_module(f"ksi_daemon.transport.{module_name}")
            
            # Start the transport
            if hasattr(module, 'start_server'):
                task = create_tracked_task("transport", module.start_server(), task_name=f"{transport_name}_server")
                transport_tasks.append(task)
                logger.info(f"Started {transport_name} transport")
            else:
                logger.warning(f"Transport {transport_name} has no start_server function")
                
        except ImportError as e:
            logger.error(f"Failed to import transport {transport_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to start transport {transport_name}: {e}")


async def stop_transports() -> None:
    """Stop all active transports."""
    logger.info("Stopping all transports...")
    
    # Map transport names to module names
    transport_modules = {
        "unix": "unix_socket",
        "websocket": "websocket"
    }
    
    # Import all enabled transports and call their stop functions
    for transport_name in config.enabled_transports:
        try:
            # Get actual module name
            module_name = transport_modules.get(transport_name, transport_name)
            module = importlib.import_module(f"ksi_daemon.transport.{module_name}")
            if hasattr(module, 'stop_server'):
                await module.stop_server()
                logger.info(f"Stopped {transport_name} transport")
        except Exception as e:
            logger.error(f"Error stopping transport {transport_name}: {e}")
    
    # Cancel all transport tasks
    for task in transport_tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    transport_tasks.clear()
    logger.info("All transports stopped")


def get_transport_info() -> Dict[str, Any]:
    """Get information about all available transports."""
    info = {
        "enabled": config.enabled_transports,
        "available": ["unix", "websocket"],
        "details": {}
    }
    
    # Map transport names to module names
    transport_modules = {
        "unix": "unix_socket",
        "websocket": "websocket"
    }
    
    # Get info from each transport module
    for transport_name in ["unix", "websocket"]:
        try:
            module_name = transport_modules.get(transport_name, transport_name)
            module = importlib.import_module(f"ksi_daemon.transport.{module_name}")
            if hasattr(module, 'MODULE_INFO'):
                info["details"][transport_name] = module.MODULE_INFO
        except ImportError:
            info["details"][transport_name] = {"status": "not available"}
    
    return info