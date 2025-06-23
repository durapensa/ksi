-- Agent Shared State Database Schema
-- SQLite database for agent coordination and shared state
-- Convention: Use agent_id.purpose.detail format for keys (suggested, not enforced)

CREATE TABLE IF NOT EXISTS agent_shared_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,           -- JSON blob for the actual data
    namespace TEXT,                -- Auto-extracted from key (agent_id.purpose.detail → agent_id.purpose)
    owner_agent_id TEXT NOT NULL,  -- Which agent created this entry  
    scope TEXT DEFAULT 'shared',   -- "private", "shared", "coordination"
    created_at TEXT NOT NULL,      -- ISO timestamp when created
    expires_at TEXT,               -- ISO timestamp when expires (NULL = never)
    metadata TEXT                  -- JSON blob for tags, purpose, description, etc.
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_namespace ON agent_shared_state(namespace);
CREATE INDEX IF NOT EXISTS idx_owner ON agent_shared_state(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_expires ON agent_shared_state(expires_at);
CREATE INDEX IF NOT EXISTS idx_scope ON agent_shared_state(scope);
CREATE INDEX IF NOT EXISTS idx_created_at ON agent_shared_state(created_at);

-- Common queries agents can use via sqlite3 CLI:
-- 
-- Suggested key convention: agent_id.purpose.detail (e.g., "agent_001.status.current", "task_coord.assignments.active")
--
-- List all namespaces:
-- sqlite3 agent_shared_state.db "SELECT DISTINCT namespace FROM agent_shared_state WHERE namespace IS NOT NULL;"
--
-- Find my data:
-- sqlite3 agent_shared_state.db "SELECT key, value, created_at FROM agent_shared_state WHERE owner_agent_id = 'agent_001';"
--
-- Find data in namespace:
-- sqlite3 agent_shared_state.db "SELECT key, value, owner_agent_id FROM agent_shared_state WHERE namespace = 'task_coord';"
--
-- Cleanup expired entries:
-- sqlite3 agent_shared_state.db "DELETE FROM agent_shared_state WHERE expires_at IS NOT NULL AND expires_at < datetime('now');"
--
-- Find recent activity:
-- sqlite3 agent_shared_state.db "SELECT key, owner_agent_id, created_at FROM agent_shared_state WHERE created_at > datetime('now', '-1 hour');"
--
-- Search by scope:
-- sqlite3 agent_shared_state.db "SELECT key, value FROM agent_shared_state WHERE scope = 'coordination';"
--
-- Find keys matching pattern:
-- sqlite3 agent_shared_state.db "SELECT key, value FROM agent_shared_state WHERE key LIKE 'agent_001.status.%';"