# Enhanced KSI Introspection for Claude

This document outlines specific introspection capabilities and documentation enhancements that would make KSI more effective for Claude agents.

## Current Introspection Gaps

### 1. Event Discovery Limitations

**Current**: `system:discover` returns all events with basic metadata
```json
{
  "events": {
    "completion": [
      {
        "event": "completion:async",
        "summary": "Create an async completion request",
        "parameters": {...}
      }
    ]
  }
}
```

**Missing**:
- No usage examples
- No typical response formats
- No error scenarios
- No performance expectations
- No relationship to other events

### 2. State Visibility

**Current**: Can get/set state keys but no overview
**Missing**:
- What state keys exist across the system
- Which agents own which keys
- State schemas/types
- State usage patterns

### 3. Agent Introspection

**Current**: `agent:list` shows active agents
**Missing**:
- Agent capabilities and permissions
- Agent conversation history
- Agent resource usage
- Agent interaction patterns

### 4. System Context

**Current**: No unified view of system state
**Missing**:
- Active sessions overview
- System resource usage
- Performance metrics
- Configuration details

## Proposed Introspection Enhancements

### 1. Rich Event Discovery

```python
{"event": "system:discover_event", "data": {
  "event": "completion:async",
  "include_examples": true,
  "include_schema": true,
  "include_errors": true
}}
```

**Response**:
```json
{
  "event": "completion:async",
  "summary": "Create an async completion request",
  "description": "Queues a completion request for processing...",
  "parameters": {
    "prompt": {
      "type": "string",
      "required": true,
      "description": "The prompt text",
      "examples": ["Hello", "Analyze this code"]
    },
    "session_id": {
      "type": "string", 
      "required": false,
      "description": "Previous session ID for continuity",
      "format": "sess_[uuid]"
    }
  },
  "returns": {
    "request_id": "Unique request identifier",
    "status": "queued|processing",
    "queue_position": "Position in queue if queued"
  },
  "errors": [
    {
      "code": "INVALID_MODEL",
      "description": "Model not supported",
      "example": "Model 'gpt-4' not found"
    }
  ],
  "examples": [
    {
      "description": "Simple completion",
      "request": {"event": "completion:async", "data": {"prompt": "Hello"}},
      "response": {"request_id": "req_123", "status": "queued"}
    },
    {
      "description": "Continue conversation",
      "request": {"event": "completion:async", "data": {
        "prompt": "What did I say?",
        "session_id": "sess_abc"
      }},
      "response": {"request_id": "req_124", "status": "processing"}
    }
  ],
  "related_events": [
    "completion:status",
    "completion:cancel",
    "completion:result"
  ],
  "performance": {
    "typical_latency": "5-30s",
    "timeout": "300s",
    "rate_limits": "10 concurrent requests"
  }
}
```

### 2. System Context API

```python
{"event": "system:context", "data": {
  "include": ["sessions", "agents", "resources", "config"]
}}
```

**Response**:
```json
{
  "sessions": {
    "active": 3,
    "recent": [
      {
        "session_id": "sess_123",
        "started": "2024-01-01T10:00:00Z",
        "last_activity": "2024-01-01T10:05:00Z",
        "message_count": 5,
        "participants": ["user", "claude-cli/sonnet"]
      }
    ]
  },
  "agents": {
    "active": 2,
    "agents": [
      {
        "agent_id": "researcher_001",
        "profile": "researcher",
        "permissions": "trusted",
        "status": "idle",
        "created": "2024-01-01T09:00:00Z"
      }
    ]
  },
  "resources": {
    "completion_queue": {
      "queued": 0,
      "processing": 1,
      "workers": 4
    },
    "memory": {
      "used_mb": 125,
      "limit_mb": 1024
    }
  },
  "config": {
    "socket_path": "var/run/daemon.sock",
    "log_level": "INFO",
    "plugins_loaded": 19
  }
}
```

### 3. Event Relationship Graph

```python
{"event": "system:event_graph", "data": {
  "root_event": "completion:async"
}}
```

**Response**:
```json
{
  "root": "completion:async",
  "triggers": [
    {
      "event": "completion:started",
      "condition": "always"
    },
    {
      "event": "completion:result",
      "condition": "on_success"
    }
  ],
  "monitors": [
    "completion:status",
    "completion:cancel"
  ],
  "related": [
    "conversation:active",
    "session:continue"
  ],
  "workflow": {
    "description": "Typical completion flow",
    "steps": [
      "completion:async -> queued",
      "completion:started -> processing", 
      "completion:result -> complete"
    ]
  }
}
```

### 4. Capability Discovery

```python
{"event": "system:capabilities", "data": {}}
```

