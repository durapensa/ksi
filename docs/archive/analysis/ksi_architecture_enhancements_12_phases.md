# KSI Architectural Enhancement Opportunities

## Executive Summary

This document presents 12 major architectural enhancements for KSI, organized into four implementation phases. Each enhancement builds on KSI's existing event-driven foundation while introducing modern patterns that improve scalability, composability, and developer experience.

## Phase 1: Foundation (Weeks 1-2)

### 1. Event Envelope & Middleware System

**Problem**: Manual correlation ID management, inconsistent error handling, and repeated cross-cutting concerns.

**Solution**: Introduce a typed event envelope with middleware pipeline.

```python
# ksi_common/events/envelope.py
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
import uuid
from datetime import datetime

@dataclass
class EventMetadata:
    correlation_id: str
    timestamp: datetime
    source: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
@dataclass
class EventEnvelope:
    event_name: str
    data: Dict[str, Any]
    metadata: EventMetadata
    
    @classmethod
    def create(cls, event_name: str, data: Dict[str, Any], source: str) -> 'EventEnvelope':
        return cls(
            event_name=event_name,
            data=data,
            metadata=EventMetadata(
                correlation_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                source=source
            )
        )

# Middleware system
class EventMiddleware:
    def __init__(self):
        self.middleware_stack: List[Callable] = []
    
    def use(self, middleware: Callable):
        """Add middleware to the stack."""
        self.middleware_stack.append(middleware)
    
    async def process(self, envelope: EventEnvelope):
        """Process envelope through middleware stack."""
        for middleware in self.middleware_stack:
            envelope = await middleware(envelope)
        return envelope

# Example middleware
async def logging_middleware(envelope: EventEnvelope) -> EventEnvelope:
    logger.info(f"Processing event: {envelope.event_name}", 
                correlation_id=envelope.metadata.correlation_id)
    return envelope

async def auth_middleware(envelope: EventEnvelope) -> EventEnvelope:
    # Verify permissions based on envelope metadata
    if not check_permissions(envelope.metadata.source, envelope.event_name):
        raise PermissionError(f"Denied: {envelope.event_name}")
    return envelope
```

**Benefits**:
- Automatic correlation ID propagation
- Consistent cross-cutting concerns (logging, auth, metrics)
- Cleaner plugin code focused on business logic
- Easy to add new middleware (rate limiting, circuit breaking)

### 2. Async-First Plugin System

**Problem**: Mixed sync/async hooks require runtime checks and limit performance.

**Solution**: Explicit async plugin variants with concurrent execution support.

```python
# ksi_daemon/async_hookspecs.py
import pluggy
from typing import List, Dict, Any, AsyncIterator

hookspec = pluggy.HookspecMarker("ksi")

@hookspec
async def ksi_handle_event_async(
    envelope: EventEnvelope, 
    context: EventContext
) -> Optional[EventEnvelope]:
    """Async event handler with envelope pattern."""

@hookspec
async def ksi_stream_event_async(
    envelope: EventEnvelope,
    context: EventContext  
) -> AsyncIterator[EventEnvelope]:
    """Streaming event handler for long-running operations."""

@hookspec
async def ksi_ready_async() -> Dict[str, Any]:
    """Async plugin initialization with service registration."""

# Enhanced plugin base
class AsyncPlugin:
    """Base class for async-first plugins."""
    
    async def initialize(self):
        """Async initialization logic."""
        pass
    
    async def shutdown(self):
        """Async cleanup logic."""
        pass
    
    @property
    def supports_concurrent_execution(self) -> bool:
        """Whether this plugin can handle concurrent events."""
        return True

# Router enhancement for concurrent execution
class ConcurrentEventRouter:
    async def route_event(self, envelope: EventEnvelope):
        # Get all plugins that handle this event
        handlers = self.get_handlers(envelope.event_name)
        
        # Separate concurrent and sequential handlers
        concurrent = [h for h in handlers if h.supports_concurrent_execution]
        sequential = [h for h in handlers if not h.supports_concurrent_execution]
        
        # Execute concurrent handlers in parallel
        if concurrent:
            results = await asyncio.gather(*[
                handler.ksi_handle_event_async(envelope, self.context)
                for handler in concurrent
            ])
            # First non-None result wins
            for result in results:
                if result:
                    return result
        
        # Execute sequential handlers
        for handler in sequential:
            result = await handler.ksi_handle_event_async(envelope, self.context)
            if result:
                return result
```

**Benefits**:
- No runtime async detection needed
- Parallel plugin execution for better performance
- Explicit streaming support for long operations
- Clean async lifecycle management

### 3. Unified Result Type 

**Problem**: Inconsistent error handling with mix of None, dict, and exceptions.

**Solution**: Railway-oriented programming with Result type.

