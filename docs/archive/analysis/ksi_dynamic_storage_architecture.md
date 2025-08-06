# KSI Dynamic Storage Architecture

## Executive Summary

This document presents a refined storage architecture for the KSI multi-agent system that embraces dynamic, peer-to-peer agent relationships while solving critical technical challenges around write contention and data duplication. The design leverages existing `var/logs/responses/` as the single source of truth for completion data while maintaining efficient indexing for complex multi-agent interactions.

## Core Design Principles

### 1. Dynamic Agent Relationships
- No fixed hierarchy (orchestrator/worker) assumptions
- Supports peer-to-peer, self-organizing, and emergent topologies
- Agents can dynamically shift roles within conversations
- Teams and coalitions can form and dissolve organically

### 2. Minimal Data Duplication
- `var/logs/responses/` remains the single source of truth for completion results
- Event storage only for non-completion events
- SQL serves as pure navigation index, not data storage

### 3. Write Contention Solution
- Session-based JSONL files with single owner
- Daemon-serialized write queue prevents conflicts
- Async-safe by design

### 4. Efficient Reconstruction
- Minimal index enables fast queries
- File pointers instead of duplicated content
- Time-based organization supports archival

## Storage Architecture

### Directory Structure

```
var/logs/
├── responses/                    # JSONL completion logs (source of truth)
│   └── sessions/
│       ├── sess_{uuid1}.jsonl   # Each session owned by initiating agent
│       ├── sess_{uuid2}.jsonl   
│       └── sess_{uuid3}.jsonl
├── events/                      # Only non-completion events
│   └── 2024-01-15/
│       ├── evt_1234567890.123_agent_spawn.json
│       ├── evt_1234567890.456_state_change.json
│       └── evt_1234567890.789_team_formation.json
└── index/
    └── daily/
        └── 2024-01-15.db       # Daily SQLite indexes
```

### JSONL Session Files

Each session file contains a chronological sequence of completion requests and responses:

```jsonl
{"event": "completion:request", "data": {"prompt": "Any agents interested in data analysis?", "pattern": "peer_discovery", "session_id": "sess_abc123", "agent_id": "agent_explorer"}, "timestamp": 1735500000.123}
{"event": "completion:result", "data": {"response": "I have data analysis capabilities", "agent_id": "agent_analyzer", "model": "claude-3-opus", "usage": {...}}, "correlation_id": "req_123", "timestamp": 1735500010.456}
{"event": "completion:request", "data": {"prompt": "Let's collaborate on this dataset", "pattern": "peer_to_peer", "to_agent": "agent_analyzer"}, "timestamp": 1735500020.789}
{"event": "completion:result", "data": {"response": "Agreed, I'll start with statistical analysis", "agent_id": "agent_explorer"}, "correlation_id": "req_124", "timestamp": 1735500030.123}
```

### SQL Index Schema

```sql
-- Minimal index for navigation and queries
CREATE TABLE ksi_index (
    -- Core identifiers
    id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    
    -- File location (the only storage reference)
    file_path TEXT NOT NULL,
    line_number INTEGER,
    byte_offset INTEGER,            -- For efficient seeking
    
    -- Dynamic agent relationships
    initiating_agent TEXT NOT NULL, -- Session owner
    participating_agents TEXT,      -- JSON array of all participants
    agent_roles TEXT,              -- JSON: {"agent_id": "current_role"}
    
    -- Communication metadata
    pattern_type TEXT,             -- 'peer_to_peer', 'broadcast', 'team', 'swarm'
    conversation_id TEXT,
    correlation_id TEXT,           -- Links requests to responses
    
    -- Minimal flags for filtering
    is_completion BOOLEAN DEFAULT 0,
    is_request BOOLEAN DEFAULT 0,
    has_response BOOLEAN DEFAULT 0,
    requests_response BOOLEAN DEFAULT 0
);

-- Indexes for common query patterns
CREATE INDEX idx_timeline ON ksi_index(timestamp);
CREATE INDEX idx_session ON ksi_index(session_id, timestamp);
CREATE INDEX idx_agent ON ksi_index(initiating_agent, timestamp);
CREATE INDEX idx_participants ON ksi_index(participating_agents);
CREATE INDEX idx_conversation ON ksi_index(conversation_id, timestamp);
CREATE INDEX idx_pattern ON ksi_index(pattern_type, timestamp);
CREATE INDEX idx_pending ON ksi_index(requests_response, has_response) 
    WHERE requests_response = 1 AND has_response = 0;
```

## Write Contention Solution

### Daemon Write Serialization

The daemon ensures write safety through a single write queue:

