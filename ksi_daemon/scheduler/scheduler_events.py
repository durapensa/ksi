#!/usr/bin/env python3
"""
Scheduler event registration module.

This module ensures the scheduler service handlers are loaded and registered
when the KSI daemon starts up.
"""

# Import all handlers from scheduler_service
# The @event_handler decorators will auto-register them
from .scheduler_service import (
    handle_schedule_once,
    handle_cancel,
    handle_list,
    handle_status
)