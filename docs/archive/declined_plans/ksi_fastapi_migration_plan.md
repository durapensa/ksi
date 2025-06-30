# KSI FastAPI + FastStream Migration Plan

## Executive Summary

This document outlines the comprehensive migration strategy for transitioning the KSI daemon from Unix sockets to a modern FastAPI + FastStream architecture with redislite as the embedded message broker. This migration will dramatically simplify the codebase while maintaining the event-driven architecture and adding powerful new capabilities.

**Key Benefits:**
- **Zero External Dependencies**: redislite provides a fully embedded Redis instance
- **Simplified Schema Validation**: FastAPI's Pydantic models replace custom validation
- **Native Pub/Sub**: FastStream provides production-ready message patterns
- **WebSocket Support**: Real-time bidirectional communication
- **Auto-Generated API Docs**: Swagger/OpenAPI documentation out of the box
- **Better Tooling**: Standard HTTP debugging tools and browser DevTools

## Architecture Comparison

### Current Architecture (Unix Sockets)
```
┌─────────────┐     Unix Socket      ┌─────────────┐
│   chat.py   │ ────────────────────>│  daemon.py  │
└─────────────┘                      └──────┬──────┘
                                            │
                                     Custom Message Bus
                                            │
                        ┌───────────────────┼───────────────────┐
                        │                   │                   │
                  ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐
                  │  Agent 1  │      │  Agent 2  │      │  Agent N  │
                  └───────────┘      └───────────┘      └───────────┘
```

**Pain Points:**
- Complex custom protocol parsing
- Manual JSON validation everywhere
- Custom message bus implementation
- Limited to local machine access
- Difficult debugging and monitoring
- No standard tooling support

### Proposed Architecture (FastAPI + FastStream)
```
┌─────────────┐     HTTP/WebSocket   ┌─────────────────┐
│   Client    │ ───────────────────>│   FastAPI App   │
└─────────────┘                      └────────┬────────┘
                                              │
                                      FastStream + redislite
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        │                     │                     │
                  ┌─────▼─────┐        ┌─────▼─────┐        ┌─────▼─────┐
                  │  Agent 1  │        │  Agent 2  │        │  Agent N  │
                  └───────────┘        └───────────┘        └───────────┘
```

**Advantages:**
- Automatic request/response validation
- Built-in async pub/sub patterns
- WebSocket for real-time updates
- Remote access capability
- Standard HTTP debugging tools
- Auto-generated API documentation

## Why redislite is Perfect for KSI

### 1. **Zero Configuration**
```python
import redislite

# That's it! No Redis server needed
redis_connection = redislite.Redis()
```

### 2. **Embedded Operation**
- Runs in-process with your application
- No separate Redis server to manage
- Data persists to a single file
- Perfect for KSI's self-contained design

### 3. **Full Redis API Compatibility**
```python
# All Redis pub/sub features work
await redis_connection.publish('agent:hello', json.dumps({"message": "Hello"}))
```

### 4. **FastStream Integration**
```python
from faststream import FastStream
from faststream.redis import RedisBroker
import redislite

# Create embedded Redis instance
redis = redislite.Redis('/tmp/ksi_redis.db')

# Use with FastStream
broker = RedisBroker(connection=redis)
app = FastStream(broker)
```

## Detailed Implementation Phases

### Phase 1: Foundation Setup (Week 1)

#### 1.1 Create FastAPI Application Structure
```python
# ksi_api/main.py
from fastapi import FastAPI, WebSocket
from faststream import FastStream
from faststream.redis import RedisBroker
import redislite
from contextlib import asynccontextmanager

# Embedded Redis instance
redis_db = redislite.Redis('data/ksi_messages.db')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await broker.start()
    yield
    # Shutdown
    await broker.close()

# FastStream setup
broker = RedisBroker(connection=redis_db)
faststream_app = FastStream(broker)

# FastAPI setup
app = FastAPI(
    title="KSI Daemon API",
    version="2.0.0",
    lifespan=lifespan
)
```