**Response**:
```json
{
  "models": [
    {
      "name": "claude-cli/sonnet",
      "type": "completion",
      "features": ["tools", "vision", "long_context"],
      "limits": {
        "max_tokens": 4096,
        "context_window": 200000
      }
    }
  ],
  "profiles": [
    {
      "name": "researcher",
      "description": "Research-focused agent profile",
      "permissions": ["read", "write", "web_access"],
      "tools": {
        "allowed": ["all"],
        "disallowed": ["Bash"]
      }
    }
  ],
  "features": {
    "multi_agent": true,
    "persistence": true,
    "monitoring": true,
    "composition": true
  }
}
```

### 5. Interactive Help System

```python
{"event": "system:help", "data": {
  "topic": "sessions",
  "format": "tutorial"
}}
```

**Response**:
```json
{
  "topic": "sessions",
  "tutorial": {
    "overview": "Sessions provide conversation continuity...",
    "steps": [
      {
        "title": "Start a new conversation",
        "description": "Omit session_id for clean context",
        "example": {"event": "completion:async", "data": {"prompt": "Hello"}},
        "explanation": "Returns a new session_id in response"
      },
      {
        "title": "Continue conversation", 
        "description": "Use previous session_id",
        "example": {"event": "completion:async", "data": {
          "prompt": "What did I say?",
          "session_id": "sess_123"
        }},
        "explanation": "Links to previous context"
      }
    ],
    "tips": [
      "Session IDs are generated by providers",
      "Each response has a new session_id",
      "Sessions can be exported/analyzed"
    ],
    "common_issues": [
      {
        "issue": "Session not found",
        "cause": "Invalid or expired session_id",
        "solution": "Check session:list for valid IDs"
      }
    ]
  }
}
```

## Documentation Enhancements

### 1. Event Cookbook

```python
{"event": "system:cookbook", "data": {
  "scenario": "multi_agent_research"
}}
```

Returns complete working examples for common scenarios:
- Multi-agent research
- Long conversation management  
- State sharing patterns
- Error handling strategies
- Performance optimization

### 2. Troubleshooting Guide

```python
{"event": "system:troubleshoot", "data": {
  "error": "COMPLETION_TIMEOUT"
}}
```

Returns:
- Common causes
- Diagnostic steps
- Solution strategies
- Related issues

### 3. Best Practices API

```python
{"event": "system:best_practices", "data": {
  "topic": "agent_orchestration"
}}
```

Returns:
- Recommended patterns
- Anti-patterns to avoid
- Performance considerations
- Security guidelines

## Implementation Priority

### Phase 1: Core Discovery (1 week)
1. Enhanced event discovery with examples
2. System context API
3. Capability discovery
4. Event relationship graph

### Phase 2: Interactive Help (1 week)
1. Tutorial system
2. Cookbook examples
3. Troubleshooting guide
4. Best practices API

### Phase 3: Advanced Introspection (2 weeks)
1. Performance profiling API
2. State schema discovery
3. Agent interaction visualization
4. System health diagnostics

## Benefits for Claude

### 1. Self-Learning
- Claude can discover capabilities without external documentation
- Examples show correct usage patterns
- Error scenarios help avoid mistakes

### 2. Adaptive Behavior
- Claude can check system state before operations
- Performance metrics inform strategy
- Capability discovery enables feature detection

### 3. Better Error Recovery
- Detailed error information enables fixes
- Troubleshooting API provides solutions
- Related events show alternatives

### 4. Efficient Orchestration
- Event graphs show efficient workflows
- Best practices prevent anti-patterns
- Performance data enables optimization

## Example Claude Interaction

```python
# Claude exploring KSI for the first time
async with EventClient() as client:
    # What can I do?
    caps = await client.system.capabilities()
    print(f"Available models: {caps['models']}")
    print(f"Features: {caps['features']}")
    
    # How do I use completions?
    help = await client.system.help(topic="completion", format="tutorial")
    for step in help['tutorial']['steps']:
        print(f"{step['title']}: {step['example']}")
    
    # What's the system state?
    ctx = await client.system.context(include=["sessions", "agents"])
    print(f"Active sessions: {ctx['sessions']['active']}")
    
    # Show me a working example
    cookbook = await client.system.cookbook(scenario="simple_chat")
    # Execute the example...
```

## Conclusion

Enhanced introspection would transform KSI from a powerful but opaque system into a self-documenting, Claude-friendly platform. The key improvements:

1. **Rich metadata** with examples and schemas
2. **Interactive help** with tutorials and cookbooks
3. **System visibility** for informed decisions
4. **Relationship mapping** for understanding workflows
5. **Troubleshooting support** for error recovery

These enhancements would enable Claude to:
- Learn KSI capabilities independently
- Adapt strategies based on system state
- Recover from errors gracefully
- Optimize performance automatically
- Teach users through examples