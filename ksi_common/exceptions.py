"""Common exception classes for KSI.

Provides a hierarchy of exceptions used across all KSI components.
"""

from typing import Optional, Dict, Any


class KSIError(Exception):
    """Base exception for all KSI-related errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for protocol responses."""
        result = {"message": self.message}
        if self.code:
            result["code"] = self.code
        if self.details:
            result["details"] = self.details
        return result


class KSIConnectionError(KSIError):
    """Raised when connection to daemon fails."""
    
    def __init__(self, message: str = "Failed to connect to daemon", **kwargs):
        super().__init__(message, code="CONNECTION_ERROR", **kwargs)


class ProtocolError(KSIError):
    """Raised when protocol violations occur."""
    
    def __init__(self, message: str = "Protocol error", **kwargs):
        super().__init__(message, code="PROTOCOL_ERROR", **kwargs)


class KSITimeoutError(KSIError):
    """Raised when operations timeout."""
    
    def __init__(self, message: str = "Operation timed out", **kwargs):
        super().__init__(message, code="TIMEOUT_ERROR", **kwargs)


class AuthenticationError(KSIError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, code="AUTH_ERROR", **kwargs)


class PermissionError(KSIError):
    """Raised when permission is denied."""
    
    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(message, code="PERMISSION_ERROR", **kwargs)


class ResourceNotFoundError(KSIError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(message, code="NOT_FOUND", **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class InvalidRequestError(KSIError):
    """Raised when request is invalid."""
    
    def __init__(self, message: str = "Invalid request", **kwargs):
        super().__init__(message, code="INVALID_REQUEST", **kwargs)


class DaemonError(KSIError):
    """Raised when daemon encounters an error."""
    
    def __init__(self, message: str = "Daemon error", **kwargs):
        super().__init__(message, code="DAEMON_ERROR", **kwargs)


class ModuleError(KSIError):
    """Raised when module encounters an error."""
    
    def __init__(self, module_name: str, message: str, **kwargs):
        full_message = f"Module '{module_name}' error: {message}"
        super().__init__(full_message, code="MODULE_ERROR", **kwargs)
        self.module_name = module_name


# Backward compatibility alias
PluginError = ModuleError