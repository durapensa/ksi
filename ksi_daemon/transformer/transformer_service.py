#!/usr/bin/env python3
"""
Transformer Service - Pattern-Level Transformer Management

High-level management of transformers from pattern files.
Works with the core transformer infrastructure in event_system.py.

Responsibilities:
- Load/unload transformers from pattern YAML files
- Track which systems are using which patterns
- Reference counting for shared patterns
- Hot-reload support for development
- Integration with composition system

Does NOT duplicate event_system.py functionality - uses existing
router.register_transformer_from_yaml() and router.unregister_transformer().
"""

import asyncio
import yaml
import time
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, TypedDict
from typing_extensions import NotRequired, Required
from dataclasses import dataclass, field

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("transformer_service", version="1.0.0")


@dataclass
class PatternTransformerInfo:
    """Information about transformers loaded from a pattern."""
    pattern_name: str
    file_path: str
    transformer_sources: List[str] = field(default_factory=list)  # Source events
    loaded_by: Set[str] = field(default_factory=set)  # Systems using this pattern
    load_time: float = field(default_factory=time.time)
    transformers_data: List[Dict[str, Any]] = field(default_factory=list)  # Original YAML data


class TransformerService:
    """Service for managing pattern-level transformer loading."""
    
    def __init__(self):
        # Pattern registry: pattern_name -> PatternTransformerInfo
        self._loaded_patterns: Dict[str, PatternTransformerInfo] = {}
        
        # Track which patterns contain transformers (for discovery)
        self._patterns_with_transformers: Set[str] = set()
        
        # Reference to router for transformer operations
        self._router = None
    
    def _get_router(self):
        """Get router instance, cached for performance."""
        if self._router is None:
            self._router = get_router()
        return self._router
    
    async def load_pattern_transformers(self, pattern_name: str, source_system: str, 
                                      force_reload: bool = False) -> Dict[str, Any]:
        """Load transformers from a pattern file.
        
        Args:
            pattern_name: Name of the pattern to load
            source_system: System requesting the load (e.g., "orchestration", "evaluation")
            force_reload: Force reload even if already loaded
            
        Returns:
            Status information about the load operation
        """
        try:
            # Check if already loaded
            if pattern_name in self._loaded_patterns and not force_reload:
                # Add this system to the users
                pattern_info = self._loaded_patterns[pattern_name]
                pattern_info.loaded_by.add(source_system)
                
                logger.debug(f"Pattern {pattern_name} already loaded, added {source_system} as user")
                return {
                    "status": "already_loaded",
                    "pattern": pattern_name,
                    "transformers": len(pattern_info.transformer_sources),
                    "loaded_by": list(pattern_info.loaded_by)
                }
            
            # Load pattern file via composition system
            pattern_data = await self._load_pattern_file(pattern_name)
            
            # Extract transformers section
            transformers = pattern_data.get('transformers', [])
            if not transformers:
                logger.info(f"Pattern {pattern_name} has no transformers section")
                return {
                    "status": "no_transformers",
                    "pattern": pattern_name,
                    "transformers": 0
                }
            
            # If force_reload, unload existing transformers first
            if force_reload and pattern_name in self._loaded_patterns:
                await self._unload_pattern_transformers_internal(pattern_name)
            
            # Load transformers via event system
            router = self._get_router()
            loaded_sources = []
            failed_count = 0
            
            for transformer_def in transformers:
                try:
                    # Validate basic structure
                    if 'source' not in transformer_def or 'target' not in transformer_def:
                        logger.warning(f"Invalid transformer in pattern {pattern_name}: missing source or target")
                        failed_count += 1
                        continue
                    
                    # Register with core event system
                    router.register_transformer_from_yaml(transformer_def)
                    loaded_sources.append(transformer_def['source'])
                    
                    logger.debug(f"Loaded transformer: {transformer_def['source']} -> {transformer_def['target']}")
                    
                except Exception as e:
                    logger.error(f"Failed to load transformer from pattern {pattern_name}: {e}")
                    failed_count += 1
            
            # Create pattern info
            pattern_info = PatternTransformerInfo(
                pattern_name=pattern_name,
                file_path=self._get_pattern_file_path(pattern_name),
                transformer_sources=loaded_sources,
                loaded_by={source_system},
                transformers_data=transformers
            )
            
            # Store in registry
            self._loaded_patterns[pattern_name] = pattern_info
            self._patterns_with_transformers.add(pattern_name)
            
            logger.info(f"Loaded {len(loaded_sources)} transformers from pattern {pattern_name} for {source_system}")
            
            return {
                "status": "loaded",
                "pattern": pattern_name,
                "transformers": len(loaded_sources),
                "failed": failed_count,
                "loaded_by": [source_system]
            }
            
        except Exception as e:
            logger.error(f"Failed to load pattern transformers for {pattern_name}: {e}")
            return {
                "status": "error",
                "pattern": pattern_name,
                "error": str(e)
            }
    
    async def unload_pattern_transformers(self, pattern_name: str, source_system: str) -> Dict[str, Any]:
        """Unload transformers from a pattern (with reference counting).
        
        Args:
            pattern_name: Name of the pattern to unload
            source_system: System requesting the unload
            
        Returns:
            Status information about the unload operation
        """
        if pattern_name not in self._loaded_patterns:
            return {
                "status": "not_loaded",
                "pattern": pattern_name
            }
        
        pattern_info = self._loaded_patterns[pattern_name]
        
        # Remove this system from users
        pattern_info.loaded_by.discard(source_system)
        
        # If no more users, actually unload the transformers
        if not pattern_info.loaded_by:
            await self._unload_pattern_transformers_internal(pattern_name)
            
            logger.info(f"Unloaded {len(pattern_info.transformer_sources)} transformers from pattern {pattern_name}")
            return {
                "status": "unloaded",
                "pattern": pattern_name,
                "transformers": len(pattern_info.transformer_sources)
            }
        else:
            logger.debug(f"Pattern {pattern_name} still used by: {pattern_info.loaded_by}")
            return {
                "status": "still_in_use",
                "pattern": pattern_name,
                "loaded_by": list(pattern_info.loaded_by)
            }
    
    async def _unload_pattern_transformers_internal(self, pattern_name: str):
        """Internal method to actually unload transformers."""
        if pattern_name not in self._loaded_patterns:
            return
        
        pattern_info = self._loaded_patterns[pattern_name]
        router = self._get_router()
        
        # Unregister each transformer
        for source in pattern_info.transformer_sources:
            try:
                router.unregister_transformer(source)
                logger.debug(f"Unregistered transformer: {source}")
            except Exception as e:
                logger.error(f"Failed to unregister transformer {source}: {e}")
        
        # Remove from registry
        del self._loaded_patterns[pattern_name]
        self._patterns_with_transformers.discard(pattern_name)
    
    async def reload_pattern_transformers(self, pattern_name: str) -> Dict[str, Any]:
        """Reload transformers from a pattern file.
        
        Args:
            pattern_name: Name of the pattern to reload
            
        Returns:
            Status information about the reload operation
        """
        if pattern_name not in self._loaded_patterns:
            return {
                "status": "not_loaded",
                "pattern": pattern_name
            }
        
        # Get current users
        pattern_info = self._loaded_patterns[pattern_name]
        current_users = pattern_info.loaded_by.copy()
        
        # Force reload for first user (will unload/reload)
        if current_users:
            first_user = next(iter(current_users))
            result = await self.load_pattern_transformers(pattern_name, first_user, force_reload=True)
            
            # Re-add other users
            for user in current_users:
                if user != first_user:
                    self._loaded_patterns[pattern_name].loaded_by.add(user)
            
            result["reloaded_for"] = list(current_users)
            return result
        
        return {"status": "no_users", "pattern": pattern_name}
    
    def list_loaded_patterns(self) -> Dict[str, Any]:
        """List all loaded patterns and their transformer information."""
        patterns = {}
        
        for pattern_name, pattern_info in self._loaded_patterns.items():
            patterns[pattern_name] = {
                "transformers": len(pattern_info.transformer_sources),
                "transformer_sources": pattern_info.transformer_sources,
                "loaded_by": list(pattern_info.loaded_by),
                "load_time": pattern_info.load_time,
                "file_path": pattern_info.file_path
            }
        
        return {
            "patterns": patterns,
            "total_patterns": len(patterns),
            "total_transformers": sum(len(info.transformer_sources) for info in self._loaded_patterns.values())
        }
    
    def get_usage_info(self) -> Dict[str, Any]:
        """Get information about which systems are using which patterns."""
        usage_by_system = {}
        usage_by_pattern = {}
        
        for pattern_name, pattern_info in self._loaded_patterns.items():
            usage_by_pattern[pattern_name] = list(pattern_info.loaded_by)
            
            for system in pattern_info.loaded_by:
                if system not in usage_by_system:
                    usage_by_system[system] = []
                usage_by_system[system].append(pattern_name)
        
        return {
            "by_system": usage_by_system,
            "by_pattern": usage_by_pattern,
            "total_patterns": len(self._loaded_patterns),
            "total_systems": len(usage_by_system)
        }
    
    async def _load_pattern_file(self, pattern_name: str) -> Dict[str, Any]:
        """Load pattern file via composition system or direct file access."""
        # Try via composition system first (preferred)
        try:
            router = self._get_router()
            result = await router.emit("composition:get", {"name": pattern_name, "type": "orchestration"})
            
            if result and isinstance(result, list) and result:
                response = result[0]  # First result
                logger.debug(f"Composition response type: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'not a dict'}")
                
                # Handle different response formats
                if isinstance(response, dict):
                    # Direct response (new format)
                    if response.get('status') == 'success' and 'composition' in response:
                        return response['composition']
                    # Old format with data wrapper
                    elif response.get('data', {}).get('status') == 'success':
                        return response['data']['composition']
        except Exception as e:
            logger.debug(f"Could not load pattern {pattern_name} via composition system: {e}")
        
        # Fallback to direct file access
        file_path = self._get_pattern_file_path(pattern_name)
        if file_path.exists():
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        
        raise FileNotFoundError(f"Pattern file not found: {pattern_name}")
    
    def _get_pattern_file_path(self, pattern_name: str) -> Path:
        """Get the file path for a pattern."""
        patterns_dir = Path("var") / "lib" / "compositions" / "orchestrations"
        
        # Try .yaml first, then .yml
        yaml_path = patterns_dir / f"{pattern_name}.yaml"
        if yaml_path.exists():
            return yaml_path
        
        return patterns_dir / f"{pattern_name}.yml"


