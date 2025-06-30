# KSI Battle-Tested Architecture Migration Plan

## Executive Summary

This document outlines a migration strategy for KSI from its current Unix socket-based daemon architecture to a modern, battle-tested stack using industry-standard Python packages. The key principle: **use each tool for what it's designed for**.

- **FastAPI**: HTTP/WebSocket API layer (NOT a process manager)
- **Celery/Dramatiq**: Background task execution and subprocess management
- **Redis**: Pub/sub messaging and task queue backend
- **FastStream**: Event-driven messaging integration with FastAPI
- **SQLite/PostgreSQL**: Persistent state storage

This architecture maintains KSI's event-driven design while leveraging proven solutions that thousands of production systems rely on daily.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│            (chat.py, monitor_tui.py, orchestrate.py)            │
└───────────────┬────────────────────────────────┬───────────────┘
                │ HTTP/WebSocket                 │
┌───────────────▼────────────────────────────────▼───────────────┐
│                          FastAPI Layer                          │
│  • REST endpoints for commands                                  │
│  • WebSocket connections for real-time events                  │
│  • Request validation and routing                               │
│  • NO process management, NO blocking operations                │
└───────────────┬────────────────────────────────┬───────────────┘
                │                                │
┌───────────────▼────────────────┐  ┌───────────▼───────────────┐
│      Celery/Dramatiq Worker     │  │    FastStream Handler     │
│  • Subprocess management         │  │  • Event subscriptions    │
│  • Claude process spawning       │  │  • Message routing        │
│  • Long-running tasks           │  │  • Real-time streaming   │
│  • Task retry/failure handling  │  │  • WebSocket dispatch     │
└───────────────┬────────────────┘  └───────────┬───────────────┘
                │                                │
┌───────────────▼────────────────────────────────▼───────────────┐
│                         Redis Backend                           │
│  • Task queue (Celery/Dramatiq)                               │
│  • Pub/Sub message bus                                         │
│  • Session state cache                                         │
│  • Real-time event distribution                                │
└─────────────────────────────────────────────────────────────────┘
```

## Redis Backend Analysis

### redislite Compatibility

**redislite** is an embedded Redis that runs in-process, perfect for KSI's minimal deployment philosophy. However, it has limitations:

| Component | redislite Support | Notes |
|-----------|------------------|-------|
| Basic Redis Commands | ✅ Yes | GET, SET, PUBLISH, SUBSCRIBE work |
| Celery | ❌ No | Requires real Redis features (Lua scripts, persistence) |
| Dramatiq | ⚠️ Limited | Basic queue operations work, advanced features don't |
| FastStream | ✅ Yes | Pub/sub operations fully supported |
| Direct Pub/Sub | ✅ Yes | PUBLISH/SUBSCRIBE work perfectly |

### Recommended Alternatives

1. **Redis in Docker** (Recommended)
   ```yaml
   # docker-compose.yml
   services:
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
       volumes:
         - ./data/redis:/data
       command: redis-server --appendonly yes
   ```

2. **KeyDB** (Redis Alternative)
   - Drop-in Redis replacement
   - Better performance, multi-threading
   - Same protocol, works with all tools

3. **Hybrid Approach**
   - Use redislite for development
   - Use Redis/KeyDB for production
   - Configuration switch:
   ```python
   REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
   # Falls back to redislite if configured
   ```

## Detailed Implementation

### 1. FastAPI Application Structure

```python
# app/main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
from typing import Dict, List
import uuid

