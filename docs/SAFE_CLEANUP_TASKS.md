# Safe Cleanup Tasks for KSI

These cleanup tasks have been verified as safe to perform without affecting intended functionality.

## Completed Cleanups (2025-06-29)

### 1. ✅ Remove Multi-Socket References
- **Files**: README.md, tests/test_event_client.py
- **Changes**: Updated to reflect single socket architecture
- **Commit**: 3f6b04e

### 2. ✅ Update Test Files
- **File**: `tests/test_event_client.py`
- **Changes**: Removed legacy compatibility test and references
- **Commit**: 3f6b04e

### 3. ✅ Clean Migration Scripts
- **File**: `tools/migrate_to_unified_compositions.py`
- **Changes**: Moved to `tools/archive/migrate_to_unified_compositions_20250629.py`
- **Commit**: 3f6b04e

### 4. ✅ Update Placeholder TODOs
- **File**: `interfaces/monitor_textual.py:76`
- **Changes**: Updated TODO to feature request comment
- **Commit**: 3f6b04e

### 5. ✅ Remove Legacy JSON Profile Code
- **Files**: `ksi_common/paths.py`, `ksi_client/profile_loader.py`, `interfaces/chat_textual.py`
- **Changes**: Removed dead JSON profile loading code
- **Commit**: 71ae525

### 6. ✅ Remove Legacy Prompt Path Fallback
- **File**: `ksi_daemon/plugins/composition/composition_service.py`
- **Changes**: Removed fallback to non-existent var/prompts
- **Commit**: 71ae525

## Investigated and Completed

### 1. ✅ Profile Loader Fallbacks
- **Investigation**: No code generates JSON profiles anymore
- **Action taken**: Removed all JSON profile loading code
- **Result**: System fully uses YAML compositions

### 2. ✅ Legacy Prompt Paths
- **Investigation**: var/prompts directory doesn't exist
- **Action taken**: Removed fallback code
- **Result**: All prompts use var/lib/compositions/prompts

## Cleanups NOT to Perform

### 1. Injection Router TODOs
- **Reason**: Core functionality pending implementation
- **Action**: Keep and track in project roadmap

### 2. Session Management "Legacy" Methods
- **Reason**: Part of session federation design
- **Action**: Rename methods to clarify intent

### 3. Completion Queue Cancellation
- **Reason**: Needed for graceful shutdown
- **Action**: Implement when addressing shutdown issues

## Cleanup Process

1. **Verify intent**: Check git history and design docs
2. **Test impact**: Run full test suite after changes
3. **Document changes**: Update project_knowledge.md
4. **Commit atomically**: One cleanup type per commit

## Next Safe Cleanup: Multi-Socket References

The safest immediate cleanup is removing multi-socket references from documentation since the system is fully migrated to single socket architecture.