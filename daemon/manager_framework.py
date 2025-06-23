#!/usr/bin/env python3
"""
Base Manager Class - Common functionality for all daemon managers

Provides common patterns for:
- State serialization/deserialization
- Error handling
- Logging setup
- Directory management
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Callable
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

T = TypeVar('T', bound='BaseManager')


def with_error_handling(operation_name: str = None):
    """Decorator for standardized error handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            op_name = operation_name or func.__name__
            try:
                result = func(self, *args, **kwargs)
                self.logger.debug(f"{op_name} completed successfully")
                return result
            except Exception as e:
                self.logger.error(f"{op_name} failed", 
                                error_type=type(e).__name__, 
                                error_message=str(e),
                                exc_info=True)
                raise
        return wrapper
    return decorator


def require_manager(*manager_names: str):
    """Decorator to check if required managers are available"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for manager_name in manager_names:
                if not hasattr(self, manager_name) or getattr(self, manager_name) is None:
                    self.logger.warning(f"{func.__name__} requires {manager_name} but it's not available")
                    return None
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def log_operation(level: str = "info"):
    """Decorator for consistent operation logging"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            log_func = getattr(self.logger, level)
            log_func(f"Starting {func.__name__}", args=args, kwargs=kwargs)
            result = await func(self, *args, **kwargs)
            log_func(f"Completed {func.__name__}", result=result)
            return result
        
        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            log_func = getattr(self.logger, level)
            log_func(f"Starting {func.__name__}", args=args, kwargs=kwargs)
            result = func(self, *args, **kwargs)
            log_func(f"Completed {func.__name__}", result=result)
            return result
        
        # Return appropriate wrapper based on whether func is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator


class BaseManager(ABC):
    """Base class for all daemon managers"""
    
    def __init__(self, manager_name: str, required_dirs: Optional[list] = None):
        """
        Initialize base manager
        
        Args:
            manager_name: Name for logging context
            required_dirs: List of directories this manager needs
        """
        self.manager_name = manager_name
        self.logger = structlog.get_logger(manager_name)
        self.required_dirs = required_dirs or []
        
        # Ensure required directories exist
        self._ensure_directories()
        
        # Initialize in subclasses
        self._initialize()
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        for dir_path in self.required_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {dir_path}")
    
    @abstractmethod
    def _initialize(self):
        """Initialize manager-specific state - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize manager state for hot reload - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def deserialize_state(self, state: Dict[str, Any]):
        """Deserialize manager state from hot reload - must be implemented by subclasses"""
        pass
    
    @with_error_handling("save_json_file")
    def save_json_file(self, filepath: str, data: Any, indent: int = 2):
        """Save data to JSON file with error handling"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=indent)
    
    @with_error_handling("load_json_file")
    def load_json_file(self, filepath: str, default: Any = None) -> Any:
        """Load data from JSON file with error handling"""
        if not os.path.exists(filepath):
            return default
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @with_error_handling("append_jsonl")
    def append_jsonl(self, filepath: str, entry: Dict[str, Any]):
        """Append entry to JSONL file"""
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the manager's state for diagnostics"""
        return {
            'manager_name': self.manager_name,
            'state': self.serialize_state()
        }


class CleanupStrategy(ABC):
    """Base class for cleanup strategies"""
    
    @abstractmethod
    def cleanup(self, context: Dict[str, Any]) -> str:
        """Execute cleanup and return result message"""
        pass


class FileCleanupStrategy(CleanupStrategy):
    """Strategy for cleaning up files"""
    
    def __init__(self, directory: str, pattern: str, exclude: Optional[list] = None):
        self.directory = Path(directory)
        self.pattern = pattern
        self.exclude = exclude or []
    
    def cleanup(self, context: Dict[str, Any]) -> str:
        if not self.directory.exists():
            return f"No {self.directory} directory found"
        
        files_removed = 0
        for file_path in self.directory.glob(self.pattern):
            if file_path.name not in self.exclude and not file_path.is_symlink():
                file_path.unlink()
                files_removed += 1
        
        # Clean broken symlinks
        for file_path in self.directory.glob('*'):
            if file_path.is_symlink() and not file_path.exists():
                file_path.unlink()
                files_removed += 1
        
        return f"Removed {files_removed} files from {self.directory}"


class ManagerRegistry:
    """Registry for manager instances to enable cross-references"""
    
    _instance = None
    _managers: Dict[str, BaseManager] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, name: str, manager: BaseManager):
        """Register a manager instance"""
        cls._managers[name] = manager
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseManager]:
        """Get a manager instance by name"""
        return cls._managers.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseManager]:
        """Get all registered managers"""
        return cls._managers.copy()
    
    @classmethod
    def clear(cls):
        """Clear all registered managers"""
        cls._managers.clear()


def atomic_operation(operation_name: str = None):
    """Decorator for operations that should be atomic (all-or-nothing)"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            op_name = operation_name or func.__name__
            # Save current state
            state_backup = self.serialize_state()
            
            try:
                result = await func(self, *args, **kwargs)
                self.logger.info(f"Atomic operation {op_name} completed successfully")
                return result
            except Exception as e:
                # Restore state on failure
                self.logger.error(f"Atomic operation {op_name} failed, rolling back", 
                                error=str(e))
                self.deserialize_state(state_backup)
                raise
        
        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            op_name = operation_name or func.__name__
            # Save current state
            state_backup = self.serialize_state()
            
            try:
                result = func(self, *args, **kwargs)
                self.logger.info(f"Atomic operation {op_name} completed successfully")
                return result
            except Exception as e:
                # Restore state on failure
                self.logger.error(f"Atomic operation {op_name} failed, rolling back", 
                                error=str(e))
                self.deserialize_state(state_backup)
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator