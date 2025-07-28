#!/usr/bin/env python3
"""
Composition Index - Database indexing and discovery for compositions
"""

import json
import aiosqlite
import asyncio
import yaml
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
        db_path = config.composition_index_db_path
    
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
                component_type TEXT NOT NULL,
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
        
        # Evaluations table for unified index
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_hash TEXT NOT NULL,
                component_path TEXT NOT NULL,
                certificate_id TEXT NOT NULL,
                status TEXT,
                model TEXT,
                model_version_date TEXT,
                test_suite TEXT,
                tests_passed INTEGER,
                tests_total INTEGER,
                performance_class TEXT,
                evaluation_date TEXT,
                indexed_at TEXT NOT NULL,
                FOREIGN KEY (component_hash) REFERENCES composition_index(file_hash)
            )
        ''')
        
        # Indexes for efficient queries
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_type ON composition_index(component_type)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_repo ON composition_index(repository_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_name ON composition_index(name)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_comp_author ON composition_index(author)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_eval_hash ON evaluations(component_hash)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_eval_status ON evaluations(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_eval_model ON evaluations(model)')
        
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
        # Support both 'type' and 'component_type' fields
        if 'name' not in comp_data:
            logger.debug(f"Missing required field 'name' in {file_path}")
            return False
            
        if 'type' not in comp_data and 'component_type' not in comp_data:
            logger.debug(f"Missing required field 'type' or 'component_type' in {file_path}")
            return False
            
        # Calculate relative path from compositions directory
        relative_path = file_path.relative_to(config.compositions_dir)
        
        # Extract metadata - only support 'component_type' field
        simple_name = comp_data['name']
        comp_type = comp_data.get('component_type')
        
        if not comp_type:
            logger.warning(f"Missing component_type in {file_path}")
            return None
        
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
                (name, component_type, repository_id, file_path, file_hash, file_size,
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


async def remove_file(file_path: Path) -> bool:
    """Remove a composition file from the index."""
    try:
        # Get relative path for lookup
        if file_path.is_absolute():
            relative_path = file_path.relative_to(config.compositions_dir)
        else:
            relative_path = file_path
        
        # Delete from index
        async with _get_db() as conn:
            cursor = await conn.execute(
                'DELETE FROM composition_index WHERE file_path = ?',
                (str(relative_path),)
            )
            await conn.commit()
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.debug(f"Removed {deleted_count} entries for {file_path} from index")
                return True
            else:
                logger.debug(f"No index entries found for {file_path}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to remove {file_path} from index: {e}")
        return False


async def rebuild(repository_id: str = 'local') -> Dict[str, Any]:
    """Rebuild unified composition and evaluation index.
    
    Returns:
        Dict with indexed counts and skipped files
    """
    if repository_id != 'local':
        return {'compositions_indexed': 0, 'evaluations_indexed': 0, 'skipped_files': []}
        
    # Clear existing indexes
    async with _get_db() as conn:
        await conn.execute('DELETE FROM composition_index WHERE repository_id = ?', (repository_id,))
        await conn.execute('DELETE FROM evaluations')  # Clear all evaluations
        await conn.commit()
    
    # Scan composition directory
    if not config.compositions_dir.exists():
        logger.warning(f"Compositions directory does not exist: {config.compositions_dir}")
        return {'compositions_indexed': 0, 'evaluations_indexed': 0, 'skipped_files': []}
    
    indexed_count = 0
    skipped_files = []
    total_scanned = 0
    
    # Scan for both YAML and Markdown files
    for pattern in ['*.yaml', '*.yml', '*.md']:
        for comp_file in config.compositions_dir.rglob(pattern):
            total_scanned += 1
            result = await index_file(comp_file)
            if result is True:
                indexed_count += 1
            elif result is False:
                skipped_files.append({
                    'path': str(comp_file.relative_to(config.compositions_dir)),
                    'reason': 'Failed to parse or validate'
                })
    
    # Index evaluations from registry.yaml
    eval_result = await index_evaluations()
    eval_count = eval_result['indexed'] if isinstance(eval_result, dict) else eval_result
    
    # Check for stale registry entries (files in registry but not on disk)
    stale_entries = []
    if isinstance(eval_result, dict) and 'stale_entries' in eval_result:
        stale_entries = eval_result['stale_entries']
            
    logger.info(f"Indexed {indexed_count}/{total_scanned} compositions and {eval_count} evaluations")
    if skipped_files:
        logger.warning(f"Skipped {len(skipped_files)} files during indexing")
    if stale_entries:
        logger.warning(f"Found {len(stale_entries)} stale evaluation registry entries")
    
    return {
        'compositions_indexed': indexed_count,
        'evaluations_indexed': eval_count,
        'total_scanned': total_scanned,
        'skipped_files': skipped_files,
        'stale_registry_entries': stale_entries
    }


async def index_evaluations() -> Dict[str, Any]:
    """Index evaluations from registry.yaml and check for stale entries."""
    registry_path = Path("var/lib/evaluations/registry.yaml")
    if not registry_path.exists():
        logger.warning(f"Evaluation registry not found: {registry_path}")
        return {'indexed': 0, 'stale_entries': []}
    
    try:
        with open(registry_path, 'r') as f:
            registry = yaml.safe_load(f)
        
        components = registry.get('components', {})
        indexed_count = 0
        stale_entries = []
        
        async with _get_db() as conn:
            for component_hash, component_data in components.items():
                # Skip if component_hash is not a proper sha256
                if not component_hash.startswith('sha256:'):
                    continue
                    
                component_path = component_data.get('path', '')
                
                # Check if component file exists
                if component_path:
                    full_path = Path(component_path)
                    if not full_path.exists():
                        stale_entries.append({
                            'hash': component_hash,
                            'path': component_path,
                            'reason': 'Component file not found'
                        })
                        logger.debug(f"Stale registry entry: {component_path} not found")
                        # Still index the evaluations - they're historical records
                
                evaluations = component_data.get('evaluations', [])
                
                for eval_data in evaluations:
                    await conn.execute('''
                        INSERT INTO evaluations
                        (component_hash, component_path, certificate_id, status, model,
                         model_version_date, test_suite, tests_passed, tests_total,
                         performance_class, evaluation_date, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        component_hash,
                        component_path,
                        eval_data.get('certificate_id', ''),
                        eval_data.get('status', 'unknown'),
                        eval_data.get('model', ''),
                        eval_data.get('model_version_date', ''),
                        eval_data.get('test_suite', ''),
                        eval_data.get('tests_passed', 0),
                        eval_data.get('tests_total', 0),
                        eval_data.get('performance_class', ''),
                        eval_data.get('date', ''),
                        format_for_logging()
                    ))
                    indexed_count += 1
            
            await conn.commit()
        
        logger.info(f"Indexed {indexed_count} evaluations from registry")
        if stale_entries:
            logger.warning(f"Found {len(stale_entries)} stale registry entries")
            
        return {'indexed': indexed_count, 'stale_entries': stale_entries}
        
    except Exception as e:
        logger.error(f"Failed to index evaluations: {e}")
        return {'indexed': 0, 'stale_entries': []}


# discover() function removed - now handled by evaluation_integration.discover_with_evaluations()
# This keeps composition_index focused on indexing, evaluation_integration handles discovery


async def get_count(query: Dict[str, Any] = None) -> int:
    """Get count of compositions matching query."""
    if query is None:
        query = {}
    
    conditions = []
    params = []
    
    if 'component_type' in query:
        conditions.append('component_type = ?')
        params.append(query['component_type'])
    
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
                SELECT DISTINCT component_type
                FROM composition_index 
                WHERE component_type IS NOT NULL
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
                WHERE component_type = ?
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