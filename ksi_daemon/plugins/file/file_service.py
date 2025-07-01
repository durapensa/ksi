#!/usr/bin/env python3
"""
File Service Plugin

Provides safe file operations with automatic backup and rollback capabilities.
All file operations are sandboxed and include comprehensive validation.
"""

import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, List
from typing_extensions import NotRequired
import pluggy
from datetime import datetime

from ksi_daemon.plugin_utils import plugin_metadata, event_handler, create_ksi_describe_events_hook
from ksi_common.logging import get_bound_logger
from ksi_common.config import config

# Per-plugin TypedDict definitions (type safety)
class FileReadData(TypedDict):
    """Type-safe data for file:read."""
    path: str
    encoding: NotRequired[str]
    binary: NotRequired[bool]

class FileWriteData(TypedDict):
    """Type-safe data for file:write."""
    path: str
    content: str
    encoding: NotRequired[str]
    create_backup: NotRequired[bool]
    binary: NotRequired[bool]

class FileBackupData(TypedDict):
    """Type-safe data for file:backup."""
    path: str
    backup_name: NotRequired[str]

class FileRollbackData(TypedDict):
    """Type-safe data for file:rollback."""
    path: str
    backup_name: NotRequired[str]

class FileListData(TypedDict):
    """Type-safe data for file:list."""
    path: str
    pattern: NotRequired[str]
    recursive: NotRequired[bool]
    include_hidden: NotRequired[bool]

class FileValidateData(TypedDict):
    """Type-safe data for file:validate."""
    path: str
    check_writable: NotRequired[bool]
    check_content: NotRequired[str]

# Plugin metadata
plugin_metadata("file_service", version="1.0.0",
                description="Safe file operations with backup and rollback")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_bound_logger("file_service", version="1.0.0")

# Plugin info
PLUGIN_INFO = {
    "name": "file_service",
    "version": "1.0.0",
    "description": "Safe file operations with backup and rollback"
}

# Configuration
BACKUP_DIR = config.daemon_tmp_dir / "backups" / "files"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
ALLOWED_EXTENSIONS = {'.txt', '.md', '.yaml', '.yml', '.json', '.py', '.js', '.css', '.html', '.xml', '.log'}


@hookimpl
def ksi_plugin_context(context):
    """Receive infrastructure from daemon context."""
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"File service plugin initialized with backup dir: {BACKUP_DIR}")


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle file-related events using decorated handlers."""
    # Look for decorated handlers
    import sys
    import inspect
    module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    return None


def _validate_path(path: str, operation: str) -> Dict[str, Any]:
    """Validate file path for safety using KSI's directory structure."""
    try:
        # Convert to absolute path
        abs_path = Path(path).resolve()
        
        # Define allowed KSI directories from config
        allowed_dirs = [
            config.compositions_dir,
            config.fragments_dir,
            config.schemas_dir,
            config.capabilities_dir,
            config.daemon_tmp_dir,
            config.daemon_log_dir,
            config.log_dir,
            config.experiments_dir,
            config.lib_dir,
            Path.cwd() / "memory",  # Allow memory directory
            Path.cwd() / "docs",    # Allow docs directory
        ]
        
        # Security checks - ensure path is within allowed KSI directories
        path_allowed = False
        for allowed_dir in allowed_dirs:
            try:
                allowed_dir_resolved = allowed_dir.resolve()
                if str(abs_path).startswith(str(allowed_dir_resolved)):
                    path_allowed = True
                    break
            except Exception:
                continue
        
        if not path_allowed:
            return {"error": f"Path outside allowed KSI directories: {path}"}
        
        # Check file extension for writes
        if operation in ['write'] and abs_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return {"error": f"File extension not allowed: {abs_path.suffix}"}
        
        return {"valid": True, "path": abs_path}
    except Exception as e:
        return {"error": f"Invalid path: {str(e)}"}


def _create_backup(file_path: Path, backup_name: Optional[str] = None) -> Dict[str, Any]:
    """Create a backup of the file."""
    try:
        if not file_path.exists():
            return {"error": "File does not exist"}
        
        # Generate backup name
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}_{timestamp}"
        
        backup_path = BACKUP_DIR / backup_name
        
        # Create backup
        shutil.copy2(file_path, backup_path)
        
        # Calculate checksum for integrity
        with open(backup_path, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
        
        # Store backup metadata
        metadata = {
            "original_path": str(file_path),
            "backup_name": backup_name,
            "backup_path": str(backup_path),
            "timestamp": datetime.now().isoformat(),
            "checksum": checksum,
            "size": backup_path.stat().st_size
        }
        
        metadata_path = BACKUP_DIR / f"{backup_name}.meta"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "status": "backup_created",
            "backup_name": backup_name,
            "backup_path": str(backup_path),
            "checksum": checksum
        }
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return {"error": f"Backup failed: {str(e)}"}


