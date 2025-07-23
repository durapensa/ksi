"""Minimal system component registry for runtime objects.

This module provides a lightweight registry for system components that need
to be shared across modules but cannot be serialized (event emitters, state
managers, etc.). These are runtime-only references, not persisted anywhere.

PYTHONIC CONTEXT REFACTOR: Prevents "max depth exceeded" errors by keeping
non-serializable objects out of the event system.
"""

from typing import Any, Dict, Optional
import threading


class SystemRegistry:
    """Simple thread-safe registry for system components."""
    
    _components: Dict[str, Any] = {}
    _lock = threading.Lock()
    
    @classmethod
    def set(cls, name: str, component: Any) -> None:
        """Register a system component.
        
        Args:
            name: Component name (e.g., "state_manager", "event_emitter")
            component: The component instance
        """
        with cls._lock:
            cls._components[name] = component
    
    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """Get a registered component.
        
        Args:
            name: Component name
            
        Returns:
            The component instance or None if not registered
        """
        with cls._lock:
            return cls._components.get(name)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all components. Used for testing and shutdown."""
        with cls._lock:
            cls._components.clear()