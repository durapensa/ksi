#!/usr/bin/env python3
"""
Discovery Cache Module

Provides SQLite-based caching for expensive discovery analysis operations.
Tracks file modification times to automatically invalidate stale entries.
"""

import os
import json
import time
import sqlite3
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("discovery_cache", version="1.0.0")

# Analysis schema version - bump when cache format changes
CACHE_SCHEMA_VERSION = 1


class DiscoveryCache:
    """Manages cached discovery analysis results."""
    
    def __init__(self):
        self.db_path = config.db_dir / "discovery_cache.db"
        self._init_db()
        
    def _init_db(self):
        """Initialize cache database schema."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Discovery analysis cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discovery_cache (
                    event_name TEXT PRIMARY KEY,
                    module_path TEXT NOT NULL,
                    module_mtime REAL NOT NULL,
                    handler_name TEXT,
                    typed_dict_analysis TEXT,
                    ast_analysis TEXT,
                    docstring_info TEXT,
                    analysis_version INTEGER DEFAULT 1,
                    cached_at REAL NOT NULL
                )
            """)
            
            # Example mining cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS example_cache (
                    event_name TEXT PRIMARY KEY,
                    examples TEXT,
                    last_event_id INTEGER,
                    cached_at REAL NOT NULL
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovery_module ON discovery_cache(module_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovery_mtime ON discovery_cache(module_mtime)")
            
            conn.commit()
        finally:
            conn.close()
            
    def is_cache_valid(self, event_name: str, module_path: str) -> bool:
        """Check if cache entry is still valid."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT module_mtime, analysis_version FROM discovery_cache WHERE event_name = ?",
                (event_name,)
            )
            row = cursor.fetchone()
            
            if not row:
                return False
                
            cached_mtime, version = row
            
            # Check schema version
            if version != CACHE_SCHEMA_VERSION:
                return False
                
            # Check file modification time
            try:
                actual_mtime = os.path.getmtime(module_path)
                return abs(cached_mtime - actual_mtime) < 0.001  # Float comparison tolerance
            except OSError:
                return False
                
        finally:
            conn.close()
            
    def get_cached_analysis(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis for an event."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                """SELECT module_path, handler_name, typed_dict_analysis, 
                          ast_analysis, docstring_info 
                   FROM discovery_cache WHERE event_name = ?""",
                (event_name,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
                
            module_path, handler_name, typed_dict_json, ast_json, docstring_json = row
            
            # Validate cache before returning
            if not self.is_cache_valid(event_name, module_path):
                return None
                
            # Reconstruct analysis result
            analysis = {
                "module": module_path,
                "handler": handler_name,
            }
            
            if typed_dict_json:
                analysis.update(json.loads(typed_dict_json))
            if ast_json:
                analysis.update(json.loads(ast_json))
            if docstring_json:
                analysis.update(json.loads(docstring_json))
                
            return analysis
            
        finally:
            conn.close()
            
    def update_cache_entry(self, event_name: str, module_path: str, 
                          handler_name: str, analysis: Dict[str, Any]):
        """Update cache entry for an event."""
        # Separate analysis components
        typed_dict_data = {}
        ast_data = {}
        docstring_data = {}
        
        # Categorize analysis results
        for key, value in analysis.items():
            if key in ["parameters", "required_params", "optional_params"]:
                typed_dict_data[key] = value
            elif key in ["triggers", "emitted_events", "implementation_details"]:
                ast_data[key] = value
            elif key in ["summary", "description", "examples"]:
                docstring_data[key] = value
                
        # Get module mtime
        try:
            module_mtime = os.path.getmtime(module_path)
        except OSError:
            logger.warning(f"Could not get mtime for {module_path}")
            return
            
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT OR REPLACE INTO discovery_cache 
                (event_name, module_path, module_mtime, handler_name,
                 typed_dict_analysis, ast_analysis, docstring_info,
                 analysis_version, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_name,
                module_path,
                module_mtime,
                handler_name,
                json.dumps(typed_dict_data) if typed_dict_data else None,
                json.dumps(ast_data) if ast_data else None,
                json.dumps(docstring_data) if docstring_data else None,
                CACHE_SCHEMA_VERSION,
                time.time()
            ))
            conn.commit()
        finally:
            conn.close()
            
    def get_cached_examples(self, event_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached examples for an event."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT examples FROM example_cache WHERE event_name = ?",
                (event_name,)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                return json.loads(row[0])
            return None
            
        finally:
            conn.close()
            
    def update_examples_batch(self, examples_by_event: Dict[str, List[Dict[str, Any]]]):
        """Update examples for multiple events in a single transaction."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            for event_name, examples in examples_by_event.items():
                conn.execute("""
                    INSERT OR REPLACE INTO example_cache 
                    (event_name, examples, cached_at)
                    VALUES (?, ?, ?)
                """, (
                    event_name,
                    json.dumps(examples),
                    time.time()
                ))
            conn.commit()
        finally:
            conn.close()
            
    def get_stale_entries(self) -> List[Tuple[str, str]]:
        """Get list of stale cache entries that need updating."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT event_name, module_path FROM discovery_cache"
            )
            
            stale = []
            for event_name, module_path in cursor:
                if not self.is_cache_valid(event_name, module_path):
                    stale.append((event_name, module_path))
                    
            return stale
            
        finally:
            conn.close()
            
    def clear_cache(self):
        """Clear all cache entries."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM discovery_cache")
            conn.execute("DELETE FROM example_cache")
            conn.commit()
        finally:
            conn.close()


# Global cache instance
_cache = None

def get_discovery_cache() -> DiscoveryCache:
    """Get the global discovery cache instance."""
    global _cache
    if _cache is None:
        _cache = DiscoveryCache()
    return _cache


async def warm_discovery_cache():
    """Background task to progressively warm the discovery cache."""
    cache = get_discovery_cache()
    logger.info("Starting discovery cache warming")
    
    # Wait for daemon to fully start
    await asyncio.sleep(2.0)
    
    # Get stale entries
    stale_entries = cache.get_stale_entries()
    if stale_entries:
        logger.info(f"Found {len(stale_entries)} stale cache entries to update")
        
        # Update stale entries gradually
        for event_name, module_path in stale_entries:
            # TODO: Call analyzer to update cache
            # This will be implemented when we refactor the analyzer
            await asyncio.sleep(0.1)  # Yield between updates
            
    logger.info("Discovery cache warming complete")