```python
# ksi_common/result.py
from typing import TypeVar, Generic, Union, Callable, Optional
from dataclasses import dataclass

T = TypeVar('T')
E = TypeVar('E')

@dataclass
class Success(Generic[T]):
    value: T

@dataclass  
class Failure(Generic[E]):
    error: E

Result = Union[Success[T], Failure[E]]

class ResultOps:
    """Functional operations on Result types."""
    
    @staticmethod
    def map(result: Result[T, E], func: Callable[[T], T]) -> Result[T, E]:
        """Map function over success value."""
        match result:
            case Success(value):
                return Success(func(value))
            case Failure(error):
                return Failure(error)
    
    @staticmethod
    def flat_map(result: Result[T, E], func: Callable[[T], Result[T, E]]) -> Result[T, E]:
        """Monadic bind operation."""
        match result:
            case Success(value):
                return func(value)
            case Failure(error):
                return Failure(error)
    
    @staticmethod
    def map_error(result: Result[T, E], func: Callable[[E], E]) -> Result[T, E]:
        """Map function over error value."""
        match result:
            case Success(value):
                return Success(value)
            case Failure(error):
                return Failure(func(error))

# Usage in plugins
async def handle_completion(envelope: EventEnvelope) -> Result[Dict, KSIError]:
    try:
        # Validate input
        validation = validate_prompt(envelope.data.get('prompt'))
        if not validation.is_valid:
            return Failure(ValidationError(validation.errors))
        
        # Call LLM
        response = await call_llm(envelope.data)
        
        # Transform response
        return Success({
            'response': response.text,
            'model': response.model,
            'usage': response.usage
        })
        
    except LLMError as e:
        return Failure(ServiceError(f"LLM failed: {e}"))
```

**Benefits**:
- Explicit error handling without exceptions in hot path
- Composable error transformations
- Type-safe error propagation
- Functional programming patterns

## Phase 2: Compositional Power (Weeks 3-4)

### 4. Type-Safe Event Registry

**Problem**: Events discovered at runtime with no compile-time guarantees.

**Solution**: Type-safe event registry with runtime validation.

```python
# ksi_common/events/registry.py
from typing import Type, Dict, Any, Protocol, runtime_checkable
from pydantic import BaseModel, ValidationError

@runtime_checkable
class EventHandler(Protocol):
    """Protocol for type-safe event handlers."""
    
    async def handle(self, data: BaseModel) -> BaseModel:
        ...

class EventRegistry:
    """Type-safe event registry with schema validation."""
    
    def __init__(self):
        self._events: Dict[str, Type[BaseModel]] = {}
        self._responses: Dict[str, Type[BaseModel]] = {}
        self._handlers: Dict[str, EventHandler] = {}
    
    def register_event(
        self,
        event_name: str,
        request_schema: Type[BaseModel],
        response_schema: Type[BaseModel],
        handler: Optional[EventHandler] = None
    ):
        """Register event with type information."""
        self._events[event_name] = request_schema
        self._responses[event_name] = response_schema
        if handler:
            self._handlers[event_name] = handler
    
    async def emit(self, event_name: str, data: Dict[str, Any]) -> BaseModel:
        """Emit event with automatic validation."""
        # Validate request
        request_schema = self._events.get(event_name)
        if not request_schema:
            raise ValueError(f"Unknown event: {event_name}")
        
        try:
            validated_data = request_schema(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid data for {event_name}: {e}")
        
        # Find handler
        handler = self._handlers.get(event_name)
        if not handler:
            raise ValueError(f"No handler for {event_name}")
        
        # Execute with validated data
        response = await handler.handle(validated_data)
        
        # Validate response
        response_schema = self._responses[event_name]
        if not isinstance(response, response_schema):
            raise TypeError(f"Invalid response type for {event_name}")
        
        return response

# Example usage
class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: int = 100
    temperature: float = 0.7

class CompletionResponse(BaseModel):
    text: str
    usage: Dict[str, int]

registry = EventRegistry()
registry.register_event(
    "completion:async",
    CompletionRequest,
    CompletionResponse,
    CompletionHandler()
)

# Type-safe emission
response = await registry.emit("completion:async", {
    "prompt": "Hello, world!",
    "max_tokens": 50
})
# response is guaranteed to be CompletionResponse
```

**Benefits**:
- Compile-time type checking with mypy
- Runtime validation with Pydantic
- Self-documenting API from schemas
- Generated TypeScript/OpenAPI definitions

### 5. Composition Layers

**Problem**: Limited primitives for composing complex event flows.

**Solution**: Higher-order event combinators and flow composition.

