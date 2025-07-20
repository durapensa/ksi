"""Shared utilities for async operation management across KSI services.

Provides functional utilities for tracking async operations, managing background tasks,
thread pool execution, and emitting progress events - following patterns from the completion service.
"""

import asyncio
import functools
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Set, Callable, TypeVar
from ksi_common.timestamps import timestamp_utc
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("async_operations")

T = TypeVar('T')

# Global registries for operation tracking
active_operations: Dict[str, Dict[str, Any]] = {}
background_tasks: Dict[str, asyncio.Task] = {}
cleanup_tasks: Set[asyncio.Task] = set()

# Global thread pool executor - lazily initialized
_thread_pool_executor: Optional[ThreadPoolExecutor] = None


def generate_operation_id(prefix: str = "op") -> str:
    """Generate a unique operation ID with optional prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def start_operation(
    operation_id: Optional[str] = None,
    operation_type: str = "default", 
    service_name: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Start tracking a new async operation.
    
    Args:
        operation_id: Optional ID, will be generated if not provided
        operation_type: Type of operation (e.g., "optimization", "completion")
        service_name: Name of the service starting the operation
        metadata: Additional operation metadata
        
    Returns:
        The operation ID (generated or provided)
    """
    if not operation_id:
        operation_id = generate_operation_id(service_name)
    
    active_operations[operation_id] = {
        "status": "queued",
        "type": operation_type,
        "service": service_name,
        "started_at": timestamp_utc(),
        "metadata": metadata or {}
    }
    
    logger.debug(f"Started operation {operation_id} for {service_name}")
    return operation_id


def update_operation_status(
    operation_id: str,
    status: str,
    **kwargs
) -> bool:
    """Update the status of an active operation.
    
    Args:
        operation_id: ID of the operation to update
        status: New status
        **kwargs: Additional fields to update
        
    Returns:
        True if operation was found and updated, False otherwise
    """
    if operation_id not in active_operations:
        logger.warning(f"Attempted to update unknown operation: {operation_id}")
        return False
    
    active_operations[operation_id].update({
        "status": status,
        "updated_at": timestamp_utc(),
        **kwargs
    })
    
    return True


