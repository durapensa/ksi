# Celery vs Dramatiq Analysis for KSI

## Executive Summary

After analyzing both Celery and Dramatiq in the context of KSI's minimal daemon architecture and specific requirements for managing Claude CLI processes, **Dramatiq emerges as the better choice**. Its simplicity, minimal configuration requirements, and reliable task execution align perfectly with KSI's philosophy while providing all necessary features for subprocess management, retries, and event publishing.

## KSI's Specific Requirements

Before diving into the comparison, let's clarify KSI's unique needs:

1. **Long-running subprocess management**: Claude CLI processes that run for minutes
2. **Process lifecycle control**: Start, monitor, and cleanup of subprocesses
3. **Event-driven architecture**: Publishing completion events to the message bus
4. **Minimal infrastructure**: No complex dependencies or configuration
5. **Reliable execution**: Retry failed tasks with proper error handling
6. **Simple deployment**: Easy to understand and maintain

## Detailed Comparison

### 1. Complexity and Configuration

**Celery**:
- Requires a message broker (Redis, RabbitMQ, etc.)
- Complex configuration with many options
- Steep learning curve with extensive documentation
- Multiple components to manage (worker, beat scheduler, flower for monitoring)
- Configuration example:

```python
# celery_config.py
from celery import Celery

app = Celery('ksi_tasks')
app.config_from_object({
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 3600,  # 1 hour
    'task_soft_time_limit': 3000,  # 50 minutes
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1,  # Important for subprocess cleanup
})
```

**Dramatiq**:
- Works with Redis out of the box with minimal configuration
- Simple, intuitive API design
- Minimal configuration required
- Single worker process model is easier to understand
- Configuration example:

```python
# dramatiq_config.py
import dramatiq
from dramatiq.brokers.redis import RedisBroker

redis_broker = RedisBroker(host="localhost")
dramatiq.set_broker(redis_broker)
```

**Winner**: Dramatiq - Its minimal configuration philosophy aligns with KSI's approach

### 2. Subprocess Management Features

**Celery**:
```python
# celery_tasks.py
from celery import Task
import asyncio
import subprocess
import os
import signal

class ClaudeTask(Task):
    """Custom task class for subprocess management"""
    
    def __init__(self):
        self.processes = {}
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Cleanup subprocess on failure"""
        if task_id in self.processes:
            process = self.processes[task_id]
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            del self.processes[task_id]

@app.task(base=ClaudeTask, bind=True, max_retries=3)
def spawn_claude(self, prompt, session_id=None, model='sonnet'):
    """Spawn Claude CLI process"""
    try:
        cmd = ['claude', '--model', model, '--print', '--output-format', 'json']
        if session_id:
            cmd.extend(['--resume', session_id])
        
        # Start subprocess with new process group for cleanup
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
            text=True
        )
        
        # Track process
        self.processes[self.request.id] = process
        
        # Send prompt and wait
        stdout, stderr = process.communicate(input=prompt, timeout=300)
        
        if process.returncode != 0:
            raise Exception(f"Claude failed: {stderr}")
        
        return json.loads(stdout)
        
    except subprocess.TimeoutExpired:
        # Kill process group
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        raise self.retry(countdown=60)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
    finally:
        # Cleanup
        if self.request.id in self.processes:
            del self.processes[self.request.id]
```

**Dramatiq**:
```python
# dramatiq_tasks.py
import dramatiq
import subprocess
import os
import signal
import json
from dramatiq.middleware import Shutdown

# Simple process tracking
running_processes = {}

@dramatiq.actor(max_retries=3, min_backoff=30000)
def spawn_claude(prompt, session_id=None, model='sonnet', task_id=None):
    """Spawn Claude CLI process with Dramatiq"""
    process = None
    try:
        cmd = ['claude', '--model', model, '--print', '--output-format', 'json']
        if session_id:
            cmd.extend(['--resume', session_id])
        
        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
            text=True
        )
        
        # Track process
        if task_id:
            running_processes[task_id] = process
        
        # Send prompt and wait
        stdout, stderr = process.communicate(input=prompt, timeout=300)
        
        if process.returncode != 0:
            raise Exception(f"Claude failed: {stderr}")
        
        result = json.loads(stdout)
        
        # Publish completion event
        publish_completion.send(task_id=task_id, result=result)
        
        return result
        
    except subprocess.TimeoutExpired:
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        raise
    finally:
        # Cleanup
        if task_id in running_processes:
            del running_processes[task_id]

# Graceful shutdown middleware
class ProcessCleanupMiddleware(dramatiq.Middleware):
    def before_worker_shutdown(self, broker, worker):
        """Clean up any running processes on shutdown"""
        for task_id, process in running_processes.items():
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
```