# Create service instance
transformer_service = TransformerService()


# TypedDict definitions for event handlers

class TransformerLoadPatternData(TypedDict):
    """Load transformers from a pattern file."""
    pattern: Required[str]  # Name of the pattern to load
    source: NotRequired[str]  # System requesting the load (default: 'unknown')
    force_reload: NotRequired[bool]  # Force reload even if already loaded (default: False)


class TransformerUnloadPatternData(TypedDict):
    """Unload transformers from a pattern."""
    pattern: Required[str]  # Name of the pattern to unload
    source: NotRequired[str]  # System requesting the unload (default: 'unknown')


class TransformerReloadPatternData(TypedDict):
    """Reload transformers from a pattern file."""
    pattern: Required[str]  # Name of the pattern to reload


class TransformerListByPatternData(TypedDict):
    """List all loaded patterns and their transformers."""
    # No specific fields - returns all loaded patterns
    pass


class TransformerGetUsageData(TypedDict):
    """Get usage information - which systems use which patterns."""
    # No specific fields - returns all usage information
    pass


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for transformer service
    pass


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


# Event handlers
@event_handler("transformer:load_pattern")
async def handle_load_pattern(data: TransformerLoadPatternData) -> Dict[str, Any]:
    """Load transformers from a pattern file.
    
    Parameters:
        pattern: str - Name of the pattern to load
        source: str - System requesting the load (e.g., "orchestration")
        force_reload: bool - Force reload even if already loaded (optional)
    """
    pattern_name = data.get('pattern')
    source_system = data.get('source', 'unknown')
    force_reload = data.get('force_reload', False)
    
    if not pattern_name:
        return {"error": "pattern name required"}
    
    return await transformer_service.load_pattern_transformers(pattern_name, source_system, force_reload)


