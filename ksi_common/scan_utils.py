#!/usr/bin/env python3
"""
Directory Scanning Utilities - Common patterns for finding and loading files

Provides consistent patterns for:
- Finding YAML/JSON files in directories
- Loading multiple files with error handling
- Pattern matching and filtering
- Batch file operations
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union, Iterator
import yaml
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from ksi_common.logging import get_bound_logger
from ksi_common.file_utils import load_yaml_file, load_json_file

logger = get_bound_logger("scan_utils")


def find_files(
    directory: Union[str, Path],
    pattern: str = "*.yaml",
    recursive: bool = True,
    exclude_patterns: Optional[List[str]] = None
) -> List[Path]:
    """
    Find files matching pattern in directory.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern (default: "*.yaml")
        recursive: Search recursively
        exclude_patterns: Patterns to exclude
        
    Returns:
        List of matching file paths
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        logger.warning(f"Directory does not exist: {dir_path}")
        return []
    
    # Get all matching files
    if recursive:
        files = list(dir_path.rglob(pattern))
    else:
        files = list(dir_path.glob(pattern))
    
    # Apply exclusions
    if exclude_patterns:
        filtered = []
        for file in files:
            exclude = False
            for exc_pattern in exclude_patterns:
                if file.match(exc_pattern):
                    exclude = True
                    break
            if not exclude:
                filtered.append(file)
        files = filtered
    
    return sorted(files)


def load_all_yaml_files(
    directory: Union[str, Path],
    recursive: bool = True,
    validate_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
    parallel: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    Load all YAML files from a directory.
    
    Args:
        directory: Directory to scan
        recursive: Search recursively
        validate_func: Optional validation function
        parallel: Load files in parallel
        
    Returns:
        Dict mapping relative paths to loaded content
    """
    dir_path = Path(directory)
    yaml_files = find_files(dir_path, "*.yaml", recursive)
    
    results = {}
    errors = []
    
    if parallel and len(yaml_files) > 3:
        # Use thread pool for parallel loading
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {
                executor.submit(_load_yaml_with_validation, file, validate_func): file
                for file in yaml_files
            }
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    data = future.result()
                    if data is not None:
                        rel_path = file.relative_to(dir_path)
                        results[str(rel_path)] = data
                except Exception as e:
                    errors.append((file, e))
    else:
        # Sequential loading
        for file in yaml_files:
            try:
                data = _load_yaml_with_validation(file, validate_func)
                if data is not None:
                    rel_path = file.relative_to(dir_path)
                    results[str(rel_path)] = data
            except Exception as e:
                errors.append((file, e))
    
    # Log errors
    for file, error in errors:
        logger.error(f"Failed to load {file}: {error}")
    
    return results


def _load_yaml_with_validation(
    file_path: Path,
    validate_func: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> Optional[Dict[str, Any]]:
    """Load and optionally validate a YAML file."""
    try:
        data = load_yaml_file(file_path)
        
        # Apply validation if provided
        if validate_func and not validate_func(data):
            logger.warning(f"Validation failed for {file_path}")
            return None
        
        return data
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        raise


def scan_directory_structure(
    root: Union[str, Path],
    max_depth: Optional[int] = None
) -> Dict[str, Any]:
    """
    Scan directory structure and return tree representation.
    
    Args:
        root: Root directory to scan
        max_depth: Maximum depth to scan
        
    Returns:
        Directory tree structure
    """
    root_path = Path(root)
    
    if not root_path.exists():
        return {"error": f"Directory not found: {root}"}
    
    def build_tree(path: Path, current_depth: int = 0) -> Dict[str, Any]:
        tree = {
            "name": path.name,
            "path": str(path),
            "type": "directory" if path.is_dir() else "file"
        }
        
        if path.is_dir() and (max_depth is None or current_depth < max_depth):
            children = []
            try:
                for child in sorted(path.iterdir()):
                    if not child.name.startswith('.'):
                        children.append(build_tree(child, current_depth + 1))
                tree["children"] = children
            except PermissionError:
                tree["error"] = "Permission denied"
        
        return tree
    
    return build_tree(root_path)


def find_files_by_content(
    directory: Union[str, Path],
    content_matcher: Callable[[Dict[str, Any]], bool],
    file_pattern: str = "*.yaml",
    recursive: bool = True
) -> List[Path]:
    """
    Find files where content matches a condition.
    
    Args:
        directory: Directory to search
        content_matcher: Function that returns True for matching content
        file_pattern: File pattern to search
        recursive: Search recursively
        
    Returns:
        List of matching file paths
    """
    matching_files = []
    
    for file_path in find_files(directory, file_pattern, recursive):
        try:
            if file_pattern.endswith('.yaml'):
                content = load_yaml_file(file_path)
            elif file_pattern.endswith('.json'):
                content = load_json_file(file_path)
            else:
                continue
            
            if content_matcher(content):
                matching_files.append(file_path)
                
        except Exception as e:
            logger.debug(f"Skipping {file_path}: {e}")
    
    return matching_files


class DirectoryWatcher:
    """Watch directory for changes (simple polling implementation)."""
    
    def __init__(self, directory: Union[str, Path], pattern: str = "*"):
        self.directory = Path(directory)
        self.pattern = pattern
        self._file_mtimes: Dict[Path, float] = {}
        self._scan_files()
    
    def _scan_files(self):
        """Scan directory and record modification times."""
        self._file_mtimes.clear()
        
        for file_path in find_files(self.directory, self.pattern):
            try:
                self._file_mtimes[file_path] = file_path.stat().st_mtime
            except OSError:
                pass
    
    def get_changes(self) -> Dict[str, List[Path]]:
        """
        Get changes since last scan.
        
        Returns:
            Dict with 'added', 'modified', 'removed' lists
        """
        changes = {
            'added': [],
            'modified': [],
            'removed': []
        }
        
        current_files = {}
        for file_path in find_files(self.directory, self.pattern):
            try:
                mtime = file_path.stat().st_mtime
                current_files[file_path] = mtime
                
                if file_path not in self._file_mtimes:
                    changes['added'].append(file_path)
                elif mtime > self._file_mtimes[file_path]:
                    changes['modified'].append(file_path)
                    
            except OSError:
                pass
        
        # Check for removed files
        for file_path in self._file_mtimes:
            if file_path not in current_files:
                changes['removed'].append(file_path)
        
        # Update state
        self._file_mtimes = current_files
        
        return changes


def batch_process_files(
    files: List[Path],
    processor: Callable[[Path], Any],
    parallel: bool = True,
    max_workers: int = 4
) -> Dict[Path, Any]:
    """
    Process multiple files with a function.
    
    Args:
        files: List of file paths
        processor: Function to process each file
        parallel: Process in parallel
        max_workers: Max parallel workers
        
    Returns:
        Dict mapping file paths to results
    """
    results = {}
    
    if parallel and len(files) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(processor, file): file
                for file in files
            }
            
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    results[file] = future.result()
                except Exception as e:
                    results[file] = {"error": str(e)}
    else:
        for file in files:
            try:
                results[file] = processor(file)
            except Exception as e:
                results[file] = {"error": str(e)}
    
    return results