```python
# ksi_common/composition.py
from typing import List, Callable, Any, TypeVar
from functools import reduce

T = TypeVar('T')

class EventFlow:
    """Composable event flow builder."""
    
    def __init__(self, registry: EventRegistry):
        self.registry = registry
        self.steps: List[Callable] = []
    
    def then(self, event_name: str, transform: Optional[Callable] = None):
        """Add event to flow with optional transformation."""
        async def step(data):
            result = await self.registry.emit(event_name, data)
            return transform(result) if transform else result
        
        self.steps.append(step)
        return self
    
    def parallel(self, *event_names: str):
        """Execute events in parallel."""
        async def step(data):
            results = await asyncio.gather(*[
                self.registry.emit(event, data) for event in event_names
            ])
            return results
        
        self.steps.append(step)
        return self
    
    def conditional(self, predicate: Callable, true_event: str, false_event: str):
        """Conditional branching."""
        async def step(data):
            event = true_event if predicate(data) else false_event
            return await self.registry.emit(event, data)
        
        self.steps.append(step)
        return self
    
    async def execute(self, initial_data: Any):
        """Execute the composed flow."""
        return await reduce(
            lambda acc, step: step(acc),
            self.steps,
            initial_data
        )

# Composition layer for behavior building
class CompositionLayer:
    """Layer for composing agent behaviors."""
    
    def __init__(self):
        self.layers: List[Callable] = []
    
    def add_behavior(self, behavior: Callable):
        """Add behavior layer."""
        self.layers.append(behavior)
    
    def compose(self) -> Callable:
        """Compose all layers into single behavior."""
        async def composed(data):
            result = data
            for layer in self.layers:
                result = await layer(result)
            return result
        return composed
    
    def __add__(self, other: 'CompositionLayer') -> 'CompositionLayer':
        """Combine composition layers."""
        new_layer = CompositionLayer()
        new_layer.layers = self.layers + other.layers
        return new_layer

# Example: Composed chat behavior
auth_layer = CompositionLayer()
auth_layer.add_behavior(verify_permissions)
auth_layer.add_behavior(check_rate_limits)

completion_layer = CompositionLayer()
completion_layer.add_behavior(validate_prompt)
completion_layer.add_behavior(enhance_prompt)
completion_layer.add_behavior(call_llm)

chat_behavior = auth_layer + completion_layer
```

**Benefits**:
- Declarative flow composition
- Reusable behavior layers
- Easy to test individual components
- Visual flow representation possible

### 6. Streaming Event Client

**Problem**: Limited to request/response pattern, no streaming support.

**Solution**: Streaming client with backpressure and cancellation.

```python
# ksi_client/streaming.py
from typing import AsyncIterator, Optional, Dict, Any
import asyncio

class StreamingEventClient(EventClient):
    """Enhanced client with streaming support."""
    
    async def stream_event(
        self,
        event_name: str,
        data: Dict[str, Any],
        buffer_size: int = 10
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream responses with backpressure control."""
        if not self.connected:
            raise KSIConnectionError("Not connected")
        
        # Create stream request
        stream_id = str(uuid.uuid4())
        request = {
            "event": event_name,
            "data": data,
            "stream_id": stream_id,
            "stream": True
        }
        
        # Setup stream buffer with backpressure
        stream_buffer = asyncio.Queue(maxsize=buffer_size)
        self._active_streams[stream_id] = stream_buffer
        
        try:
            # Send request
            await self._send_message(request)
            
            # Yield responses as they arrive
            while True:
                try:
                    # Wait for next chunk with timeout
                    chunk = await asyncio.wait_for(
                        stream_buffer.get(),
                        timeout=30.0
                    )
                    
                    # Check for end of stream
                    if chunk.get("stream_end"):
                        break
                    
                    yield chunk
                    
                except asyncio.TimeoutError:
                    raise KSITimeoutError("Stream timeout")
                    
        finally:
            # Cleanup stream
            self._active_streams.pop(stream_id, None)
            
            # Send cancel if still active
            if self.connected:
                await self._send_message({
                    "event": "stream:cancel",
                    "stream_id": stream_id
                })
    
    async def subscribe_to_events(
        self,
        pattern: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> 'Subscription':
        """Subscribe to event pattern with automatic reconnection."""
        subscription = Subscription(pattern, handler)
        
        # Send subscription request
        await self._send_message({
            "event": "pubsub:subscribe",
            "pattern": pattern,
            "subscription_id": subscription.id
        })
        
        self._subscriptions[subscription.id] = subscription
        return subscription

class Subscription:
    """Manages event subscription lifecycle."""
    
    def __init__(self, pattern: str, handler: Callable):
        self.id = str(uuid.uuid4())
        self.pattern = pattern
        self.handler = handler
        self.active = True
    
    async def unsubscribe(self):
        """Cancel subscription."""
        self.active = False
        # Actual unsubscribe logic here
```

**Benefits**:
- Real-time event streaming
- Backpressure control prevents overwhelming
- Automatic reconnection handling
- Clean cancellation semantics

## Phase 3: Advanced Patterns (Weeks 5-6)

### 7. Event Store & Time-Travel

**Problem**: No event replay capability, cannot reconstruct system state.

**Solution**: Persistent event store with time-travel debugging.

