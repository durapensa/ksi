"""
Task Management Utilities - Standardized patterns for async task creation and tracking.

Provides utilities for managing background tasks, task cleanup, and periodic tasks.
Complements async_operations.py with simpler, more direct task management patterns.
"""

import asyncio
from typing import Dict, Set, Optional, Callable, Any, Coroutine, List
from functools import wraps
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("task_management")

# Global task registry for each service
_service_tasks: Dict[str, Set[asyncio.Task]] = {}
_periodic_tasks: Dict[str, asyncio.Task] = {}


def create_tracked_task(
    service_name: str,
    coro: Coroutine,
    task_name: Optional[str] = None,
    error_handler: Optional[Callable[[Exception], None]] = None
) -> asyncio.Task:
    """Create and track a background task for a service.
    
    Args:
        service_name: Name of the service creating the task
        coro: Coroutine to run
        task_name: Optional name for the task
        error_handler: Optional error handler function
        
    Returns:
        The created asyncio.Task
        
    Example:
        task = create_tracked_task(
            "agent_service",
            process_agent_messages(agent_id),
            task_name=f"agent_{agent_id}_processor"
        )
    """
    # Ensure service has a task set
    if service_name not in _service_tasks:
        _service_tasks[service_name] = set()
    
    # Create the task
    task = asyncio.create_task(coro, name=task_name)
    _service_tasks[service_name].add(task)
    
    # Add cleanup and error handling
    def done_callback(t: asyncio.Task):
        _service_tasks[service_name].discard(t)
        
        # Handle errors
        if t.cancelled():
            logger.debug(f"Task {task_name or 'unnamed'} cancelled for {service_name}")
        elif t.exception():
            exc = t.exception()
            logger.error(f"Task {task_name or 'unnamed'} failed for {service_name}: {exc}")
            if error_handler:
                try:
                    error_handler(exc)
                except Exception as handler_exc:
                    logger.error(f"Error handler failed: {handler_exc}")
    
    task.add_done_callback(done_callback)
    return task


async def cleanup_service_tasks(
    service_name: str,
    timeout: float = 5.0,
    cancel_remaining: bool = True
) -> Dict[str, Any]:
    """Clean up all tasks for a service during shutdown.
    
    Args:
        service_name: Name of the service
        timeout: Time to wait for tasks to complete
        cancel_remaining: Whether to cancel tasks that don't complete
        
    Returns:
        Cleanup statistics
        
    Example:
        @service_shutdown("my_service")
        async def shutdown(data, context):
            stats = await cleanup_service_tasks("my_service")
            logger.info(f"Cleaned up {stats['cancelled']} tasks")
    """
    if service_name not in _service_tasks:
        return {"total": 0, "completed": 0, "cancelled": 0}
    
    tasks = list(_service_tasks[service_name])
    if not tasks:
        return {"total": 0, "completed": 0, "cancelled": 0}
    
    # Wait for tasks to complete with timeout
    logger.info(f"Waiting for {len(tasks)} tasks to complete for {service_name}")
    done, pending = await asyncio.wait(tasks, timeout=timeout)
    
    stats = {
        "total": len(tasks),
        "completed": len(done),
        "cancelled": 0
    }
    
    # Cancel remaining tasks if requested
    if cancel_remaining and pending:
        logger.warning(f"Cancelling {len(pending)} tasks for {service_name}")
        for task in pending:
            task.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*pending, return_exceptions=True)
        stats["cancelled"] = len(pending)
    
    # Clear the task set
    _service_tasks[service_name].clear()
    
    return stats


def periodic_task(
    interval: float,
    service_name: str,
    task_id: str,
    start_immediately: bool = True
):
    """Decorator to create a periodic task that runs at regular intervals.
    
    Args:
        interval: Seconds between executions
        service_name: Name of the service
        task_id: Unique ID for this periodic task
        start_immediately: Whether to run immediately or wait for first interval
        
    Example:
        @periodic_task(60.0, "monitor_service", "health_check")
        async def check_health():
            # This runs every 60 seconds
            await perform_health_check()
    """
    def decorator(func):
        @wraps(func)
        async def periodic_wrapper():
            """Run the function periodically."""
            # Wait for first interval if not starting immediately
            if not start_immediately:
                await asyncio.sleep(interval)
            
            while True:
                try:
                    # Run the periodic function
                    await func()
                except asyncio.CancelledError:
                    # Clean shutdown
                    logger.info(f"Periodic task {task_id} cancelled")
                    break
                except Exception as e:
                    # Log error but continue running
                    logger.error(f"Periodic task {task_id} error: {e}")
                
                # Wait for next interval
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
        
        # Store reference to start the task
        periodic_wrapper._interval = interval
        periodic_wrapper._service_name = service_name
        periodic_wrapper._task_id = task_id
        
        return periodic_wrapper
    return decorator


