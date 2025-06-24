#!/usr/bin/env python3
"""
Shutdown Plugin

Handles graceful shutdown of the KSI daemon.
Responds to system:shutdown events and coordinates shutdown process.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from ...plugin_base import EventHandlerPlugin, hookimpl
from ...plugin_types import EventContext

logger = logging.getLogger(__name__)


class ShutdownPlugin(EventHandlerPlugin):
    """Plugin that handles daemon shutdown."""
    
    def __init__(self):
        super().__init__(
            name="shutdown_handler",
            handled_events=["system:shutdown"],
            version="1.0.0",
            description="Graceful shutdown handler"
        )
        self.shutdown_in_progress = False
    
    def handle_event(self, event_name: str, data: Dict[str, Any], 
                    context: EventContext) -> Optional[Dict[str, Any]]:
        """Handle shutdown requests."""
        if event_name != "system:shutdown" or self.shutdown_in_progress:
            return None
        
        self.shutdown_in_progress = True
        
        # Extract shutdown parameters
        reason = data.get("reason", "manual")
        grace_period = data.get("grace_period", 5.0)
        save_state = data.get("save_state", True)
        
        logger.info(f"Shutdown requested: reason={reason}, grace_period={grace_period}s")
        
        # Schedule shutdown
        asyncio.create_task(self._perform_shutdown(context, reason, grace_period, save_state))
        
        return {
            "status": "accepted",
            "message": f"Shutdown initiated with {grace_period}s grace period"
        }
    
    async def _perform_shutdown(self, context: EventContext, reason: str, 
                               grace_period: float, save_state: bool):
        """Perform the actual shutdown sequence."""
        try:
            # Emit pre-shutdown event
            await context.emit("system:pre_shutdown", {
                "reason": reason,
                "save_state": save_state
            })
            
            # Give plugins time to clean up
            logger.info(f"Waiting {grace_period}s for graceful shutdown...")
            await asyncio.sleep(grace_period)
            
            # Save state if requested
            if save_state:
                logger.info("Saving daemon state...")
                await context.emit("system:save_state", {})
            
            # Emit final shutdown event
            await context.emit("system:shutdown_complete", {
                "reason": reason
            })
            
            # Set daemon shutdown event if available
            if hasattr(context, '_plugin_manager'):
                pm = context._plugin_manager
                if hasattr(pm, 'config') and 'daemon' in pm.config:
                    # This is a bit hacky - in real implementation we'd have
                    # a cleaner way to signal the daemon
                    import signal
                    import os
                    os.kill(os.getpid(), signal.SIGTERM)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    @hookimpl
    def ksi_register_commands(self) -> Dict[str, str]:
        """Register legacy command mapping."""
        return {
            "SHUTDOWN": "system:shutdown"
        }
    
    @hookimpl
    def ksi_metrics_collected(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Add shutdown status to metrics."""
        metrics["shutdown"] = {
            "in_progress": self.shutdown_in_progress
        }
        return metrics


# Plugin instance
plugin = ShutdownPlugin()