```python
class ResponseLogWriter:
    """Daemon component that serializes all JSONL writes"""
    
    def __init__(self):
        self.write_queue = asyncio.Queue()
        self.file_handles = {}  # Keep files open for efficiency
        self.session_locks = {}  # Ensure single writer per session
        
    async def queue_completion_event(self, event):
        """Queue completion for serialized writing"""
        session_id = event.get("data", {}).get("session_id")
        if not session_id:
            raise ValueError("Completion event must have session_id")
            
        await self.write_queue.put({
            "session_id": session_id,
            "event": event,
            "timestamp": time.time()
        })
        
    async def write_worker(self):
        """Single worker that performs all writes"""
        while True:
            item = await self.write_queue.get()
            session_id = item["session_id"]
            
            # Ensure we have exclusive access to this session file
            if session_id not in self.session_locks:
                self.session_locks[session_id] = asyncio.Lock()
                
            async with self.session_locks[session_id]:
                # Get or create file handle
                if session_id not in self.file_handles:
                    filepath = f"var/logs/responses/sessions/{session_id}.jsonl"
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    self.file_handles[session_id] = open(filepath, 'a')
                    
                # Write atomically
                f = self.file_handles[session_id]
                byte_offset = f.tell()
                line_data = json.dumps(item["event"])
                f.write(line_data + '\n')
                f.flush()
                
                # Update index
                await self.update_index(
                    event=item["event"],
                    file_path=filepath,
                    byte_offset=byte_offset
                )
```

## Dynamic Communication Patterns

### Peer-to-Peer Discovery

```jsonl
// Agent broadcasts capability query
{"event": "completion:request", "data": {"prompt": "Looking for agents with NLP capabilities", "pattern": "peer_discovery", "broadcast": true}, "metadata": {"session_id": "sess_discovery_123", "agent_id": "agent_researcher"}}

// Multiple agents respond
{"event": "completion:result", "data": {"response": "I have NLP capabilities: sentiment analysis, entity extraction", "agent_id": "agent_nlp_1", "capabilities": ["sentiment", "ner"]}}
{"event": "completion:result", "data": {"response": "I specialize in text generation and summarization", "agent_id": "agent_nlp_2", "capabilities": ["generation", "summary"]}}
```

### Self-Organizing Team Formation

```jsonl
// Initial team formation request
{"event": "completion:request", "data": {"prompt": "Forming team for customer analysis project", "pattern": "team_formation", "team_id": "team_customer_analysis"}, "metadata": {"session_id": "sess_team_456"}}

// Agents join with self-declared roles
{"event": "completion:result", "data": {"response": "Joining as data analyst", "agent_id": "agent_analyst", "role": "data_analyst", "team_id": "team_customer_analysis"}}
{"event": "completion:result", "data": {"response": "I'll handle visualization", "agent_id": "agent_viz", "role": "visualizer", "team_id": "team_customer_analysis"}}

// Dynamic coordination emerges
{"event": "completion:request", "data": {"prompt": "I'll coordinate the first phase", "pattern": "role_assumption", "previous_role": "peer", "new_role": "phase_coordinator"}, "metadata": {"agent_id": "agent_analyst", "team_id": "team_customer_analysis"}}
```

### Dynamic Role Transitions

```jsonl
// Agent takes on temporary orchestrator role
{"event": "completion:request", "data": {"prompt": "Taking lead on data pipeline", "context": {"role_transition": {"from": "contributor", "to": "pipeline_orchestrator", "duration": "task_scoped"}}}}

// Later returns to peer role
{"event": "completion:request", "data": {"prompt": "Pipeline complete, returning to peer role", "context": {"role_transition": {"from": "pipeline_orchestrator", "to": "peer"}}}}
```

## Query Patterns

### Finding Peer Interactions

```python
async def find_peer_interactions(agent_id, time_window):
    """Find all peer-to-peer interactions involving an agent"""
    return await db.execute("""
        SELECT id, timestamp, file_path, line_number, participating_agents
        FROM ksi_index
        WHERE pattern_type = 'peer_to_peer'
        AND participating_agents LIKE ?
        AND timestamp > ?
        ORDER BY timestamp
    """, (f'%"{agent_id}"%', time.time() - time_window))
```

### Tracking Role Evolution

```python
async def get_agent_role_history(agent_id, session_id):
    """Track how an agent's role evolved in a session"""
    events = await db.execute("""
        SELECT timestamp, agent_roles, file_path, line_number
        FROM ksi_index
        WHERE session_id = ?
        AND participating_agents LIKE ?
        ORDER BY timestamp
    """, (session_id, f'%"{agent_id}"%'))
    
    role_history = []
    for event in events:
        roles = json.loads(event['agent_roles'])
        if agent_id in roles:
            role_history.append({
                'timestamp': event['timestamp'],
                'role': roles[agent_id]
            })
    return role_history
```

### Finding Unanswered Requests

```python
async def find_pending_requests(time_limit=300):
    """Find requests that haven't received responses"""
    return await db.execute("""
        SELECT id, timestamp, initiating_agent, file_path
        FROM ksi_index
        WHERE requests_response = 1
        AND has_response = 0
        AND timestamp > ?
        ORDER BY timestamp
    """, (time.time() - time_limit,))
```

