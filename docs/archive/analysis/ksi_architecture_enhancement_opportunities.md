# KSI Architecture Enhancement Opportunities for Claude Integration

This document identifies specific architectural enhancements that would improve Claude's ability to work with KSI effectively.

## Current Architecture Strengths

1. **Event-driven design**: Clean abstraction for all operations
2. **Plugin system**: Extensible without core changes
3. **Async-first**: Non-blocking operations throughout
4. **Discovery mechanism**: Events can be introspected

## Key Architectural Gaps

### 1. Event Metadata Limitations

**Current State**:
```python
@event_handler("completion:async")
def handle_completion_async(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create an async completion request."""
    # Implementation
```

**Problem**: Limited metadata extraction from docstrings

**Enhancement Opportunity**:
```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class CompletionRequest:
    prompt: str
    model: Literal["claude-cli/sonnet", "claude-cli/opus"] = "claude-cli/sonnet"
    session_id: Optional[str] = None
    priority: Literal["low", "normal", "high"] = "normal"
    
    class Meta:
        examples = [
            {"prompt": "Hello", "_comment": "Simple greeting"},
            {"prompt": "Analyze code", "session_id": "sess_123", "_comment": "Continue session"}
        ]
        errors = {
            "INVALID_MODEL": "Model must be sonnet or opus",
            "SESSION_NOT_FOUND": "Session ID not found or expired"
        }

@event_handler("completion:async", schema=CompletionRequest)
def handle_completion_async(request: CompletionRequest) -> Dict[str, Any]:
    """Create an async completion request."""
    # Type-safe implementation with rich metadata
```

**Benefits**:
- Type safety with runtime validation
- Rich examples in metadata
- Better IDE support
- Automatic schema generation

### 2. Event Relationship Tracking

**Current State**: Events are independent with no declared relationships

**Enhancement Opportunity**:
```python
@event_handler("completion:async")
@triggers("completion:started", "completion:queued")
@emits("completion:result", "completion:error")
@related_to("completion:status", "completion:cancel")
def handle_completion_async(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create an async completion request."""
    # Implementation
```

**Implementation**:
```python
# Event registry tracks relationships
EVENT_REGISTRY = {
    "completion:async": {
        "handler": handle_completion_async,
        "triggers": ["completion:started", "completion:queued"],
        "emits": ["completion:result", "completion:error"],
        "related": ["completion:status", "completion:cancel"],
        "workflow": "completion_flow"
    }
}
```

### 3. Workflow Definition System

**Current State**: Workflows are implicit in code

**Enhancement Opportunity**:
```yaml
# var/lib/workflows/completion_flow.yaml
name: completion_flow
description: Standard completion request flow
steps:
  - event: completion:async
    transitions:
      - to: completion:queued
        when: queue_full
      - to: completion:started
        when: immediate_capacity
  - event: completion:started
    transitions:
      - to: completion:result
        when: success
      - to: completion:error
        when: failure
  - event: completion:result
    transitions:
      - to: injection:process
        when: injection_enabled
```

**Benefits**:
- Visual workflow understanding
- Testable state machines
- Documentation generation
- Claude can reason about flows

### 4. Contract-Based Event System

**Current State**: Informal event contracts

**Enhancement Opportunity**:
```python
from ksi_common.contracts import EventContract, requires, ensures, invariant

@EventContract
class CompletionContract:
    @requires(lambda data: len(data.get("prompt", "")) > 0)
    @requires(lambda data: data.get("model") in ["claude-cli/sonnet", "claude-cli/opus"])
    @ensures(lambda result: "request_id" in result)
    @ensures(lambda result: result.get("status") in ["queued", "processing"])
    @invariant(lambda: active_requests() < MAX_CONCURRENT)
    def completion_async(self, data: Dict) -> Dict:
        pass
```

**Runtime Benefits**:
- Contract violations caught early
- Better error messages
- Self-documenting invariants
- Testable specifications

### 5. Event Testing Framework

**Current State**: Manual testing with nc/echo commands

**Enhancement Opportunity**:
```python
# Event test DSL
class TestCompletionFlow(KSIEventTest):
    async def test_simple_completion(self):
        # Given
        await self.given_system_state(agents=0, queue_empty=True)
        
        # When
        response = await self.send_event("completion:async", {
            "prompt": "Hello"
        })
        
        # Then
        self.assert_event_emitted("completion:started", within="5s")
        self.assert_response_contains(response, "request_id")
        
        # And eventually
        result = await self.wait_for_event("completion:result", timeout="30s")
        self.assert_equals(result["request_id"], response["request_id"])
```

### 6. Plugin Capability Declaration

**Current State**: Plugins implement hooks without declaring capabilities

**Enhancement Opportunity**:
```python
# In plugin module
KSI_PLUGIN_MANIFEST = {
    "name": "completion_service",
    "version": "3.0.0",
    "capabilities": {
        "models": ["claude-cli/sonnet", "claude-cli/opus"],
        "features": ["async_completion", "session_continuity", "priority_queue"],
        "events": {
            "handles": ["completion:*"],
            "emits": ["completion:started", "completion:result", "completion:error"]
        }
    },
    "requirements": {
        "services": ["state", "messaging"],
        "python": ">=3.11",
        "system": ["claude-cli"]
    },
    "configuration": {
        "max_concurrent": {"type": "int", "default": 10},
        "timeout": {"type": "int", "default": 300}
    }
}
```

