#!/usr/bin/env python3
"""
Command handlers package - Individual command implementations
Each command is a separate class using the command registry pattern
"""

# Import all command handlers to ensure registration
# These will be added as we migrate commands from json_handlers.py

from .cleanup import CleanupHandler
from .spawn import SpawnHandler
from .health_check import HealthCheckHandler
from .get_commands import GetCommandsHandler
from .get_processes import GetProcessesHandler

__all__ = [
    'CleanupHandler', 
    'SpawnHandler',
    'HealthCheckHandler',
    'GetCommandsHandler',
    'GetProcessesHandler'
]