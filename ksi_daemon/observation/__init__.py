"""
Observation system for agent event monitoring with historical analysis.
"""

from .observation_manager import should_observe_event, notify_observers

# Replay module is loaded for its event handlers but doesn't export functions
import ksi_daemon.observation.replay  # noqa

__all__ = ["should_observe_event", "notify_observers"]