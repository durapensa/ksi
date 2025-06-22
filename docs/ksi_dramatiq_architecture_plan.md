# KSI Dramatiq Architecture Plan: Clean Parallel Implementation

## Executive Summary

This document outlines a clean-break approach to modernizing KSI using FastAPI, FastStream, and Dramatiq. Rather than attempting backward compatibility or migration layers, we implement a completely separate system that runs alongside the existing daemon. This parallel approach allows us to:

- Prove the new architecture without disrupting existing functionality
- Avoid the complexity and compromises of compatibility layers
- Build with modern best practices from the ground up
- Migrate gradually once the new system is proven

The new system uses HTTP/WebSocket for all communication, Dramatiq for task management, and FastStream for event streaming - completely independent of Unix sockets and the legacy daemon.

## Architecture Overview

### Parallel Systems Design

```
Existing System                    New System (Phase 1)
┌─────────────────┐               ┌─────────────────┐
│   daemon.py     │               │  FastAPI App    │
│  (Unix Socket)  │               │  (HTTP:8000)    │
└────────┬────────┘               └────────┬────────┘
         │                                  │
┌────────┴────────┐               ┌────────┴────────┐
│    chat.py      │               │  chat_fast.py   │
│ (Socket Client) │               │  (HTTP Client)  │
└─────────────────┘               └─────────────────┘

Both systems run independently with no shared components
```

### New System Components

```
┌─────────────────────────────────────────────────┐
│                 FastAPI Server                   │
│  ┌───────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ REST API  │  │WebSocket │  │  FastStream │ │
│  │ Endpoints │  │ Handler  │  │   Events    │ │
│  └─────┬─────┘  └────┬─────┘  └──────┬──────┘ │
└────────┼─────────────┼───────────────┼─────────┘
         │             │               │
         └─────────────┴───────────────┘
                       │
         ┌─────────────┴─────────────┐
         │      Dramatiq Tasks       │
         │  ┌─────────────────────┐  │
         │  │  Claude Execution   │  │
         │  │  Background Jobs    │  │
         │  │  Event Processing   │  │
         │  └─────────────────────┘  │
         └───────────────────────────┘
```

## Detailed Implementation

### 1. FastAPI Application Structure

```python
# app/main.py
from fastapi import FastAPI, WebSocket
from faststream.nats import NatsBroker
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from contextlib import asynccontextmanager
import uvicorn

# Configure Dramatiq with Redis broker
redis_broker = RedisBroker(url="redis://localhost:6379")
dramatiq.set_broker(redis_broker)

# Configure FastStream for events
broker = NatsBroker("nats://localhost:4222")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    await broker.start()
    yield
    # Shutdown
    await broker.close()

app = FastAPI(
    title="KSI Modern API",
    lifespan=lifespan
)

# REST endpoints
@app.post("/chat")
async def create_chat(message: str, session_id: str = None):
    """Queue a chat message for processing"""
    from app.tasks import process_claude_message
    
    # Queue task with Dramatiq
    result = process_claude_message.send(
        message=message,
        session_id=session_id
    )
    
    return {
        "task_id": result.message_id,
        "status": "queued"
    }

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Check task status"""
    # Implementation depends on result backend
    pass

# WebSocket for real-time updates
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Subscribe to session events
    @broker.subscriber(f"chat.{session_id}")
    async def handle_message(data: dict):
        await websocket.send_json(data)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except:
        await websocket.close()
```

### 2. Dramatiq Task Definitions

```python
# app/tasks.py
import dramatiq
import subprocess
import json
from app.events import publish_event

@dramatiq.actor(max_retries=3)
def process_claude_message(message: str, session_id: str = None):
    """Process a message with Claude CLI"""
    
    # Build Claude command
    cmd = [
        "claude",
        "--model", "sonnet",
        "--print",
        "--output-format", "json"
    ]
    
    if session_id:
        cmd.extend(["--resume", session_id])
    
    # Execute Claude
    try:
        result = subprocess.run(
            cmd,
            input=message,
            text=True,
            capture_output=True,
            check=True
        )
        
        # Parse response
        response = json.loads(result.stdout)
        
        # Publish completion event
        publish_event.send(
            topic=f"chat.{session_id}",
            data={
                "type": "completion",
                "response": response,
                "session_id": session_id
            }
        )
        
        return response
        
    except subprocess.CalledProcessError as e:
        # Publish error event
        publish_event.send(
            topic=f"chat.{session_id}",
            data={
                "type": "error",
                "error": str(e),
                "session_id": session_id
            }
        )
        raise

@dramatiq.actor
def publish_event(topic: str, data: dict):
    """Publish event to FastStream"""
    from app.main import broker
    import asyncio
    
    # Bridge sync Dramatiq to async FastStream
    loop = asyncio.new_event_loop()
    loop.run_until_complete(
        broker.publish(data, topic)
    )
    loop.close()

@dramatiq.actor(queue_name="background")
def analyze_conversation(session_id: str):
    """Background analysis task"""
    # Load conversation history
    # Perform analysis
    # Store results
    pass

@dramatiq.actor(queue_name="scheduled", time_limit=600000)
def generate_daily_summary():
    """Scheduled task for daily summaries"""
    # Aggregate data
    # Generate summary
    # Send notifications
    pass
```

### 3. Modern Chat Client

