# Safe Cleanup Tasks for KSI

These cleanup tasks have been verified as safe to perform without affecting intended functionality.

## Confirmed Safe Cleanups

### 1. Remove Multi-Socket References
- **Files**: README.md, tests, documentation
- **Reason**: System fully migrated to single socket architecture
- **Safe because**: No code depends on multi-socket patterns

### 2. Update Test Files
- **File**: `tests/test_event_client.py`
- **Task**: Remove "legacy format compatibility" comments
- **Safe because**: Tests should reflect current architecture

### 3. Clean Migration Scripts
- **File**: `tools/migrate_to_unified_compositions.py`
- **Task**: Move to `tools/archive/` with timestamp
- **Safe because**: Migration is complete, but preserve for reference

### 4. Update Placeholder TODOs
- **File**: `interfaces/monitor_textual.py:76`
- **Task**: Change "TODO: Get real memory metrics" to documented feature request
- **Safe because**: It's a future enhancement, not incomplete work

## Cleanups Requiring Investigation

### 1. Profile Loader Fallbacks
- **Investigation needed**: Are JSON profiles still generated anywhere?
- **If no**: Can remove JSON loading code
- **If yes**: Document where and why

### 2. Legacy Prompt Paths
- **Investigation needed**: Do any deployments still have var/prompts?
- **If no**: Remove fallback code
- **If yes**: Add migration guide

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