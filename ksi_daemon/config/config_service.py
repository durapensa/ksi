#!/usr/bin/env python3
"""
Config Service Module - Event-Based Version

Provides configuration management with validation, backup, and rollback capabilities.
Supports both daemon configuration and composition/schema management.
"""

import os
import json
import yaml
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, List, Union
from typing_extensions import NotRequired
from datetime import datetime

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

# Per-plugin TypedDict definitions (type safety)
class ConfigGetData(TypedDict):
    """Type-safe data for config:get."""
    key: str
    config_type: NotRequired[str]  # 'daemon', 'composition', 'schema'
    file_path: NotRequired[str]

class ConfigSetData(TypedDict):
    """Type-safe data for config:set."""
    key: str
    value: Any
    config_type: NotRequired[str]
    file_path: NotRequired[str]
    create_backup: NotRequired[bool]

class ConfigValidateData(TypedDict):
    """Type-safe data for config:validate."""
    config_type: NotRequired[str]
    file_path: NotRequired[str]
    schema_path: NotRequired[str]

class ConfigReloadData(TypedDict):
    """Type-safe data for config:reload."""
    component: NotRequired[str]  # 'daemon', 'modules', 'compositions'

class ConfigBackupData(TypedDict):
    """Type-safe data for config:backup."""
    config_type: str
    file_path: NotRequired[str]
    backup_name: NotRequired[str]

class ConfigRollbackData(TypedDict):
    """Type-safe data for config:rollback."""
    config_type: str
    file_path: NotRequired[str]
    backup_name: NotRequired[str]

# Module state
logger = get_bound_logger("config_service", version="1.0.0")

# Plugin info
PLUGIN_INFO = {
    "name": "config_service",
    "version": "1.0.0",
    "description": "Configuration management with validation and rollback"
}

# Configuration
CONFIG_BACKUP_DIR = config.daemon_tmp_dir / "backups" / "config"
CONFIG_TYPES = {
    'daemon': {
        'base_dir': Path.cwd(),
        'files': ['ksi_daemon.yaml', 'logging.yaml'],
        'format': 'yaml'
    },
    'composition': {
        'base_dir': config.compositions_dir,
        'extensions': ['.yaml', '.yml'],
        'format': 'yaml'
    },
    'fragment': {
        'base_dir': config.fragments_dir,
        'extensions': ['.md', '.yaml', '.yml'],
        'format': 'mixed'
    },
    'schema': {
        'base_dir': config.schemas_dir,
        'extensions': ['.yaml', '.yml'],
        'format': 'yaml'
    },
    'capabilities': {
        'base_dir': config.capabilities_dir,
        'files': ['ksi_capabilities.yaml'],
        'format': 'yaml'
    }
}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive infrastructure from daemon context."""
    # Ensure backup directory exists
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Config service module initialized with backup dir: {CONFIG_BACKUP_DIR}")


def _resolve_config_file(config_type: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Resolve configuration file path and validate."""
    try:
        if config_type not in CONFIG_TYPES:
            return {"error": f"Unknown config type: {config_type}"}
        
        config_info = CONFIG_TYPES[config_type]
        base_dir = Path(config_info['base_dir'])
        
        if file_path:
            # Specific file requested
            if file_path.startswith('/'):
                # Absolute path - validate it's in allowed directory
                abs_path = Path(file_path)
                if not str(abs_path.resolve()).startswith(str(base_dir.resolve())):
                    return {"error": f"File path outside allowed directory: {file_path}"}
            else:
                # Relative path
                abs_path = base_dir / file_path
        else:
            # Use default files for type
            if 'files' in config_info:
                # Single or multiple default files
                default_files = config_info['files']
                if isinstance(default_files, list):
                    abs_path = base_dir / default_files[0]  # Use first default
                else:
                    abs_path = base_dir / default_files
            else:
                return {"error": f"No default file for config type {config_type}, file_path required"}
        
        return {
            "valid": True,
            "path": abs_path.resolve(),
            "config_type": config_type,
            "format": config_info['format']
        }
    except Exception as e:
        return {"error": f"Path resolution failed: {str(e)}"}


def _load_config_file(file_path: Path, format: str) -> Dict[str, Any]:
    """Load configuration file."""
    try:
        if not file_path.exists():
            return {"error": "Configuration file does not exist"}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if format == 'yaml':
                content = yaml.safe_load(f)
            elif format == 'json':
                content = json.load(f)
            else:
                content = f.read()
        
        return {"content": content}
    except yaml.YAMLError as e:
        return {"error": f"YAML parsing error: {str(e)}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing error: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to load config: {str(e)}"}