def start_periodic_task(periodic_func: Callable) -> asyncio.Task:
    """Start a periodic task decorated with @periodic_task.
    
    Args:
        periodic_func: Function decorated with @periodic_task
        
    Returns:
        The created task
        
    Example:
        @periodic_task(60.0, "monitor", "cleanup")
        async def cleanup_old_data():
            await remove_expired_entries()
            
        # In startup handler:
        cleanup_task = start_periodic_task(cleanup_old_data)
    """
    if not hasattr(periodic_func, '_task_id'):
        raise ValueError("Function must be decorated with @periodic_task")
    
    task_id = periodic_func._task_id
    service_name = periodic_func._service_name
    
    # Cancel existing task if any
    if task_id in _periodic_tasks:
        old_task = _periodic_tasks[task_id]
        if not old_task.done():
            old_task.cancel()
    
    # Create and track the task
    task = create_tracked_task(
        service_name,
        periodic_func(),
        task_name=f"periodic_{task_id}"
    )
    _periodic_tasks[task_id] = task
    
    logger.info(f"Started periodic task {task_id} for {service_name}")
    return task


def stop_periodic_task(task_id: str) -> bool:
    """Stop a periodic task by ID.
    
    Args:
        task_id: ID of the periodic task
        
    Returns:
        True if task was stopped, False if not found
    """
    if task_id not in _periodic_tasks:
        return False
    
    task = _periodic_tasks[task_id]
    if not task.done():
        task.cancel()
    
    del _periodic_tasks[task_id]
    logger.info(f"Stopped periodic task {task_id}")
    return True


async def run_with_timeout(
    coro: Coroutine,
    timeout: float,
    service_name: str,
    operation_name: str
) -> Optional[Any]:
    """Run a coroutine with timeout and proper error handling.
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        service_name: Name of the service
        operation_name: Name of the operation for logging
        
    Returns:
        Result of the coroutine or None if timed out
        
    Example:
        result = await run_with_timeout(
            fetch_data_from_api(),
            timeout=30.0,
            service_name="api_service",
            operation_name="fetch_user_data"
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"{service_name}: {operation_name} timed out after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"{service_name}: {operation_name} failed: {e}")
        raise


def create_task_group(service_name: str) -> 'TaskGroup':
    """Create a task group for managing related tasks together.
    
    Args:
        service_name: Name of the service
        
    Returns:
        TaskGroup instance
        
    Example:
        async with create_task_group("agent_service") as group:
            group.create_task(process_message(msg1))
            group.create_task(process_message(msg2))
            # All tasks complete or cancel when exiting the context
    """
    return TaskGroup(service_name)


class TaskGroup:
    """Context manager for grouped task management."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.tasks: Set[asyncio.Task] = set()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Wait for all tasks to complete
        if self.tasks:
            done, pending = await asyncio.wait(self.tasks, timeout=5.0)
            
            # Cancel any remaining tasks
            for task in pending:
                task.cancel()
            
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
    
    def create_task(
        self,
        coro: Coroutine,
        name: Optional[str] = None
    ) -> asyncio.Task:
        """Create a task in this group."""
        task = create_tracked_task(
            self.service_name,
            coro,
            task_name=name
        )
        self.tasks.add(task)
        
        # Remove from group when done
        task.add_done_callback(self.tasks.discard)
        return task


# Utility functions for common patterns

async def stagger_startup(
    tasks: List[Callable[[], Coroutine]],
    delay: float = 0.1,
    service_name: str = "unknown"
) -> List[asyncio.Task]:
    """Start multiple tasks with a staggered delay.
    
    Useful for avoiding thundering herd problems during startup.
    
    Args:
        tasks: List of coroutine functions to start
        delay: Delay between starting each task
        service_name: Name of the service
        
    Returns:
        List of created tasks
    """
    created_tasks = []
    
    for i, task_func in enumerate(tasks):
        if i > 0:
            await asyncio.sleep(delay)
        
        task = create_tracked_task(
            service_name,
            task_func(),
            task_name=f"staggered_{i}"
        )
        created_tasks.append(task)
    
    return created_tasks


def get_service_task_stats(service_name: Optional[str] = None) -> Dict[str, Any]:
    """Get statistics about running tasks.
    
    Args:
        service_name: Optional service name to filter by
        
    Returns:
        Task statistics
    """
    stats = {}
    
    if service_name:
        services = [service_name] if service_name in _service_tasks else []
    else:
        services = list(_service_tasks.keys())
    
    for svc in services:
        tasks = _service_tasks[svc]
        stats[svc] = {
            "total": len(tasks),
            "running": sum(1 for t in tasks if not t.done()),
            "completed": sum(1 for t in tasks if t.done() and not t.cancelled()),
            "cancelled": sum(1 for t in tasks if t.cancelled()),
            "failed": sum(1 for t in tasks if t.done() and t.exception() is not None)
        }
    
    # Add periodic tasks info
    stats["periodic_tasks"] = {
        task_id: "running" if not task.done() else "stopped"
        for task_id, task in _periodic_tasks.items()
    }
    
    return stats