**Winner**: Dramatiq - Cleaner API with better middleware support for lifecycle management

### 3. Error Handling and Reliability

**Celery**:
- Complex retry mechanisms with multiple decorators
- Requires careful configuration of timeouts and limits
- Error handling spread across multiple callbacks
- Task state tracking can be complex

**Dramatiq**:
- Simple, declarative retry configuration
- Built-in exponential backoff
- Clear error propagation
- Middleware system for cross-cutting concerns

Example comparison:

```python
# Celery - Complex error handling
@app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3})
def celery_task(self, data):
    try:
        # Task logic
        pass
    except SpecificError as exc:
        # Custom retry logic
        raise self.retry(exc=exc, countdown=60)

# Dramatiq - Simple and clear
@dramatiq.actor(max_retries=3, min_backoff=15000, max_backoff=300000)
def dramatiq_task(data):
    # Task logic - exceptions automatically trigger retries
    pass
```

**Winner**: Dramatiq - More intuitive error handling

### 4. Performance Characteristics

**Celery**:
- Higher memory footprint with prefork pool
- Better for CPU-bound tasks with multiprocessing
- More overhead for simple tasks
- Complex worker pool management

**Dramatiq**:
- Lightweight single-threaded workers
- Perfect for I/O-bound tasks (like subprocess management)
- Lower memory footprint
- Simple process model

For KSI's use case (spawning CLI processes), both are more than adequate, but Dramatiq's lighter footprint is advantageous.

**Winner**: Dramatiq - Better suited for I/O-bound subprocess management

### 5. Event Publishing Integration

**Celery with KSI's message bus**:
```python
@app.task(bind=True)
def spawn_with_events(self, prompt, agent_id):
    result = spawn_claude(prompt)
    
    # Complex: Need to establish socket connection from worker
    async def publish_event():
        reader, writer = await asyncio.open_unix_connection('/tmp/ksi.sock')
        command = {
            "command": "PUBLISH",
            "params": {
                "from_agent": agent_id,
                "event_type": "PROCESS_COMPLETE",
                "payload": {"result": result}
            }
        }
        writer.write(json.dumps(command).encode() + b'\n')
        await writer.drain()
        writer.close()
    
    # Run async code in sync context
    asyncio.run(publish_event())
    return result
```

**Dramatiq with KSI's message bus**:
```python
@dramatiq.actor
def publish_completion(task_id, result):
    """Separate actor for event publishing"""
    import socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect('/tmp/ksi.sock')
    
    command = {
        "command": "PUBLISH",
        "params": {
            "from_agent": "task_worker",
            "event_type": "PROCESS_COMPLETE", 
            "payload": {"task_id": task_id, "result": result}
        }
    }
    sock.send(json.dumps(command).encode() + b'\n')
    sock.close()

@dramatiq.actor(max_retries=3)
def spawn_with_events(prompt, agent_id):
    result = spawn_claude(prompt)
    # Chain to publishing actor
    publish_completion.send(task_id=dramatiq.get_current_message_id(), result=result)
    return result
```

**Winner**: Dramatiq - Better actor composition and chaining

### 6. Community and Ecosystem

**Celery**:
- Larger community and ecosystem
- More third-party extensions
- Better documentation coverage
- More Stack Overflow answers

**Dramatiq**:
- Smaller but focused community
- Fewer extensions but covers core needs
- Clear, concise documentation
- Growing adoption in Python community

**Winner**: Celery - But this advantage is less relevant for KSI's focused use case

## Integration with KSI Architecture

### How Dramatiq Fits KSI's Design

