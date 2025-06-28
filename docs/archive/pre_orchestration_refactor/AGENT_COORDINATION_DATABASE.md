# Agent Coordination Database Guide

## Overview

The KSI daemon provides a SQLite-based key-value store for agent coordination and shared state management. This system uses a **hybrid approach**:

1. **Simple daemon commands** for basic operations (SET_SHARED, GET_SHARED)
2. **Direct sqlite3 CLI access** for complex queries and data discovery

## Database Location

The database is located at `var/db/agent_shared_state.db` (configurable via `KSI_DB_PATH` environment variable).

## Schema

```sql
CREATE TABLE agent_shared_state (
    key TEXT PRIMARY KEY,              -- Unique key (suggest: agent_id.purpose.detail)
    value TEXT NOT NULL,               -- JSON data
    namespace TEXT,                    -- Auto-extracted from key 
    owner_agent_id TEXT NOT NULL,     -- Agent that created this entry
    scope TEXT DEFAULT 'shared',      -- "private", "shared", "coordination"
    created_at TEXT NOT NULL,         -- ISO timestamp
    expires_at TEXT,                  -- Optional expiration (ISO timestamp)
    metadata TEXT                     -- Optional JSON metadata
);
```

## Key Naming Convention

**Recommended format**: `agent_id.purpose.detail`

Examples:
- `agent_001.status.current` → Status information for agent_001
- `task_coord.assignments.active` → Active task assignments
- `chat_session.participants.list` → List of chat participants
- `workflow.stage_3.results` → Results from workflow stage 3

The namespace is auto-extracted from the first two parts: `agent_001.status`, `task_coord.assignments`, etc.

## Usage Methods

### Method 1: Daemon Commands (Simple)

Use daemon commands for basic set/get operations:

```bash
# Set a value
echo '{"command": "SET_SHARED", "parameters": {"key": "agent_001.status.current", "value": "working", "owner_agent_id": "agent_001"}}' | nc -U var/run/ksi_daemon.sock

# Get a value  
echo '{"command": "GET_SHARED", "parameters": {"key": "agent_001.status.current"}}' | nc -U var/run/ksi_daemon.sock
```

### Method 2: sqlite3 CLI (Advanced)

Use direct SQLite access for complex queries and discovery:

```bash
# Connect to database
sqlite3 var/db/agent_shared_state.db

# Or run single commands
sqlite3 var/db/agent_shared_state.db "SELECT key, value FROM agent_shared_state WHERE namespace = 'task_coord';"
```

## Common Query Patterns

### Discovery Queries

```sql
-- List all active namespaces
SELECT DISTINCT namespace FROM agent_shared_state WHERE namespace IS NOT NULL;

-- Find all agents currently active
SELECT DISTINCT owner_agent_id FROM agent_shared_state;

-- See what data types exist
SELECT 
    namespace,
    COUNT(*) as entry_count,
    MAX(created_at) as latest_update
FROM agent_shared_state 
GROUP BY namespace 
ORDER BY latest_update DESC;
```

### Data Retrieval

```sql
-- Get all my data
SELECT key, value, created_at 
FROM agent_shared_state 
WHERE owner_agent_id = 'agent_001';

-- Find coordination data
SELECT key, value, owner_agent_id 
FROM agent_shared_state 
WHERE scope = 'coordination';

-- Get recent activity (last hour)
SELECT key, owner_agent_id, created_at 
FROM agent_shared_state 
WHERE created_at > datetime('now', '-1 hour');

-- Search by pattern
SELECT key, value 
FROM agent_shared_state 
WHERE key LIKE 'agent_001.status.%';
```

### Maintenance Queries

```sql
-- Clean up expired entries
DELETE FROM agent_shared_state 
WHERE expires_at IS NOT NULL AND expires_at < datetime('now');

-- Count entries by scope
SELECT scope, COUNT(*) as count 
FROM agent_shared_state 
GROUP BY scope;

-- Find oldest entries
SELECT key, owner_agent_id, created_at 
FROM agent_shared_state 
ORDER BY created_at ASC 
LIMIT 10;
```

## Scope Types

- **`private`**: Data intended only for the creating agent
- **`shared`**: Data available to all agents (default)
- **`coordination`**: Data specifically for multi-agent coordination

## Best Practices

### Key Design
- Use descriptive, hierarchical keys: `agent_id.purpose.detail`
- Keep keys readable: `chat.participants` not `c.p`
- Use consistent naming across your agent system

