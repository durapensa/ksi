# OpenAI API Shim Implementation Plan

## Executive Summary

This document outlines the plan to create an OpenAI-compatible API shim that wraps the existing `claude --print` functionality. The shim will be integrated incrementally with the current daemon architecture, allowing gradual migration while maintaining full backward compatibility.

## Architecture Overview

### Current State
- **Daemon**: Unix socket-based process manager
- **Claude Process**: Spawned via subprocess with `claude --print`
- **Clients**: Connect via Unix socket using custom JSON protocol

### Target State
- **API Shim**: FastAPI server providing OpenAI-compatible endpoints
- **Task Queue**: Dramatiq for async task execution
- **Daemon Integration**: Daemon optionally uses API instead of direct spawning
- **Gradual Migration**: Clients can use either daemon or API directly

## Phase 1: Minimal API Shim

### 1.1 Core Components

#### FastAPI Application (`api_shim.py`)
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import dramatiq
import litellm
import json
import subprocess
import time
import uuid

app = FastAPI(title="Claude OpenAI-Compatible API")

class ChatCompletionRequest(BaseModel):
    model: str = "sonnet"
    messages: list
    temperature: float = 0.7
    max_tokens: int = None
    stream: bool = False
    metadata: dict = {}  # Custom metadata for session_id, enable_tools, etc.
```

#### Dramatiq Task Worker
```python
@dramatiq.actor(queue_name="claude_tasks", time_limit=300000)  # 5 min timeout
def claude_executor(messages, model="sonnet", session_id=None, enable_tools=True):
    """Execute claude --print with given parameters"""
    # Format messages to single prompt
    prompt = format_messages_to_prompt(messages)
    
    # Build command
    cmd = ["claude", "--model", model, "--print", "--output-format", "json"]
    
    if enable_tools:
        cmd.extend(["--allowedTools", "Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch"])
    
    if session_id:
        cmd.extend(["--resume", session_id])
    
    # Execute
    process = subprocess.run(cmd, input=prompt.encode(), capture_output=True)
    
    if process.returncode != 0:
        raise Exception(f"Claude failed: {process.stderr.decode()}")
    
    # Parse output
    result = json.loads(process.stdout.decode())
    return result
```

#### Chat Completions Endpoint
```python
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""
    
    # Extract custom metadata
    session_id = request.metadata.get("session_id")
    enable_tools = request.metadata.get("enable_tools", True)
    agent_id = request.metadata.get("agent_id")
    
    # Queue task
    task = claude_executor.send(
        messages=request.messages,
        model=request.model,
        session_id=session_id,
        enable_tools=enable_tools
    )
    
    # For sync mode, wait for result
    if not request.stream:
        try:
            result = task.get_result(block=True, timeout=120)
            
            # Convert to OpenAI format
            return {
                "id": result.get("sessionId", f"chat-{uuid.uuid4()}"),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result.get("result", "")
                    },
                    "finish_reason": "stop"
                }],
                "usage": estimate_usage(request.messages, result.get("result", ""))
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Streaming not implemented in Phase 1
    raise HTTPException(status_code=501, detail="Streaming not yet implemented")
```

### 1.2 Setup Requirements

#### Dependencies (`requirements_api.txt`)
```
fastapi==0.104.1
uvicorn==0.24.0
dramatiq[redis]==1.15.0
redis==5.0.1
litellm==1.0.0
pydantic==2.5.0
```

#### Docker Compose (`docker-compose.yml`)
```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    volumes:
      - ./claude_logs:/app/claude_logs
      - ./sockets:/app/sockets

  worker:
    build: .
    command: dramatiq api_shim:claude_executor
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    volumes:
      - ./claude_logs:/app/claude_logs
      - ./sockets:/app/sockets

volumes:
  redis_data:
