#!/usr/bin/env python3
"""
KSI Client Exceptions

Custom exceptions for the adaptive KSI client.
"""


class KSIError(Exception):
    """Base exception for all KSI client errors."""
    pass


class KSIConnectionError(KSIError):
    """Raised when connection to daemon fails."""
    pass


class KSIDaemonError(KSIError):
    """Raised when daemon operations fail."""
    pass


class KSITimeoutError(KSIError):
    """Raised when operations timeout."""
    pass


class KSIDiscoveryError(KSIError):
    """Raised when event discovery fails."""
    pass


class KSIValidationError(KSIError):
    """Raised when parameter validation fails."""
    pass


class KSIEventError(KSIError):
    """Raised when event execution fails."""
    
    def __init__(self, event_name: str, message: str, response: dict = None):
        self.event_name = event_name
        self.response = response
        super().__init__(f"Event {event_name} failed: {message}")


class KSIPermissionError(KSIError):
    """Raised when permission checks fail."""
    
    def __init__(self, profile: str, message: str):
        self.profile = profile
        super().__init__(f"Permission profile '{profile}' error: {message}")