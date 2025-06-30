#!/usr/bin/env python3
"""
Composition Events Plugin

Thin event handler wrapper that exposes composition index through events.
All actual functionality is provided by daemon infrastructure.
"""

from typing import Dict, Any, Optional
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata
from ksi_common.logging import get_logger

# Plugin metadata
plugin_metadata("composition_events", version="1.0.0", 
                description="Event handlers for composition indexing")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("composition_events")
composition_index = None

# Plugin info
PLUGIN_INFO = {
    "name": "composition_events",
    "version": "1.0.0",
    "description": "Event handlers for composition indexing"
}


@hookimpl
def ksi_plugin_context(context):
    """Receive infrastructure from daemon context."""
    global composition_index
    
    composition_index = context.get("composition_index")
    
    if composition_index:
        logger.info("Composition events plugin connected to composition index")
    else:
        logger.error("Composition index not available in context")


@hookimpl(trylast=True)  # Run after state infrastructure is ready
def ksi_startup(config):
    """Initialize composition index on startup."""
    if composition_index:
        try:
            # Rebuild index on startup
            indexed_count = composition_index.rebuild_index()
            logger.info(f"Composition index rebuilt: {indexed_count} compositions")
            return {"composition_index_rebuilt": indexed_count}
        except Exception as e:
            logger.error(f"Failed to rebuild composition index: {e}")
    return None


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle composition-related events."""
    
    if not composition_index:
        return {"error": "Composition index infrastructure not available"}
    
    # Composition discovery
    if event_name == "composition:discover":
        return handle_discover(data)
    
    # Get composition path
    elif event_name == "composition:get_path":
        return handle_get_path(data)
    
    # Get composition metadata
    elif event_name == "composition:get_metadata":
        return handle_get_metadata(data)
    
    # Rebuild index
    elif event_name == "composition:rebuild_index":
        return handle_rebuild_index(data)
    
    # Index single file
    elif event_name == "composition:index_file":
        return handle_index_file(data)
    
    return None


def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle composition discovery."""
    try:
        # Use composition index to discover
        results = composition_index.discover(data)
        
        return {
            "status": "success",
            "compositions": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Composition discovery failed: {e}")
        return {"error": str(e)}


def handle_get_path(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get composition path."""
    full_name = data.get("full_name")
    
    if not full_name:
        return {"error": "full_name is required"}
    
    try:
        path = composition_index.get_path(full_name)
        
        if path:
            return {
                "status": "success",
                "full_name": full_name,
                "path": str(path),
                "found": True
            }
        else:
            return {
                "status": "not_found",
                "full_name": full_name,
                "found": False
            }
    except Exception as e:
        logger.error(f"Failed to get composition path: {e}")
        return {"error": str(e)}


def handle_get_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get composition metadata."""
    full_name = data.get("full_name")
    
    if not full_name:
        return {"error": "full_name is required"}
    
    try:
        metadata = composition_index.get_metadata(full_name)
        
        if metadata:
            return {
                "status": "success",
                "full_name": full_name,
                "metadata": metadata,
                "found": True
            }
        else:
            return {
                "status": "not_found",
                "full_name": full_name,
                "found": False
            }
    except Exception as e:
        logger.error(f"Failed to get composition metadata: {e}")
        return {"error": str(e)}


def handle_rebuild_index(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle rebuild composition index."""
    repository_id = data.get("repository_id", "local")
    
    try:
        indexed_count = composition_index.rebuild_index(repository_id)
        
        return {
            "status": "success",
            "repository_id": repository_id,
            "indexed_count": indexed_count
        }
    except Exception as e:
        logger.error(f"Failed to rebuild composition index: {e}")
        return {"error": str(e)}


def handle_index_file(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle index single composition file."""
    file_path = data.get("file_path")
    
    if not file_path:
        return {"error": "file_path is required"}
    
    try:
        from pathlib import Path
        path = Path(file_path)
        
        success = composition_index.index_composition_file(path)
        
        return {
            "status": "success" if success else "failed",
            "file_path": file_path,
            "indexed": success
        }
    except Exception as e:
        logger.error(f"Failed to index composition file: {e}")
        return {"error": str(e)}


# Module-level marker for plugin discovery
ksi_plugin = True