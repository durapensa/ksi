#!/usr/bin/env python3
"""
[DEPRECATED] Legacy response models file

This file is maintained for backward compatibility only.
All models have been migrated to the new protocols/ directory structure.
New code should import from daemon.protocols instead.
"""

# Re-export everything from the new protocols module for backward compatibility
from .protocols import *

# Legacy warning for developers
import warnings
warnings.warn(
    "response_models.py is deprecated. Import from daemon.protocols instead.",
    DeprecationWarning,
    stacklevel=2
)