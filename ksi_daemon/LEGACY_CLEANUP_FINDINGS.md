# KSI Daemon Legacy Cleanup Findings

## Summary
This document summarizes findings from a systematic review of the ksi_daemon codebase to identify legacy and backward-compatible code that can be removed.

## Files Identified for Removal

### 1. Backup/Original Files (Can be removed immediately)
- `ksi_daemon/__init___original.py` - Original version of __init__.py, no active imports
- `ksi_daemon/command_registry_original.py` - Original command registry, no active imports  
- `ksi_daemon/commands/completion_with_worker.py.bak` - Old completion handler with background worker

### 2. Legacy DI Implementation Files (Can be removed)
- `ksi_daemon/__init___di.py` - Only imported by command_registry_di.py
- `ksi_daemon/command_registry_di.py` - Contains CommandHandlerProxy but no active usage

### 3. Python Cache Files (Safe to remove)
All `__pycache__` directories and `.pyc` files throughout the codebase

## Architecture Analysis

### Current Architecture (Active)
- **Entry Point**: `ksi-daemon.py` → `ksi_daemon/__init__.py`
- **Core**: `KSIDaemonCore` from `core.py`
- **Commands**: Self-registering decorators in `command_registry.py`
- **DI**: `di_container.py` with aioinject
- **Event System**: `message_bus.py` (actively used)

### Plugin Architecture (Future - 90% Complete)
- **Status**: NEW architecture being actively developed, NOT experimental
- **Files**: `core_plugin.py`, `plugin_manager.py`, `plugin_loader.py`, `event_bus.py`
- **Progress**: In "Compatibility Mode" - legacy commands mapped to events
- **Migration Path**: Compatibility → Hybrid → Pure Event Mode

## Key Findings

### 1. Successful Aioinject Refactoring
- All command handlers are now stateless (per AIOINJECT_REFACTORING.md)
- No `initialize()` methods found in handlers
- No background workers or queues in handlers
- `asyncio.create_task()` usage is appropriate for one-time operations

### 2. Event System Clarification
- **message_bus.py**: Primary event system (production)
- **enhanced_message_bus.py**: Extended version with backward compatibility
- **event_bus.py**: Part of new plugin architecture (not yet in production)

### 3. Deprecated Code Patterns Found
- `send_text_response()` in command_handler.py - marked deprecated
- Factory function in enhanced_message_bus.py for backward compatibility
- `track_session_output()` in session_manager - legacy naming

### 4. Test Considerations
Tests may be written for outdated pre-refactor parts. It's acceptable to remove old code even if tests exist for it, as tests are being rewritten in parallel.

## Recommendations

### Immediate Actions
1. Remove all files with `_original` and `.bak` suffixes
2. Remove `*_di.py` files (legacy DI attempt)
3. Clean up all `__pycache__` directories

### Future Considerations
1. Complete plugin architecture (10% remaining per PLUGIN_ARCHITECTURE.md)
2. Remove deprecated `send_text_response()` method after compatibility period
3. Consider consolidating message_bus implementations after plugin migration

### Do NOT Remove
1. Plugin architecture files - actively being developed
2. Current command handlers - working production code
3. manager_framework.py - still used by managers
4. Any files in plugins/ directory - part of new architecture

## Migration Status
- Plugin architecture is the future, not abandoned code
- Currently running hybrid system during transition
- Full migration planned but not yet complete

---
*Generated: 2025-06-24*
*Review Status: Complete*