```python
# ksi_daemon/infrastructure/event_store.py
from typing import List, Optional, AsyncIterator
import aiosqlite
from datetime import datetime

class EventStore:
    """Persistent event store with replay capabilities."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def initialize(self):
        """Create event store schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stream_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    INDEX idx_stream (stream_id, sequence_id),
                    INDEX idx_timestamp (timestamp)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    stream_id TEXT NOT NULL,
                    sequence_id INTEGER NOT NULL,
                    state_data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (stream_id, sequence_id)
                )
            """)
    
    async def append(self, stream_id: str, event: EventEnvelope) -> int:
        """Append event to stream."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO events (stream_id, event_name, event_data, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                stream_id,
                event.event_name,
                json.dumps(event.data),
                json.dumps(asdict(event.metadata)),
                event.metadata.timestamp.timestamp()
            ))
            
            await db.commit()
            return cursor.lastrowid
    
    async def read_stream(
        self,
        stream_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None
    ) -> AsyncIterator[EventEnvelope]:
        """Read events from stream."""
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT event_name, event_data, metadata 
                FROM events 
                WHERE stream_id = ? AND sequence_id >= ?
            """
            params = [stream_id, from_sequence]
            
            if to_sequence:
                query += " AND sequence_id <= ?"
                params.append(to_sequence)
            
            query += " ORDER BY sequence_id"
            
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    yield self._deserialize_event(row)
    
    async def time_travel(
        self,
        stream_id: str,
        target_time: datetime
    ) -> AsyncIterator[EventEnvelope]:
        """Replay events up to specific time."""
        async with aiosqlite.connect(self.db_path) as db:
            # Find nearest snapshot before target time
            cursor = await db.execute("""
                SELECT sequence_id, state_data 
                FROM snapshots 
                WHERE stream_id = ? AND timestamp <= ?
                ORDER BY timestamp DESC LIMIT 1
            """, (stream_id, target_time.timestamp()))
            
            snapshot = await cursor.fetchone()
            start_sequence = snapshot[0] if snapshot else 0
            
            # Replay events from snapshot to target time
            async with db.execute("""
                SELECT event_name, event_data, metadata 
                FROM events 
                WHERE stream_id = ? AND sequence_id > ? AND timestamp <= ?
                ORDER BY sequence_id
            """, (stream_id, start_sequence, target_time.timestamp())) as cursor:
                async for row in cursor:
                    yield self._deserialize_event(row)

# Time-travel debugging interface
class TimeTravelDebugger:
    """Debug system state at any point in time."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    async def reconstruct_state(self, timestamp: datetime) -> Dict[str, Any]:
        """Reconstruct complete system state at timestamp."""
        state = {}
        
        # Get all streams
        streams = await self.get_all_streams()
        
        for stream_id in streams:
            # Replay events for each stream
            stream_state = {}
            async for event in self.event_store.time_travel(stream_id, timestamp):
                # Apply event to state
                stream_state = self.apply_event(stream_state, event)
            
            state[stream_id] = stream_state
        
        return state
    
    async def find_state_change(
        self,
        stream_id: str,
        predicate: Callable[[Dict], bool]
    ) -> Optional[EventEnvelope]:
        """Find when specific state change occurred."""
        state = {}
        
        async for event in self.event_store.read_stream(stream_id):
            old_state = state.copy()
            state = self.apply_event(state, event)
            
            if predicate(state) and not predicate(old_state):
                return event
        
        return None
```

**Benefits**:
- Complete audit trail of all events
- Time-travel debugging capability
- State reconstruction at any point
- Event sourcing patterns enabled

### 8. Distributed Transactions (Sagas)

**Problem**: No support for distributed transactions across services.

**Solution**: Saga pattern with automatic compensation.