#### 1.2 Define Pydantic Models (Replacing command_schemas.py)
```python
# ksi_api/models.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

class CommandType(str, Enum):
    SPAWN = "SPAWN"
    SPAWN_ASYNC = "SPAWN:async:claude"
    REGISTER_AGENT = "REGISTER_AGENT"
    SEND_MESSAGE = "SEND_MESSAGE"
    SUBSCRIBE = "SUBSCRIBE"
    STATUS = "STATUS"
    SHUTDOWN = "SHUTDOWN"

class BaseCommand(BaseModel):
    session_id: str = Field(..., regex="^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SpawnCommand(BaseCommand):
    command: CommandType = CommandType.SPAWN
    prompt: str
    model: str = "sonnet"
    tools: Optional[List[str]] = None
    agent_profile: Optional[str] = None

class AgentRegistration(BaseCommand):
    command: CommandType = CommandType.REGISTER_AGENT
    agent_id: str
    profile: str
    capabilities: List[str]

class MessageEvent(BaseModel):
    event_type: str
    source: str
    target: Optional[str] = None
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Phase 2: API Endpoints Implementation (Week 1-2)

#### 2.1 Core Command Endpoints
```python
# ksi_api/routes/commands.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from ksi_api.models import SpawnCommand, AgentRegistration
from ksi_api.services import agent_manager, process_manager

router = APIRouter(prefix="/api/v1", tags=["commands"])

