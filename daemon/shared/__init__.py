#!/usr/bin/env python3
"""
Daemon Shared Package - Utilities shared between client and server

This package contains utilities that are used by both client and server code,
such as schemas, validation, and common data structures.

Usage:
    from daemon.shared import CommandValidator, CommandType
"""

# Import validation utilities (these are safe for both client and server)
try:
    from ..command_validator import CommandValidator, validate_command, validate_response
    from ..command_schemas import CommandType, COMMAND_MAPPINGS
except ImportError:
    # Graceful fallback if dependencies aren't available
    CommandValidator = None
    validate_command = None
    validate_response = None
    CommandType = None
    COMMAND_MAPPINGS = None

__all__ = [
    'CommandValidator',
    'validate_command', 
    'validate_response',
    'CommandType',
    'COMMAND_MAPPINGS'
]

# Version info
__version__ = "2.0"