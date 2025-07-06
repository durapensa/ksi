#!/usr/bin/env python3
"""
Example: Completion handler using enhanced decorator for rich discovery.
"""

import sys
sys.path.insert(0, '..')

from typing import Dict, Any
from ksi_daemon.enhanced_decorators import (
    enhanced_event_handler, EventCategory, EventParameter, EventExample
)
from ksi_daemon.event_types import CompletionAsyncData

@enhanced_event_handler(
    "completion:async",
    category=EventCategory.COMPUTE,
    summary="Request an async completion from an LLM provider",
    description="""
    Sends a prompt to a language model and returns immediately with a request ID.
    The actual completion will be delivered asynchronously through the completion:result event.
    
    Supports multiple providers including Claude (via claude-cli) and OpenAI models (via litellm).
    Session management allows for conversation continuity across requests.
    """,
    parameters=[
        EventParameter(
            name="prompt",
            type="string",
            description="The prompt text to send to the LLM",
            required=True,
            example="Explain quantum computing in simple terms"
        ),
        EventParameter(
            name="model",
            type="string", 
            description="Model identifier (provider/model format)",
            required=True,
            allowed_values=[
                "claude-cli/sonnet", "claude-cli/opus", "claude-cli/haiku",
                "litellm/gpt-4", "litellm/gpt-3.5-turbo"
            ],
            example="claude-cli/sonnet"
        ),
        EventParameter(
            name="session_id",
            type="string",
            description="Session ID for conversation continuity (omit for new session)",
            required=False,
            example="abc-123-def"
        ),
        EventParameter(
            name="temperature",
            type="float",
            description="Sampling temperature (0.0-2.0)",
            required=False,
            default=0.7,
            constraints={"min": 0.0, "max": 2.0}
        ),
        EventParameter(
            name="max_tokens",
            type="integer",
            description="Maximum tokens to generate",
            required=False,
            default=4000,
            constraints={"min": 1, "max": 128000}
        ),
        EventParameter(
            name="priority",
            type="string",
            description="Request priority for queue management",
            required=False,
            default="normal",
            allowed_values=["critical", "high", "normal", "low", "background"]
        )
    ],
    examples=[
        EventExample(
            description="Basic completion request",
            data={
                "prompt": "What is the capital of France?",
                "model": "claude-cli/sonnet"
            },
            expected_result={
                "status": "queued",
                "request_id": "req_123",
                "estimated_wait_ms": 100
            }
        ),
        EventExample(
            description="Continue conversation with session",
            data={
                "prompt": "What about its population?",
                "model": "claude-cli/sonnet",
                "session_id": "session_abc123"
            },
            context="Following up on previous question about Paris",
            expected_result={
                "status": "queued",
                "request_id": "req_124",
                "session_id": "session_abc123_continued"
            }
        ),
        EventExample(
            description="High-priority request with custom parameters",
            data={
                "prompt": "Urgent: Summarize this error log",
                "model": "litellm/gpt-4",
                "priority": "critical",
                "temperature": 0.2,
                "max_tokens": 500
            },
            context="Production incident response"
        )
    ],
    data_type=CompletionAsyncData,
    # Performance characteristics
    async_response=True,
    typical_duration_ms=100,  # Just queuing time
    has_side_effects=True,    # Creates state/logs
    idempotent=False,         # Each request is unique
    # Resource/cost hints
    has_cost=True,            # LLM API calls cost money
    requires_auth=False,      # Auth handled by providers
    rate_limited=True,        # Provider rate limits apply
    # Best practices
    best_practices=[
        "Always handle the async response via completion:result event",
        "Use session_id for multi-turn conversations",
        "Set appropriate priority to manage queue effectively",
        "Monitor costs with high-volume usage",
        "Use temperature=0 for deterministic outputs"
    ],
    common_errors=[
        "Invalid model identifier - use provider/model format",
        "Session not found - session_ids expire after inactivity",
        "Rate limit exceeded - implement backoff strategy",
        "Request timeout - check completion:status event"
    ],
    related_events=[
        "completion:result",
        "completion:status",
        "completion:cancel",
        "completion:session_status"
    ]
)
def handle_completion_async(data: CompletionAsyncData) -> Dict[str, Any]:
    """
    Queue an async completion request.
    
    This is a mock implementation for demonstration.
    """
    import uuid
    import time
    
    # Generate request ID
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    
    # Mock queue position calculation
    queue_position = 1  # In real implementation, check actual queue
    estimated_wait = queue_position * 100  # 100ms per position
    
    # Handle session continuity
    session_id = data.get("session_id")
    if session_id:
        # Continue existing session
        new_session_id = f"{session_id}_cont_{int(time.time())}"
    else:
        # Start new session
        new_session_id = f"session_{uuid.uuid4().hex[:12]}"
    
    return {
        "status": "queued",
        "request_id": request_id,
        "session_id": new_session_id,
        "queue_position": queue_position,
        "estimated_wait_ms": estimated_wait,
        "timestamp": time.time()
    }

# Test the enhanced discovery
if __name__ == "__main__":
    import json
    
    if hasattr(handle_completion_async, '_ksi_event_metadata'):
        metadata = handle_completion_async._ksi_event_metadata
        
        # Pretty print the discovered metadata
        print(json.dumps(metadata, indent=2, default=str))