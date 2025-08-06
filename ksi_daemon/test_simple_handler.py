#!/usr/bin/env python3
"""
Simple test handler to verify data is received correctly.
"""

from typing import Dict, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import success_response
import logging

logger = logging.getLogger(__name__)


@event_handler("test:simple")
async def handle_simple_test(data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Simple test handler that logs what it receives."""
    logger.info(f"test:simple received data type: {type(data)}")
    logger.info(f"test:simple received data value: {data}")
    logger.info(f"test:simple received context type: {type(context)}")
    
    # Ensure data is a dictionary
    if not isinstance(data, dict):
        logger.error(f"test:simple received non-dict data: {type(data)} = {data}")
        # Convert to dict if possible
        if isinstance(data, str):
            # If it's a context reference, wrap it
            data = {"_raw_data": data}
        else:
            data = {}
    
    return success_response({
        "test": "simple",
        "received_type": str(type(data)),
        "has_context": context is not None
    })