def get_operation_status(operation_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of an operation.
    
    Args:
        operation_id: ID of the operation
        
    Returns:
        Operation status dict or None if not found
    """
    return active_operations.get(operation_id)


def complete_operation(
    operation_id: str,
    result: Any = None,
    cleanup_delay: int = 300  # 5 minutes default
) -> bool:
    """Mark an operation as completed and schedule cleanup.
    
    Args:
        operation_id: ID of the operation
        result: Operation result
        cleanup_delay: Seconds before cleaning up operation data
        
    Returns:
        True if operation was found and completed, False otherwise
    """
    if not update_operation_status(operation_id, "completed", result=result):
        return False
    
    # Schedule cleanup
    cleanup_task = asyncio.create_task(
        cleanup_operation_after_delay(operation_id, cleanup_delay)
    )
    cleanup_tasks.add(cleanup_task)
    cleanup_task.add_done_callback(cleanup_tasks.discard)
    
    return True


def fail_operation(
    operation_id: str,
    error: str,
    error_type: Optional[str] = None,
    partial_results: Any = None
) -> bool:
    """Mark an operation as failed.
    
    Args:
        operation_id: ID of the operation
        error: Error message
        error_type: Type of error for categorization
        partial_results: Any partial results before failure
        
    Returns:
        True if operation was found and marked failed, False otherwise
    """
    return update_operation_status(
        operation_id,
        "failed",
        error=error,
        error_type=error_type or "unknown",
        partial_results=partial_results
    )


async def cleanup_operation_after_delay(operation_id: str, delay: int):
    """Clean up operation data after a delay.
    
    Args:
        operation_id: ID of the operation to clean up
        delay: Seconds to wait before cleanup
    """
    await asyncio.sleep(delay)
    
    # Remove from active operations
    if operation_id in active_operations:
        del active_operations[operation_id]
        logger.debug(f"Cleaned up operation {operation_id}")
    
    # Clean up any associated tasks
    if operation_id in background_tasks:
        task = background_tasks.pop(operation_id)
        if not task.done():
            task.cancel()


def create_background_task(
    operation_id: str,
    coro: Callable,
    task_name: Optional[str] = None
) -> asyncio.Task:
    """Create and track a background task for an operation.
    
    Args:
        operation_id: ID of the associated operation
        coro: Coroutine to run
        task_name: Optional name for the task
        
    Returns:
        The created asyncio.Task
    """
    task = asyncio.create_task(coro, name=task_name)
    background_tasks[operation_id] = task
    
    # Clean up when done
    def cleanup_callback(t):
        if operation_id in background_tasks and background_tasks[operation_id] == t:
            del background_tasks[operation_id]
    
    task.add_done_callback(cleanup_callback)
    return task


async def cancel_operation(operation_id: str) -> bool:
    """Cancel an active operation and its associated tasks.
    
    Args:
        operation_id: ID of the operation to cancel
        
    Returns:
        True if operation was cancelled, False if not found
    """
    # Update status
    if not update_operation_status(operation_id, "cancelled"):
        return False
    
    # Cancel associated task if any
    if operation_id in background_tasks:
        task = background_tasks[operation_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    return True


def get_active_operations_summary(
    service_name: Optional[str] = None,
    operation_type: Optional[str] = None
) -> Dict[str, Any]:
    """Get a summary of active operations.
    
    Args:
        service_name: Filter by service name
        operation_type: Filter by operation type
        
    Returns:
        Summary dict with counts and operation lists
    """
    operations = list(active_operations.values())
    
    # Apply filters
    if service_name:
        operations = [op for op in operations if op.get("service") == service_name]
    if operation_type:
        operations = [op for op in operations if op.get("type") == operation_type]
    
    # Group by status
    by_status = {}
    for op in operations:
        status = op.get("status", "unknown")
        if status not in by_status:
            by_status[status] = 0
        by_status[status] += 1
    
    return {
        "total": len(operations),
        "by_status": by_status,
        "operations": operations
    }


# Progress emission helpers - services implement their own emit functions
def build_progress_event(
    operation_id: str,
    status: str,
    service_name: str,
    **kwargs
) -> Dict[str, Any]:
    """Build a standardized progress event.
    
    Args:
        operation_id: ID of the operation
        status: Current status
        service_name: Name of the service
        **kwargs: Additional event data
        
    Returns:
        Event dict ready for emission
    """
    return {
        f"{service_name}_id": operation_id,
        "status": status,
        "timestamp": timestamp_utc(),
        **kwargs
    }


def build_result_event(
    operation_id: str,
    result: Any,
    service_name: str,
    **kwargs
) -> Dict[str, Any]:
    """Build a standardized result event.
    
    Args:
        operation_id: ID of the operation
        result: Operation result
        service_name: Name of the service
        **kwargs: Additional event data
        
    Returns:
        Event dict ready for emission
    """
    return {
        f"{service_name}_id": operation_id,
        "result": result,
        "timestamp": timestamp_utc(),
        **kwargs
    }


def build_error_event(
    operation_id: str,
    error: str,
    service_name: str,
    error_type: Optional[str] = None,
    partial_results: Any = None,
    **kwargs
) -> Dict[str, Any]:
    """Build a standardized error event.
    
    Args:
        operation_id: ID of the operation
        error: Error message
        service_name: Name of the service
        error_type: Type of error
        partial_results: Any partial results
        **kwargs: Additional event data
        
    Returns:
        Event dict ready for emission
    """
    return {
        f"{service_name}_id": operation_id,
        "error": error,
        "error_type": error_type or "unknown",
        "partial_results": partial_results,
        "timestamp": timestamp_utc(),
        **kwargs
    }


# Thread pool execution utilities
def get_thread_pool_executor() -> ThreadPoolExecutor:
    """Get or create the shared thread pool executor.
    
    Returns:
        The shared ThreadPoolExecutor instance
    """
    global _thread_pool_executor
    
    if _thread_pool_executor is None:
        # Get pool size from config or use default
        pool_size = getattr(config, 'thread_pool_size', 4)
        _thread_pool_executor = ThreadPoolExecutor(
            max_workers=pool_size,
            thread_name_prefix="ksi_pool"
        )
        logger.info(f"Created thread pool executor with {pool_size} workers")
    
    return _thread_pool_executor


async def run_in_thread_pool(
    func: Callable[..., T],
    *args,
    **kwargs
) -> T:
    """Run a synchronous function in the shared thread pool.
    
    This is ideal for running sync-only code (like DSPy) from async contexts.
    
    Args:
        func: Synchronous function to run
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        The result of the function
        
    Example:
        result = await run_in_thread_pool(
            dspy_optimize,
            component_name="my_component",
            num_trials=10
        )
    """
    loop = asyncio.get_event_loop()
    executor = get_thread_pool_executor()
    
    # Use functools.partial to bind args/kwargs
    bound_func = functools.partial(func, *args, **kwargs)
    
    # Run in thread pool
    return await loop.run_in_executor(executor, bound_func)


async def run_sync_with_timeout(
    func: Callable[..., T],
    timeout: float,
    *args,
    **kwargs
) -> T:
    """Run a synchronous function in thread pool with timeout.
    
    Args:
        func: Synchronous function to run
        timeout: Timeout in seconds
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        The result of the function
        
    Raises:
        asyncio.TimeoutError: If function exceeds timeout
    """
    try:
        return await asyncio.wait_for(
            run_in_thread_pool(func, *args, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Thread pool execution timed out after {timeout}s")
        raise


def shutdown_thread_pool():
    """Shutdown the thread pool executor gracefully.
    
    Should be called during application shutdown.
    """
    global _thread_pool_executor
    
    if _thread_pool_executor is not None:
        logger.info("Shutting down thread pool executor")
        _thread_pool_executor.shutdown(wait=True)
        _thread_pool_executor = None