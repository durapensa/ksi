#!/usr/bin/env python3
"""
Command handlers package - Individual command implementations
Each command is a separate class using the command registry pattern
"""

# Import all command handlers to ensure registration
# These will be added as we migrate commands from json_handlers.py

from .cleanup import CleanupHandler
from .spawn import SpawnHandler

__all__ = ['CleanupHandler', 'SpawnHandler']