```

## Phase 2: Daemon Integration

### 2.1 Modify ClaudeProcessManager

Update `daemon/claude_process.py` to support API-based execution:

```python
class ClaudeProcessManager:
    def __init__(self, state_manager=None, utils_manager=None):
        # Existing initialization
        self.running_processes = {}
        self.state_manager = state_manager
        self.utils_manager = utils_manager
        self.message_bus = None
        
        # New API configuration
        self.use_api_shim = os.getenv("USE_CLAUDE_API_SHIM", "false").lower() == "true"
        self.api_base = os.getenv("CLAUDE_API_BASE", "http://localhost:8000/v1")
        
        # Initialize litellm if using API
        if self.use_api_shim:
            import litellm
            litellm.api_base = self.api_base
            self.litellm = litellm
    
    async def spawn_claude(self, prompt: str, session_id: str = None, 
                          model: str = 'sonnet', agent_id: str = None, 
                          enable_tools: bool = True) -> dict:
        """Spawn claude process - via API or direct"""
        
        if self.use_api_shim:
            return await self._spawn_claude_via_api(
                prompt, session_id, model, agent_id, enable_tools
            )
        else:
            # Existing direct spawn code
            return await self._spawn_claude_direct(
                prompt, session_id, model, agent_id, enable_tools
            )
    
    async def _spawn_claude_via_api(self, prompt, session_id, model, 
                                   agent_id, enable_tools):
        """Spawn Claude via OpenAI-compatible API"""
        
        try:
            # Use litellm for API call
            response = await self.litellm.acompletion(
                model=f"openai/{model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.api_base,
                metadata={
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "enable_tools": enable_tools
                }
            )
            
            # Convert OpenAI format to Claude format
            claude_response = {
                "sessionId": response.id,
                "result": response.choices[0].message.content,
                "model": model,
                "timestamp": TimestampManager.format_for_logging(),
                "agent_id": agent_id
            }
            
            # Use existing logging/tracking code
            new_session_id = claude_response.get("sessionId")
            if new_session_id:
                # Log to JSONL (existing code works as-is)
                log_file = f'claude_logs/{new_session_id}.jsonl'
                # ... existing logging code ...
            
            return claude_response
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return {"error": str(e), "returncode": -1}
    
    async def _spawn_claude_direct(self, prompt, session_id, model, 
                                  agent_id, enable_tools):
        """Original direct spawn implementation"""
        # Move existing spawn_claude code here unchanged
        # ... existing implementation ...
```

### 2.2 Configuration Management

Create `config/api_shim.yaml`:
```yaml
api_shim:
  enabled: false  # Default disabled
  base_url: http://localhost:8000/v1
  timeout: 120
  retry_attempts: 3
  
dramatiq:
  broker: redis://localhost:6379
  queue_name: claude_tasks
  
models:
  available:
    - sonnet
    - opus
    - haiku
  default: sonnet
```

## Phase 3: Client Migration

### 3.1 Update chat_textual.py

Add configuration option to use API directly:

```python
class ChatInterface(App):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.use_api = args.use_api or os.getenv("USE_CLAUDE_API", "false").lower() == "true"
        
        if self.use_api:
            # Initialize litellm client
            import litellm
            self.client = litellm
            self.api_base = os.getenv("CLAUDE_API_BASE", "http://localhost:8000/v1")
        else:
            # Use existing agent process
            self.agent_process = self._init_agent_process()
    
    async def send_message(self, message: str):
        if self.use_api:
            # Direct API call
            response = await self.client.acompletion(
                model="openai/sonnet",
                messages=self._build_message_history(message),
                api_base=self.api_base,
                metadata={"session_id": self.session_id}
            )
            self._display_response(response.choices[0].message.content)
        else:
            # Existing agent process code
            response = await self.agent_process.generate_claude_response(message, "chat")
            self._display_response(response)