```python
# ksi_daemon/sagas.py
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum

class SagaStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"

@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    retry_policy: Optional[Dict[str, Any]] = None

class Saga:
    """Distributed transaction coordinator."""
    
    def __init__(self, saga_id: str, steps: List[SagaStep]):
        self.saga_id = saga_id
        self.steps = steps
        self.status = SagaStatus.PENDING
        self.completed_steps: List[str] = []
        self.step_results: Dict[str, Any] = {}
    
    async def execute(self, initial_data: Dict[str, Any]) -> Result[Dict, SagaError]:
        """Execute saga with automatic compensation on failure."""
        self.status = SagaStatus.RUNNING
        current_data = initial_data
        
        try:
            # Execute each step
            for step in self.steps:
                result = await self._execute_step(step, current_data)
                
                if isinstance(result, Failure):
                    # Step failed, start compensation
                    await self._compensate()
                    return result
                
                # Step succeeded
                self.completed_steps.append(step.name)
                self.step_results[step.name] = result.value
                current_data = result.value
            
            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            return Success(self.step_results)
            
        except Exception as e:
            # Unexpected error, compensate
            await self._compensate()
            return Failure(SagaError(f"Saga failed: {e}"))
    
    async def _execute_step(
        self,
        step: SagaStep,
        data: Dict[str, Any]
    ) -> Result[Dict, StepError]:
        """Execute single step with retry policy."""
        retry_count = 0
        max_retries = step.retry_policy.get("max_retries", 3) if step.retry_policy else 0
        
        while retry_count <= max_retries:
            try:
                result = await step.action(data)
                return Success(result)
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    return Failure(StepError(step.name, str(e)))
                
                # Wait before retry
                delay = step.retry_policy.get("delay", 1) * retry_count
                await asyncio.sleep(delay)
    
    async def _compensate(self):
        """Run compensation for completed steps in reverse order."""
        self.status = SagaStatus.COMPENSATING
        
        for step_name in reversed(self.completed_steps):
            step = next(s for s in self.steps if s.name == step_name)
            
            if step.compensation:
                try:
                    step_data = self.step_results.get(step_name, {})
                    await step.compensation(step_data)
                except Exception as e:
                    logger.error(f"Compensation failed for {step_name}: {e}")
        
        self.status = SagaStatus.FAILED

# Example: Multi-agent completion saga
class CompletionSaga(Saga):
    """Saga for distributed completion across multiple agents."""
    
    def __init__(self):
        steps = [
            SagaStep(
                name="validate_permissions",
                action=self.validate_permissions,
                compensation=None  # No compensation needed
            ),
            SagaStep(
                name="reserve_resources",
                action=self.reserve_resources,
                compensation=self.release_resources,
                retry_policy={"max_retries": 3, "delay": 1}
            ),
            SagaStep(
                name="execute_completion",
                action=self.execute_completion,
                compensation=self.cancel_completion
            ),
            SagaStep(
                name="store_results",
                action=self.store_results,
                compensation=self.delete_results
            )
        ]
        
        super().__init__(f"completion_{uuid.uuid4()}", steps)
    
    async def validate_permissions(self, data: Dict) -> Dict:
        # Check if user has permission for requested operation
        return {"validated": True, "profile": data["permission_profile"]}
    
    async def reserve_resources(self, data: Dict) -> Dict:
        # Reserve compute resources for completion
        return {"resource_id": "gpu_123", "reserved_until": "..."}
    
    async def release_resources(self, data: Dict) -> None:
        # Release reserved resources
        await release_resource(data["resource_id"])
```

**Benefits**:
- Distributed transaction support
- Automatic compensation on failure
- Retry policies per step
- Complete transaction visibility

### 9. Resource Pool Management

**Problem**: No resource pooling for expensive operations.

**Solution**: Generic async resource pool with health checks.

```python
# ksi_common/pools.py
from typing import TypeVar, Generic, List, Optional, Callable
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

T = TypeVar('T')

@dataclass
class PooledResource(Generic[T]):
    resource: T
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    health_check_failed: bool = False

class ResourcePool(Generic[T]):
    """Generic async resource pool with health management."""
    
    def __init__(
        self,
        factory: Callable[[], T],
        min_size: int = 1,
        max_size: int = 10,
        health_check: Optional[Callable[[T], bool]] = None,
        max_age: Optional[timedelta] = None,
        max_uses: Optional[int] = None
    ):
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self.health_check = health_check
        self.max_age = max_age
        self.max_uses = max_uses
        
        self.pool: List[PooledResource[T]] = []
        self.available: asyncio.Queue[PooledResource[T]] = asyncio.Queue()
        self.size = 0
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Pre-warm pool to minimum size."""
        for _ in range(self.min_size):
            resource = await self._create_resource()
            await self.available.put(resource)
    
    async def acquire(self, timeout: Optional[float] = None) -> T:
        """Acquire resource from pool."""
        deadline = time.time() + timeout if timeout else None
        
        while True:
            # Try to get available resource
            try:
                remaining = deadline - time.time() if deadline else None
                if remaining and remaining <= 0:
                    raise asyncio.TimeoutError()
                
                pooled = await asyncio.wait_for(
                    self.available.get(),
                    timeout=remaining
                )
            except asyncio.TimeoutError:
                # No available resources, try to create new one
                async with self._lock:
                    if self.size < self.max_size:
                        pooled = await self._create_resource()
                        break
                    else:
                        raise ResourcePoolExhausted()
            
            # Check if resource is still valid
            if await self._is_resource_valid(pooled):
                pooled.last_used = datetime.utcnow()
                pooled.use_count += 1
                return pooled.resource
            else:
                # Resource invalid, destroy and create new one
                await self._destroy_resource(pooled)
                if self.size < self.max_size:
                    pooled = await self._create_resource()
                    return pooled.resource
    
    async def release(self, resource: T):
        """Return resource to pool."""
        # Find pooled wrapper
        pooled = next((p for p in self.pool if p.resource == resource), None)
        if not pooled:
            return
        
        # Check if resource should be retired
        if not await self._is_resource_valid(pooled):
            await self._destroy_resource(pooled)
            # Create replacement if below minimum
            if self.size < self.min_size:
                new_pooled = await self._create_resource()
                await self.available.put(new_pooled)
        else:
            # Return to available queue
            await self.available.put(pooled)
    
    async def _create_resource(self) -> PooledResource[T]:
        """Create new pooled resource."""
        resource = await self.factory()
        pooled = PooledResource(
            resource=resource,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow()
        )
        
        async with self._lock:
            self.pool.append(pooled)
            self.size += 1
        
        return pooled
    
    async def _is_resource_valid(self, pooled: PooledResource[T]) -> bool:
        """Check if resource is still valid."""
        # Age check
        if self.max_age:
            age = datetime.utcnow() - pooled.created_at
            if age > self.max_age:
                return False
        
        # Use count check
        if self.max_uses and pooled.use_count >= self.max_uses:
            return False
        
        # Health check
        if self.health_check:
            try:
                return await self.health_check(pooled.resource)
            except Exception:
                return False
        
        return True

# Example: LLM connection pool
class LLMConnectionPool(ResourcePool[LLMConnection]):
    """Pool for expensive LLM connections."""
    
    def __init__(self):
        super().__init__(
            factory=self.create_connection,
            min_size=2,
            max_size=10,
            health_check=self.check_connection_health,
            max_age=timedelta(minutes=30),
            max_uses=1000
        )
    
    async def create_connection(self) -> LLMConnection:
        """Create new LLM connection."""
        return await LLMConnection.connect(
            api_key=config.llm_api_key,
            timeout=30
        )
    
    async def check_connection_health(self, conn: LLMConnection) -> bool:
        """Verify connection is still alive."""
        try:
            await conn.ping()
            return True
        except Exception:
            return False
```

