# KSI Event Logging & Monitoring System

## Executive Summary

This document presents the comprehensive event logging and monitoring system for KSI - a critical safety infrastructure that enables autonomous agent operation while providing complete observability, forensic analysis, and real-time monitoring capabilities.

**🚨 CRITICAL SAFETY REQUIREMENT**: This system is mandatory before any autonomous agent deployment. Previous agent experiments compromised the KSI system without adequate audit trails.

## Current State vs Required Architecture

### Current Implementation ✅ (Partially Complete)

**Event Logging Core** (`ksi_daemon/event_log.py`)
- Ring buffer with 10k event capacity
- Pattern-based filtering (`completion:*`, `agent:*`)
- High-performance logging with minimal overhead
- Integration with `SimpleEventRouter`

**Monitoring API** (`ksi_daemon/plugins/core/monitor.py`)
- `monitor:get_events` - Query events with filtering
- `monitor:get_stats` - System statistics
- `monitor:clear_log` - Log management
- Pull-based architecture (no broadcast overhead)

**Response Storage** (`var/logs/responses/`)
- Individual JSONL files: `{session_id}.jsonl`
- One completion per file
- Provider-agnostic response format with KSI metadata
- Current format:
```json
{
  "ksi": {
    "provider": "claude-cli",
    "request_id": "uuid", 
    "timestamp": "ISO8601",
    "duration_ms": 7103
  },
  "response": {
    "result": "completion text",
    "session_id": "uuid",
    "total_cost_usd": 0.084,
    "usage": {...}
  }
}
```

### Critical Gaps 🚨 (Implementation Required)

**1. File Persistence** - Event log data lost on daemon restart
**2. Real-time Tailing** - No capability for live event streaming
**3. Structured Indexes** - No SQLite for complex multi-agent queries
**4. Tamper-evident Design** - No audit trail integrity verification
**5. Agent Isolation Boundaries** - No permission system for event access

## Complete Architecture Design

### Layer 1: Event Collection & Storage

#### Enhanced Event Log with Persistence
```python
class PersistentEventLog(DaemonEventLog):
    """Extended event log with file persistence and rotation."""
    
    def __init__(self, persist_dir: Path = "var/logs/events"):
        self.daily_files = {}  # {date: file_handle}
        self.current_file = None
        super().__init__(persist_to_file=persist_dir)
    
    def _persist_entry(self, entry: EventLogEntry):
        """Write to daily JSONL file with rotation."""
        date_str = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d")
        
        if date_str not in self.daily_files:
            filepath = self.persist_dir / f"events_{date_str}.jsonl"
            self.daily_files[date_str] = open(filepath, 'a')
            
        self.daily_files[date_str].write(json.dumps(entry.to_dict()) + '\n')
        self.daily_files[date_str].flush()
```

#### Unified Storage Architecture
```
var/logs/
├── responses/                    # Completion results (current)
│   └── {session_id}.jsonl       # One completion per file
├── events/                      # All non-completion events (NEW)
│   ├── 2025-06-30.jsonl        # Daily event files
│   └── 2025-07-01.jsonl
├── daemon/                      # System logs (current)
│   ├── daemon.log
│   └── tool_usage.jsonl
├── chat_textual.log             # Client interface logs (current)
├── archive/                     # Archived logs (current)
└── index/                       # Navigation indexes (NEW)
    ├── daily_2025-06-30.db     # SQLite for complex queries
    └── correlation_chains.db    # Event correlation tracking
```

**Client Logging**: Interface logs are placed directly in `var/logs/` using the pattern `{script_name}.log`. Use `config.get_client_log_file()` which automatically detects the calling script name from `sys.argv[0]` for zero-configuration client logging.

### Layer 2: Real-time Event Streaming