### Data Format
- Store structured data as JSON in the `value` field
- Use `metadata` field for search tags, descriptions, etc.
- Set appropriate `scope` for data visibility

### Expiration
- Set `expires_at` for temporary data (ISO format: `2025-06-23T20:30:00Z`)
- Use daemon cleanup or manual DELETE queries to remove expired data

### Performance
- Use the indexed fields for WHERE clauses: `namespace`, `owner_agent_id`, `scope`, `created_at`
- Avoid full table scans on large datasets

## Example Agent Patterns

### Status Broadcasting
```sql
-- Agent broadcasts its status
INSERT OR REPLACE INTO agent_shared_state 
(key, value, namespace, owner_agent_id, scope, created_at)
VALUES 
('agent_001.status.current', 
 '{"state": "working", "task": "analysis", "progress": 0.6}',
 'agent_001.status',
 'agent_001', 
 'shared',
 datetime('now'));
```

### Task Coordination
```sql
-- Coordinator assigns tasks
INSERT OR REPLACE INTO agent_shared_state 
(key, value, namespace, owner_agent_id, scope, created_at, expires_at)
VALUES 
('task_coord.assignments.task_123',
 '{"assignee": "agent_002", "deadline": "2025-06-23T22:00:00Z", "priority": "high"}',
 'task_coord.assignments',
 'coordinator',
 'coordination',
 datetime('now'),
 '2025-06-23T22:00:00Z');

-- Agent checks for assignments
SELECT key, value 
FROM agent_shared_state 
WHERE namespace = 'task_coord.assignments' 
  AND json_extract(value, '$.assignee') = 'agent_002';
```

### Resource Sharing
```sql
-- Agent shares analysis results
INSERT INTO agent_shared_state 
(key, value, namespace, owner_agent_id, scope, created_at, metadata)
VALUES 
('research.results.dataset_alpha',
 '{"findings": [...], "confidence": 0.85, "method": "statistical"}',
 'research.results',
 'research_agent',
 'shared',
 datetime('now'),
 '{"tags": ["analysis", "dataset_alpha"], "type": "research_findings"}');

-- Other agents discover results
SELECT key, value, owner_agent_id
FROM agent_shared_state 
WHERE namespace = 'research.results'
  AND json_extract(metadata, '$.tags') LIKE '%analysis%';
```

## Environment Configuration

Override database location:
```bash
export KSI_DB_PATH=/custom/path/coordination.db
```

The configuration system automatically ensures the database directory exists and initializes the schema.

## Integration with Daemon Commands

While sqlite3 CLI provides full flexibility, the daemon also exposes these commands:

- `SET_SHARED` - Create/update entries
- `GET_SHARED` - Retrieve specific entries  
- `CLEANUP` - Remove expired entries

These provide a simpler interface for basic operations while sqlite3 handles complex queries and discovery.

## Complete JSON Command Examples

### Setting Agent Status
```bash
# Using netcat to send JSON command
echo '{
  "command": "SET_SHARED",
  "version": "2.0", 
  "parameters": {
    "key": "agent_001.status.current",
    "value": {"state": "working", "task": "analysis", "progress": 0.75},
    "owner_agent_id": "agent_001",
    "scope": "shared",
    "metadata": {"tags": ["status", "agent_001"], "type": "status_update"}
  }
}' | nc -U var/run/ksi_daemon.sock
```

### Getting Shared Data
```bash
echo '{
  "command": "GET_SHARED",
  "version": "2.0",
  "parameters": {
    "key": "agent_001.status.current"  
  }
}' | nc -U var/run/ksi_daemon.sock
```

### Advanced Discovery with sqlite3
```bash
# Find all coordination data with metadata
sqlite3 var/db/agent_shared_state.db "
SELECT 
  key,
  value,
  owner_agent_id,
  created_at,
  metadata
FROM agent_shared_state 
WHERE scope = 'coordination' 
  AND created_at > datetime('now', '-24 hours')
ORDER BY created_at DESC;
"

# Count entries by namespace
sqlite3 var/db/agent_shared_state.db "
SELECT 
  namespace,
  COUNT(*) as entries,
  MAX(created_at) as latest_activity
FROM agent_shared_state 
WHERE namespace IS NOT NULL
GROUP BY namespace 
ORDER BY latest_activity DESC;
"
```

This hybrid approach gives agents both simple operations through daemon commands and full SQL power for complex coordination patterns.