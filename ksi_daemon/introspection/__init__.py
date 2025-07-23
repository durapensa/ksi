#!/usr/bin/env python3
"""
Introspection module for KSI

Provides tools for analyzing and understanding event flows,
correlations, and system behavior.
"""

# Import all handlers to ensure they register
from . import event_genealogy

__all__ = ['event_genealogy']