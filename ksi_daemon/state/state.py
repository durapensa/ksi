#!/usr/bin/env python3
"""
State Events Plugin - Compatibility Bridge

This module now serves as a compatibility bridge to the unified core state module.
All state functionality has been moved to ksi_daemon.core.state for better organization.

This file remains to maintain backward compatibility for any direct imports,
but the actual functionality is provided by core.state.
"""

# Import all functionality from the unified core state module
from ksi_daemon.core.state import *

# Explicit imports for key components (for IDE and documentation clarity)
from ksi_daemon.core.state import (
    CoreStateManager,
    get_state_manager,
    initialize_state,
    
    # Event handlers (automatically registered when core.state is imported)
    handle_get,
    handle_set,
    handle_delete,
    handle_list,
    handle_async_get,
    handle_async_set,
    handle_async_delete,
    handle_async_push,
    handle_async_pop,
    handle_async_get_keys,
    handle_async_queue_length,
    
    # Type definitions
    StateSetData,
    StateGetData,
    StateDeleteData,
    StateListData,
)

# Legacy plugin info for compatibility
PLUGIN_INFO = {
    "name": "state_events",
    "version": "5.0.0",
    "description": "Compatibility bridge to core state management"
}