**Benefits**:
- Reusable connection pooling
- Automatic health management
- Resource lifecycle control
- Performance optimization

## Phase 4: Resilience & Scale (Weeks 7-8)

### 10. Adaptive Circuit Breaker

**Problem**: Simple circuit breakers don't adapt to changing conditions.

**Solution**: ML-based adaptive circuit breaker.

```python
# ksi_daemon/resilience/circuit_breaker.py
from typing import Callable, Optional, Dict, Any
import numpy as np
from collections import deque
from datetime import datetime, timedelta

class AdaptiveCircuitBreaker:
    """Circuit breaker that learns from system behavior."""
    
    def __init__(
        self,
        failure_threshold: float = 0.5,
        recovery_timeout: timedelta = timedelta(seconds=60),
        window_size: int = 100
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_size = window_size
        
        # State
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        
        # Adaptive learning
        self.response_times = deque(maxlen=window_size)
        self.error_patterns = deque(maxlen=window_size)
        self.load_metrics = deque(maxlen=window_size)
        
        # ML model for prediction
        self.predictor = self._initialize_predictor()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is open")
        
        # Predict failure probability
        failure_probability = self._predict_failure()
        
        # Adaptive threshold adjustment
        if failure_probability > self.failure_threshold * 1.5:
            # Preemptively open circuit if high failure probability
            self.state = CircuitState.OPEN
            raise CircuitOpenError("Preemptive circuit break")
        
        # Execute function
        start_time = datetime.utcnow()
        try:
            result = await func(*args, **kwargs)
            
            # Record success
            self._record_success(start_time)
            
            # Reset circuit if in half-open state
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            
            return result
            
        except Exception as e:
            # Record failure
            self._record_failure(start_time, e)
            
            # Update circuit state
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.CLOSED:
                if self._failure_rate() > self.failure_threshold:
                    self.state = CircuitState.OPEN
            
            raise
    
    def _predict_failure(self) -> float:
        """Use ML to predict failure probability."""
        if len(self.response_times) < 10:
            return 0.0  # Not enough data
        
        # Extract features
        features = self._extract_features()
        
        # Simple prediction model (can be replaced with more sophisticated ML)
        recent_failure_rate = sum(self.error_patterns[-10:]) / 10
        response_time_trend = np.polyfit(range(10), list(self.response_times)[-10:], 1)[0]
        load_spike = max(self.load_metrics[-5:]) if self.load_metrics else 0
        
        # Weighted prediction
        failure_probability = (
            0.5 * recent_failure_rate +
            0.3 * (1 if response_time_trend > 0.1 else 0) +
            0.2 * (1 if load_spike > 0.8 else 0)
        )
        
        return failure_probability
    
    def _extract_features(self) -> Dict[str, float]:
        """Extract features for ML prediction."""
        return {
            "avg_response_time": np.mean(self.response_times),
            "response_time_std": np.std(self.response_times),
            "recent_failure_rate": sum(self.error_patterns[-20:]) / 20,
            "load_trend": np.polyfit(range(len(self.load_metrics)), 
                                    list(self.load_metrics), 1)[0],
            "time_since_last_failure": (
                (datetime.utcnow() - self.last_failure_time).total_seconds()
                if self.last_failure_time else float('inf')
            )
        }
    
    def update_load_metric(self, load: float):
        """Update system load metric for prediction."""
        self.load_metrics.append(load)

class CircuitBreakerManager:
    """Manages circuit breakers across services."""
    
    def __init__(self):
        self.breakers: Dict[str, AdaptiveCircuitBreaker] = {}
    
    def get_breaker(self, service: str) -> AdaptiveCircuitBreaker:
        """Get or create circuit breaker for service."""
        if service not in self.breakers:
            self.breakers[service] = AdaptiveCircuitBreaker()
        return self.breakers[service]
    
    async def call_with_breaker(
        self,
        service: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Call function with circuit breaker protection."""
        breaker = self.get_breaker(service)
        return await breaker.call(func, *args, **kwargs)
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health status of all circuit breakers."""
        return {
            service: {
                "state": breaker.state.value,
                "failure_rate": breaker._failure_rate(),
                "predicted_failure_probability": breaker._predict_failure()
            }
            for service, breaker in self.breakers.items()
        }
```

