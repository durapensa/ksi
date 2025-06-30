# Configuration Migration Strategy

## Overview

This document outlines the strategy for migrating KSI components to use the shared `ksi_common` configuration with pydantic-settings.

## Current State

- **ksi_common**: Now has `KSIBaseConfig` with pydantic-settings
- **ksi_daemon**: Has its own `KSIConfig` with many daemon-specific settings
- **ksi_client**: No formal config, hardcoded paths
- **ksi_admin**: No formal config
- **interfaces**: `chat_textual.py` now uses ksi_common config

## Migration Plan

### Phase 1: ksi_daemon Migration

1. **Option A: Inheritance** (Recommended)
   ```python
   # ksi_daemon/config.py
   from ksi_common import KSIBaseConfig
   
   class KSIConfig(KSIBaseConfig):
       # Add daemon-specific fields
       pid_file: Path = Path("var/run/ksi_daemon.pid")
       db_path: Path = Path("var/db/agent_shared_state.db")
       # ... etc
   ```

2. **Option B: Composition**
   ```python
   # Keep existing KSIConfig but use ksi_common for shared paths
   from ksi_common import config as base_config
   
   # Use base_config.socket_path, etc.
   ```

### Phase 2: ksi_client Migration

```python
# ksi_client/__init__.py or ksi_client/config.py
from ksi_common import config

# Use config.socket_path directly
# Or extend if client needs specific settings:
class ClientConfig(KSIBaseConfig):
    retry_attempts: int = 3
    connection_timeout: float = 10.0
```

### Phase 3: ksi_admin Migration

Similar to ksi_client, use the base config directly.

## Benefits of Shared Configuration

1. **Environment Variable Consistency**
   ```bash
   # Works for ALL components
   export KSI_SOCKET_PATH=/custom/daemon.sock
   export KSI_LOG_LEVEL=DEBUG
   ```

2. **Single Source of Truth**
   - Socket path defined once
   - Log directories consistent
   - Timeout values shared

3. **Easy Testing**
   ```python
   # In tests
   os.environ['KSI_SOCKET_PATH'] = '/tmp/test.sock'
   from ksi_common import reload_config
   reload_config()
   ```

4. **Docker/Kubernetes Ready**
   ```yaml
   # docker-compose.yml
   environment:
     - KSI_SOCKET_PATH=/var/ksi/daemon.sock
     - KSI_LOG_LEVEL=INFO
     - KSI_LOG_FORMAT=json
   ```

## Environment Variables Reference

### Base Configuration (ksi_common)
- `KSI_SOCKET_PATH` - Unix socket path
- `KSI_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `KSI_LOG_FORMAT` - Log format (json, console)
- `KSI_LOG_DIR` - Log directory
- `KSI_SESSION_LOG_DIR` - Session logs directory
- `KSI_STATE_DIR` - State directory
- `KSI_SOCKET_TIMEOUT` - Socket timeout in seconds
- `KSI_DEBUG` - Enable debug mode

### Daemon Extensions (ksi_daemon)
- `KSI_PID_FILE` - Daemon PID file path
- `KSI_DB_PATH` - SQLite database path
- `KSI_COMPLETION_TIMEOUT_DEFAULT` - Default completion timeout
- ... (all other daemon-specific settings)

## Testing Strategy

1. **Unit Tests**
   ```python
   def test_config_override():
       os.environ['KSI_SOCKET_PATH'] = '/test/path.sock'
       config = KSIBaseConfig()
       assert config.socket_path == Path('/test/path.sock')
   ```

2. **Integration Tests**
   - Start daemon with custom env vars
   - Verify all components connect to correct socket

3. **Backward Compatibility**
   - Keep existing imports working during transition
   - Gradual migration per component

## Implementation Timeline

1. **Week 1**: Update ksi_daemon to inherit from KSIBaseConfig
2. **Week 2**: Update ksi_client and ksi_admin
3. **Week 3**: Update all interfaces and tools
4. **Week 4**: Remove old config code, update documentation

## Code Examples

### Using Shared Config in New Code
```python
from ksi_common import config

# Direct usage
client = AsyncClient(socket_path=str(config.socket_path))

# With environment override
# KSI_SOCKET_PATH=/tmp/custom.sock python my_script.py
```

### Extending Config for Component
```python
from ksi_common import KSIBaseConfig

class MyComponentConfig(KSIBaseConfig):
    # Inherits all base settings
    # Add component-specific settings
    my_setting: str = "default"
    my_timeout: int = 30

config = MyComponentConfig()
```

### .env File Support
```bash
# .env file in project root
KSI_SOCKET_PATH=/custom/daemon.sock
KSI_LOG_LEVEL=DEBUG
KSI_LOG_FORMAT=json
```

All components will automatically load these settings.