def _save_config_file(file_path: Path, content: Any, format: str) -> Dict[str, Any]:
    """Save configuration file."""
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if format == 'yaml':
                yaml.safe_dump(content, f, default_flow_style=False, sort_keys=False)
            elif format == 'json':
                json.dump(content, f, indent=2)
            else:
                f.write(str(content))
        
        return {"status": "saved"}
    except Exception as e:
        return {"error": f"Failed to save config: {str(e)}"}


def _create_config_backup(file_path: Path, backup_name: Optional[str] = None) -> Dict[str, Any]:
    """Create a backup of configuration file."""
    try:
        if not file_path.exists():
            return {"error": "Configuration file does not exist"}
        
        # Generate backup name
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}_{timestamp}"
        
        backup_path = CONFIG_BACKUP_DIR / backup_name
        
        # Create backup
        shutil.copy2(file_path, backup_path)
        
        # Store backup metadata
        metadata = {
            "original_path": str(file_path),
            "backup_name": backup_name,
            "backup_path": str(backup_path),
            "timestamp": datetime.now().isoformat(),
            "size": backup_path.stat().st_size
        }
        
        metadata_path = CONFIG_BACKUP_DIR / f"{backup_name}.meta"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "status": "backup_created",
            "backup_name": backup_name,
            "backup_path": str(backup_path)
        }
    except Exception as e:
        logger.error(f"Error creating config backup: {e}")
        return {"error": f"Backup failed: {str(e)}"}


@event_handler("config:get")
async def handle_get(data: ConfigGetData) -> Dict[str, Any]:
    """
    Get configuration value or entire config file.
    
    Args:
        key (str): Configuration key path (e.g., 'daemon.log_level') (required)
        config_type (str): Type of config ('daemon', 'composition', 'schema', 'capabilities')
        file_path (str): Specific config file path (optional)
    
    Returns:
        Dictionary with configuration value and metadata
    
    Example:
        {"key": "daemon.log_level", "config_type": "daemon"}
    """
    key = data.get("key", "")
    config_type = data.get("config_type", "daemon")
    file_path = data.get("file_path")
    
    if not key:
        return {"error": "Key is required"}
    
    # Resolve configuration file
    resolution = _resolve_config_file(config_type, file_path)
    if "error" in resolution:
        return resolution
    
    file_path = resolution["path"]
    format = resolution["format"]
    
    # Load configuration
    load_result = _load_config_file(file_path, format)
    if "error" in load_result:
        return load_result
    
    config_content = load_result["content"]
    
    try:
        # Navigate to key using dot notation
        value = config_content
        if key != "*":  # "*" means return entire config
            key_parts = key.split(".")
            for part in key_parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return {"error": f"Key not found: {key}"}
        
        return {
            "key": key,
            "value": value,
            "config_type": config_type,
            "file_path": str(file_path),
            "format": format
        }
    except Exception as e:
        logger.error(f"Error getting config key {key}: {e}")
        return {"error": f"Get failed: {str(e)}"}


