# Next Session TODO - Daemon Refactoring

## 🎯 PRIORITY: Complete System Control Commands Migration

**Current Progress**: 23/29 commands migrated (79%)
**Remaining**: Only 6 commands left!

### Immediate Tasks

#### 1. System Control Commands (Priority 5 - 3 commands)
- [x] **RELOAD_MODULE** - Module reload functionality (completed)
- [ ] **RELOAD_DAEMON** - Hot reload daemon
- [ ] **SHUTDOWN** - Graceful shutdown

#### 2. Final Remaining Commands (3 commands)  
- [ ] **LOAD_STATE** - Load saved state
- [ ] **MESSAGE_BUS_STATS** - Get message bus statistics
- [ ] **AGENT_CONNECTION** - Handle agent connections

### Implementation Approach

**For System Control Commands**:
1. Check existing handlers in `daemon/json_handlers.py` (around lines 683-700)
2. Create parameter models in `daemon/models.py` if needed
3. Follow established patterns from composition system migration
4. Use `@command_handler` decorator with comprehensive validation
5. Add to `daemon/commands/__init__.py`

**Key Files to Reference**:
- `daemon/json_handlers.py` - Existing implementations
- `daemon/commands/` - Migration patterns
- `daemon/models.py` - Parameter model definitions
- `tests/test_migrated_commands.py` - Test patterns

### Session Start Instructions

1. **Read Context**: 
   - `memory/claude_code/project_knowledge.md` - Recent work completed
   - `daemon/REFACTORING_TODO.md` - Current progress & remaining tasks

2. **Quick Migration Strategy**:
   - Start with RELOAD_MODULE, RELOAD_DAEMON, SHUTDOWN (similar functionality)
   - Then finish LOAD_STATE, MESSAGE_BUS_STATS, AGENT_CONNECTION
   - Update tests, progress tracking, and documentation
   - Clean up legacy handlers when complete

3. **Final Cleanup After Migration**:
   - Remove legacy handler dictionary from `command_handler.py`
   - Delete `json_handlers.py` entirely
   - Update documentation to reflect 100% migration
   - Run comprehensive tests

### Recent Accomplishments

**Just Completed** (23 commands total):
- ✅ Identity Management (5): CREATE_IDENTITY, UPDATE_IDENTITY, GET_IDENTITY, LIST_IDENTITIES, REMOVE_IDENTITY
- ✅ Composition System (5): GET_COMPOSITIONS, GET_COMPOSITION, VALIDATE_COMPOSITION, LIST_COMPONENTS, COMPOSE_PROMPT
- ✅ Agent Management (4): REGISTER_AGENT, GET_AGENTS, SPAWN_AGENT, ROUTE_TASK
- ✅ Message Bus (2): SUBSCRIBE, PUBLISH
- ✅ State Management (2): SET_SHARED, GET_SHARED
- ✅ Process Control (2): CLEANUP, SPAWN
- ✅ System Status (3): HEALTH_CHECK, GET_COMMANDS, GET_PROCESSES

**Enhanced Patterns Established**:
- Standardized list responses with metadata
- Rich error messages with suggestions
- Complete object returns
- Comprehensive validation & testing
- Smart discovery with similarity matching

### Final Goal

**100% Migration Complete** - Transform the daemon from legacy if/elif chains to modern command registry pattern with:
- Type-safe Pydantic validation
- Consistent API patterns  
- Comprehensive error handling
- Rich help documentation
- Ready for simpervisor integration

**Next session should complete the final 6 commands and achieve 100% migration!**