#### Live Event Tailing
```python
class EventStreamer:
    """Real-time event streaming for monitoring interfaces."""
    
    def __init__(self, event_log: PersistentEventLog):
        self.event_log = event_log
        self.subscribers = {}  # {client_id: EventSubscription}
        
    async def subscribe(self, client_id: str, filters: Dict):
        """Subscribe to live event stream with filters."""
        subscription = EventSubscription(
            client_id=client_id,
            event_patterns=filters.get("patterns", ["*"]),
            since=time.time()
        )
        self.subscribers[client_id] = subscription
        
    async def stream_events(self, client_id: str):
        """Stream events to subscriber via async generator."""
        subscription = self.subscribers.get(client_id)
        if not subscription:
            return
            
        while subscription.active:
            new_events = self.event_log.get_events(
                event_patterns=subscription.event_patterns,
                since=subscription.last_seen,
                limit=100
            )
            
            for event in new_events:
                yield event
                subscription.last_seen = event["timestamp"]
                
            await asyncio.sleep(0.1)  # 100ms polling
```

### Layer 3: Structured Navigation & Analysis

#### SQLite Index for Complex Queries
```sql
-- Daily event index for complex multi-agent analysis
CREATE TABLE event_index (
    id INTEGER PRIMARY KEY,
    timestamp REAL NOT NULL,
    event_name TEXT NOT NULL,
    event_type TEXT,  -- completion, agent, state, system
    
    -- Agent context
    agent_id TEXT,
    session_id TEXT,
    correlation_id TEXT,
    
    -- File location (no content duplication)
    source_file TEXT NOT NULL,
    line_number INTEGER,
    byte_offset INTEGER,
    
    -- Pattern classification
    pattern_type TEXT,  -- peer_to_peer, broadcast, orchestration
    requires_response BOOLEAN DEFAULT 0,
    has_response BOOLEAN DEFAULT 0,
    
    -- Security context
    permission_level TEXT DEFAULT 'normal',  -- emergency, high, normal, low
    tamper_hash TEXT  -- Integrity verification
);

-- Indexes for common monitoring queries
CREATE INDEX idx_timeline ON event_index(timestamp);
CREATE INDEX idx_agent_activity ON event_index(agent_id, timestamp);
CREATE INDEX idx_session_flow ON event_index(session_id, timestamp);
CREATE INDEX idx_correlation_chain ON event_index(correlation_id);
CREATE INDEX idx_pending_responses ON event_index(requires_response, has_response) 
    WHERE requires_response = 1 AND has_response = 0;
```

#### Correlation Chain Reconstruction
```python
class CorrelationTracker:
    """Tracks and reconstructs complex event chains."""
    
    async def build_correlation_chain(self, correlation_id: str):
        """Build complete chain from root correlation ID."""
        chain_events = await db.execute("""
            WITH RECURSIVE correlation_chain AS (
                -- Start with root correlation
                SELECT * FROM event_index 
                WHERE correlation_id = ?
                
                UNION ALL
                
                -- Find child events  
                SELECT e.* FROM event_index e
                JOIN correlation_chain c ON e.parent_correlation = c.correlation_id
            )
            SELECT * FROM correlation_chain ORDER BY timestamp
        """, (correlation_id,))
        
        return [self._reconstruct_event(row) for row in chain_events]
    
    async def find_orphaned_requests(self, max_age_minutes: int = 5):
        """Find completion requests without responses."""
        return await db.execute("""
            SELECT * FROM event_index 
            WHERE event_name LIKE 'completion:%request'
            AND requires_response = 1 
            AND has_response = 0
            AND timestamp > ?
        """, (time.time() - max_age_minutes * 60,))
```

### Layer 4: Safety & Security Features