from .tasks import spawn_claude_task, register_agent_task
from .events import event_manager
from .models import (
    SpawnRequest, SpawnResponse, 
    RegisterAgentRequest, AgentStatus
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    # Start event manager
    await event_manager.start()
    yield
    # Cleanup
    await event_manager.stop()

app = FastAPI(lifespan=lifespan)

# Active WebSocket connections
websocket_connections: Dict[str, WebSocket] = {}

@app.post("/spawn", response_model=SpawnResponse)
async def spawn_claude(request: SpawnRequest):
    """Spawn a Claude process - delegates to Celery"""
    task_id = str(uuid.uuid4())
    
    # Queue task with Celery - non-blocking
    spawn_claude_task.apply_async(
        args=[request.prompt, request.session_id, request.allowed_tools],
        task_id=task_id
    )
    
    # Return immediately
    return SpawnResponse(
        task_id=task_id,
        status="queued",
        message="Claude process queued for execution"
    )

@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time event streaming"""
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    websocket_connections[connection_id] = websocket
    
    try:
        # Subscribe to events
        async def handle_event(event: dict):
            await websocket.send_json(event)
        
        await event_manager.subscribe("*", handle_event)
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
    finally:
        websocket_connections.pop(connection_id, None)

@app.post("/agents/register")
async def register_agent(request: RegisterAgentRequest):
    """Register a new agent"""
    # Queue registration task
    task = register_agent_task.apply_async(
        args=[request.dict()]
    )
    
    return {"agent_id": request.agent_id, "status": "registering"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_connections": len(websocket_connections)
    }
```

### 2. Celery Task Management

```python
# app/tasks.py
from celery import Celery, Task
import subprocess
import json
import asyncio
from typing import Optional, List
import os

# Celery configuration
celery_app = Celery(
    'ksi',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Important: Don't use pickle for security
    task_reject_on_worker_lost=True,
    task_acks_late=True,
)

class ClaudeTask(Task):
    """Base task with event publishing"""
    
    def publish_event(self, event_type: str, data: dict):
        """Publish event to Redis pub/sub"""
        import redis
        r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
        
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        r.publish('ksi:events', json.dumps(event))

@celery_app.task(bind=True, base=ClaudeTask)
def spawn_claude_task(
    self,
    prompt: str,
    session_id: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None
):
    """Spawn Claude subprocess - runs in Celery worker"""
    
    # Publish start event
    self.publish_event("SPAWN_START", {
        "task_id": self.request.id,
        "session_id": session_id
    })
    
    # Build command
    cmd = ["claude", "--model", "sonnet", "--print", "--output-format", "json"]
    
    if session_id:
        cmd.extend(["--resume", session_id])
    
    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])
    
    try:
        # Run subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send prompt
        stdout, stderr = process.communicate(input=prompt)
        
        # Parse output
        result = json.loads(stdout)
        
        # Log to file
        log_path = f"claude_logs/{session_id or 'no-session'}.jsonl"
        with open(log_path, 'a') as f:
            f.write(json.dumps(result) + '\n')
        
        # Publish completion event
        self.publish_event("SPAWN_COMPLETE", {
            "task_id": self.request.id,
            "session_id": session_id,
            "output": result
        })
        
        return {
            "status": "success",
            "session_id": session_id,
            "output": result
        }
        
    except Exception as e:
        # Publish error event
        self.publish_event("SPAWN_ERROR", {
            "task_id": self.request.id,
            "error": str(e)
        })
        
        raise

@celery_app.task(bind=True, base=ClaudeTask)
def register_agent_task(self, agent_data: dict):
    """Register agent in the system"""
    # Implementation here
    pass
```

### 3. FastStream Event Integration

```python
# app/events.py
from faststream import FastStream
from faststream.redis import RedisBroker
import json
from typing import Dict, Callable, List
import asyncio

class EventManager:
    """Manages event subscriptions and distribution"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.broker = RedisBroker(redis_url)
        self.app = FastStream(self.broker)
        self.handlers: Dict[str, List[Callable]] = {}
        
        # Set up event handler
        @self.broker.subscriber("ksi:events")
        async def handle_redis_event(data: bytes):
            event = json.loads(data)
            await self._distribute_event(event)
    
    async def start(self):
        """Start the event manager"""
        await self.app.start()
    
    async def stop(self):
        """Stop the event manager"""
        await self.app.stop()
    
    async def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to events"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def _distribute_event(self, event: dict):
        """Distribute event to handlers"""
        event_type = event.get("type")
        
        # Handle wildcard subscribers
        for handler in self.handlers.get("*", []):
            await handler(event)
        
        # Handle specific subscribers
        for handler in self.handlers.get(event_type, []):
            await handler(event)

# Global event manager instance
event_manager = EventManager()
```

### 4. Client Migration

```python
# clients/async_client.py
import aiohttp
import asyncio
import json
from typing import Optional, List, AsyncIterator

class KSIClient:
    """Async client for KSI API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
    
    async def spawn_claude(
        self, 
        prompt: str, 
        session_id: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None
    ) -> dict:
        """Spawn a Claude process"""
        async with self.session.post(
            f"{self.base_url}/spawn",
            json={
                "prompt": prompt,
                "session_id": session_id,
                "allowed_tools": allowed_tools
            }
        ) as resp:
            return await resp.json()
    
    async def connect_events(self) -> AsyncIterator[dict]:
        """Connect to event stream"""
        self.ws = await self.session.ws_connect(f"{self.base_url}/events")
        
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                yield json.loads(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

# Example usage
async def main():
    async with KSIClient() as client:
        # Spawn Claude
        result = await client.spawn_claude(
            "Hello! Tell me about yourself.",
            session_id="test-session"
        )
        print(f"Spawned task: {result}")
        
        # Listen for events
        async for event in client.connect_events():
            print(f"Event: {event}")
            if event.get("type") == "SPAWN_COMPLETE":
                break

if __name__ == "__main__":
    asyncio.run(main())
```

### 5. Migration Strategy

#### Phase 1: Parallel Operation (Week 1-2)
1. Deploy FastAPI + Celery alongside existing daemon
2. Implement core endpoints (spawn, register, events)
3. Create compatibility layer that forwards to Unix socket
4. Test with existing clients through adapter

#### Phase 2: Client Migration (Week 3-4)
1. Update clients to use HTTP/WebSocket
2. Maintain backward compatibility
3. Add retry logic and connection pooling
4. Monitor performance and reliability

#### Phase 3: Feature Parity (Week 5-6)
1. Implement all daemon commands in FastAPI
2. Migrate agent management to Celery
3. Add monitoring and health checks
4. Load test the new system

#### Phase 4: Cutover (Week 7)
1. Switch all clients to new API
2. Run both systems in parallel briefly
3. Decommission Unix socket daemon
4. Archive old code

## Testing Strategy

### Unit Tests
```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_spawn_endpoint():
    response = client.post("/spawn", json={
        "prompt": "Test prompt",
        "session_id": "test-123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "task_id" in data

def test_websocket_events():
    with client.websocket_connect("/events") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"
```

### Integration Tests
```python
# tests/test_integration.py
import asyncio
import pytest
from app.tasks import spawn_claude_task

@pytest.mark.asyncio
async def test_spawn_claude_integration():
    # Test actual Claude spawning
    result = spawn_claude_task.apply_async(
        args=["Hello!", "test-session", None]
    )
    
    # Wait for result
    output = result.get(timeout=30)
    assert output["status"] == "success"
    assert "output" in output
```

## Monitoring and Observability

### Prometheus Metrics
```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
spawn_requests = Counter('ksi_spawn_requests_total', 'Total spawn requests')
spawn_duration = Histogram('ksi_spawn_duration_seconds', 'Spawn duration')
active_connections = Gauge('ksi_active_connections', 'Active WebSocket connections')
```

### Structured Logging
```python
# app/logging.py
import structlog

logger = structlog.get_logger()

# Log with context
logger.info("spawn_requested", 
    session_id=session_id,
    prompt_length=len(prompt),
    allowed_tools=allowed_tools
)
```

## Performance Considerations

### Celery Optimization
```python
# Celery configuration for performance
celery_app.conf.update(
    worker_prefetch_multiplier=1,  # Prevent hogging
    task_compression='gzip',       # Compress large payloads
    result_compression='gzip',
    worker_max_tasks_per_child=100,  # Prevent memory leaks
)
```

### Redis Connection Pooling
```python
# Use connection pooling
import redis

redis_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50
)

r = redis.Redis(connection_pool=redis_pool)
```

### FastAPI Performance
```python
# Use uvloop for better async performance
import uvloop
import asyncio

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Run with Gunicorn + Uvicorn workers
# gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Security Considerations

1. **API Authentication**
   ```python
   from fastapi import Security, HTTPException
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   @app.post("/spawn")
   async def spawn_claude(
       request: SpawnRequest,
       credentials: HTTPAuthorizationCredentials = Security(security)
   ):
       # Validate token
       if not validate_token(credentials.credentials):
           raise HTTPException(status_code=401)
   ```

2. **Rate Limiting**
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   
   @app.post("/spawn")
   @limiter.limit("10/minute")
   async def spawn_claude(request: SpawnRequest):
       # Rate limited endpoint
   ```

3. **Input Validation**
   ```python
   from pydantic import BaseModel, validator
   
   class SpawnRequest(BaseModel):
       prompt: str
       session_id: Optional[str] = None
       allowed_tools: Optional[List[str]] = None
       
       @validator('prompt')
       def validate_prompt(cls, v):
           if len(v) > 10000:
               raise ValueError('Prompt too long')
           return v
   ```

## Conclusion

This migration plan transforms KSI from a custom Unix socket daemon to a production-ready architecture using battle-tested components. Each tool is used for its intended purpose:

- **FastAPI**: Pure API layer, no process management
- **Celery**: Robust subprocess and task management
- **Redis**: Proven pub/sub and queue backend
- **FastStream**: Clean event-driven integration

The architecture maintains KSI's event-driven philosophy while gaining:
- Horizontal scalability
- Built-in retry/failure handling
- Production monitoring capabilities
- Industry-standard deployment patterns

This is not reinventing the wheel - it's using the best wheels available, exactly as they were designed to be used.