```

### 3.2 Update orchestrate_v3.py

Modify agent spawning to optionally use API:

```python
class MultiClaudeOrchestratorV3:
    def __init__(self):
        self.daemon_socket = Path("sockets/claude_daemon.sock")
        self.use_api = os.getenv("ORCHESTRATOR_USE_API", "false").lower() == "true"
        self.api_base = os.getenv("CLAUDE_API_BASE", "http://localhost:8000/v1")
    
    async def spawn_agent_via_api(self, agent_id, profile, task, context):
        """Spawn agent using API instead of daemon"""
        import httpx
        
        # Create initial prompt
        prompt = f"{task}\nContext: {context}"
        
        # Call API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                json={
                    "model": profile.get("model", "sonnet"),
                    "messages": [{"role": "user", "content": prompt}],
                    "metadata": {
                        "agent_id": agent_id,
                        "profile": profile
                    }
                }
            )
            
        return response.json()
```

## Phase 4: Testing & Rollout

### 4.1 Testing Strategy

1. **Unit Tests** (`tests/test_api_shim.py`)
   - Test endpoint responses
   - Test Claude command construction
   - Test error handling

2. **Integration Tests** (`tests/test_daemon_api_integration.py`)
   - Test daemon with USE_CLAUDE_API_SHIM=true
   - Compare outputs between direct and API modes
   - Test session continuity

3. **Performance Tests**
   - Measure latency difference
   - Test concurrent request handling
   - Monitor resource usage

### 4.2 Rollout Plan

#### Stage 1: Development (Week 1-2)
- Implement API shim
- Set up Dramatiq workers
- Basic testing

#### Stage 2: Integration (Week 3)
- Update ClaudeProcessManager
- Add configuration management
- Integration testing

#### Stage 3: Client Updates (Week 4)
- Update chat_textual.py
- Update orchestrate_v3.py
- End-to-end testing

#### Stage 4: Gradual Rollout (Week 5-6)
- Deploy with USE_CLAUDE_API_SHIM=false
- Enable for specific use cases
- Monitor and compare metrics

#### Stage 5: Full Migration (Week 7-8)
- Enable API by default
- Update documentation
- Deprecation notices for direct spawning

## Phase 5: Future Enhancements

### 5.1 Streaming Support
- Implement Server-Sent Events (SSE)
- Stream partial Claude outputs
- Update clients for streaming

### 5.2 Additional Providers
- Add OpenAI provider support
- Add Anthropic API support
- Add local model support (Ollama)

### 5.3 Advanced Features
- Request queuing and prioritization
- Rate limiting and quotas
- Usage tracking and analytics
- Multi-tenant support

## Configuration Examples

### Environment Variables
```bash
# For daemon to use API
export USE_CLAUDE_API_SHIM=true
export CLAUDE_API_BASE=http://localhost:8000/v1

# For clients to use API directly
export USE_CLAUDE_API=true
export CLAUDE_API_BASE=http://localhost:8000/v1

# For Dramatiq
export DRAMATIQ_BROKER=redis://localhost:6379
```

### Running the System
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start Dramatiq workers (in one terminal)
dramatiq api_shim:claude_executor

# Start API server (in another terminal)
uvicorn api_shim:app --host 0.0.0.0 --port 8000

# Start daemon with API support
USE_CLAUDE_API_SHIM=true python daemon.py

# Or use clients directly with API
USE_CLAUDE_API=true python interfaces/chat_textual.py
```

## Benefits

1. **Incremental Migration**: No breaking changes, gradual adoption
2. **Standards Compliance**: OpenAI-compatible API
3. **Provider Flexibility**: Easy to add new LLM providers via litellm
4. **Scalability**: Separate API and worker scaling
5. **Monitoring**: Standard HTTP metrics and observability
6. **Testing**: Easier to test with standard HTTP tools

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Performance regression | Benchmark both modes, optimize as needed |
| API/worker downtime | Fallback to direct spawning |
| Session continuity issues | Careful session ID mapping |
| Feature parity gaps | Comprehensive testing checklist |

## Success Criteria

1. API shim handles all current daemon Claude spawning use cases
2. No performance regression > 10%
3. All existing clients work with both modes
4. Easy provider switching via configuration
5. Improved observability and debugging

## Conclusion

This incremental approach provides a clean path to modernize the LLM integration while maintaining stability. The OpenAI-compatible API opens up compatibility with a vast ecosystem of tools while preserving the unique features of the KSI daemon architecture.