**Benefits**:
- Predictive failure prevention
- Adaptive threshold adjustment
- System-wide health visibility
- Reduced cascading failures

### 11. Event Testing Framework

**Problem**: Testing event-driven systems is complex.

**Solution**: BDD-style event testing framework.

```python
# ksi_testing/event_test.py
from typing import List, Dict, Any, Callable
import asyncio

class EventTestHarness:
    """BDD-style testing for event-driven systems."""
    
    def __init__(self):
        self.given_events: List[EventEnvelope] = []
        self.when_event: Optional[EventEnvelope] = None
        self.then_expectations: List[Callable] = []
        self.mock_handlers: Dict[str, Callable] = {}
    
    def given(self, *events: EventEnvelope) -> 'EventTestHarness':
        """Setup initial events."""
        self.given_events.extend(events)
        return self
    
    def when(self, event: EventEnvelope) -> 'EventTestHarness':
        """Specify event to test."""
        self.when_event = event
        return self
    
    def then(self, expectation: Callable) -> 'EventTestHarness':
        """Add expectation to verify."""
        self.then_expectations.append(expectation)
        return self
    
    def mock_handler(self, event_name: str, handler: Callable) -> 'EventTestHarness':
        """Mock specific event handler."""
        self.mock_handlers[event_name] = handler
        return self
    
    async def run(self) -> TestResult:
        """Execute test scenario."""
        # Create test event store
        event_store = InMemoryEventStore()
        
        # Create test router with mocked handlers
        router = TestEventRouter(self.mock_handlers)
        
        # Apply given events
        for event in self.given_events:
            await event_store.append("test", event)
            await router.route_event(event)
        
        # Execute when event
        if self.when_event:
            await event_store.append("test", self.when_event)
            result = await router.route_event(self.when_event)
        else:
            result = None
        
        # Verify expectations
        failures = []
        for expectation in self.then_expectations:
            try:
                await expectation(event_store, result)
            except AssertionError as e:
                failures.append(str(e))
        
        return TestResult(
            passed=len(failures) == 0,
            failures=failures,
            events_processed=len(self.given_events) + (1 if self.when_event else 0)
        )

# Example test
async def test_completion_with_permission_check():
    """Test that completion checks permissions."""
    
    result = await (
        EventTestHarness()
        .given(
            EventEnvelope.create("permission:grant", {
                "user": "alice",
                "permission": "completion:*"
            }, "test")
        )
        .when(
            EventEnvelope.create("completion:async", {
                "prompt": "Hello",
                "user": "alice"
            }, "test")
        )
        .then(lambda store, result: 
            assert result.data.get("response") is not None
        )
        .then(lambda store, result:
            assert "permission:check" in [e.event_name for e in store.events]
        )
        .run()
    )
    
    assert result.passed

# Property-based testing for events
from hypothesis import given, strategies as st

class EventPropertyTest:
    """Property-based testing for event handlers."""
    
    @given(
        prompt=st.text(min_size=1, max_size=1000),
        temperature=st.floats(min_value=0.0, max_value=2.0)
    )
    async def test_completion_always_returns_text(self, prompt: str, temperature: float):
        """Verify completion always returns text."""
        event = EventEnvelope.create("completion:async", {
            "prompt": prompt,
            "temperature": temperature
        }, "test")
        
        result = await self.router.route_event(event)
        
        assert isinstance(result.data.get("response"), str)
        assert len(result.data["response"]) > 0
```

**Benefits**:
- BDD-style event testing
- Property-based testing support
- Event flow verification
- Mock handler injection

### 12. Multi-Daemon Federation

**Problem**: Single daemon limits horizontal scaling.

**Solution**: Federated daemon architecture with routing.