#### Tamper-evident Event Log
```python
class TamperEvidentLog:
    """Event log with cryptographic integrity verification."""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
        self.previous_hash = b"genesis"
        
    def log_with_integrity(self, entry: EventLogEntry):
        """Log event with tamper-evident hash chain."""
        # Create integrity hash
        content = json.dumps(entry.to_dict(), sort_keys=True).encode()
        integrity_hash = hashlib.sha256(
            self.previous_hash + content + self.secret_key
        ).hexdigest()
        
        # Add hash to entry
        entry.tamper_hash = integrity_hash
        self.previous_hash = integrity_hash.encode()
        
        # Log normally
        self.log_event(entry)
        
    async def verify_integrity(self, start_time: float = None):
        """Verify event log integrity against tampering."""
        events = self.get_events(since=start_time)
        current_hash = b"genesis"
        
        for event in events:
            expected_hash = hashlib.sha256(
                current_hash + 
                json.dumps({k:v for k,v in event.items() if k != 'tamper_hash'}, 
                          sort_keys=True).encode() + 
                self.secret_key
            ).hexdigest()
            
            if event.get('tamper_hash') != expected_hash:
                return {
                    "integrity": "COMPROMISED",
                    "tampered_event": event,
                    "expected_hash": expected_hash
                }
                
            current_hash = expected_hash.encode()
            
        return {"integrity": "VERIFIED", "events_verified": len(events)}
```

#### Agent Permission Boundaries
```python
class AgentEventAccess:
    """Controls agent access to event log data."""
    
    permission_levels = {
        "system": ["*"],  # Full access
        "orchestrator": ["completion:*", "agent:*", "state:*"],
        "agent": ["completion:result", "agent:message", "state:get"],
        "observer": ["completion:result", "monitor:stats"]
    }
    
    def check_access(self, agent_id: str, event_patterns: List[str]):
        """Verify agent can access requested event patterns."""
        agent_perms = self.get_agent_permissions(agent_id)
        
        for pattern in event_patterns:
            if not any(fnmatch.fnmatch(pattern, allowed) 
                      for allowed in agent_perms):
                raise PermissionError(
                    f"Agent {agent_id} denied access to {pattern}"
                )
                
    async def filtered_event_query(self, agent_id: str, query_params: Dict):
        """Query events with agent permission filtering."""
        # Validate permissions
        self.check_access(agent_id, query_params.get("event_patterns", ["*"]))
        
        # Add agent-specific filters
        if agent_id != "system":
            # Agents can only see their own sessions unless orchestrator
            agent_role = self.get_agent_role(agent_id)
            if agent_role != "orchestrator":
                query_params["agent_filter"] = agent_id
                
        return await self.event_log.get_events(**query_params)
```

### Layer 5: Monitoring Interfaces

#### Enhanced TUI Monitoring (Building on Existing)
```python
# Enhanced monitor_textual.py features
class EnhancedMonitorTUI:
    """Advanced monitoring interface with real-time capabilities."""
    
    def __init__(self):
        self.event_streamer = EventStreamer()
        self.correlation_tracker = CorrelationTracker()
        
    async def live_event_feed(self):
        """Real-time event feed with filtering."""
        async for event in self.event_streamer.stream_events("monitor_tui"):
            # Display event with correlation highlighting
            self.display_event_with_context(event)
            
    def display_event_with_context(self, event):
        """Display event with correlation chain context."""
        # Show event
        self.console.print(self.format_event(event))
        
        # Show correlation context if available
        if event.get("correlation_id"):
            chain_summary = self.correlation_tracker.get_chain_summary(
                event["correlation_id"]
            )
            if len(chain_summary) > 1:
                self.console.print(f"  ↳ Part of {len(chain_summary)}-event chain")
```

#### Forensic Analysis Tools
```python
class ForensicAnalyzer:
    """Tools for post-incident analysis and investigation."""
    
    async def analyze_agent_cascade_failure(self, start_time: float):
        """Analyze agent cascade failures like the June 21-23 incident."""
        # Get all events in timeframe
        events = await self.get_events(since=start_time, limit=None)
        
        # Identify failure patterns
        analysis = {
            "timeline": self.build_failure_timeline(events),
            "agent_interactions": self.analyze_agent_communication(events),
            "resource_usage": self.analyze_resource_consumption(events),
            "cascade_triggers": self.identify_cascade_triggers(events),
            "recovery_points": self.find_recovery_opportunities(events)
        }
        
        return analysis
        
    def build_failure_timeline(self, events: List[Dict]):
        """Reconstruct precise failure timeline."""
        timeline = []
        for event in events:
            if event["event_name"] in ["agent:spawn", "agent:terminate", 
                                     "system:error", "completion:timeout"]:
                timeline.append({
                    "timestamp": event["timestamp"],
                    "event": event["event_name"],
                    "agent": event.get("agent_id"),
                    "details": event["data"]
                })
        return sorted(timeline, key=lambda x: x["timestamp"])
```

