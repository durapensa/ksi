# Async Completion Queue with Event-Driven Injection

## Overview

The async completion queue with event-driven injection enables autonomous agent coordination through completion chains while maintaining safety through circuit breakers and conversation linearity.

## Architecture Components

### 1. Injection Router Plugin (`ksi_daemon/plugins/injection/injection_router.py`)
- Routes async completion results through system-reminder injection
- Supports different trigger types (antThinking, coordination, research, memory)
- Integrates with prompt composition system for flexible templates

### 2. Circuit Breaker System (`ksi_daemon/plugins/injection/circuit_breakers.py`)
- **Ideation Depth Tracking**: Prevents chains deeper than configured limit
- **Context Poisoning Detection**: Identifies patterns like:
  - Recursive self-reference
  - Hallucination cascades
  - Topic drift
  - Coherence degradation
  - Circular reasoning
- **Token Budget Management**: Enforces resource limits
- **Time Window Controls**: Prevents long-running chains

### 3. Completion Queue (`ksi_daemon/plugins/completion/completion_queue.py`)
- Priority-based request queuing (CRITICAL, HIGH, NORMAL, LOW, BACKGROUND)
- Conversation lock management to prevent forking
- Fork detection and tracking when conversation IDs change

### 4. Conversation Lock Service (`ksi_daemon/plugins/conversation/conversation_lock.py`)
- Distributed locking per conversation_id
- Queue management for parallel requests
- Fork detection and parent/child tracking
- Lock expiration and automatic transfer

## Usage Examples

### Basic Async Completion with Injection

```python
# Queue a completion with injection metadata
request = {
    'prompt': 'Research quantum computing applications',
    'session_id': 'research_001',
    'injection_config': {
        'enabled': True,
        'trigger_type': 'research',
        'target_sessions': ['coordinator_session'],
        'follow_up_guidance': 'Consider storing findings in collective memory'
    },
    'circuit_breaker_config': {
        'max_depth': 5,
        'token_budget': 50000,
        'time_window': 3600,
        'parent_request_id': None  # Set to chain requests
    }
}

# Send via event system
response = await daemon.send_event('completion:async', request)
```

### Handling Completion Results

When a completion finishes, the injection router automatically:
1. Checks circuit breakers
2. Composes injection content using templates
3. Wraps in `<system-reminder>` tags
4. Queues injection for target sessions

The injected content includes:
- The completion result
- Trigger-specific boilerplate (e.g., analytical thinking prompts)
- Circuit breaker status
- Custom follow-up guidance

### Conversation Lock Events

```python
# Acquire lock before completion
lock_result = await daemon.send_event('conversation:acquire_lock', {
    'request_id': 'req_123',
    'conversation_id': 'conv_456',
    'metadata': {'agent': 'researcher'}
})

if lock_result['acquired']:
    # Proceed with completion
    pass
else:
    # Request is queued at position lock_result['position']
    pass

# Release lock after completion
await daemon.send_event('conversation:release_lock', {
    'request_id': 'req_123'
})
```

### Circuit Breaker Configuration

```python
circuit_breaker_config = {
    'max_depth': 5,              # Maximum chain depth
    'token_budget': 50000,       # Token limit for chain
    'time_window': 3600,         # Time window in seconds
    'parent_request_id': 'req_parent'  # Link to parent
}
```

## Event Flow

1. **Request Queuing**
   - Check circuit breakers
   - Acquire conversation lock
   - Queue based on priority

2. **Completion Processing**
   - Process completion
   - Return result with `completion:result` event

3. **Injection Routing**
   - Injection router handles `completion:result`
   - Checks injection metadata
   - Composes and queues injection

4. **Target Session Injection**
   - Injection delivered as system-reminder
   - Trigger boilerplate prompts follow-up
   - Circuit breaker status included

## Safety Features

### Circuit Breakers Prevent:
- Infinite loops through depth limiting
- Context poisoning through pattern detection
- Resource exhaustion through token budgets
- Runaway processing through time windows

### Conversation Locks Prevent:
- Parallel modifications to same conversation
- Race conditions in multi-agent scenarios
- Untracked conversation forks

## Integration with Existing System

The system integrates seamlessly with KSI's event-driven architecture:
- New events: `injection:queued`, `injection:blocked`, `conversation:locked`, etc.
- Compatible with existing completion service
- Works with prompt composition system
- Supports future MCP tool integration

## Testing

Run the comprehensive test suite:
```bash
python tests/test_injection_system.py
```

Tests cover:
- Circuit breaker limiting
- Conversation lock management
- Fork detection
- Injection routing
- Full integration scenarios