# KSI SQLite Reference Architecture Plan

**Date**: 2025-01-22  
**Author**: Claude (Opus 4)  
**Purpose**: Detailed implementation plan for modernizing KSI with a lightweight, reference-based architecture

## Executive Summary

This plan outlines a comprehensive modernization of KSI using a **reference-based architecture** that combines:
- **SQLite** for metadata, event routing, and state management
- **File system** for Claude responses and large data
- **FastAPI + FastStream** for unified HTTP/WebSocket and messaging
- **Lightweight libraries** for reliability without operational complexity

The key insight: Events contain references to files, not the data itself. This maintains KSI's proven file-based approach while adding a queryable event layer that enables sophisticated routing and workflow management.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Design Principles](#core-design-principles)
3. [Technology Stack](#technology-stack)
4. [Storage Architecture](#storage-architecture)
5. [Event-Driven Message Bus](#event-driven-message-bus)
6. [Process Lifecycle Management](#process-lifecycle-management)
7. [Workflow Engine Design](#workflow-engine-design)
8. [Implementation Phases](#implementation-phases)
9. [Migration Strategy](#migration-strategy)
10. [Testing Strategy](#testing-strategy)
11. [Operational Considerations](#operational-considerations)
12. [Risk Analysis](#risk-analysis)
13. [Success Metrics](#success-metrics)

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI + FastStream                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   HTTP API  │  │  WebSocket   │  │   Message Handlers     │ │
│  │  /spawn     │  │  Real-time   │  │   @subscriber("...")   │ │
│  │  /agents    │  │  Updates     │  │   Async Processing     │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  SQLite (WAL)   │
                    │  ┌──────────┐   │
                    │  │ Messages │   │──► Event routing (references)
                    │  ├──────────┤   │
                    │  │Workflows │   │──► State tracking
                    │  ├──────────┤   │
                    │  │Processes │   │──► Spawn lifecycle
                    │  ├──────────┤   │
                    │  │ Config   │   │──► Dynamic settings
                    │  ├──────────┤   │
                    │  │ Agents   │   │──► Registry & status
                    │  └──────────┘   │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
     ┌──────────────────┐         ┌──────────────────┐
     │   File System    │         │   File System    │
     │  claude_logs/    │         │     state/       │
     │  ├── {id}.jsonl  │         │  ├── workflows/  │
     │  └── index.db    │         │  └── shared/     │
     └──────────────────┘         └──────────────────┘
```

### Reference-Based Design

The architecture separates **metadata** from **data**:

- **SQLite stores references**: `{response_file: "claude_logs/abc.jsonl", line: 5}`
- **Files store actual data**: Full Claude responses, large prompts, conversation history
- **Events are lightweight**: 100-500 bytes per message
- **Queries are fast**: SQL for finding data, files for reading it

## Core Design Principles

### 1. Keep It Simple
- Single SQLite file for all metadata
- Standard file system for data
- No external services required
- `cp ksi.db backup.db` for backups

### 2. Event-Driven, Not Polling
- Publishers write events to SQLite
- Subscribers use efficient queries
- Short-interval async checks (not busy-waiting)
- File watchers for real-time updates

### 3. Crash-Resilient
- WAL mode for durability
- State persisted after each step
- Idempotent operations
- Resume from exact failure point

### 4. Developer-Friendly
- SQL queries for debugging
- Structured logs with correlation IDs
- Fast unit tests with in-memory SQLite
- Rich terminal output

## Technology Stack

### Core Components

| Component | Technology | Purpose | Why This Choice |
|-----------|------------|---------|-----------------|
| API Framework | FastAPI | HTTP/WebSocket endpoints | Automatic validation, async native |
| Message Bus | FastStream + SQLite | Event routing | Unified with API, SQL queryable |
| Database | SQLite + WAL | Metadata & state | Zero ops, ACID, concurrent reads |
| Process Retry | Tenacity | Retry logic | Lightweight, decorators |
| Logging | structlog | Structured logs | JSON output, correlation IDs |
| Configuration | python-dotenv + SQLite | Settings | Env vars + dynamic config |
| File I/O | aiofiles | Async file ops | Non-blocking I/O |
| CLI | Click | Command interface | Declarative, testable |
| Terminal UI | Rich | Beautiful output | Tables, progress bars |
| Hot Reload | Watchdog | File monitoring | Development productivity |

### Additional Libraries

- **httpx**: Async HTTP client for external APIs
- **pytest**: Testing framework with fixtures
- **Alembic**: SQLite schema migrations
- **python-dateutil**: Time handling
- **pydantic**: Data validation for configs
- **schedule**: Cron-like job scheduling
- **black**: Code formatting
- **mypy**: Type checking

## Storage Architecture

### SQLite Schema Design

```sql
-- Messages table: Event bus core
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,                    -- e.g., "claude.spawn.request"
    event_type TEXT NOT NULL,               -- e.g., "SPAWN_REQUEST"
    data JSON NOT NULL,                     -- Event payload (with file refs)
    status TEXT DEFAULT 'pending',          -- pending/processing/completed/failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error TEXT
);
CREATE INDEX idx_messages_topic_status ON messages(topic, status);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Workflows table: Workflow state tracking
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,                    -- Workflow instance ID
    type TEXT NOT NULL,                     -- Workflow type (debate, analysis, etc.)
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER,
    state JSON,                             -- Small workflow state
    checkpoint_file TEXT,                   -- Reference to large state file
    status TEXT DEFAULT 'running',          -- running/paused/completed/failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processes table: Claude spawn tracking
CREATE TABLE processes (
    id TEXT PRIMARY KEY,                    -- Process ID
    workflow_id TEXT,
    agent_id TEXT,
    status TEXT DEFAULT 'pending',          -- pending/running/completed/failed
    model TEXT DEFAULT 'sonnet',
    prompt_file TEXT,                       -- Input prompt file reference
    response_file TEXT,                     -- Output response file reference
    response_line INTEGER,                  -- Line number in JSONL
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    metrics JSON,                           -- {tokens: 1234, cost: 0.05, duration_ms: 3421}
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

-- Config table: Dynamic configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agents table: Agent registry
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    display_name TEXT,
    status TEXT DEFAULT 'inactive',         -- inactive/active/busy
    current_session_id TEXT,
    current_process_id TEXT,
    capabilities JSON,                      -- ["debate", "analysis", "coding"]
    metrics JSON,                           -- {total_tokens: 50000, total_cost: 2.50}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP
);

-- Subscriptions table: Message routing
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    topic_pattern TEXT NOT NULL,            -- Can use LIKE patterns
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, topic_pattern)
);

-- Metrics table: Performance tracking
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    tags JSON,                              -- {agent_id: "123", model: "opus"}
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_metrics_name_time ON metrics(metric_name, timestamp);
```

### File System Structure

```
ksi/
├── claude_logs/                    # Existing pattern - preserved
│   ├── {session_id}.jsonl         # Full Claude conversation logs
│   ├── latest.jsonl               # Symlink to most recent
│   └── index.sqlite               # Optional: Searchable metadata
│
├── prompts/
│   ├── queue/                     # Temporary prompts awaiting processing
│   │   └── {process_id}.txt
│   ├── templates/                 # Reusable prompt templates
│   └── archive/                   # Completed prompts (auto-cleanup)
│
├── state/
│   ├── workflows/                 # Workflow checkpoints
│   │   └── {workflow_id}/
│   │       └── step_{n}.json
│   ├── shared/                    # Large shared state
│   │   └── {key}.json
│   └── memory/                    # Project knowledge (existing)
│
├── ksi.db                         # Main SQLite database
├── ksi.db-wal                     # Write-ahead log
└── ksi.db-shm                     # Shared memory file
```

### Storage Patterns

**Small Data → SQLite**
- Event messages (100-500 bytes)
- Process status
- Configuration
- Metrics
- Agent registry

**Large Data → Files**
- Claude responses (KB-MB)
- Conversation history
- Workflow checkpoints
- Prompts
- Knowledge documents

**Hybrid Approach**
```python
# SQLite stores metadata
{
    "id": "proc_123",
    "status": "completed",
    "response_file": "claude_logs/session_abc.jsonl",
    "response_line": 5,
    "metrics": {
        "tokens": 1523,
        "cost": 0.0234,
        "duration_ms": 3421
    }
}

# File stores actual response
# claude_logs/session_abc.jsonl (line 5)
{"type": "claude", "content": "Here is my response...", "tokens": {...}}
```

## Event-Driven Message Bus

### Event Message Structure

```python
# Lightweight event messages (stored in SQLite)
{
    "id": "msg_12345",
    "topic": "claude.spawn.request",
    "event_type": "SPAWN_REQUEST",
    "data": {
        "process_id": "proc_123",
        "prompt_file": "prompts/queue/proc_123.txt",
        "model": "sonnet",
        "agent_id": "agent_456",
        "workflow_id": "wf_789"
    }
}

# Completion event
{
    "id": "msg_12346",
    "topic": "claude.spawn.complete",
    "event_type": "SPAWN_COMPLETE",
    "data": {
        "process_id": "proc_123",
        "response_file": "claude_logs/session_abc.jsonl",
        "response_line": 5,
        "summary": {
            "tokens": 1523,
            "cost": 0.0234,
            "duration_ms": 3421,
            "success": true
        }
    }
}
```

### Topic Hierarchy

```
claude.
├── spawn.
│   ├── request         # New spawn requested
│   ├── started         # Process started
│   ├── complete        # Process completed
│   └── failed          # Process failed
├── agent.
│   ├── connected       # Agent came online
│   ├── disconnected    # Agent went offline
│   ├── message         # Inter-agent message
│   └── state_change    # Agent state updated
├── workflow.
│   ├── started         # Workflow began
│   ├── step_complete   # Step finished
│   ├── checkpoint      # State saved
│   └── complete        # Workflow done
└── system.
    ├── config_change   # Configuration updated
    ├── error           # System error
    └── metric          # Performance metric
```

### Message Flow Implementation

```python
# Publishing (FastStream + SQLite)
@app.post("/spawn")
async def spawn_claude(request: SpawnRequest):
    # 1. Write prompt to file
    prompt_file = f"prompts/queue/{process_id}.txt"
    async with aiofiles.open(prompt_file, 'w') as f:
        await f.write(request.prompt)
    
    # 2. Publish event to SQLite
    await publish_event(
        topic="claude.spawn.request",
        data={
            "process_id": process_id,
            "prompt_file": prompt_file,
            "model": request.model
        }
    )
    
    return {"process_id": process_id, "status": "queued"}

# Subscribing (FastStream subscriber)
@subscriber("claude.spawn.request")
async def handle_spawn_request(msg: dict):
    # 1. Read prompt from file
    async with aiofiles.open(msg["prompt_file"]) as f:
        prompt = await f.read()
    
    # 2. Execute Claude
    response = await execute_claude(prompt, msg["model"])
    
    # 3. Save response to file
    response_file = f"claude_logs/{session_id}.jsonl"
    async with aiofiles.open(response_file, 'a') as f:
        await f.write(json.dumps(response) + '\n')
    
    # 4. Publish completion event
    await publish_event(
        topic="claude.spawn.complete",
        data={
            "process_id": msg["process_id"],
            "response_file": response_file,
            "response_line": line_number
        }
    )
```

## Process Lifecycle Management

### State Machine Design

```
┌─────────┐      ┌──────────┐      ┌─────────┐      ┌───────────┐
│ PENDING │─────►│ RUNNING  │─────►│ SUCCESS │      │ COMPLETED │
└─────────┘      └─────┬────┘      └────┬────┘      └───────────┘
                       │                 │                  ▲
                       ▼                 └──────────────────┘
                 ┌─────────┐        ┌─────────┐
                 │ FAILED  │───────►│ RETRY   │
                 └─────────┘        └─────────┘
                       │
                       ▼
                 ┌─────────┐
                 │  DEAD   │
                 └─────────┘
```

### Retry Strategy with Tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def execute_claude_with_retry(prompt: str, model: str) -> dict:
    """Execute Claude with automatic retries"""
    # Update process status
    await update_process_status(process_id, "RUNNING")
    
    try:
        # Call Claude CLI
        result = await run_claude_cli(prompt, model)
        
        # Update success
        await update_process_status(process_id, "SUCCESS", result)
        return result
        
    except Exception as e:
        # Update failure
        await update_process_status(process_id, "FAILED", error=str(e))
        raise
```

### Process Monitoring

```python
class ProcessMonitor:
    """Monitor and manage running processes"""
    
    async def check_timeouts(self):
        """Check for timed-out processes"""
        timeout_threshold = datetime.utcnow() - timedelta(minutes=5)
        
        stale_processes = await db.fetch("""
            SELECT id FROM processes 
            WHERE status = 'RUNNING' 
            AND started_at < ?
        """, timeout_threshold)
        
        for proc in stale_processes:
            await self.handle_timeout(proc['id'])
    
    async def collect_metrics(self):
        """Collect process metrics"""
        metrics = await db.fetch("""
            SELECT 
                model,
                COUNT(*) as count,
                AVG(json_extract(metrics, '$.duration_ms')) as avg_duration,
                SUM(json_extract(metrics, '$.tokens')) as total_tokens
            FROM processes
            WHERE completed_at > datetime('now', '-1 hour')
            GROUP BY model
        """)
        
        for metric in metrics:
            await self.publish_metric(
                "process.performance",
                metric
            )
```

## Workflow Engine Design

### Lightweight Workflow Implementation

```python
class SQLiteWorkflowEngine:
    """Simple but powerful workflow engine backed by SQLite"""
    
    def __init__(self, db_path: str):
        self.db = db_path
        self.workflows = {}  # Registered workflow definitions
    
    async def register_workflow(self, name: str, steps: List[WorkflowStep]):
        """Register a workflow definition"""
        self.workflows[name] = {
            "name": name,
            "steps": steps,
            "total_steps": len(steps)
        }
    
    async def start_workflow(self, workflow_type: str, params: dict) -> str:
        """Start a new workflow instance"""
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        
        # Initialize workflow in database
        await db.execute("""
            INSERT INTO workflows (id, type, total_steps, state)
            VALUES (?, ?, ?, ?)
        """, workflow_id, workflow_type, len(self.workflows[workflow_type]["steps"]), 
             json.dumps({"params": params, "results": {}}))
        
        # Trigger first step
        await self.execute_next_step(workflow_id)
        
        return workflow_id
    
    async def execute_next_step(self, workflow_id: str):
        """Execute the next step in workflow"""
        # Get current state
        workflow = await self.get_workflow(workflow_id)
        
        if workflow["current_step"] >= workflow["total_steps"]:
            await self.complete_workflow(workflow_id)
            return
        
        # Get step definition
        step = self.workflows[workflow["type"]]["steps"][workflow["current_step"]]
        
        # Execute step (this publishes an event)
        await self.publish_event(
            f"workflow.{workflow['type']}.step.{step['name']}",
            {
                "workflow_id": workflow_id,
                "step": workflow["current_step"],
                "params": step["params"],
                "context": workflow["state"]
            }
        )
    
    async def handle_step_complete(self, workflow_id: str, step_result: dict):
        """Handle step completion"""
        # Update workflow state
        workflow = await self.get_workflow(workflow_id)
        workflow["state"]["results"][f"step_{workflow['current_step']}"] = step_result
        workflow["current_step"] += 1
        
        # Save checkpoint if large
        if len(json.dumps(workflow["state"])) > 10000:
            checkpoint_file = f"state/workflows/{workflow_id}/step_{workflow['current_step']}.json"
            async with aiofiles.open(checkpoint_file, 'w') as f:
                await f.write(json.dumps(workflow["state"]))
            
            # Store reference in DB
            await db.execute("""
                UPDATE workflows 
                SET checkpoint_file = ?, state = ?, current_step = ?
                WHERE id = ?
            """, checkpoint_file, json.dumps({"checkpoint": True}), 
                 workflow["current_step"], workflow_id)
        else:
            # Store directly in DB
            await db.execute("""
                UPDATE workflows 
                SET state = ?, current_step = ?
                WHERE id = ?
            """, json.dumps(workflow["state"]), workflow["current_step"], workflow_id)
        
        # Execute next step
        await self.execute_next_step(workflow_id)
```

### Example Workflow: Multi-Agent Debate

```python
# Define debate workflow
debate_steps = [
    WorkflowStep(
        name="initialize_agents",
        handler="spawn_debate_agents",
        params={"models": ["opus", "sonnet"]}
    ),
    WorkflowStep(
        name="opening_statements",
        handler="collect_opening_statements",
        params={"timeout": 180}
    ),
    WorkflowStep(
        name="rebuttal_round_1",
        handler="conduct_rebuttal",
        params={"round": 1}
    ),
    WorkflowStep(
        name="rebuttal_round_2", 
        handler="conduct_rebuttal",
        params={"round": 2}
    ),
    WorkflowStep(
        name="closing_statements",
        handler="collect_closing_statements",
        params={"timeout": 180}
    ),
    WorkflowStep(
        name="generate_summary",
        handler="summarize_debate",
        params={"model": "opus"}
    )
]

# Register workflow
await workflow_engine.register_workflow("debate", debate_steps)

# Start debate
workflow_id = await workflow_engine.start_workflow(
    "debate",
    {"topic": "Is AI consciousness possible?"}
)
```

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Day 1-2: Project Setup**
- Initialize new project structure
- Set up development environment
- Install core dependencies
- Create SQLite schema with Alembic

**Day 3-4: Core Infrastructure**
- Implement SQLite message bus
- Create file storage utilities
- Set up structlog configuration
- Build basic FastAPI app

**Day 5-7: Integration**
- FastStream + SQLite integration
- Event publishing system
- Basic subscription handling
- Initial tests

**Deliverables:**
- Working message bus
- File reference system
- Basic API endpoints
- Unit test suite

### Phase 2: Process Management (Week 2)

**Day 1-3: Spawn System**
- Process lifecycle state machine
- Tenacity retry integration
- File-based prompt/response handling
- Process monitoring

**Day 4-5: Agent Management**
- Agent registry in SQLite
- Connection tracking
- Status management
- Capability matching

**Day 6-7: Testing**
- Process spawn tests
- Retry behavior tests
- Agent coordination tests
- Integration tests

**Deliverables:**
- Complete spawn system
- Agent management
- Monitoring dashboard
- Test coverage >80%

### Phase 3: Workflow Engine (Week 3)

**Day 1-3: Core Workflow Engine**
- Workflow definition system
- Step execution logic
- State persistence
- Checkpoint management

**Day 4-5: Standard Workflows**
- Debate workflow
- Analysis workflow
- Collaboration workflow
- Teaching workflow

**Day 6-7: Advanced Features**
- Workflow branching
- Conditional steps
- Parallel execution
- Error recovery

**Deliverables:**
- Working workflow engine
- 4+ workflow templates
- Workflow monitoring
- Recovery mechanisms

### Phase 4: Migration & Polish (Week 4)

**Day 1-2: Migration Tools**
- Data migration scripts
- Compatibility layer
- Parallel running setup
- Rollback procedures

**Day 3-4: UI/UX Improvements**
- Rich CLI interface
- Web dashboard (FastAPI + HTMX)
- Real-time updates
- Performance metrics

**Day 5-6: Production Readiness**
- systemd service files
- Backup automation
- Log rotation
- Monitoring setup

**Day 7: Documentation**
- API documentation
- Deployment guide
- Developer guide
- Migration guide

**Deliverables:**
- Migration tools
- Production configs
- Complete documentation
- Deployment scripts

### Phase 5: Optimization & Cleanup (Week 5)

**Day 1-2: Performance Tuning**
- SQLite optimization
- Index tuning
- Query optimization
- Connection pooling

**Day 3-4: Code Cleanup**
- Remove old code
- Refactor duplicates
- Improve abstractions
- Type hints

**Day 5-7: Final Testing**
- Load testing
- Chaos testing
- End-to-end tests
- User acceptance

**Deliverables:**
- Optimized system
- Clean codebase
- Performance benchmarks
- Release candidate

## Migration Strategy

### Principles

1. **No Breaking Changes**: Old system runs alongside new
2. **Gradual Cutover**: Migrate component by component
3. **Data Preservation**: All existing data maintained
4. **Rollback Ready**: Can revert at any point

### Migration Steps

#### Step 1: Parallel Infrastructure
```python
# Run new SQLite message bus alongside old system
class DualMessageBus:
    def __init__(self, old_bus, new_bus):
        self.old_bus = old_bus
        self.new_bus = new_bus
    
    async def publish(self, topic: str, data: dict):
        # Publish to both systems
        await self.old_bus.publish(topic, data)
        await self.new_bus.publish(topic, data)
```

#### Step 2: Shadow Operations
- New system processes events but doesn't affect production
- Compare results between old and new
- Identify discrepancies
- Fix issues

#### Step 3: Gradual Cutover
1. **Read Path First**: Start reading from new system
2. **Non-Critical Writes**: Move monitoring, metrics
3. **Critical Writes**: Move spawn operations
4. **Full Cutover**: Disable old system

#### Step 4: Data Migration
```python
# Migrate existing sessions to new schema
async def migrate_sessions():
    for session_file in Path("claude_logs").glob("*.jsonl"):
        session_id = session_file.stem
        
        # Create index entry
        await db.execute("""
            INSERT INTO claude_session_index 
            (session_id, file_path, line_count, created_at)
            VALUES (?, ?, ?, ?)
        """, session_id, str(session_file), 
             count_lines(session_file), 
             session_file.stat().st_ctime)
```

#### Step 5: Cleanup
- Archive old code
- Remove compatibility layers
- Update documentation
- Celebrate! 🎉

## Testing Strategy

### Testing Levels

#### Unit Tests
```python
# Test with in-memory SQLite
@pytest.fixture
def test_db():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db

def test_message_publishing(test_db):
    bus = SQLiteMessageBus(test_db)
    
    # Publish message
    msg_id = await bus.publish("test.topic", {"data": "value"})
    
    # Verify stored correctly
    msg = await bus.get_message(msg_id)
    assert msg["topic"] == "test.topic"
    assert msg["data"]["data"] == "value"
```

#### Integration Tests
```python
# Test full flow with real files
async def test_spawn_workflow(tmp_path):
    # Setup
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Test prompt")
    
    # Execute
    process_id = await spawn_claude(
        prompt_file=str(prompt_file),
        model="sonnet"
    )
    
    # Wait for completion
    result = await wait_for_completion(process_id, timeout=30)
    
    # Verify
    assert result["status"] == "completed"
    assert Path(result["response_file"]).exists()
```

#### Performance Tests
```python
# Load testing
async def test_message_throughput():
    bus = SQLiteMessageBus("test.db")
    
    # Publish 10k messages
    start = time.time()
    for i in range(10000):
        await bus.publish(f"perf.test.{i % 10}", {"index": i})
    
    duration = time.time() - start
    throughput = 10000 / duration
    
    assert throughput > 1000  # >1k msgs/sec
```

#### Chaos Tests
```python
# Test crash recovery
async def test_workflow_crash_recovery():
    # Start workflow
    wf_id = await start_workflow("debate", {"topic": "AI"})
    
    # Wait for step 2
    await wait_for_step(wf_id, 2)
    
    # Simulate crash
    os.kill(os.getpid(), signal.SIGKILL)
    
    # Restart and verify continues from step 2
    # (in new process)
    engine = WorkflowEngine()
    await engine.resume_workflows()
    
    # Verify workflow completed
    result = await wait_for_completion(wf_id)
    assert result["status"] == "completed"
```

### Test Data Management

- **Fixtures**: Standard test prompts and responses
- **Mocks**: Claude CLI responses for fast tests
- **Factories**: Generate test data programmatically
- **Cleanup**: Automatic test data removal

## Operational Considerations

### Deployment

#### Development
```bash
# .env file
DATABASE_URL=sqlite:///ksi_dev.db
LOG_LEVEL=DEBUG
CLAUDE_MOCK=true

# Run with hot reload
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

#### Production
```bash
# systemd service
[Unit]
Description=KSI Daemon
After=network.target

[Service]
Type=exec
User=ksi
WorkingDirectory=/opt/ksi
Environment="DATABASE_URL=sqlite:///ksi.db"
Environment="LOG_LEVEL=INFO"
ExecStart=/opt/ksi/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### Monitoring

#### Health Checks
```python
@app.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "disk_space": await check_disk_space(),
        "message_queue": await check_message_queue()
    }
    
    status = "healthy" if all(checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}
```

#### Metrics Dashboard
- Message throughput
- Process success rate  
- Workflow completion time
- Token usage by model
- Cost tracking

### Backup Strategy

#### Automated Backups
```python
# Daily backup script
async def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # SQLite online backup
    async with aiosqlite.connect("ksi.db") as source:
        async with aiosqlite.connect(f"backups/ksi_{timestamp}.db") as backup:
            await source.backup(backup)
    
    # Compress old backups
    for old_backup in Path("backups").glob("*.db"):
        if old_backup.stat().st_mtime < time.time() - 86400 * 7:
            compress_file(old_backup)
```

#### Recovery Procedures
1. Stop service
2. Copy backup to ksi.db
3. Verify integrity
4. Start service
5. Verify functionality

### Performance Tuning

#### SQLite Optimizations
```sql
-- Optimize for our workload
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;  -- 64MB cache
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;  -- 256MB memory map

-- Analyze periodically
ANALYZE;
```

#### Application Optimizations
- Connection pooling
- Batch processing
- Async I/O everywhere
- Efficient queries
- Index usage

### Security Considerations

#### Access Control
- File permissions (600 for DB)
- API authentication
- Rate limiting
- Input validation

#### Data Protection
- Encrypt sensitive data
- Secure file storage
- Audit logging
- Key rotation

## Risk Analysis

### Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| SQLite corruption | High | Low | WAL mode, backups, checksums |
| File system full | High | Medium | Monitoring, rotation, alerts |
| Performance degradation | Medium | Medium | Indexes, monitoring, tuning |
| Migration failure | High | Low | Rollback plan, parallel run |

### Operational Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Data loss | High | Low | Backups, WAL, replication |
| Service downtime | Medium | Low | systemd restart, monitoring |
| Resource exhaustion | Medium | Medium | Limits, monitoring, scaling |

### Mitigation Strategies

1. **Defense in Depth**: Multiple layers of protection
2. **Monitoring**: Proactive issue detection
3. **Automation**: Reduce human error
4. **Documentation**: Clear runbooks
5. **Testing**: Comprehensive test coverage

## Success Metrics

### Technical Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Code lines | 18,500 | 5,500 | cloc |
| Test coverage | Unknown | >80% | pytest-cov |
| Response time | Variable | <100ms | p95 latency |
| Reliability | Unknown | 99.9% | Uptime |

### Business Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Deployment time | Hours | Minutes | Time to deploy |
| Debug time | Hours | Minutes | Issue resolution |
| Onboarding time | Days | Hours | New dev productivity |
| Operational cost | Medium | Low | Time spent on ops |

### Quality Metrics

- **Code Quality**: Pylint score >9.0
- **Documentation**: 100% public API documented
- **Type Coverage**: >90% with mypy
- **Security**: No critical vulnerabilities

## Conclusion

This architecture modernizes KSI while preserving its core strengths:

1. **Maintains file-based approach** that works well for Claude responses
2. **Adds queryable event layer** for sophisticated routing
3. **Uses SQLite for everything** except large data
4. **Zero operational complexity** - single file database
5. **Production-ready** with proper monitoring and backups

The reference-based architecture elegantly solves the problem of mixing metadata with data, giving us the best of both worlds: SQL queryability for finding things and file system efficiency for storing them.

Total implementation time: 5 weeks
Expected code reduction: 70%
Operational complexity: Minimal
Risk level: Low with proper migration strategy

The result will be a lean, mean, Claude-orchestrating machine that's a joy to operate and develop.