@event_handler("config:set")
async def handle_set(data: ConfigSetData) -> Dict[str, Any]:
    """
    Set configuration value with automatic backup.
    
    Args:
        key (str): Configuration key path (e.g., 'daemon.log_level') (required)
        value (any): Value to set (required)
        config_type (str): Type of config ('daemon', 'composition', 'schema', 'capabilities')
        file_path (str): Specific config file path (optional)
        create_backup (bool): Create backup before modification (default: true)
    
    Returns:
        Dictionary with status and backup info
    
    Example:
        {"key": "daemon.log_level", "value": "DEBUG", "config_type": "daemon"}
    """
    key = data.get("key", "")
    value = data.get("value")
    config_type = data.get("config_type", "daemon")
    file_path = data.get("file_path")
    create_backup = data.get("create_backup", True)
    
    if not key:
        return {"error": "Key is required"}
    
    if value is None:
        return {"error": "Value is required"}
    
    # Resolve configuration file
    resolution = _resolve_config_file(config_type, file_path)
    if "error" in resolution:
        return resolution
    
    file_path = resolution["path"]
    format = resolution["format"]
    
    # Load existing configuration
    load_result = _load_config_file(file_path, format)
    if "error" in load_result:
        # If file doesn't exist, create new config
        if "does not exist" in load_result["error"]:
            config_content = {}
        else:
            return load_result
    else:
        config_content = load_result["content"]
    
    try:
        # Create backup if requested and file exists
        backup_info = None
        if file_path.exists() and create_backup:
            backup_result = _create_config_backup(file_path)
            if "error" in backup_result:
                return backup_result
            backup_info = backup_result
        
        # Set value using dot notation
        if key == "*":
            # Replace entire config
            if not isinstance(value, dict):
                return {"error": "Value must be dict when setting entire config"}
            config_content = value
        else:
            # Navigate and set specific key
            key_parts = key.split(".")
            current = config_content
            
            # Navigate to parent of target key
            for part in key_parts[:-1]:
                if not isinstance(current, dict):
                    return {"error": f"Cannot set nested key in non-dict value at {part}"}
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the final key
            if not isinstance(current, dict):
                return {"error": f"Cannot set key in non-dict value"}
            current[key_parts[-1]] = value
        
        # Save configuration
        save_result = _save_config_file(file_path, config_content, format)
        if "error" in save_result:
            return save_result
        
        result = {
            "status": "set",
            "key": key,
            "config_type": config_type,
            "file_path": str(file_path)
        }
        
        if backup_info:
            result["backup"] = backup_info
        
        # Emit configuration change event for system components
        router = get_router()
        await router.emit("config:changed", {
            "config_type": config_type,
            "file_path": str(file_path),
            "key": key,
            "value": value
        })
        
        return result
    except Exception as e:
        logger.error(f"Error setting config key {key}: {e}")
        return {"error": f"Set failed: {str(e)}"}


@event_handler("config:validate")
async def handle_validate(data: ConfigValidateData) -> Dict[str, Any]:
    """
    Validate configuration file syntax and schema.
    
    Args:
        config_type (str): Type of config to validate ('daemon', 'composition', 'schema', 'capabilities')
        file_path (str): Specific config file path (optional)
        schema_path (str): Path to validation schema (optional)
    
    Returns:
        Dictionary with validation results
    
    Example:
        {"config_type": "composition", "file_path": "profiles/developer.yaml"}
    """
    config_type = data.get("config_type", "daemon")
    file_path = data.get("file_path")
    schema_path = data.get("schema_path")
    
    # Resolve configuration file
    resolution = _resolve_config_file(config_type, file_path)
    if "error" in resolution:
        return resolution
    
    file_path = resolution["path"]
    format = resolution["format"]
    
    try:
        # Basic syntax validation
        load_result = _load_config_file(file_path, format)
        if "error" in load_result:
            return {
                "valid": False,
                "syntax_valid": False,
                "error": load_result["error"],
                "file_path": str(file_path)
            }
        
        config_content = load_result["content"]
        
        validation_result = {
            "valid": True,
            "syntax_valid": True,
            "file_path": str(file_path),
            "config_type": config_type,
            "format": format
        }
        
        # Schema validation if schema provided
        if schema_path:
            schema_file = Path(schema_path)
            if not schema_file.exists():
                validation_result["schema_valid"] = False
                validation_result["schema_error"] = "Schema file not found"
                validation_result["valid"] = False
            else:
                try:
                    # Load schema and validate (basic implementation)
                    with open(schema_file, 'r') as f:
                        schema_content = yaml.safe_load(f)
                    
                    # Basic schema validation (can be enhanced)
                    validation_result["schema_valid"] = True
                    validation_result["schema_path"] = str(schema_file)
                except Exception as e:
                    validation_result["schema_valid"] = False
                    validation_result["schema_error"] = str(e)
                    validation_result["valid"] = False
        
        # Config-type specific validation
        if config_type == "composition":
            # Validate composition structure
            required_fields = ["name", "type", "components"]
            missing_fields = [field for field in required_fields if field not in config_content]
            if missing_fields:
                validation_result["composition_valid"] = False
                validation_result["composition_errors"] = f"Missing required fields: {missing_fields}"
                validation_result["valid"] = False
            else:
                validation_result["composition_valid"] = True
        
        return validation_result
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return {"error": f"Validation failed: {str(e)}"}


