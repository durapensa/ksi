#!/usr/bin/env python3
"""
Agent Identity Operations

Functional operations for agent identity management using existing file utilities.
"""

from pathlib import Path
from typing import Dict, Any

from ksi_common.file_utils import load_json_file, save_json_file, ensure_directory
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("agent_identity_ops")


async def load_all_identities(storage_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load all agent identities from disk storage.
    
    Args:
        storage_path: Path to identity storage directory
        
    Returns:
        Dict mapping agent_id to identity data
    """
    identities = {}
    
    if not storage_path.exists():
        return identities
        
    try:
        for identity_file in storage_path.glob("*.json"):
            try:
                identity_data = load_json_file(identity_file)
                agent_id = identity_data.get("agent_id", identity_file.stem)
                identities[agent_id] = identity_data
                logger.debug(f"Loaded identity for agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to load identity from {identity_file}: {e}")
    except Exception as e:
        logger.error(f"Failed to scan identity storage: {e}")
        
    return identities


async def save_identity(storage_path: Path, agent_id: str, identity_data: Dict[str, Any]) -> bool:
    """
    Save agent identity to disk using atomic write.
    
    Args:
        storage_path: Path to identity storage directory
        agent_id: Agent ID
        identity_data: Identity data to save
        
    Returns:
        True if saved successfully
    """
    try:
        ensure_directory(storage_path)
        identity_file = storage_path / f"{agent_id}.json"
        save_json_file(identity_file, identity_data, atomic=True)
        return True
    except Exception as e:
        logger.error(f"Failed to save identity for {agent_id}: {e}")
        return False


async def remove_identity(storage_path: Path, agent_id: str) -> bool:
    """
    Remove agent identity file from disk.
    
    Args:
        storage_path: Path to identity storage directory
        agent_id: Agent ID
        
    Returns:
        True if removed successfully
    """
    identity_file = storage_path / f"{agent_id}.json"
    try:
        if identity_file.exists():
            identity_file.unlink()
        return True
    except Exception as e:
        logger.error(f"Failed to remove identity file for {agent_id}: {e}")
        return False


async def save_all_identities(storage_path: Path, identities: Dict[str, Dict[str, Any]]) -> None:
    """
    Save all identities to disk (used during shutdown).
    
    Args:
        storage_path: Path to identity storage directory
        identities: Dict mapping agent_id to identity data
    """
    for agent_id, identity_data in identities.items():
        await save_identity(storage_path, agent_id, identity_data)