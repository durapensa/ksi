#!/usr/bin/env python3
"""
Async Utilities - Centralized async/sync coordination helpers

Provides utilities for consistent async/sync patterns across KSI.
"""

import asyncio
import functools
from typing import Any, Callable, TypeVar, Coroutine
from concurrent.futures import ThreadPoolExecutor

T = TypeVar('T')


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine from sync context.
    
    Consolidates the asyncio.run() pattern used throughout KSI.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
        
    Raises:
        Any exception raised by the coroutine
    """
    try:
        # Try to get current loop - if we're already in async context
        loop = asyncio.get_running_loop()
        # If we're in an async context, we can't use asyncio.run()
        # This suggests the caller should be redesigned to be async
        raise RuntimeError(
            "run_sync() called from within async context. "
            "Consider making the calling function async instead."
        )
    except RuntimeError:
        # No event loop running - safe to use asyncio.run()
        return asyncio.run(coro)


def async_to_sync(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """
    Decorator to convert an async function to sync.
    
    Use sparingly - prefer keeping functions async when possible.
    
    Args:
        func: Async function to wrap
        
    Returns:
        Sync function that runs the async function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        return run_sync(coro)
    
    return wrapper


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """
    Ensure an event loop is available, creating one if needed.
    
    Returns:
        The current or newly created event loop
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # No loop running, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def run_in_thread_pool(func: Callable[..., T], *args, **kwargs) -> Coroutine[Any, Any, T]:
    """
    Run a sync function in a thread pool from async context.
    
    Args:
        func: Sync function to run
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Coroutine that will return the function result
    """
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(ThreadPoolExecutor(), functools.partial(func, *args, **kwargs))


# Main entry point helper
def main_entry_point(main_func: Callable[[], Coroutine[Any, Any, Any]]) -> None:
    """
    Standard entry point for async main functions.
    
    Handles KeyboardInterrupt gracefully and provides consistent error handling.
    
    Args:
        main_func: Async main function to run
    """
    try:
        asyncio.run(main_func())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        raise