## Session Management

### Session Ownership

- Each session has a single initiating agent who "owns" the write capability
- Other agents participate via the event system, not direct writes
- Prevents write contention while supporting any communication pattern

### Session Lifecycle

```python
async def create_session(initiating_agent, pattern_type='general'):
    """Create a new session owned by an agent"""
    session_id = f"sess_{uuid4()}"
    
    # Register session
    await db.execute("""
        INSERT INTO session_registry 
        (session_id, initiating_agent, created_at, pattern_type, status)
        VALUES (?, ?, ?, ?, 'active')
    """, (session_id, initiating_agent, time.time(), pattern_type))
    
    return session_id

async def get_session_participants(session_id):
    """Get all unique participants in a session"""
    result = await db.execute("""
        SELECT DISTINCT participating_agents
        FROM ksi_index
        WHERE session_id = ?
    """, (session_id,))
    
    all_participants = set()
    for row in result:
        participants = json.loads(row['participating_agents'])
        all_participants.update(participants)
    
    return list(all_participants)
```

## Storage Efficiency

### What Goes Where

**In JSONL Response Files:**
- All completion requests (prompts, context)
- All completion results (responses, usage)
- Session and correlation metadata
- Timestamps and agent identifiers

**In Event Files (Individual JSON):**
- Agent lifecycle events (spawn, terminate)
- State management events (set, get, delete)
- Team formation events
- System events (health, shutdown)
- Any non-completion event

**In SQL Index:**
- File pointers (path, line number, byte offset)
- Minimal metadata for queries
- Relationship tracking (participants, roles)
- Pattern classification
- Boolean flags for filtering

### Archive Strategy

```bash
# Daily rotation and compression
#!/bin/bash
DATE=$(date -d "yesterday" +%Y-%m-%d)

# Archive completed sessions
find var/logs/responses/sessions/ -name "*.jsonl" -mtime +1 | while read file; do
    if grep -q '"status": "completed"' "$file"; then
        gzip "$file"
        mv "$file.gz" "var/archive/sessions/$DATE/"
    fi
done

# Archive old event files
tar -czf "var/archive/events/events_$DATE.tar.gz" "var/logs/events/$DATE/"
rm -rf "var/logs/events/$DATE/"

# Compact old indexes
sqlite3 "var/logs/index/daily/$DATE.db" "VACUUM;"
```

## Integration Points

### Event Handler Integration

```python
async def handle_completion_event(event_name, data, context):
    """Route completion events to storage"""
    
    if event_name == "completion:request":
        # Add agent context
        data["agent_id"] = context.get("agent_id")
        data["pattern"] = detect_communication_pattern(data)
        
    # Queue for serialized writing
    await response_writer.queue_completion_event({
        "event": event_name,
        "data": data,
        "metadata": context,
        "timestamp": time.time()
    })
```

### Message Routing Integration

```python
async def route_message(message):
    """Route messages with pattern detection"""
    pattern = detect_pattern(message)
    
    if pattern in ["peer_to_peer", "team", "broadcast"]:
        # These generate completions - will be logged
        await emit_event("completion:request", {
            "prompt": message["content"],
            "pattern": pattern,
            "routing": message.get("routing", {})
        })
    else:
        # Direct agent message - store as event
        await store_event(message)
```

## Benefits of This Architecture

### 1. **Supports Dynamic Topologies**
- No hierarchy assumptions in storage structure
- Roles tracked in metadata, not file organization
- Natural support for emergent organizations

### 2. **Zero Write Contention**
- Session ownership model prevents conflicts
- Single write queue in daemon
- Async-safe by design

### 3. **Minimal Duplication**
- Leverages existing response logs
- No content duplication between storage layers
- SQL as pure navigation index

### 4. **Efficient Queries**
- Indexed metadata enables fast lookups
- Pattern-based queries for analysis
- Temporal queries for evolution tracking

### 5. **Operational Simplicity**
- Clear separation of concerns
- Easy archival and rotation
- Debugging via standard tools (grep, jq)

## Future Considerations

### Distributed KSI Deployments
- Session ownership could map to node affinity
- Cross-node session migration via ownership transfer
- Federated indexes for multi-node queries

### Advanced Analytics
- Graph analysis of agent relationships
- Pattern mining for optimal team compositions
- Role transition optimization

### Performance Optimizations
- Bloom filters for existence checks
- Compressed indexes for historical data
- Tiered storage for hot/cold data

## Conclusion

This architecture embraces the dynamic, self-organizing nature of multi-agent systems while solving critical technical challenges. By leveraging session ownership for write safety and maintaining minimal indexes for efficient queries, the system can scale to support complex agent interactions without sacrificing performance or flexibility.