```python
# ksi_task_worker.py
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Prometheus, Shutdown
import subprocess
import json
import logging

# Configure Dramatiq
redis_broker = RedisBroker(host="localhost")
redis_broker.add_middleware(Prometheus())
redis_broker.add_middleware(Shutdown())
dramatiq.set_broker(redis_broker)

logger = logging.getLogger(__name__)

class KSITaskManager:
    """Integrates Dramatiq with KSI's daemon"""
    
    def __init__(self, daemon_socket_path='/tmp/ksi.sock'):
        self.daemon_socket = daemon_socket_path
        self.active_tasks = {}
    
    def publish_to_daemon(self, event_type, payload):
        """Publish events back to KSI daemon"""
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.daemon_socket)
        
        command = {
            "command": "PUBLISH",
            "params": {
                "from_agent": "task_worker",
                "event_type": event_type,
                "payload": payload
            }
        }
        sock.send(json.dumps(command).encode() + b'\n')
        response = sock.recv(4096)
        sock.close()
        return json.loads(response)

# Global task manager
task_manager = KSITaskManager()

@dramatiq.actor(max_retries=3, min_backoff=30000, time_limit=600000)
def execute_claude_task(prompt, session_id=None, model='sonnet', agent_id=None):
    """Execute Claude CLI as a Dramatiq task"""
    
    task_id = dramatiq.get_current_message().message_id
    
    # Notify daemon of task start
    task_manager.publish_to_daemon("TASK_STARTED", {
        "task_id": task_id,
        "agent_id": agent_id,
        "prompt": prompt[:100] + "..."
    })
    
    try:
        # Build command
        cmd = [
            'claude', '--model', model, '--print', '--output-format', 'json',
            '--allowedTools', 'Task,Bash,Glob,Grep,LS,Read,Edit,MultiEdit,Write'
        ]
        if session_id:
            cmd.extend(['--resume', session_id])
        
        # Execute
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=prompt, timeout=300)
        
        if process.returncode != 0:
            raise Exception(f"Claude CLI failed: {stderr}")
        
        result = json.loads(stdout)
        
        # Notify daemon of completion
        task_manager.publish_to_daemon("TASK_COMPLETED", {
            "task_id": task_id,
            "agent_id": agent_id,
            "session_id": result.get('sessionId'),
            "result": result
        })
        
        return result
        
    except Exception as e:
        # Notify daemon of failure
        task_manager.publish_to_daemon("TASK_FAILED", {
            "task_id": task_id,
            "agent_id": agent_id,
            "error": str(e)
        })
        raise

# Actor for chained operations
@dramatiq.actor
def process_claude_output(result, agent_id):
    """Process Claude output and trigger follow-up actions"""
    # Extract tool calls, analyze output, etc.
    tool_calls = result.get('tool_calls', [])
    
    if tool_calls:
        task_manager.publish_to_daemon("TOOLS_EXECUTED", {
            "agent_id": agent_id,
            "tools": [tc['tool'] for tc in tool_calls]
        })

# Usage from KSI daemon
def spawn_task_from_daemon(prompt, session_id=None, model='sonnet', agent_id=None):
    """Called by daemon to spawn async task"""
    # Send to Dramatiq
    result = execute_claude_task.send(
        prompt=prompt,
        session_id=session_id,
        model=model,
        agent_id=agent_id
    )
    
    # Return task ID immediately
    return result.message_id
```

### Deployment Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   KSI Daemon    │────►│  Redis Broker    │────►│ Dramatiq Worker │
│                 │     │                  │     │                 │
│ - Message Bus   │     │ - Task Queue     │     │ - Task Executor │
│ - Agent Manager │◄────│ - Result Store   │◄────│ - Event Publisher│
│ - State Manager │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         ▲                                                 │
         │                                                 │
         └─────────────── Unix Socket ─────────────────────┘
                       (Event Publishing)
```

## Recommendation: Dramatiq

Based on this analysis, **Dramatiq is the recommended choice** for KSI because:

1. **Simplicity**: Minimal configuration and intuitive API align with KSI's philosophy
2. **Reliability**: Robust retry mechanisms and error handling for subprocess management
3. **Lightweight**: Lower resource footprint for I/O-bound subprocess tasks
4. **Clean Integration**: Better actor composition for event publishing
5. **Maintainability**: Easier to understand and maintain for future developers

### Implementation Roadmap

1. **Phase 1**: Add Redis dependency and Dramatiq to requirements.txt
2. **Phase 2**: Create `daemon/task_worker.py` with basic Dramatiq configuration
3. **Phase 3**: Implement `execute_claude_task` actor with subprocess management
4. **Phase 4**: Add event publishing back to daemon message bus
5. **Phase 5**: Create `QUEUE_TASK` daemon command for task submission
6. **Phase 6**: Add worker management to `daemon_control.sh`

### Example Integration Code

```python
# daemon/command_handler.py addition
async def handle_queue_task(params: dict) -> dict:
    """Queue a Claude task for async execution"""
    from .task_worker import spawn_task_from_daemon
    
    prompt = params['prompt']
    session_id = params.get('session_id')
    model = params.get('model', 'sonnet')
    agent_id = params.get('agent_id')
    
    task_id = spawn_task_from_daemon(
        prompt=prompt,
        session_id=session_id,
        model=model,
        agent_id=agent_id
    )
    
    return {
        'success': True,
        'task_id': task_id,
        'status': 'queued'
    }
```

This integration maintains KSI's minimal philosophy while adding robust task queue capabilities for long-running Claude processes.