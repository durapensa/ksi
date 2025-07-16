"""KSI root directory detection utilities.

Provides functions to reliably find the KSI project root directory
from any location within the project or when installed.
"""

import os
from pathlib import Path
from typing import Optional


def find_ksi_root() -> Optional[Path]:
    """Find the KSI project root directory.
    
    Searches for the KSI root using multiple strategies:
    1. KSI_ROOT environment variable
    2. Current file location (if in ksi_common)
    3. Search upward for pyproject.toml with ksi metadata
    4. Search for ksi_common directory in parent paths
    
    Returns:
        Path to KSI root directory, or None if not found
    """
    # Strategy 1: Check KSI_ROOT environment variable
    if ksi_root_env := os.environ.get('KSI_ROOT'):
        root = Path(ksi_root_env)
        if root.exists() and (root / 'ksi_common').exists():
            return root
    
    # Strategy 2: If this file is in ksi_common, go up one level
    current_file = Path(__file__).resolve()
    if current_file.parent.name == 'ksi_common':
        return current_file.parent.parent
    
    # Strategy 3: Search upward for pyproject.toml with KSI metadata
    current = Path.cwd().resolve()
    while current != current.parent:
        pyproject = current / 'pyproject.toml'
        if pyproject.exists():
            # Simple check for KSI project
            try:
                content = pyproject.read_text()
                if 'name = "ksi"' in content or 'name = \'ksi\'' in content:
                    return current
            except Exception:
                pass
        current = current.parent
    
    # Strategy 4: Search for ksi_common directory
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / 'ksi_common').exists() and (current / 'ksi_common' / '__init__.py').exists():
            return current
        current = current.parent
    
    return None


def get_ksi_root() -> Path:
    """Get the KSI project root directory.
    
    Returns:
        Path to KSI root directory
        
    Raises:
        RuntimeError: If KSI root cannot be found
    """
    root = find_ksi_root()
    if root is None:
        raise RuntimeError(
            "Cannot find KSI root directory. Please ensure you are running "
            "from within the KSI project or set the KSI_ROOT environment variable."
        )
    return root


def is_in_ksi_project() -> bool:
    """Check if currently running from within a KSI project.
    
    Returns:
        True if in KSI project, False otherwise
    """
    return find_ksi_root() is not None