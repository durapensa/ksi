# Broken Tests Summary

## Tests with Import Errors

### 1. `tests/test_refactored_components.py`
**Error**: `ModuleNotFoundError: No module named 'daemon.utils'`
- Line 28: `from daemon.utils import UtilsManager`
- The `daemon.utils` module doesn't exist - there's no `utils.py` file in the daemon directory
- UtilsManager class is not found anywhere in the codebase

### 2. `tests/test_refactoring_integration.py`
**Error**: `ImportError: cannot import name 'DaemonClient' from partially initialized module 'daemon_client'`
- Circular import issue when importing from `prompts.discovery`
- The import chain: test → prompts.composition_selector → prompts.discovery → daemon_client
- This creates a circular dependency

### 3. Missing SyncClient
- The `daemon.client` module mentions SyncClient in docstrings but doesn't actually implement it
- Only AsyncClient is available in `daemon.client.async_client`
- No test files are directly importing SyncClient, so this isn't causing immediate failures

## Tests Requiring Daemon Running

### 4. `tests/test_daemon_protocol.py`
- Requires the daemon to be running (`python3 daemon.py`)
- Not technically broken, just needs the daemon socket to exist

## Other Potential Issues

### 5. Tests importing from `daemon.protocols`
- `tests/test_refactored_components.py` and `tests/test_refactoring_integration.py` import from `daemon.protocols`
- The protocols module exists and exports are properly defined, but dependent imports may fail

### 6. Tests in root directory vs tests/ directory
- Several test files exist in the project root: `test_spawn_no_tools.py`, `test_daemon_integration.py`, etc.
- This inconsistent organization could lead to import path issues

## Recommendations

1. **Remove or fix** the import of `daemon.utils.UtilsManager` in `test_refactored_components.py`
2. **Resolve circular import** in the prompts modules used by `test_refactoring_integration.py`
3. **Move all test files** to the `tests/` directory for consistency
4. **Add SyncClient implementation** if it's needed, or remove references to it
5. **Create a test runner** that ensures the daemon is running for integration tests