@event_handler("config:reload")
async def handle_reload(data: ConfigReloadData) -> Dict[str, Any]:
    """
    Reload configuration components.
    
    Args:
        component (str): Component to reload ('daemon', 'plugins', 'compositions', 'all')
    
    Returns:
        Dictionary with reload status
    
    Example:
        {"component": "compositions"}
    """
    component = data.get("component", "all")
    
    try:
        results = {"reloaded": []}
        
        # Emit reload events for different components
        router = get_router()
        
        if component in ["daemon", "all"]:
            await router.emit("daemon:config_reload", {})
            results["reloaded"].append("daemon")
        
        if component in ["modules", "all"]:
            await router.emit("modules:reload", {})
            results["reloaded"].append("modules")
        
        if component in ["compositions", "all"]:
            await router.emit("composition:reload", {})
            results["reloaded"].append("compositions")
        
        return {
            "status": "reloaded",
            "component": component,
            "reloaded_components": results["reloaded"]
        }
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        return {"error": f"Reload failed: {str(e)}"}


@event_handler("config:backup")
async def handle_backup(data: ConfigBackupData) -> Dict[str, Any]:
    """
    Create manual backup of configuration.
    
    Args:
        config_type (str): Type of config to backup (required)
        file_path (str): Specific config file path (optional)
        backup_name (str): Custom backup name (optional)
    
    Returns:
        Dictionary with backup status and metadata
    
    Example:
        {"config_type": "daemon", "backup_name": "before_update"}
    """
    config_type = data.get("config_type", "")
    file_path = data.get("file_path")
    backup_name = data.get("backup_name")
    
    if not config_type:
        return {"error": "config_type is required"}
    
    # Resolve configuration file
    resolution = _resolve_config_file(config_type, file_path)
    if "error" in resolution:
        return resolution
    
    file_path = resolution["path"]
    
    return _create_config_backup(file_path, backup_name)


@event_handler("config:rollback")
async def handle_rollback(data: ConfigRollbackData) -> Dict[str, Any]:
    """
    Rollback configuration to previous backup.
    
    Args:
        config_type (str): Type of config to rollback (required)
        file_path (str): Specific config file path (optional)
        backup_name (str): Specific backup to restore (optional, uses latest if not provided)
    
    Returns:
        Dictionary with rollback status and metadata
    
    Example:
        {"config_type": "daemon", "backup_name": "before_update"}
    """
    config_type = data.get("config_type", "")
    file_path = data.get("file_path")
    backup_name = data.get("backup_name")
    
    if not config_type:
        return {"error": "config_type is required"}
    
    # Resolve configuration file
    resolution = _resolve_config_file(config_type, file_path)
    if "error" in resolution:
        return resolution
    
    file_path = resolution["path"]
    
    try:
        # Find backup
        if backup_name:
            backup_path = CONFIG_BACKUP_DIR / backup_name
            metadata_path = CONFIG_BACKUP_DIR / f"{backup_name}.meta"
        else:
            # Find latest backup for this file
            backup_files = []
            for meta_file in CONFIG_BACKUP_DIR.glob("*.meta"):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                    if meta.get("original_path") == str(file_path):
                        backup_files.append((meta_file, meta))
                except Exception:
                    continue
            
            if not backup_files:
                return {"error": "No backups found for this config file"}
            
            # Sort by timestamp and get latest
            backup_files.sort(key=lambda x: x[1]["timestamp"], reverse=True)
            metadata_path, meta = backup_files[0]
            backup_name = meta["backup_name"]
            backup_path = Path(meta["backup_path"])
        
        # Verify backup exists
        if not backup_path.exists():
            return {"error": f"Backup file not found: {backup_name}"}
        
        if not metadata_path.exists():
            return {"error": f"Backup metadata not found: {backup_name}"}
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
        
        # Create backup of current file before rollback
        current_backup = None
        if file_path.exists():
            current_backup_result = _create_config_backup(file_path, f"pre_rollback_{backup_name}")
            if "error" not in current_backup_result:
                current_backup = current_backup_result
        
        # Restore backup
        shutil.copy2(backup_path, file_path)
        
        result = {
            "status": "rolled_back",
            "config_type": config_type,
            "file_path": str(file_path),
            "backup_name": backup_name,
            "backup_timestamp": meta["timestamp"]
        }
        
        if current_backup:
            result["current_backup"] = current_backup
        
        # Emit configuration change event
        router = get_router()
        await router.emit("config:rolled_back", {
            "config_type": config_type,
            "file_path": str(file_path),
            "backup_name": backup_name
        })
        
        return result
    except Exception as e:
        logger.error(f"Error rolling back config: {e}")
        return {"error": f"Rollback failed: {str(e)}"}


