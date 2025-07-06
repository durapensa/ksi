#!/usr/bin/env python3
"""
Composition Index - Database indexing and discovery for compositions
"""

import json
import aiosqlite
import hashlib
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import format_for_logging
from ksi_common.config import config

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
        
        # Indexes for efficient queries
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_type ON composition_index(type)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_repo ON composition_index(repository_id)')
        
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
        if not file_path.exists() or file_path.suffix != '.yaml':
            return False
            
        # Calculate file hash
        content = file_path.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Parse YAML metadata
        try:
            comp_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in {file_path}: {e}")
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
        async with _get_db() as conn:
            await conn.execute('''
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
                format_for_logging()
            ))
            await conn.commit()
        
        logger.debug(f"Indexed composition {full_name} from {file_path}")
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
    for yaml_file in config.compositions_dir.rglob('*.yaml'):
        if await index_file(yaml_file):
            indexed_count += 1
            
    logger.info(f"Indexed {indexed_count} compositions")
    return indexed_count


async def discover(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Query composition index."""
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
        async with _get_db() as conn:
            async with conn.execute(sql, params) as cursor:
                async for row in cursor:
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
        logger.error(f"Composition discovery failed: {e}")
        
    return results


async def get_path(full_name: str) -> Optional[Path]:
    """Get file path for a composition."""
    try:
        async with _get_db() as conn:
            async with conn.execute(
                'SELECT file_path FROM composition_index WHERE full_name = ?', 
                (full_name,)
            ) as cursor:
                row = await cursor.fetchone()
                return Path(row[0]) if row else None
    except Exception as e:
        logger.error(f"Failed to get path for {full_name}: {e}")
        return None