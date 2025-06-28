#!/usr/bin/env python3

"""
Session and Shared State Manager - Manages session tracking and shared key-value state
Handles both conversation sessions and agent coordination state
"""

from typing import Dict, Any, Optional, List
import sqlite3
import json
import hashlib
import yaml
from pathlib import Path
from .manager_framework import BaseManager, with_error_handling, log_operation
from ksi_common import TimestampManager
from .config import config

class SessionAndSharedStateManager(BaseManager):
    """Manages session tracking and shared state for agent coordination"""
    
    def __init__(self):
        super().__init__(
            manager_name="state",
            required_dirs=[]  # No file directories needed for SQLite
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.sessions = {}  # session_id -> last_output
        self.db_path = str(config.db_path)
        
        # Initialize SQLite database
        self._init_sqlite()
        
        # Initialize composition index
        self._init_composition_index()
    
    def _init_sqlite(self):
        """Initialize SQLite database for agent shared state"""
        # Ensure var/db directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Check if database exists and create if not
        if not Path(self.db_path).exists():
            self.logger.info(f"Creating new agent shared state database: {self.db_path}")
        else:
            self.logger.info(f"Using existing agent shared state database: {self.db_path}")
        
        # Always ensure schema is up to date
        # This will create missing tables without affecting existing ones
        self._create_schema()
    
    def _create_schema(self):
        """Create schema inline if schema file not available"""
        with sqlite3.connect(self.db_path) as conn:
            # Existing agent shared state schema
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_shared_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    namespace TEXT,
                    owner_agent_id TEXT NOT NULL,
                    scope TEXT DEFAULT 'shared',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    metadata TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_namespace ON agent_shared_state(namespace)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_owner ON agent_shared_state(owner_agent_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_expires ON agent_shared_state(expires_at)')
            
            # Composition index schema extension
            conn.execute('''
                CREATE TABLE IF NOT EXISTS composition_repositories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    last_sync_at TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS composition_index (
                    full_name TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT,
                    version TEXT,
                    description TEXT,
                    author TEXT,
                    extends TEXT,
                    tags TEXT,
                    capabilities TEXT,
                    dependencies TEXT,
                    loading_strategy TEXT,
                    mutable BOOLEAN DEFAULT FALSE,
                    ephemeral BOOLEAN DEFAULT FALSE,
                    indexed_at TEXT NOT NULL,
                    FOREIGN KEY (repository_id) REFERENCES composition_repositories(id)
                )
            ''')
            
            # Composition index optimizations
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_type ON composition_index(type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_repo ON composition_index(repository_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_name ON composition_index(name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_extends ON composition_index(extends)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_strategy ON composition_index(loading_strategy)')
    
    def _extract_namespace(self, key: str) -> Optional[str]:
        """Extract namespace from key using agent_id.purpose.detail convention"""
        parts = key.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[:2])  # agent_id.purpose
        return None
    
    @log_operation()
    def track_session(self, session_id: str, output: Dict[str, Any]):
        """Track a session output (legacy name for create/update)"""
        self.sessions[session_id] = output
    
    def create_session(self, session_id: str, output: Dict[str, Any]) -> str:
        """Create/update session (standardized API)"""
        self.sessions[session_id] = output
        return session_id
    
    def update_session(self, session_id: str, output: Dict[str, Any]) -> bool:
        """Update session (standardized API)"""
        if session_id in self.sessions:
            self.sessions[session_id] = output
            return True
        return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions (standardized API)"""
        from typing import List
        return [
            {'session_id': sid, 'has_output': bool(output)}
            for sid, output in self.sessions.items()
        ]
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session (standardized API)"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    @log_operation()
    def clear_sessions(self) -> int:
        """Clear all session tracking"""
        count = len(self.sessions)
        self.sessions.clear()
        return count
    
    @log_operation()
    @with_error_handling("set_shared_state")
    def set_shared_state(self, key: str, value: Any, owner_agent_id: str = "system", 
                        scope: str = "shared", expires_at: Optional[str] = None, 
                        metadata: Optional[Dict[str, Any]] = None):
        """Set shared state value with SQLite persistence"""
        return self.create_shared_state(key, value, owner_agent_id, scope, expires_at, metadata)
    
    def create_shared_state(self, key: str, value: Any, owner_agent_id: str = "system",
                          scope: str = "shared", expires_at: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create/update shared state using SQLite (standardized API)"""
        # Convert value to JSON string
        value_json = json.dumps(value) if not isinstance(value, str) else value
        
        # Extract namespace from key
        namespace = self._extract_namespace(key)
        
        # Prepare metadata
        metadata_json = json.dumps(metadata) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO agent_shared_state 
                (key, value, namespace, owner_agent_id, scope, created_at, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                key, value_json, namespace, owner_agent_id, scope,
                TimestampManager.timestamp_utc(), expires_at, metadata_json
            ))
        
        self.logger.info(f"Set shared state: {key} (owner: {owner_agent_id}, scope: {scope})")
        return key
    
    def update_shared_state(self, key: str, value: Any, owner_agent_id: str = "system") -> bool:
        """Update shared state if it exists (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT key FROM agent_shared_state WHERE key = ?', (key,))
            if cursor.fetchone():
                return bool(self.create_shared_state(key, value, owner_agent_id))
        return False
    
    @with_error_handling("get_shared_state")
    def get_shared_state(self, key: str) -> Optional[Any]:
        """Get shared state value from SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT value FROM agent_shared_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                try:
                    # Try to parse as JSON, fallback to string
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
        return None
    
    def list_shared_state(self) -> List[Dict[str, Any]]:
        """List all shared state keys from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT key, namespace, owner_agent_id, scope, created_at, expires_at 
                FROM agent_shared_state ORDER BY created_at DESC
            ''')
            return [
                {
                    'key': row[0],
                    'namespace': row[1],
                    'owner_agent_id': row[2],
                    'scope': row[3],
                    'created_at': row[4],
                    'expires_at': row[5]
                }
                for row in cursor.fetchall()
            ]
    
    def remove_shared_state(self, key: str) -> bool:
        """Remove shared state key from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM agent_shared_state WHERE key = ?', (key,))
            return cursor.rowcount > 0
    
    def clear_shared_state(self) -> int:
        """Clear all shared state from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM agent_shared_state')
            count = cursor.fetchone()[0]
            conn.execute('DELETE FROM agent_shared_state')
            return count
    
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize state for hot reload (sessions only - shared state in SQLite)"""
        return {
            'sessions': self.sessions,
            'db_path': self.db_path
        }
    
    def deserialize_state(self, state: Dict[str, Any]):
        """Deserialize state from hot reload (sessions only - shared state in SQLite)"""
        self.sessions = state.get('sessions', {})
        self.db_path = state.get('db_path', 'agent_shared_state.db')
        self.logger.info(f"Loaded state: {len(self.sessions)} sessions, SQLite DB: {self.db_path}")
        
        # Verify SQLite database is accessible
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM agent_shared_state')
                count = cursor.fetchone()[0]
                self.logger.info(f"SQLite shared state contains {count} entries")
        except Exception as e:
            self.logger.warning(f"Could not access SQLite database {self.db_path}: {e}")
    
    # ========================================
    # Composition Index Methods
    # ========================================
    
    def _init_composition_index(self):
        """Initialize local repository and index if needed"""
        with sqlite3.connect(self.db_path) as conn:
            # Ensure local repository exists
            conn.execute('''
                INSERT OR IGNORE INTO composition_repositories 
                (id, type, path, status, created_at) 
                VALUES ('local', 'local', 'var/lib/compositions', 'active', ?)
            ''', (TimestampManager.format_for_logging(),))
    
    @log_operation()
    def index_composition_file(self, file_path: Path) -> bool:
        """Index a single composition file"""
        try:
            if not file_path.exists() or file_path.suffix != '.yaml':
                return False
                
            # Calculate file hash for change detection
            content = file_path.read_text()
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Parse YAML metadata
            try:
                comp_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                self.logger.warning(f"Invalid YAML in {file_path}: {e}")
                return False
            
            if not isinstance(comp_data, dict):
                return False
                
            # Extract metadata
            name = comp_data.get('name', file_path.stem)
            comp_type = comp_data.get('type', 'unknown')
            full_name = f"local:{name}"
            
            # Extract loading strategy from metadata
            metadata = comp_data.get('metadata', {})
            loading_strategy = metadata.get('loading_strategy', 'single')
            
            # Index entry
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO composition_index
                    (full_name, name, type, repository_id, file_path, file_hash, 
                     version, description, author, extends, tags, capabilities, 
                     dependencies, loading_strategy, mutable, ephemeral, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    full_name, name, comp_type, 'local', str(file_path), file_hash,
                    comp_data.get('version', ''),
                    comp_data.get('description', ''),
                    comp_data.get('author', ''),
                    comp_data.get('extends', ''),
                    json.dumps(comp_data.get('tags', [])),
                    json.dumps(metadata.get('capabilities', [])),
                    json.dumps(comp_data.get('dependencies', [])),
                    loading_strategy,
                    metadata.get('mutable', False),
                    metadata.get('ephemeral', False),
                    TimestampManager.format_for_logging()
                ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to index {file_path}: {e}")
            return False
    
    @log_operation()
    def rebuild_composition_index(self, repository_id: str = 'local') -> int:
        """Rebuild composition index for a repository"""
        if repository_id != 'local':
            # Future: support other repositories
            return 0
            
        # Clear existing index for this repository
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM composition_index WHERE repository_id = ?', (repository_id,))
        
        # Scan composition directory
        compositions_dir = Path('var/lib/compositions')
        if not compositions_dir.exists():
            self.logger.warning(f"Compositions directory does not exist: {compositions_dir}")
            return 0
        
        indexed_count = 0
        for yaml_file in compositions_dir.rglob('*.yaml'):
            if self.index_composition_file(yaml_file):
                indexed_count += 1
                
        self.logger.info(f"Indexed {indexed_count} compositions")
        return indexed_count
    
    @log_operation()
    def discover_compositions(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Universal composition discovery - query index only"""
        # Build SQL query from parameters
        conditions = []
        params = []
        
        if 'type' in query:
            conditions.append('type = ?')
            params.append(query['type'])
            
        if 'name' in query:
            conditions.append('name LIKE ?')
            params.append(f"%{query['name']}%")
            
        if 'capabilities' in query:
            # JSON search for capabilities
            for cap in query['capabilities']:
                conditions.append('capabilities LIKE ?')
                params.append(f'%"{cap}"%')
                
        if 'tags' in query:
            # JSON search for tags
            for tag in query['tags']:
                conditions.append('tags LIKE ?')
                params.append(f'%"{tag}"%')
                
        if 'loading_strategy' in query:
            conditions.append('loading_strategy = ?')
            params.append(query['loading_strategy'])
        
        # Build final query
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        sql = f"""
            SELECT full_name, name, type, description, version, author, 
                   tags, capabilities, loading_strategy, file_path
            FROM composition_index 
            WHERE {where_clause}
            ORDER BY name
        """
        
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    results.append({
                        'full_name': row[0],
                        'name': row[1], 
                        'type': row[2],
                        'description': row[3],
                        'version': row[4],
                        'author': row[5],
                        'tags': json.loads(row[6] or '[]'),
                        'capabilities': json.loads(row[7] or '[]'),
                        'loading_strategy': row[8],
                        'file_path': row[9]
                    })
        except Exception as e:
            self.logger.error(f"Composition discovery failed: {e}")
            
        return results
    
    @log_operation()
    def get_composition_path(self, full_name: str) -> Optional[Path]:
        """Get file path for a composition"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT file_path FROM composition_index WHERE full_name = ?', 
                    (full_name,)
                )
                row = cursor.fetchone()
                return Path(row[0]) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get path for {full_name}: {e}")
            return None
    
    @log_operation()
    def get_composition_metadata(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Get composition metadata from index"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT name, type, description, version, author, extends,
                           tags, capabilities, dependencies, loading_strategy
                    FROM composition_index WHERE full_name = ?
                ''', (full_name,))
                row = cursor.fetchone()
                if row:
                    return {
                        'name': row[0],
                        'type': row[1], 
                        'description': row[2],
                        'version': row[3],
                        'author': row[4],
                        'extends': row[5],
                        'tags': json.loads(row[6] or '[]'),
                        'capabilities': json.loads(row[7] or '[]'), 
                        'dependencies': json.loads(row[8] or '[]'),
                        'loading_strategy': row[9]
                    }
        except Exception as e:
            self.logger.error(f"Failed to get metadata for {full_name}: {e}")
        return None