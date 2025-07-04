#!/usr/bin/env python3
"""
Completion Retry Manager

Provides generic retry functionality for completion requests with configurable
policies and exponential backoff. Integrates with checkpoint restore and 
failure recovery systems.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any, List
from datetime import datetime, timedelta
import time

from ksi_common.logging import get_bound_logger
from ksi_common import timestamp_utc

logger = get_bound_logger("retry_manager", version="1.0.0")


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0     # seconds
    backoff_multiplier: float = 2.0
    retryable_errors: Set[str] = field(default_factory=lambda: {
        "timeout", "network_error", "api_rate_limit", "daemon_restart", 
        "provider_error", "temporary_failure"
    })


@dataclass
class RetryState:
    """State tracking for retryable requests."""
    request_id: str
    original_data: Dict[str, Any]
    retry_attempt: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    next_retry_at: Optional[float] = None  # asyncio time
    failure_reason: Optional[str] = None
    created_at: str = field(default_factory=timestamp_utc)
    
    def should_retry(self, error_type: str, policy: RetryPolicy) -> bool:
        """Check if request should be retried based on policy."""
        return (
            self.retry_attempt < self.max_retries and
            error_type in policy.retryable_errors
        )
    
    def calculate_next_delay(self, policy: RetryPolicy) -> float:
        """Calculate next retry delay with exponential backoff."""
        delay = policy.initial_delay * (policy.backoff_multiplier ** self.retry_attempt)
        return min(delay, policy.max_delay)


class RetryManager:
    """Manages retry state and scheduling for completion requests."""
    
    def __init__(self, emit_event_func, retry_policy: Optional[RetryPolicy] = None):
        self.emit_event = emit_event_func
        self.policy = retry_policy or RetryPolicy()
        self.retry_states: Dict[str, RetryState] = {}
        self.retry_timers: Dict[str, asyncio.Task] = {}
        self.running = False
        
    async def start(self):
        """Start the retry manager."""
        self.running = True
        logger.info("Retry manager started", policy=self.policy)
    
    async def stop(self):
        """Stop the retry manager and cancel pending retries."""
        self.running = False
        
        # Cancel all pending retry timers
        for timer in self.retry_timers.values():
            if not timer.done():
                timer.cancel()
        
        # Wait for timers to complete
        if self.retry_timers:
            await asyncio.gather(*self.retry_timers.values(), return_exceptions=True)
        
        self.retry_timers.clear()
        logger.info("Retry manager stopped")
    
    def add_retry_candidate(
        self, 
        request_id: str, 
        original_data: Dict[str, Any], 
        error_type: str,
        error_message: Optional[str] = None,
        max_retries: Optional[int] = None
    ) -> bool:
        """
        Add a request as a retry candidate.
        
        Returns True if retry will be attempted, False if not retryable.
        """
        if not self.running:
            return False
        
        # Create or update retry state
        if request_id in self.retry_states:
            retry_state = self.retry_states[request_id]
            retry_state.retry_attempt += 1
            retry_state.last_error = error_type
            retry_state.failure_reason = error_message
        else:
            retry_state = RetryState(
                request_id=request_id,
                original_data=original_data.copy(),
                max_retries=max_retries or self.policy.max_attempts,
                last_error=error_type,
                failure_reason=error_message
            )
            self.retry_states[request_id] = retry_state
        
        # Check if retry is allowed
        if not retry_state.should_retry(error_type, self.policy):
            logger.warning(
                "Request not retryable",
                request_id=request_id,
                error_type=error_type,
                attempt=retry_state.retry_attempt,
                max_retries=retry_state.max_retries
            )
            self.cleanup_retry_state(request_id)
            return False
        
        # Schedule retry
        delay = retry_state.calculate_next_delay(self.policy)
        retry_state.next_retry_at = asyncio.get_event_loop().time() + delay
        
        logger.info(
            "Scheduling retry",
            request_id=request_id,
            error_type=error_type,
            attempt=retry_state.retry_attempt + 1,
            max_retries=retry_state.max_retries,
            delay_seconds=delay
        )
        
        # Cancel existing timer if any
        if request_id in self.retry_timers:
            self.retry_timers[request_id].cancel()
        
        # Schedule new retry
        self.retry_timers[request_id] = asyncio.create_task(
            self._schedule_retry(request_id, delay)
        )
        
        return True
    
    async def _schedule_retry(self, request_id: str, delay: float):
        """Schedule a retry after the specified delay."""
        try:
            await asyncio.sleep(delay)
            
            if not self.running or request_id not in self.retry_states:
                return
            
            retry_state = self.retry_states[request_id]
            
            logger.info(
                "Executing retry",
                request_id=request_id,
                attempt=retry_state.retry_attempt + 1,
                original_error=retry_state.last_error
            )
            
            # Emit retry event with original data
            await self.emit_event("completion:async", retry_state.original_data)
            
            # Clean up retry state (successful retry attempt)
            self.cleanup_retry_state(request_id)
            
        except asyncio.CancelledError:
            logger.debug("Retry cancelled", request_id=request_id)
        except Exception as e:
            logger.error(f"Retry scheduling error: {e}", request_id=request_id, exc_info=True)
            self.cleanup_retry_state(request_id)
    
    def cleanup_retry_state(self, request_id: str):
        """Clean up retry state and timers for a request."""
        self.retry_states.pop(request_id, None)
        
        if request_id in self.retry_timers:
            timer = self.retry_timers.pop(request_id)
            if not timer.done():
                timer.cancel()
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """Get current retry statistics."""
        total_retrying = len(self.retry_states)
        pending_timers = len([t for t in self.retry_timers.values() if not t.done()])
        
        return {
            "total_retrying": total_retrying,
            "pending_timers": pending_timers,
            "policy": {
                "max_attempts": self.policy.max_attempts,
                "initial_delay": self.policy.initial_delay,
                "max_delay": self.policy.max_delay,
                "backoff_multiplier": self.policy.backoff_multiplier
            }
        }
    
    def list_retrying_requests(self) -> List[Dict[str, Any]]:
        """List all requests currently being retried."""
        current_time = asyncio.get_event_loop().time()
        
        return [
            {
                "request_id": state.request_id,
                "retry_attempt": state.retry_attempt,
                "max_retries": state.max_retries,
                "last_error": state.last_error,
                "next_retry_in": max(0, state.next_retry_at - current_time) if state.next_retry_at else None,
                "created_at": state.created_at
            }
            for state in self.retry_states.values()
        ]


# Shared helper functions

def is_retryable_error(error_type: str, policy: RetryPolicy) -> bool:
    """Check if an error type is retryable according to policy."""
    return error_type in policy.retryable_errors


def extract_error_type(error_data: Dict[str, Any]) -> str:
    """Extract standardized error type from completion failure data."""
    reason = error_data.get("reason", "unknown_error")
    message = error_data.get("message", "")
    
    # Map common error patterns to standardized types
    if reason == "timeout":
        return "timeout"
    elif reason == "daemon_restart":
        return "daemon_restart"
    elif "rate limit" in message.lower():
        return "api_rate_limit"
    elif "network" in message.lower() or "connection" in message.lower():
        return "network_error"
    elif "provider" in message.lower():
        return "provider_error"
    else:
        return "temporary_failure"