```python
# chat_fast.py
import httpx
import asyncio
import websockets
import json
from typing import Optional

class FastChatClient:
    """Modern HTTP/WebSocket chat client"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None
        self.ws = None
    
    async def connect(self, session_id: Optional[str] = None):
        """Connect to chat session"""
        self.session_id = session_id or self._generate_session_id()
        
        # Connect WebSocket for real-time updates
        ws_url = f"ws://localhost:8000/ws/{self.session_id}"
        self.ws = await websockets.connect(ws_url)
        
        # Start listening for events
        asyncio.create_task(self._listen_events())
    
    async def send_message(self, message: str):
        """Send a chat message"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json={
                    "message": message,
                    "session_id": self.session_id
                }
            )
            return response.json()
    
    async def _listen_events(self):
        """Listen for WebSocket events"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self._handle_event(data)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
    
    async def _handle_event(self, event: dict):
        """Handle incoming events"""
        if event["type"] == "completion":
            print(f"\nClaude: {event['response']['content']}")
        elif event["type"] == "error":
            print(f"\nError: {event['error']}")
    
    def _generate_session_id(self) -> str:
        """Generate a new session ID"""
        import uuid
        return str(uuid.uuid4())

# CLI interface
async def main():
    client = FastChatClient()
    await client.connect()
    
    print("Connected to KSI Fast API. Type 'exit' to quit.")
    
    while True:
        try:
            message = input("\nYou: ")
            if message.lower() == 'exit':
                break
            
            await client.send_message(message)
            # Response will be printed by event handler
            
        except KeyboardInterrupt:
            break
    
    if client.ws:
        await client.ws.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Running Both Systems

```bash
# Terminal 1: Existing system
python daemon.py

# Terminal 2: New system
docker-compose up -d  # Redis and NATS
uvicorn app.main:app --reload

# Terminal 3: Dramatiq workers
dramatiq app.tasks

# Terminal 4: Use existing chat
python chat.py

# Terminal 5: Use new chat
python chat_fast.py
```

### 5. Docker Compose for Dependencies

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  nats:
    image: nats:2-alpine
    ports:
      - "4222:4222"
      - "8222:8222"  # Monitoring
    command: ["-m", "8222"]

  dramatiq-worker:
    build: .
    command: dramatiq app.tasks --processes 4 --threads 2
    depends_on:
      - redis
      - nats
    volumes:
      - ./:/app
    environment:
      - REDIS_URL=redis://redis:6379

  dramatiq-scheduler:
    build: .
    command: dramatiq app.tasks --queue scheduled --processes 1
    depends_on:
      - redis
    volumes:
      - ./:/app

volumes:
  redis_data:
```

## Phase 1: Proof of Concept

### Goals
1. **Implement core chat functionality** with the new stack
2. **Demonstrate performance improvements** over Unix socket approach
3. **Validate architecture decisions** before any migration
4. **Build confidence** in the new system

### Success Criteria
- [ ] Basic chat works with conversation continuity
- [ ] WebSocket real-time updates functional
- [ ] Background tasks process successfully
- [ ] System handles concurrent sessions
- [ ] Performance metrics show improvement

### Implementation Steps

1. **Week 1: Core Infrastructure**
   - Set up FastAPI application
   - Configure Dramatiq with Redis
   - Implement basic REST endpoints
   - Create minimal chat_fast client

2. **Week 2: Task Processing**
   - Implement Claude execution tasks
   - Add result storage and retrieval
   - Set up event publishing
   - Test task retry logic

3. **Week 3: Real-time Features**
   - Implement WebSocket handlers
   - Connect FastStream events
   - Build event routing
   - Test real-time updates

4. **Week 4: Testing and Metrics**
   - Load testing both systems
   - Performance comparison
   - Stability testing
   - Documentation

## Benefits of Clean-Break Approach

### 1. No Technical Debt
- Start with modern best practices
- No legacy compatibility constraints
- Clean, maintainable codebase
- Proper separation of concerns

### 2. Risk Mitigation
- Existing system continues working
- No disruption to current users
- Can test thoroughly before migration
- Easy rollback if needed

### 3. Faster Development
- No time spent on compatibility layers
- Use framework features directly
- Modern tooling and patterns
- Clear architecture boundaries

### 4. Better Performance
- HTTP/WebSocket more efficient than Unix sockets
- Dramatiq's Redis broker scales horizontally
- FastStream enables true event-driven architecture
- Built-in caching and optimization

### 5. Easier Debugging
- Standard HTTP tools work (curl, Postman)
- Redis CLI for queue inspection
- Dramatiq's built-in monitoring
- Clear separation of concerns

## Migration Strategy (Future)

Once Phase 1 proves successful:

1. **Feature Parity** - Implement remaining features in new system
2. **Data Migration** - Tool to migrate conversation history
3. **Client Migration** - Update documentation and tools
4. **Deprecation** - Phase out old system gradually
5. **Cleanup** - Remove legacy code

The key insight: By building a completely separate system, we can take our time to get it right without the pressure of maintaining compatibility. Users can try the new system when ready, and we can migrate at a pace that ensures quality.

## Conclusion

This clean parallel implementation with Dramatiq provides a clear path to modernizing KSI without the complexity and compromises of compatibility layers. By building alongside the existing system, we can:

- Prove the architecture works
- Deliver value incrementally  
- Migrate when confident
- Maintain system stability

The use of Dramatiq for task management, combined with FastAPI and FastStream, creates a robust, scalable foundation for KSI's future growth.