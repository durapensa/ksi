#!/usr/bin/env python3
"""
Composition Index - Database indexing and discovery for compositions
"""

import json
import aiosqlite
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import format_for_logging
from ksi_common.config import config
from ksi_common.component_loader import load_component_file, get_file_stats

logger = get_bound_logger("composition_index")

# Module state
_db_path: Optional[Path] = None
_initialized = False


@asynccontextmanager
async def _get_db():
    """Get database connection with proper cleanup."""
    if not _initialized:
        raise RuntimeError("Composition index not initialized")
    
    conn = await aiosqlite.connect(str(_db_path))
    try:
        yield conn
    finally:
        await conn.close()


async def initialize(db_path: Optional[Path] = None):
    """Initialize composition index database."""
    global _db_path, _initialized
    
    if db_path is None:
        db_path = config.db_path
    
    _db_path = db_path
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize schema
    conn = await aiosqlite.connect(str(_db_path))
    try:
        # Enable WAL mode for better concurrency
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        
        # Composition repositories table
        await conn.execute('''
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
        
        # Composition index table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS composition_index (
                name TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                repository_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT,
                file_size INTEGER,
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
                metadata JSON,  -- Complete metadata for filtering
                indexed_at TEXT NOT NULL,
                last_modified TEXT,
                FOREIGN KEY (repository_id) REFERENCES composition_repositories(id)
            )
        ''')
        
        # Add new columns if they don't exist (migration)
        try:
            await conn.execute('ALTER TABLE composition_index ADD COLUMN file_size INTEGER')
        except:
            pass  # Column already exists
        
        try:
            await conn.execute('ALTER TABLE composition_index ADD COLUMN metadata JSON')
        except:
            pass  # Column already exists
            
        try:
            await conn.execute('ALTER TABLE composition_index ADD COLUMN last_modified TEXT')
        except:
            pass  # Column already exists
        
        # Indexes for efficient queries
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_type ON composition_index(type)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_repo ON composition_index(repository_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_name ON composition_index(name)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_author ON composition_index(author)')
        
        # Ensure local repository exists
        await conn.execute('''
            INSERT OR IGNORE INTO composition_repositories 
            (id, type, path, status, created_at) 
            VALUES ('local', 'local', ?, 'active', ?)
        ''', (str(config.compositions_dir), format_for_logging()))
        
        await conn.commit()
    finally:
        await conn.close()
    
    _initialized = True
    logger.info(f"Composition index initialized at {_db_path}")


async def index_file(file_path: Path) -> bool:
    """Index a single composition file."""
    try:
        if not file_path.exists() or file_path.suffix not in ['.yaml', '.yml', '.md']:
            return False
            
        # Pattern-aware exclusions - skip non-composition files
        path_str = str(file_path)
        exclude_patterns = [
            '_archive/tests/',  # Test fixtures with intentional errors
            'README',           # Documentation files
            '.git',             # Git files
        ]
        
        # Check exclusion patterns
        for pattern in exclude_patterns:
            if pattern in path_str:
                logger.debug(f"Skipping excluded file: {file_path}")
                return False
                
        # Also skip hidden files (starting with dot)
        if file_path.name.startswith('.'):
            logger.debug(f"Skipping hidden file: {file_path}")
            return False
            
        # Get file stats first (includes hash)
        try:
            file_stats = get_file_stats(file_path)
            file_hash = file_stats['hash']
            file_size = file_stats['size']
            last_modified = file_stats['modified']
        except Exception as e:
            logger.warning(f"Failed to get file stats for {file_path}: {e}")
            return False
        
        # Parse metadata using shared component loader
        try:
            comp_data, _ = load_component_file(file_path)
        except Exception as e:
            # Use DEBUG for test files, WARNING for others
            if '_archive/tests/' in str(file_path):
                logger.debug(f"Expected parse error in test file {file_path}: {e}")
            else:
                logger.warning(f"Failed to parse file {file_path}: {e}")
            return False
        
        if not isinstance(comp_data, dict):
            logger.debug(f"File does not contain valid metadata: {file_path}")
            return False
            
        # Validate required fields based on unified architecture
        if 'name' not in comp_data or 'type' not in comp_data:
            logger.debug(f"Missing required fields (name/type) in {file_path}")
            return False
            
        # Calculate relative path from compositions directory
        relative_path = file_path.relative_to(config.compositions_dir)
        
        # Extract metadata - we already validated name and type exist
        simple_name = comp_data['name']
        comp_type = comp_data['type']
        
        # Use the relative path (without extension) as the unique identifier
        # This is consistent across all composition types
        unique_name = str(relative_path.with_suffix(''))
        
        # Extract loading strategy from metadata
        metadata = comp_data.get('metadata', {})
        loading_strategy = metadata.get('loading_strategy', 'single')
        
        # Store complete metadata as JSON for efficient filtering
        metadata_json = json.dumps(comp_data, default=str)  # default=str handles dates
        
        # Index entry with full metadata
        async with _get_db() as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO composition_index
                (name, type, repository_id, file_path, file_hash, file_size,
                 version, description, author, extends, tags, capabilities, 
                 dependencies, loading_strategy, mutable, ephemeral, metadata, 
                 indexed_at, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                unique_name, comp_type, 'local', str(relative_path), file_hash, file_size,
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
                metadata_json,
                format_for_logging(),
                last_modified
            ))
            await conn.commit()
        
        logger.debug(f"Indexed composition {unique_name} from {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to index {file_path}: {e}")
        return False