@event_handler("file:read", data_type=FileReadData)
def handle_read(data: FileReadData) -> Dict[str, Any]:
    """
    Read a file with safety validation.
    
    Args:
        path (str): The file path to read (required)
        encoding (str): File encoding (default: utf-8)
        binary (bool): Read as binary data (default: false)
    
    Returns:
        Dictionary with content, size, encoding, and metadata
    
    Example:
        {"path": "var/logs/daemon.log", "encoding": "utf-8"}
    """
    path = data.get("path", "")
    encoding = data.get("encoding", "utf-8")
    binary = data.get("binary", False)
    
    if not path:
        return {"error": "Path is required"}
    
    # Validate path
    validation = _validate_path(path, "read")
    if "error" in validation:
        return validation
    
    file_path = validation["path"]
    
    try:
        if not file_path.exists():
            return {"error": "File does not exist"}
        
        if not file_path.is_file():
            return {"error": "Path is not a file"}
        
        # Check file size
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            return {"error": f"File too large: {size} bytes (max: {MAX_FILE_SIZE})"}
        
        # Read file
        if binary:
            with open(file_path, 'rb') as f:
                content = f.read().hex()  # Return as hex string for safety
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
        
        return {
            "content": content,
            "size": size,
            "encoding": encoding if not binary else "binary",
            "path": str(file_path),
            "binary": binary,
            "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return {"error": f"Read failed: {str(e)}"}


@event_handler("file:write", data_type=FileWriteData)
def handle_write(data: FileWriteData) -> Dict[str, Any]:
    """
    Write to a file with automatic backup.
    
    Args:
        path (str): The file path to write (required)
        content (str): The content to write (required)
        encoding (str): File encoding (default: utf-8)
        create_backup (bool): Create backup before writing (default: true)
        binary (bool): Write binary data (content should be hex string) (default: false)
    
    Returns:
        Dictionary with status, backup info, and file metadata
    
    Example:
        {"path": "var/temp/output.txt", "content": "Hello World", "create_backup": true}
    """
    path = data.get("path", "")
    content = data.get("content", "")
    encoding = data.get("encoding", "utf-8")
    create_backup = data.get("create_backup", True)
    binary = data.get("binary", False)
    
    if not path:
        return {"error": "Path is required"}
    
    if content is None:
        return {"error": "Content is required"}
    
    # Validate path
    validation = _validate_path(path, "write")
    if "error" in validation:
        return validation
    
    file_path = validation["path"]
    
    try:
        # Create backup if file exists and backup requested
        backup_info = None
        if file_path.exists() and create_backup:
            backup_result = _create_backup(file_path)
            if "error" in backup_result:
                return backup_result
            backup_info = backup_result
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        if binary:
            # Convert hex string back to bytes
            try:
                content_bytes = bytes.fromhex(content)
            except ValueError:
                return {"error": "Invalid hex content for binary write"}
            
            with open(file_path, 'wb') as f:
                f.write(content_bytes)
        else:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
        
        # Get file stats
        size = file_path.stat().st_size
        
        result = {
            "status": "written",
            "path": str(file_path),
            "size": size,
            "encoding": encoding if not binary else "binary",
            "binary": binary
        }
        
        if backup_info:
            result["backup"] = backup_info
        
        return result
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        return {"error": f"Write failed: {str(e)}"}


@event_handler("file:backup", data_type=FileBackupData)
def handle_backup(data: FileBackupData) -> Dict[str, Any]:
    """
    Create a manual backup of a file.
    
    Args:
        path (str): The file path to backup (required)
        backup_name (str): Custom backup name (optional, auto-generated if not provided)
    
    Returns:
        Dictionary with backup status and metadata
    
    Example:
        {"path": "important_file.yaml", "backup_name": "before_edit"}
    """
    path = data.get("path", "")
    backup_name = data.get("backup_name")
    
    if not path:
        return {"error": "Path is required"}
    
    # Validate path
    validation = _validate_path(path, "backup")
    if "error" in validation:
        return validation
    
    file_path = validation["path"]
    
    return _create_backup(file_path, backup_name)


@event_handler("file:rollback", data_type=FileRollbackData)
def handle_rollback(data: FileRollbackData) -> Dict[str, Any]:
    """
    Rollback a file to a previous backup.
    
    Args:
        path (str): The file path to rollback (required)
        backup_name (str): Specific backup to restore (optional, uses latest if not provided)
    
    Returns:
        Dictionary with rollback status and metadata
    
    Example:
        {"path": "config.yaml", "backup_name": "before_edit"}
    """
    path = data.get("path", "")
    backup_name = data.get("backup_name")
    
    if not path:
        return {"error": "Path is required"}
    
    # Validate path
    validation = _validate_path(path, "rollback")
    if "error" in validation:
        return validation
    
    file_path = validation["path"]
    
    try:
        # Find backup
        if backup_name:
            backup_path = BACKUP_DIR / backup_name
            metadata_path = BACKUP_DIR / f"{backup_name}.meta"
        else:
            # Find latest backup for this file
            backup_files = []
            for meta_file in BACKUP_DIR.glob("*.meta"):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                    if meta.get("original_path") == str(file_path):
                        backup_files.append((meta_file, meta))
                except Exception:
                    continue
            
            if not backup_files:
                return {"error": "No backups found for this file"}
            
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
        
        # Load and verify metadata
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
        
        # Verify checksum
        with open(backup_path, 'rb') as f:
            actual_checksum = hashlib.sha256(f.read()).hexdigest()
        
        if actual_checksum != meta["checksum"]:
            return {"error": "Backup integrity check failed"}
        
        # Create backup of current file before rollback
        current_backup = None
        if file_path.exists():
            current_backup_result = _create_backup(file_path, f"pre_rollback_{backup_name}")
            if "error" not in current_backup_result:
                current_backup = current_backup_result
        
        # Restore backup
        shutil.copy2(backup_path, file_path)
        
        result = {
            "status": "rolled_back",
            "path": str(file_path),
            "backup_name": backup_name,
            "backup_timestamp": meta["timestamp"],
            "restored_size": meta["size"]
        }
        
        if current_backup:
            result["current_backup"] = current_backup
        
        return result
    except Exception as e:
        logger.error(f"Error rolling back file {file_path}: {e}")
        return {"error": f"Rollback failed: {str(e)}"}


@event_handler("file:list", data_type=FileListData)
def handle_list(data: FileListData) -> Dict[str, Any]:
    """
    List files in a directory with filtering.
    
    Args:
        path (str): The directory path to list (required)
        pattern (str): Filename pattern to match (optional)
        recursive (bool): Include subdirectories (default: false)
        include_hidden (bool): Include hidden files (default: false)
    
    Returns:
        Dictionary with files array and metadata
    
    Example:
        {"path": "var/logs", "pattern": "*.log", "recursive": true}
    """
    path = data.get("path", "")
    pattern = data.get("pattern", "*")
    recursive = data.get("recursive", False)
    include_hidden = data.get("include_hidden", False)
    
    if not path:
        return {"error": "Path is required"}
    
    # Validate path
    validation = _validate_path(path, "list")
    if "error" in validation:
        return validation
    
    dir_path = validation["path"]
    
    try:
        if not dir_path.exists():
            return {"error": "Directory does not exist"}
        
        if not dir_path.is_dir():
            return {"error": "Path is not a directory"}
        
        files = []
        
        if recursive:
            glob_pattern = f"**/{pattern}"
            items = dir_path.glob(glob_pattern)
        else:
            items = dir_path.glob(pattern)
        
        for item in items:
            # Skip hidden files unless requested
            if not include_hidden and item.name.startswith('.'):
                continue
            
            try:
                stat = item.stat()
                file_info = {
                    "name": item.name,
                    "path": str(item.relative_to(dir_path)),
                    "absolute_path": str(item),
                    "type": "file" if item.is_file() else "directory",
                    "size": stat.st_size if item.is_file() else None,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:]
                }
                files.append(file_info)
            except Exception as e:
                logger.warning(f"Error getting info for {item}: {e}")
                continue
        
        # Sort files by name
        files.sort(key=lambda x: x["name"])
        
        return {
            "files": files,
            "count": len(files),
            "path": str(dir_path),
            "pattern": pattern,
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error listing directory {dir_path}: {e}")
        return {"error": f"List failed: {str(e)}"}


@event_handler("file:validate", data_type=FileValidateData)
def handle_validate(data: FileValidateData) -> Dict[str, Any]:
    """
    Validate file access and properties.
    
    Args:
        path (str): The file path to validate (required)
        check_writable (bool): Check if file is writable (default: false)
        check_content (str): Validate file contains specific content (optional)
    
    Returns:
        Dictionary with validation results
    
    Example:
        {"path": "config.yaml", "check_writable": true, "check_content": "version:"}
    """
    path = data.get("path", "")
    check_writable = data.get("check_writable", False)
    check_content = data.get("check_content")
    
    if not path:
        return {"error": "Path is required"}
    
    # Validate path
    validation = _validate_path(path, "validate")
    if "error" in validation:
        return validation
    
    file_path = validation["path"]
    
    try:
        results = {
            "path": str(file_path),
            "exists": file_path.exists(),
            "is_file": file_path.is_file() if file_path.exists() else False,
            "is_directory": file_path.is_dir() if file_path.exists() else False,
            "readable": False,
            "writable": False,
            "valid": True
        }
        
        if file_path.exists():
            # Check permissions
            results["readable"] = os.access(file_path, os.R_OK)
            
            if check_writable:
                results["writable"] = os.access(file_path, os.W_OK)
            
            # Check file size
            if file_path.is_file():
                size = file_path.stat().st_size
                results["size"] = size
                results["size_valid"] = size <= MAX_FILE_SIZE
                
                if size > MAX_FILE_SIZE:
                    results["valid"] = False
                    results["errors"] = [f"File too large: {size} bytes"]
            
            # Check content if requested
            if check_content and file_path.is_file() and results["readable"]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    results["content_match"] = check_content in content
                except Exception as e:
                    results["content_match"] = False
                    results["content_error"] = str(e)
        
        return results
    except Exception as e:
        logger.error(f"Error validating file {file_path}: {e}")
        return {"error": f"Validation failed: {str(e)}"}


# Module-level marker for plugin discovery
ksi_plugin = True

# Enable event discovery
ksi_describe_events = create_ksi_describe_events_hook(__name__)