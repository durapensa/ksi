#!/usr/bin/env python3
"""
File Operations - Centralized file I/O utilities
Consolidates common file operations with proper error handling
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from daemon.timestamp_utils import TimestampManager

logger = structlog.get_logger('daemon.file_operations')


class FileOperations:
    """Centralized file operations with consistent error handling"""
    
    @staticmethod
    def ensure_directories(*directories: Union[str, Path]):
        """Ensure multiple directories exist"""
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.1))
    def save_json(filepath: Union[str, Path], data: Any, indent: int = 2, 
                  create_dirs: bool = True) -> bool:
        """
        Save data to JSON file with retry logic
        
        Args:
            filepath: Path to save to
            data: Data to serialize
            indent: JSON indentation
            create_dirs: Create parent directories if needed
            
        Returns:
            True if successful
        """
        try:
            filepath = Path(filepath)
            if create_dirs:
                filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first for atomicity
            temp_file = filepath.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=indent)
            
            # Atomic rename
            temp_file.replace(filepath)
            logger.debug(f"Saved JSON to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save JSON to {filepath}: {e}")
            raise
    
    @staticmethod
    def load_json(filepath: Union[str, Path], default: Any = None) -> Any:
        """
        Load data from JSON file
        
        Args:
            filepath: Path to load from
            default: Default value if file doesn't exist or is invalid
            
        Returns:
            Loaded data or default
        """
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                logger.debug(f"File {filepath} doesn't exist, returning default")
                return default
            
            with open(filepath, 'r') as f:
                return json.load(f)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {filepath}: {e}")
            return default
        except Exception as e:
            logger.error(f"Failed to load JSON from {filepath}: {e}")
            return default
    
    @staticmethod
    def append_jsonl(filepath: Union[str, Path], entry: Dict[str, Any], 
                    create_dirs: bool = True) -> bool:
        """
        Append entry to JSONL file
        
        Args:
            filepath: Path to JSONL file
            entry: Entry to append
            create_dirs: Create parent directories if needed
            
        Returns:
            True if successful
        """
        try:
            filepath = Path(filepath)
            if create_dirs:
                filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'a') as f:
                f.write(json.dumps(entry) + '\n')
            
            logger.debug(f"Appended entry to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to append to JSONL {filepath}: {e}")
            return False
    
    @staticmethod
    def read_jsonl(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Read all entries from a JSONL file
        
        Args:
            filepath: Path to JSONL file
            
        Returns:
            List of entries
        """
        entries = []
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                return entries
            
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping invalid JSON line: {e}")
                            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to read JSONL from {filepath}: {e}")
            return entries
    
    @staticmethod
    def create_symlink(target: Union[str, Path], link_path: Union[str, Path], 
                      force: bool = True) -> bool:
        """
        Create or update a symlink
        
        Args:
            target: Target file/directory
            link_path: Symlink path
            force: Remove existing symlink if present
            
        Returns:
            True if successful
        """
        try:
            target = Path(target)
            link_path = Path(link_path)
            
            if force and link_path.exists():
                link_path.unlink()
            
            link_path.symlink_to(target)
            logger.debug(f"Created symlink {link_path} -> {target}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create symlink: {e}")
            return False
    
    @staticmethod
    def clean_directory(directory: Union[str, Path], pattern: str = "*", 
                       exclude: Optional[List[str]] = None,
                       remove_broken_symlinks: bool = True) -> int:
        """
        Clean files from a directory
        
        Args:
            directory: Directory to clean
            pattern: Glob pattern for files to remove
            exclude: List of filenames to exclude
            remove_broken_symlinks: Also remove broken symlinks
            
        Returns:
            Number of files removed
        """
        directory = Path(directory)
        if not directory.exists():
            return 0
        
        exclude = exclude or []
        files_removed = 0
        
        try:
            # Remove matching files
            for file_path in directory.glob(pattern):
                if file_path.name not in exclude and file_path.is_file():
                    file_path.unlink()
                    files_removed += 1
                    logger.debug(f"Removed {file_path}")
            
            # Remove broken symlinks
            if remove_broken_symlinks:
                for file_path in directory.iterdir():
                    if file_path.is_symlink() and not file_path.exists():
                        file_path.unlink()
                        files_removed += 1
                        logger.debug(f"Removed broken symlink {file_path}")
            
            logger.info(f"Cleaned {files_removed} files from {directory}")
            return files_removed
            
        except Exception as e:
            logger.error(f"Error cleaning directory {directory}: {e}")
            return files_removed
    
    @staticmethod
    def rotate_logs(log_dir: Union[str, Path], keep_recent: int = 10, 
                   pattern: str = "*.jsonl") -> int:
        """
        Rotate log files, keeping only the most recent ones
        
        Args:
            log_dir: Log directory
            keep_recent: Number of recent files to keep
            pattern: File pattern to match
            
        Returns:
            Number of files removed
        """
        log_dir = Path(log_dir)
        if not log_dir.exists():
            return 0
        
        try:
            # Get all matching files with modification times
            files = []
            for file_path in log_dir.glob(pattern):
                if file_path.is_file() and not file_path.is_symlink():
                    files.append((file_path, file_path.stat().st_mtime))
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove older files
            files_removed = 0
            for file_path, _ in files[keep_recent:]:
                file_path.unlink()
                files_removed += 1
                logger.debug(f"Rotated out {file_path}")
            
            if files_removed > 0:
                logger.info(f"Rotated {files_removed} old log files")
            
            return files_removed
            
        except Exception as e:
            logger.error(f"Error rotating logs in {log_dir}: {e}")
            return 0


class LogEntry:
    """Helper class for creating consistent log entries"""
    
    @staticmethod
    def create(entry_type: str, content: Any, **kwargs) -> Dict[str, Any]:
        """
        Create a standardized log entry
        
        Args:
            entry_type: Type of log entry
            content: Main content
            **kwargs: Additional fields
            
        Returns:
            Log entry dict
        """
        entry = {
            "timestamp": TimestampManager.timestamp_utc(),
            "type": entry_type,
            "content": content
        }
        entry.update(kwargs)
        return entry
    
    @staticmethod
    def human(content: str, **kwargs) -> Dict[str, Any]:
        """Create a human input log entry"""
        return LogEntry.create("human", content, **kwargs)
    
    @staticmethod
    def claude(content: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Create a Claude output log entry"""
        return LogEntry.create("claude", content, **kwargs)
    
    @staticmethod
    def system(message: str, **kwargs) -> Dict[str, Any]:
        """Create a system event log entry"""
        return LogEntry.create("system", message, **kwargs)
    
    @staticmethod
    def error(error: str, details: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Create an error log entry"""
        entry = LogEntry.create("error", error, **kwargs)
        if details:
            entry["details"] = details
        return entry


# Global instance for convenience
file_ops = FileOperations()