## Implementation Roadmap

### Phase 1: Critical Safety Infrastructure (Days 1-2) 🚨

**Priority 1: File Persistence**
- Extend `DaemonEventLog` with daily JSONL file persistence
- Implement log rotation and archival
- Test daemon restart data retention

**Priority 2: Tamper-evident Logging**
- Add hash chain integrity verification
- Implement log verification tools
- Create integrity monitoring alerts

### Phase 2: Real-time Monitoring (Days 2-3)

**Priority 3: Event Streaming**
- Implement `EventStreamer` for real-time event feeds
- Enhance TUI monitoring with live updates
- Add WebSocket support for browser monitoring

**Priority 4: Structured Indexes**
- Create SQLite indexes for complex queries
- Implement correlation chain reconstruction
- Add performance analytics queries

### Phase 3: Agent Permission System (Days 3-4) 🔒

**Priority 5: Access Control**
- Implement agent permission boundaries
- Create role-based event access controls
- Add permission verification to all monitoring APIs

**Priority 6: Security Boundaries**
- Agent filesystem access restrictions
- Resource limit enforcement
- Capability-based security model

### Phase 4: Advanced Analysis (Days 4-5)

**Priority 7: Forensic Tools**
- Implement cascade failure analysis
- Create performance bottleneck detection
- Add pattern recognition for agent behavior

**Priority 8: Integration & Testing**
- End-to-end security testing
- Performance benchmarking
- Agent isolation verification

## Success Criteria

### Security & Safety ✅
- [ ] 100% event persistence across daemon restarts
- [ ] Tamper-evident audit trails with verification
- [ ] Agent permission boundaries enforced
- [ ] Zero agent access to unauthorized events

### Operational Visibility ✅
- [ ] Real-time event streaming to monitoring interfaces
- [ ] Sub-second event query performance
- [ ] Complete correlation chain reconstruction
- [ ] Historical event analysis capabilities

### Forensic Analysis ✅
- [ ] Post-incident investigation tools
- [ ] Agent cascade failure detection
- [ ] Performance bottleneck identification
- [ ] Integrity verification for audit trails

## Integration with Current System

### Minimal Breaking Changes
- Extend existing `DaemonEventLog` class (no interface changes)
- Add new monitoring APIs alongside current ones
- Preserve existing `var/logs/responses/` structure
- Maintain compatibility with current TUI interfaces

### Configuration
```yaml
# Enhanced daemon configuration
event_logging:
  ring_buffer_size: 10000
  persistence:
    enabled: true
    directory: "var/logs/events"
    rotation: "daily"
    retention_days: 30
  integrity:
    enabled: true
    verification_interval: 3600  # hourly
  streaming:
    enabled: true
    max_subscribers: 10
    
agent_permissions:
  default_level: "agent"
  permission_inheritance: true
  audit_access: true
```

## Conclusion

This comprehensive event logging and monitoring system transforms KSI from an experimental platform into a production-ready, secure multi-agent system. By building on the existing event logging foundation while adding critical safety features, we enable:

1. **🛡️ Safe Agent Autonomy** - Complete audit trails prevent system compromise
2. **🔍 Operational Excellence** - Real-time visibility into complex multi-agent interactions  
3. **🔬 Forensic Capabilities** - Post-incident analysis to prevent future failures
4. **📊 Performance Optimization** - Data-driven system improvements

The implementation leverages existing infrastructure while addressing the critical gaps that currently prevent autonomous agent deployment. This is not just monitoring - it's the safety foundation that makes KSI's multi-agent vision possible.