@event_handler("transformer:unload_pattern") 
async def handle_unload_pattern(data: TransformerUnloadPatternData) -> Dict[str, Any]:
    """Unload transformers from a pattern.
    
    Parameters:
        pattern: str - Name of the pattern to unload
        source: str - System requesting the unload
    """
    pattern_name = data.get('pattern')
    source_system = data.get('source', 'unknown')
    
    if not pattern_name:
        return {"error": "pattern name required"}
    
    return await transformer_service.unload_pattern_transformers(pattern_name, source_system)


@event_handler("transformer:reload_pattern")
async def handle_reload_pattern(data: TransformerReloadPatternData) -> Dict[str, Any]:
    """Reload transformers from a pattern file.
    
    Parameters:
        pattern: str - Name of the pattern to reload
    """
    pattern_name = data.get('pattern')
    
    if not pattern_name:
        return {"error": "pattern name required"}
    
    return await transformer_service.reload_pattern_transformers(pattern_name)


@event_handler("transformer:list_by_pattern")
async def handle_list_by_pattern(data: TransformerListByPatternData) -> Dict[str, Any]:
    """List all loaded patterns and their transformers."""
    return transformer_service.list_loaded_patterns()


@event_handler("transformer:get_usage")
async def handle_get_usage(data: TransformerGetUsageData) -> Dict[str, Any]:
    """Get usage information - which systems use which patterns."""
    return transformer_service.get_usage_info()


@event_handler("system:startup")
async def handle_startup(data: SystemStartupData) -> Dict[str, Any]:
    """Initialize transformer service on startup."""
    logger.info("Transformer service started - ready for pattern-based transformer loading")
    
    return {
        "status": "transformer_service_ready",
        "features": [
            "pattern_loading",
            "reference_counting", 
            "hot_reload",
            "usage_tracking"
        ]
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean up on shutdown."""
    # Unload all patterns
    for pattern_name in list(transformer_service._loaded_patterns.keys()):
        await transformer_service._unload_pattern_transformers_internal(pattern_name)
    
    logger.info("Transformer service shutdown - all patterns unloaded")