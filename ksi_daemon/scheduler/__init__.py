"""
Scheduler module for KSI daemon.

Provides event scheduling capabilities for delayed event execution.
"""

# The scheduler service registers its handlers via @event_handler decorators
# when scheduler_events.py is imported by daemon_core.py

__all__ = []