async def rebuild(repository_id: str = 'local') -> int:
    """Rebuild composition index for a repository."""
    if repository_id != 'local':
        return 0
        
    # Clear existing index
    async with _get_db() as conn:
        await conn.execute('DELETE FROM composition_index WHERE repository_id = ?', (repository_id,))
        await conn.commit()
    
    # Scan composition directory
    if not config.compositions_dir.exists():
        logger.warning(f"Compositions directory does not exist: {config.compositions_dir}")
        return 0
    
    indexed_count = 0
    # Scan for both YAML and Markdown files
    for pattern in ['*.yaml', '*.yml', '*.md']:
        for comp_file in config.compositions_dir.rglob(pattern):
            if await index_file(comp_file):
                indexed_count += 1
            
    logger.info(f"Indexed {indexed_count} compositions")
    return indexed_count


async def discover(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Query composition index with SQL-based filtering."""
    conditions = []
    params = []
    
    if 'type' in query:
        conditions.append('type = ?')
        params.append(query['type'])
        
    if 'name' in query:
        conditions.append('name LIKE ?')
        params.append(f"%{query['name']}%")
        
    if 'capabilities' in query:
        for cap in query['capabilities']:
            conditions.append('capabilities LIKE ?')
            params.append(f'%"{cap}"%')
            
    if 'tags' in query:
        for tag in query['tags']:
            conditions.append('tags LIKE ?')
            params.append(f'%"{tag}"%')
            
    if 'loading_strategy' in query:
        conditions.append('loading_strategy = ?')
        params.append(query['loading_strategy'])
    
    # Metadata filtering using JSON functions
    if 'metadata_filter' in query:
        for key, value in query['metadata_filter'].items():
            if isinstance(value, list):
                # For array values, check if any match
                sub_conditions = []
                for v in value:
                    sub_conditions.append(f"json_extract(metadata, '$.{key}') LIKE ?")
                    params.append(f'%{v}%')
                conditions.append(f"({' OR '.join(sub_conditions)})")
            else:
                # For scalar values, exact match
                conditions.append(f"json_extract(metadata, '$.{key}') = ?")
                params.append(value)
    
    where_clause = ' AND '.join(conditions) if conditions else '1=1'
    
    # Add LIMIT clause if specified
    limit_clause = ""
    if 'limit' in query and isinstance(query['limit'], int) and query['limit'] > 0:
        limit_clause = f" LIMIT {query['limit']}"
    
    sql = f"""
        SELECT name, type, description, version, author, 
               tags, capabilities, loading_strategy, file_path, metadata
        FROM composition_index 
        WHERE {where_clause}
        ORDER BY name{limit_clause}
    """
    
    # Debug logging
    logger.debug(f"SQL query: {sql}")
    logger.debug(f"SQL params: {params}")
    
    results = []
    try:
        async with _get_db() as conn:
            async with conn.execute(sql, params) as cursor:
                async for row in cursor:
                    result = {
                        'name': row[0],
                        'type': row[1],
                        'description': row[2],
                        'version': row[3],
                        'author': row[4],
                        'tags': json.loads(row[5] or '[]'),
                        'capabilities': json.loads(row[6] or '[]'),
                        'loading_strategy': row[7],
                        'file_path': row[8]
                    }
                    
                    # Include full metadata if requested
                    if query.get('include_metadata', False) and row[9]:
                        result['metadata'] = json.loads(row[9])
                    
                    results.append(result)
    except Exception as e:
        logger.error(f"Composition discovery failed: {e}")
        
    return results


async def get_count(query: Dict[str, Any] = None) -> int:
    """Get count of compositions matching query."""
    if query is None:
        query = {}
    
    conditions = []
    params = []
    
    if 'type' in query:
        conditions.append('type = ?')
        params.append(query['type'])
    
    where_clause = ' AND '.join(conditions) if conditions else '1=1'
    sql = f"SELECT COUNT(*) FROM composition_index WHERE {where_clause}"
    
    try:
        async with _get_db() as conn:
            async with conn.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        logger.error(f"Failed to get composition count: {e}")
        return 0


async def get_path(name: str) -> Optional[Path]:
    """Get file path for a composition."""
    try:
        async with _get_db() as conn:
            async with conn.execute(
                'SELECT file_path FROM composition_index WHERE name = ?', 
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Convert relative path back to absolute
                    relative_path = Path(row[0])
                    return config.compositions_dir / relative_path
                return None
    except Exception as e:
        logger.error(f"Failed to get path for {name}: {e}")
        return None


async def get_unique_component_types() -> List[str]:
    """Get all unique component types from the index."""
    try:
        async with _get_db() as conn:
            # Get distinct types from the index
            async with conn.execute("""
                SELECT DISTINCT type
                FROM composition_index 
                WHERE type IS NOT NULL
            """) as cursor:
                types = [row[0] for row in await cursor.fetchall() if row[0]]
                return types if types else ['component']
    except Exception as e:
        logger.error(f"Failed to get unique component types: {e}")
        return ['component']  # Fallback


async def filter_by_component_type(component_type: str) -> List[Dict[str, Any]]:
    """Filter components by their type."""
    try:
        async with _get_db() as conn:
            async with conn.execute("""
                SELECT * FROM composition_index
                WHERE type = ?
            """, (component_type,)) as cursor:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in await cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to filter by component type {component_type}: {e}")
        return []


def normalize_component_path(name: str, component_type: str = 'component') -> str:
    """Normalize component path based on type and naming convention."""
    # Map component types to default directories
    type_dirs = {
        'core': 'core',
        'persona': 'personas',
        'behavior': 'behaviors', 
        'orchestration': 'orchestrations',
        'evaluation': 'evaluations',
        'evaluation_suite': 'evaluations/suites',
        'tool': 'tools',
        'example': 'examples'
    }
    
    # If path already contains directory, use as-is
    if '/' in name:
        return name
        
    # Otherwise, organize by type
    if component_type in type_dirs:
        return f"{type_dirs[component_type]}/{name}"
    
    # Default to type-based directory
    return f"{component_type}/{name}"


# Removed update_component_type_in_index - no longer needed with unified 'type' field