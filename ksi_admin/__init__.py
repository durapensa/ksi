"""
KSI Admin Library - Administrative and monitoring tools for KSI daemon.

This library provides administrative capabilities complementary to ksi_client:
- ksi_client: For agents participating in the system
- ksi_admin: For monitoring, controlling, and managing the system

No dependencies on ksi_client - completely standalone implementation.
"""

from .monitor import MonitorClient
from .metrics import MetricsClient
from .control import ControlClient
from .debug import DebugClient

__version__ = "0.1.0"
__all__ = [
    "MonitorClient",
    "MetricsClient", 
    "ControlClient",
    "DebugClient",
]