```python
# ksi_daemon/federation.py
from typing import List, Dict, Any, Optional
import consistent_hash

class DaemonNode:
    """Represents a daemon in the federation."""
    
    def __init__(self, node_id: str, address: str, capabilities: List[str]):
        self.node_id = node_id
        self.address = address
        self.capabilities = capabilities
        self.health_score = 1.0
        self.load = 0.0
    
    def can_handle(self, event_name: str) -> bool:
        """Check if node can handle event type."""
        namespace = event_name.split(":")[0]
        return namespace in self.capabilities

class FederationRouter:
    """Routes events across federated daemons."""
    
    def __init__(self):
        self.nodes: Dict[str, DaemonNode] = {}
        self.hash_ring = consistent_hash.ConsistentHash()
        self.local_node_id = str(uuid.uuid4())
    
    def register_node(self, node: DaemonNode):
        """Register daemon node in federation."""
        self.nodes[node.node_id] = node
        self.hash_ring.add_node(node.node_id)
    
    async def route_event(self, envelope: EventEnvelope) -> Optional[EventEnvelope]:
        """Route event to appropriate daemon."""
        # Determine target node
        target_node = self._select_node(envelope)
        
        if target_node.node_id == self.local_node_id:
            # Handle locally
            return await self.local_router.route_event(envelope)
        else:
            # Forward to remote daemon
            return await self._forward_to_node(target_node, envelope)
    
    def _select_node(self, envelope: EventEnvelope) -> DaemonNode:
        """Select best node for event."""
        event_name = envelope.event_name
        
        # Get nodes that can handle this event
        capable_nodes = [
            node for node in self.nodes.values()
            if node.can_handle(event_name)
        ]
        
        if not capable_nodes:
            raise NoCapableNode(f"No node can handle {event_name}")
        
        # Select based on load and health
        return min(capable_nodes, key=lambda n: n.load / n.health_score)
    
    async def _forward_to_node(
        self,
        node: DaemonNode,
        envelope: EventEnvelope
    ) -> Optional[EventEnvelope]:
        """Forward event to remote daemon."""
        async with RemoteDaemonClient(node.address) as client:
            return await client.send_event(envelope)

class FederatedEventClient(EventClient):
    """Client that discovers and uses federated daemons."""
    
    def __init__(self, discovery_service: str):
        super().__init__()
        self.discovery_service = discovery_service
        self.federation_router = FederationRouter()
    
    async def discover_federation(self):
        """Discover all daemons in federation."""
        response = await self.http_client.get(f"{self.discovery_service}/nodes")
        
        for node_data in response.json():
            node = DaemonNode(
                node_id=node_data["id"],
                address=node_data["address"],
                capabilities=node_data["capabilities"]
            )
            self.federation_router.register_node(node)
    
    async def send_event(
        self,
        event_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send event through federation."""
        envelope = EventEnvelope.create(event_name, data, self.client_id)
        
        # Let federation router handle it
        result = await self.federation_router.route_event(envelope)
        
        if result:
            return result.data
        else:
            raise KSIEventError(event_name, "No response from federation")

# Federation coordinator
class FederationCoordinator:
    """Coordinates daemon federation."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peers: Dict[str, DaemonNode] = {}
        self.gossip_protocol = GossipProtocol()
    
    async def join_federation(self, seed_nodes: List[str]):
        """Join existing federation."""
        for seed in seed_nodes:
            try:
                async with RemoteDaemonClient(seed) as client:
                    # Get current federation state
                    state = await client.get_federation_state()
                    
                    # Register ourselves
                    await client.register_node(self.get_node_info())
                    
                    # Update local state
                    self.update_federation_state(state)
                    
                    break
            except Exception as e:
                logger.warning(f"Failed to join via {seed}: {e}")
    
    async def gossip_loop(self):
        """Gossip protocol for state synchronization."""
        while True:
            # Select random peer
            if self.peers:
                peer = random.choice(list(self.peers.values()))
                
                # Exchange state
                await self.gossip_protocol.exchange_state(peer, {
                    "load": self.get_current_load(),
                    "health": self.get_health_score(),
                    "capabilities": self.get_capabilities()
                })
            
            await asyncio.sleep(5)  # Gossip interval
```

**Benefits**:
- Horizontal scaling capability
- Automatic load distribution
- Capability-based routing
- Resilient federation with gossip

## Implementation Strategy

### Phase 1: Foundation (Weeks 1-2)
- Implement Event Envelope & Middleware
- Create Async-First Plugin System
- Add Unified Result Type

### Phase 2: Compositional Power (Weeks 3-4)
- Build Type-Safe Event Registry
- Implement Composition Layers
- Add Streaming Event Client

### Phase 3: Advanced Patterns (Weeks 5-6)
- Create Event Store with Time-Travel
- Implement Saga Pattern
- Build Resource Pool Management

### Phase 4: Resilience & Scale (Weeks 7-8)
- Add Adaptive Circuit Breaker
- Create Event Testing Framework
- Implement Multi-Daemon Federation

## Conclusion

These enhancements transform KSI into a modern, scalable event-driven platform while maintaining backward compatibility. The phased approach allows incremental adoption with immediate benefits at each stage.

Key improvements:
- **Better developer experience** through type safety and composition
- **Improved performance** via async-first design and resource pooling  
- **Enhanced reliability** with circuit breakers and sagas
- **Scalability** through federation and streaming

The architecture remains true to KSI's event-driven philosophy while adding the sophistication needed for production workloads.