@router.post("/spawn")
async def spawn_claude(
    command: SpawnCommand,
    background_tasks: BackgroundTasks
):
    """Spawn a new Claude process with the given prompt."""
    try:
        # Publish to FastStream for async processing
        await broker.publish(
            command.dict(),
            channel="commands:spawn"
        )
        
        return {
            "status": "accepted",
            "session_id": command.session_id,
            "message": "Spawn command queued for processing"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/register")
async def register_agent(registration: AgentRegistration):
    """Register a new agent with the system."""
    result = await agent_manager.register(
        agent_id=registration.agent_id,
        profile=registration.profile,
        capabilities=registration.capabilities
    )
    return {"status": "registered", "agent": result}

@router.get("/agents")
async def list_agents():
    """List all registered agents."""
    agents = await agent_manager.list_agents()
    return {"agents": agents}

@router.get("/status")
async def system_status():
    """Get current system status."""
    return {
        "status": "healthy",
        "agents": await agent_manager.count(),
        "active_processes": await process_manager.count_active(),
        "redis_info": redis_db.info()
    }
```

#### 2.2 WebSocket Support
```python
# ksi_api/routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Handle disconnected clients
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Subscribe to all events
        async with broker.subscriber("events:*") as subscriber:
            async for message in subscriber:
                await websocket.send_json(message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Phase 3: FastStream Event Handlers (Week 2)

#### 3.1 Message Processing
```python
# ksi_api/handlers/spawn_handler.py
from faststream import FastStream
from faststream.redis import RedisBroker
import subprocess
import asyncio

@faststream_app.subscriber("commands:spawn")
async def handle_spawn(command: dict):
    """Process spawn commands asynchronously."""
    session_id = command['session_id']
    prompt = command['prompt']
    
    # Build Claude command
    cmd = [
        "claude",
        "--model", command.get('model', 'sonnet'),
        "--print",
        "--output-format", "json",
        "--resume", session_id
    ]
    
    if command.get('tools'):
        cmd.extend(["--allowedTools", ",".join(command['tools'])])
    
    # Spawn process
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Send prompt
    stdout, stderr = await process.communicate(prompt.encode())
    
    # Publish result
    await broker.publish({
        "session_id": session_id,
        "status": "completed" if process.returncode == 0 else "failed",
        "output": stdout.decode() if stdout else None,
        "error": stderr.decode() if stderr else None,
        "timestamp": datetime.utcnow().isoformat()
    }, channel=f"results:{session_id}")
    
    # Broadcast to WebSocket clients
    await broker.publish({
        "event": "spawn_complete",
        "session_id": session_id,
        "status": "completed" if process.returncode == 0 else "failed"
    }, channel="events:broadcast")
```

#### 3.2 Inter-Agent Communication
```python
# ksi_api/handlers/agent_communication.py
@faststream_app.subscriber("agents:messages")
async def handle_agent_message(message: dict):
    """Route messages between agents."""
    target = message.get('target')
    
    if target:
        # Direct message
        await broker.publish(
            message['payload'],
            channel=f"agents:{target}:inbox"
        )
    else:
        # Broadcast to all agents
        await broker.publish(
            message['payload'],
            channel="agents:broadcast"
        )
    
    # Log to message bus
    await broker.publish({
        "type": "agent_communication",
        "from": message['source'],
        "to": target or "broadcast",
        "timestamp": datetime.utcnow().isoformat()
    }, channel="events:message_bus")
```

### Phase 4: Migration Strategy (Week 3)

#### 4.1 Dual-Mode Operation
```python
# ksi_api/compatibility/unix_socket_bridge.py
import asyncio
import json
from pathlib import Path

class UnixSocketBridge:
    """Maintains backward compatibility with Unix socket clients."""
    
    def __init__(self, socket_path: str, api_client):
        self.socket_path = Path(socket_path)
        self.api_client = api_client
        
    async def start(self):
        """Bridge Unix socket commands to FastAPI."""
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        async with server:
            await server.serve_forever()
            
    async def handle_client(self, reader, writer):
        """Translate Unix socket protocol to HTTP API calls."""
        try:
            data = await reader.read(65536)
            command = json.loads(data.decode())
            
            # Map old command format to new API
            if command.get('action') == 'SPAWN':
                response = await self.api_client.post(
                    "/api/v1/spawn",
                    json={
                        "session_id": command['sessionId'],
                        "prompt": command['prompt'],
                        "model": command.get('model', 'sonnet'),
                        "tools": command.get('tools')
                    }
                )
            
            writer.write(json.dumps(response).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
```

#### 4.2 Gradual Migration Path

1. **Week 1**: Deploy FastAPI alongside existing daemon
   - Run on different port (8000)
   - Bridge for backward compatibility
   - Test with new clients

2. **Week 2**: Migrate clients
   - Update chat.py to use HTTP/WebSocket
   - Update monitoring tools
   - Maintain Unix socket bridge

3. **Week 3**: Deprecate Unix sockets
   - Remove Unix socket code
   - Full FastAPI/WebSocket operation
   - Archive old daemon code

### Phase 5: Testing Approach (Ongoing)

#### 5.1 Unit Tests
```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from ksi_api.main import app

client = TestClient(app)

def test_spawn_command():
    response = client.post(
        "/api/v1/spawn",
        json={
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "prompt": "Hello, Claude!",
            "model": "sonnet"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

def test_invalid_session_id():
    response = client.post(
        "/api/v1/spawn",
        json={
            "session_id": "invalid-id",
            "prompt": "Hello!"
        }
    )
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_websocket_events():
    with client.websocket_connect("/ws") as websocket:
        # Trigger an event
        await broker.publish(
            {"test": "event"},
            channel="events:broadcast"
        )
        
        data = websocket.receive_json()
        assert data["test"] == "event"
```

#### 5.2 Integration Tests
```python
# tests/test_integration.py
import asyncio
import httpx

async def test_full_spawn_flow():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Send spawn command
        response = await client.post(
            "/api/v1/spawn",
            json={
                "session_id": "test-session-id",
                "prompt": "What is 2+2?",
                "model": "sonnet"
            }
        )
        
        assert response.status_code == 200
        
        # Wait for result via WebSocket
        # ... WebSocket subscription code ...
```

## Performance Considerations

### 1. **redislite Performance**
- In-memory operation with periodic persistence
- No network overhead (embedded)
- Suitable for KSI's message volume
- Benchmark: ~50k messages/second

### 2. **FastAPI Optimizations**
```python
# Use uvloop for better async performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Run with Gunicorn + Uvicorn workers
# gunicorn ksi_api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 3. **Connection Pooling**
```python
# Reuse Redis connections
redis_pool = redislite.Redis(
    'data/ksi_messages.db',
    decode_responses=True
)
```

## Risk Mitigation

### 1. **Data Migration**
- Export existing state before migration
- Test import into redislite
- Keep backups of Unix socket logs

### 2. **Rollback Plan**
- Keep old daemon.py code archived
- Dual-mode operation allows instant rollback
- Document all configuration changes

### 3. **Monitoring**
```python
# Built-in health checks
@app.get("/health")
async def health_check():
    try:
        # Check Redis
        redis_db.ping()
        
        # Check message broker
        await broker.ping()
        
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### 4. **Error Handling**
```python
# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

## Benefits Summary

### Immediate Benefits
1. **Schema Validation**: Automatic with Pydantic models
2. **API Documentation**: Auto-generated Swagger UI
3. **Better Debugging**: Standard HTTP tools work
4. **WebSocket Support**: Real-time updates built-in
5. **No External Dependencies**: redislite is embedded

### Long-term Benefits
1. **Scalability**: Can distribute across machines
2. **Standard Patterns**: Industry-standard message queue
3. **Ecosystem**: Vast FastAPI/Redis ecosystem
4. **Monitoring**: APM tools support FastAPI
5. **Testing**: Better testing frameworks available

## Migration Checklist

- [ ] Set up FastAPI project structure
- [ ] Implement Pydantic models for all commands
- [ ] Create core API endpoints
- [ ] Set up FastStream handlers
- [ ] Implement WebSocket support
- [ ] Add Unix socket bridge for compatibility
- [ ] Write comprehensive tests
- [ ] Update client applications
- [ ] Deploy in dual-mode
- [ ] Monitor performance
- [ ] Deprecate Unix socket code
- [ ] Archive old implementation

## Code Examples: Before and After

### Before (Unix Socket)
```python
# Complex manual parsing
def handle_command(self, data: bytes) -> str:
    try:
        command = json.loads(data.decode('utf-8'))
        
        # Manual validation
        if 'action' not in command:
            return json.dumps({"error": "Missing action"})
            
        if command['action'] == 'SPAWN':
            if 'sessionId' not in command:
                return json.dumps({"error": "Missing sessionId"})
            if 'prompt' not in command:
                return json.dumps({"error": "Missing prompt"})
                
            # More manual validation...
            
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON"})
```

### After (FastAPI)
```python
# Automatic validation and parsing
@app.post("/api/v1/spawn")
async def spawn_claude(command: SpawnCommand):
    # Command is already validated!
    await broker.publish(command.dict(), channel="commands:spawn")
    return {"status": "accepted", "session_id": command.session_id}
```

### Before (Message Bus)
```python
# Custom message bus implementation
class MessageBus:
    def __init__(self):
        self.subscribers = defaultdict(list)
        
    async def publish(self, channel: str, message: dict):
        for callback in self.subscribers[channel]:
            try:
                await callback(message)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
```

### After (FastStream)
```python
# Production-ready message patterns
@faststream_app.subscriber("commands:spawn")
async def handle_spawn(command: dict):
    # Automatic message routing and error handling
    result = await process_spawn(command)
    await broker.publish(result, channel=f"results:{command['session_id']}")
```

## Conclusion

The migration to FastAPI + FastStream with redislite represents a significant modernization of the KSI architecture. By leveraging these production-tested frameworks, we can eliminate thousands of lines of custom code while gaining powerful new capabilities. The embedded nature of redislite ensures we maintain KSI's self-contained philosophy while gaining all the benefits of Redis pub/sub patterns.

This migration will make KSI more maintainable, debuggable, and extensible while preserving its core event-driven architecture and adding exciting new capabilities like WebSocket support and remote access.