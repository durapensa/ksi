"""Common utilities for KSI.

Provides utility functions used across KSI components.

DEPRECATED: Most functions have been removed as they were thin wrappers.
- generate_id: Use uuid.uuid4().hex[:8] directly
- generate_correlation_id: Use str(uuid.uuid4()) directly
- read_json_file/write_json_file: Use ksi_daemon.file_operations functions
- merge_dicts: Use dict.update() or {**base, **updates} for shallow merge
"""

import uuid
from typing import Optional


# Deprecated functions kept for backward compatibility
def generate_id(prefix: Optional[str] = None) -> str:
    """DEPRECATED: Use uuid.uuid4().hex[:8] directly."""
    unique_part = uuid.uuid4().hex[:8]
    if prefix:
        return f"{prefix}_{unique_part}"
    return unique_part


def generate_correlation_id() -> str:
    """DEPRECATED: Use str(uuid.uuid4()) directly."""
    return str(uuid.uuid4())