#!/usr/bin/env python3
"""
Transformer Checkpoint Handlers - Integrate transformer state with checkpoint system.

Provides checkpoint/restore functionality for transformer configurations and loaded states.
"""

from typing import Dict, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger
from ksi_common.service_transformer_manager import get_transformer_manager
from ksi_common.event_response_builder import event_response_builder

logger = get_bound_logger("transformer_checkpoint", version="1.0.0")


@event_handler("checkpoint:collect")
async def collect_transformer_checkpoint(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect transformer state for checkpoint."""
    try:
        manager = get_transformer_manager()
        checkpoint_data = await manager.collect_checkpoint_data()
        
        logger.info(f"Collected transformer checkpoint data for {len(checkpoint_data.get('loaded_transformers', {}))} services")
        
        return event_response_builder({
            "transformer_state": checkpoint_data
        }, context)
    except Exception as e:
        logger.error(f"Failed to collect transformer checkpoint: {e}")
        return event_response_builder({
            "transformer_state": {}
        }, context)


@event_handler("checkpoint:restore")
async def restore_transformer_checkpoint(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restore transformer state from checkpoint."""
    checkpoint_data = data.get("transformer_state", {})
    
    if not checkpoint_data:
        logger.info("No transformer state in checkpoint to restore")
        return event_response_builder({"status": "no_transformer_state"}, context)
    
    try:
        manager = get_transformer_manager()
        await manager.restore_from_checkpoint(checkpoint_data)
        
        return event_response_builder({
            "status": "restored",
            "services_restored": len(checkpoint_data.get("service_configs", {}))
        }, context)
    except Exception as e:
        logger.error(f"Failed to restore transformer checkpoint: {e}")
        return event_response_builder({
            "status": "error",
            "error": str(e)
        }, context)