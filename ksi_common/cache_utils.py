#!/usr/bin/env python3
"""
Cache Utilities - Common caching patterns for KSI system

Provides consistent patterns for:
- In-memory caching with TTL
- File-based caching
- Cache invalidation
- LRU caching
"""

import time
import json
from pathlib import Path
from typing import Any, Dict, Optional, Callable, TypeVar
from datetime import datetime, timezone, timedelta
from functools import lru_cache, wraps
import hashlib

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now

logger = get_bound_logger("cache_utils")

T = TypeVar('T')


class TTLCache:
    """Time-based cache with automatic expiration."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize TTL cache.
        
        Args:
            ttl_seconds: Time to live in seconds (default 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            self._misses += 1
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            # Expired
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def invalidate(self, key: str) -> bool:
        """Remove specific key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl_seconds
        }


def ttl_cache(ttl_seconds: int = 300):
    """
    Decorator for caching function results with TTL.
    
    Args:
        ttl_seconds: Time to live in seconds
        
    Usage:
        @ttl_cache(ttl_seconds=60)
        def expensive_operation(param):
            return compute_result(param)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = TTLCache(ttl_seconds)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        
        # Attach cache instance for manual control
        wrapper.cache = cache
        return wrapper
    
    return decorator


class FileCache:
    """File-based cache for persistent storage."""
    
    def __init__(self, cache_dir: Path, ttl_seconds: Optional[int] = None):
        """
        Initialize file cache.
        
        Args:
            cache_dir: Directory for cache files
            ttl_seconds: Optional TTL for cached files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        # Hash the key to avoid filesystem issues
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from file cache."""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            # Check TTL if configured
            if self.ttl_seconds is not None:
                mtime = cache_path.stat().st_mtime
                if time.time() - mtime > self.ttl_seconds:
                    cache_path.unlink()
                    return None
            
            with open(cache_path, 'r') as f:
                data = json.load(f)
                return data['value']
                
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_path}: {e}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in file cache."""
        cache_path = self._get_cache_path(key)
        
        try:
            data = {
                'key': key,
                'value': value,
                'timestamp': utc_now().isoformat()
            }
            
            # Write atomically
            tmp_path = cache_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            tmp_path.replace(cache_path)
            
        except Exception as e:
            logger.error(f"Failed to write cache file {cache_path}: {e}")
    
    def clear(self) -> int:
        """Clear all cache files and return count removed."""
        count = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")
        return count
    
    def cleanup_expired(self) -> int:
        """Remove expired cache files."""
        if self.ttl_seconds is None:
            return 0
        
        count = 0
        current_time = time.time()
        
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                mtime = cache_file.stat().st_mtime
                if current_time - mtime > self.ttl_seconds:
                    cache_file.unlink()
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to check/remove cache file {cache_file}: {e}")
        
        return count


class CacheManager:
    """Manages multiple caches with periodic cleanup."""
    
    def __init__(self):
        self.caches: Dict[str, TTLCache] = {}
        self.file_caches: Dict[str, FileCache] = {}
    
    def get_memory_cache(self, name: str, ttl_seconds: int = 300) -> TTLCache:
        """Get or create named memory cache."""
        if name not in self.caches:
            self.caches[name] = TTLCache(ttl_seconds)
        return self.caches[name]
    
    def get_file_cache(self, name: str, cache_dir: Path, ttl_seconds: Optional[int] = None) -> FileCache:
        """Get or create named file cache."""
        if name not in self.file_caches:
            self.file_caches[name] = FileCache(cache_dir, ttl_seconds)
        return self.file_caches[name]
    
    def cleanup_all(self) -> Dict[str, int]:
        """Cleanup all expired entries in all caches."""
        results = {}
        
        # Memory caches
        for name, cache in self.caches.items():
            count = cache.cleanup_expired()
            if count > 0:
                results[f"memory:{name}"] = count
        
        # File caches
        for name, cache in self.file_caches.items():
            count = cache.cleanup_expired()
            if count > 0:
                results[f"file:{name}"] = count
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches."""
        return {
            "memory_caches": {
                name: cache.stats() for name, cache in self.caches.items()
            },
            "file_caches": {
                name: {"cache_dir": str(cache.cache_dir), "ttl": cache.ttl_seconds}
                for name, cache in self.file_caches.items()
            }
        }


# Global cache manager instance
_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    return _cache_manager


# Convenience functions
def get_memory_cache(name: str, ttl_seconds: int = 300) -> TTLCache:
    """Get or create a named memory cache."""
    return _cache_manager.get_memory_cache(name, ttl_seconds)


def get_file_cache(name: str, cache_dir: Path, ttl_seconds: Optional[int] = None) -> FileCache:
    """Get or create a named file cache."""
    return _cache_manager.get_file_cache(name, cache_dir, ttl_seconds)