### 7. Structured Error System

**Current State**: String error messages

**Enhancement Opportunity**:
```python
from ksi_common.errors import KSIError, error_code

@error_code("COMP_001")
class ModelNotFoundError(KSIError):
    """The specified model is not available."""
    
    def __init__(self, model: str, available: List[str]):
        self.model = model
        self.available = available
        super().__init__(
            f"Model '{model}' not found. Available: {', '.join(available)}",
            suggestions=[
                f"Use one of: {', '.join(available)}",
                "Check model name spelling",
                "Run system:capabilities to see all models"
            ],
            related_events=["system:capabilities", "system:help"]
        )
```

**Error Response**:
```json
{
  "error": {
    "code": "COMP_001",
    "type": "ModelNotFoundError",
    "message": "Model 'gpt-4' not found. Available: claude-cli/sonnet, claude-cli/opus",
    "suggestions": [
      "Use one of: claude-cli/sonnet, claude-cli/opus",
      "Check model name spelling",
      "Run system:capabilities to see all models"
    ],
    "related_events": ["system:capabilities", "system:help"],
    "context": {
      "requested_model": "gpt-4",
      "available_models": ["claude-cli/sonnet", "claude-cli/opus"]
    }
  }
}
```

### 8. Event Middleware System

**Current State**: Direct event handling

**Enhancement Opportunity**:
```python
# Composable middleware
@middleware
async def rate_limit_middleware(event_name: str, data: Dict, next: Callable):
    """Rate limit events per client."""
    client_id = data.get("client_id", "anonymous")
    if not await check_rate_limit(client_id, event_name):
        raise RateLimitError(client_id, event_name)
    return await next(event_name, data)

@middleware  
async def auth_middleware(event_name: str, data: Dict, next: Callable):
    """Authenticate and authorize events."""
    if requires_auth(event_name):
        token = data.get("auth_token")
        if not await validate_token(token):
            raise AuthenticationError()
    return await next(event_name, data)

@middleware
async def metrics_middleware(event_name: str, data: Dict, next: Callable):
    """Collect metrics for all events."""
    start = time.time()
    try:
        result = await next(event_name, data)
        record_success(event_name, time.time() - start)
        return result
    except Exception as e:
        record_failure(event_name, time.time() - start, e)
        raise
```

### 9. Event Versioning

**Current State**: No versioning strategy

**Enhancement Opportunity**:
```python
@event_handler("completion:async", version="2.0")
@deprecates("completion:request", "Use completion:async instead")
def handle_completion_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """V2 completion with priority support."""
    pass

# Automatic version negotiation
{"event": "completion:async", "version": "2.0", "data": {...}}
{"event": "completion:async", "data": {...}}  # Uses latest
```

### 10. Tool Bridge System

**Current State**: No direct tool integration

**Enhancement Opportunity**:
```python
# Bridge KSI events to Claude tools
class KSIToolBridge:
    def __init__(self, client: EventClient):
        self.client = client
        
    async def generate_tools(self) -> List[Dict]:
        """Generate Claude tool definitions from KSI events."""
        tools = []
        discovery = await self.client.system.discover()
        
        for namespace, events in discovery["events"].items():
            for event in events:
                if self._should_expose_as_tool(event):
                    tools.append(self._event_to_tool(event))
        
        return tools
    
    def _event_to_tool(self, event: Dict) -> Dict:
        """Convert KSI event to Claude tool definition."""
        return {
            "name": f"ksi_{event['event'].replace(':', '_')}",
            "description": event["summary"],
            "input_schema": {
                "type": "object",
                "properties": self._convert_parameters(event["parameters"]),
                "required": event.get("required_params", [])
            }
        }
```

## Implementation Roadmap

### Phase 1: Foundation (1 week)
1. Structured error system
2. Event metadata enhancements
3. Basic contract system

### Phase 2: Discovery (1 week)
1. Plugin capability manifests
2. Event relationship tracking
3. Workflow definitions

### Phase 3: Integration (2 weeks)
1. Tool bridge system
2. Event middleware
3. Testing framework

### Phase 4: Advanced (2 weeks)
1. Event versioning
2. Performance profiling
3. Advanced contracts

## Expected Benefits

### For Claude
1. **Better Understanding**: Rich metadata and examples
2. **Safer Operations**: Contracts prevent errors
3. **Efficient Workflows**: Understand event relationships
4. **Native Integration**: Tool bridge for seamless use

### For KSI
1. **Self-Documenting**: Metadata in code
2. **More Reliable**: Contracts catch bugs
3. **Better Testing**: Event test framework
4. **Future-Proof**: Versioning support

### For Users
1. **Better Errors**: Helpful suggestions
2. **Discoverable**: Rich introspection
3. **Predictable**: Contract guarantees
4. **Flexible**: Multiple integration paths

## Conclusion

These architectural enhancements would transform KSI from a powerful but opaque event system into a self-describing, contract-based platform that Claude can understand and use effectively. The key principles:

1. **Rich Metadata**: Every event self-documents
2. **Explicit Contracts**: Guarantees and invariants
3. **Relationship Tracking**: Understand workflows
4. **Tool Integration**: Native Claude support
5. **Testing First**: Verifiable behavior

With these enhancements, Claude could:
- Automatically discover and understand all capabilities
- Generate appropriate tool calls from events
- Reason about workflows and dependencies
- Provide helpful error recovery suggestions
- Test interactions before execution