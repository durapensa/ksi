#!/usr/bin/env python3
"""
Component hashing utility for evaluation tracking.
Generates stable SHA-256 hashes for component content.
"""
import hashlib
import re
from pathlib import Path
from typing import Optional

def normalize_content(content: bytes) -> bytes:
    """Normalize component content for stable hashing."""
    # Normalize line endings
    content = content.replace(b'\r\n', b'\n')
    # Remove trailing whitespace from lines
    lines = content.split(b'\n')
    normalized_lines = [line.rstrip() for line in lines]
    return b'\n'.join(normalized_lines)

def extract_version(content: str) -> Optional[str]:
    """Extract version from component frontmatter."""
    # Look for version in YAML frontmatter
    version_match = re.search(r'^version:\s*["\']?([0-9.]+)["\']?', content, re.MULTILINE)
    if version_match:
        return version_match.group(1)
    return None

def hash_component(component_path: Path) -> tuple[str, Optional[str]]:
    """
    Generate SHA-256 hash for component content.
    Returns (hash, version) tuple.
    """
    with open(component_path, 'rb') as f:
        content = f.read()
    
    normalized = normalize_content(content)
    sha256_hash = hashlib.sha256(normalized).hexdigest()
    
    # Try to extract version
    try:
        text_content = content.decode('utf-8')
        version = extract_version(text_content)
    except:
        version = None
    
    return f"sha256:{sha256_hash}", version

def hash_component_at_path(path: str) -> dict:
    """Hash a component and return metadata."""
    component_path = Path(path)
    if not component_path.exists():
        raise FileNotFoundError(f"Component not found: {path}")
    
    hash_value, version = hash_component(component_path)
    
    # Extract component type from path
    parts = component_path.parts
    if 'components' in parts:
        idx = parts.index('components')
        if idx + 1 < len(parts):
            component_type = parts[idx + 1]
        else:
            component_type = 'unknown'
    else:
        component_type = 'unknown'
    
    return {
        'path': str(component_path),
        'hash': hash_value,
        'version': version,
        'type': component_type,
        'filename': component_path.name
    }

if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python hash_component.py <component_path>")
        sys.exit(1)
    
    try:
        result = hash_component_at_path(sys.argv[1])
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)