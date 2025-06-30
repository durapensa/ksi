# Unified Structured Logging Migration

## Overview
Migrated all KSI components to use a unified structured logging system based on structlog.
Previously, different components used different logging approaches:
- ksi_daemon: Had its own structlog configuration
- ksi_client/ksi_admin: Used standard Python logging
- interfaces: Mixed usage, with chat_textual.py missing logger definition

## Changes Made

### 1. Created Unified Logging in ksi_common
- **File**: `ksi_common/logging.py`
- Moved all structlog configuration from ksi_daemon to ksi_common
- Provides structured logging with:
  - Automatic context propagation (request IDs, session IDs)
  - JSON or console output formats
  - TUI-aware configuration (disables console output in Textual apps)
  - Context managers for operations, commands, and agents

### 2. Updated ksi_common Exports
- Added logging utilities to `ksi_common/__init__.py`
- Exported functions:
  - `get_logger()` - Get a structured logger instance
  - `configure_structlog()` - Configure logging system
  - Context managers and utilities

### 3. Migrated Components

#### ksi_daemon
- Converted `ksi_daemon/logging_config.py` to a compatibility wrapper
- Removed structlog configuration from `ksi_daemon/config.py`
- Updated `plugin_utils.py` to use structured logging

#### ksi_client
- Updated `event_client.py` to use `get_logger(__name__)`
- Updated `utils.py` to use structured logging

#### ksi_admin
- Updated all modules to use structured logging:
  - `base.py`
  - `monitor.py`
  - `control.py`
  - `debug.py`
  - `metrics.py`

#### interfaces
- Fixed `chat_textual.py` missing logger error
- Updated to use structured logging with TUI support
- Configured to log to file only (no console output in TUI mode)

## Benefits

1. **Consistent Logging**: All components now use the same logging system
2. **Structured Data**: JSON format available for production use
3. **Context Propagation**: Request IDs and other context automatically included
4. **Better Debugging**: Correlation IDs help trace requests across components
5. **TUI Support**: Automatic detection prevents console corruption
6. **Centralized Configuration**: Single place to configure logging behavior

## Usage Examples

### Basic Usage
```python
from ksi_common import get_logger

logger = get_logger(__name__)
logger.info("operation.started", user_id=123, action="login")
```

### With Context
```python
from ksi_common import async_operation_context

async with async_operation_context(request_id="abc-123", user_id=456):
    logger.info("processing.request")  # Context automatically included
```

### Configuration
```python
from ksi_common import configure_structlog

# For daemon/CLI apps
configure_structlog(
    log_level="INFO",
    log_format="json",  # or "console"
    log_file=Path("app.log")
)

# For TUI apps (automatically disables console)
configure_structlog(
    log_level="INFO",
    log_format="console",
    log_file=Path("app.log"),
    disable_console_in_tui=True
)
```

## Output Formats

### Console Format (Development)
```
2025-06-26T13:49:06.554455Z [info     ] Event listener started for client chat_test [ksi_client.event_client]
```

### JSON Format (Production)
```json
{
  "event": "Event listener started for client chat_test",
  "logger": "ksi_client.event_client",
  "level": "info",
  "timestamp": "2025-06-26T13:49:06.554455Z",
  "request_id": "abc-123"
}
```

## Migration Complete
All KSI components now use unified structured logging from ksi_common.