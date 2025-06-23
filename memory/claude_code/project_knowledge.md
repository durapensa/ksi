# KSI Project Knowledge for Claude Code

## Project Overview
Minimal daemon system for managing Claude processes with conversation continuity.

## ✅ COMPLETED Development Tasks
- **Daemon Refactoring**: ✅ **FULLY COMPLETE** - See `docs/refactoring_final_status.md` for summary
  - 29/29 commands migrated (100%) using command registry pattern
  - Manager APIs standardized for simpervisor migration
  - All priorities completed: Process Control, Agent Management, Message Bus, Identity Management, Composition System, System Control, and Other commands
  - Legacy handler dictionary removed - clean modern architecture achieved

### Important Patterns & Gotchas Discovered
1. **Parameter Model Conflicts**: Watch for duplicate parameter models between `models.py` and command handlers
   - Command handlers should NOT redefine parameter models if they exist in models.py
   - If a handler needs different validation, update the model in models.py
2. **Legacy Schema Validation**: The old `command_schemas.py` (now `legacy_command_schemas.py`) can interfere
   - It's only used by GET_COMMANDS for listing commands
   - Don't rely on it for validation
3. **Response Patterns**: Use `ResponseFactory.success()` and `ResponseFactory.error()`
   - Error responses don't support extra kwargs like `details`
   - Include rich information in the error message string instead
4. **Testing Pattern**: Expected errors are successes!
   - SUBSCRIBE without connection should error
   - PUBLISH with invalid payload should error
   - These are correct behaviors, not test failures

### ✅ Recent Session COMPLETED (2025-06-23 PM)

**Composition System Commands Migration** - All 5 commands successfully migrated:
- ✅ GET_COMPOSITIONS - List compositions with metadata and filtering
- ✅ GET_COMPOSITION - Get detailed composition info with validation status
- ✅ VALIDATE_COMPOSITION - Comprehensive validation of composition and context
- ✅ LIST_COMPONENTS - List components with directory structure and previews
- ✅ COMPOSE_PROMPT - Generate prompts with analysis and warnings

**Enhanced Features Implemented**:
- Rich composition discovery with similarity matching
- Comprehensive validation workflow (structure + context + test composition)
- Component organization by directory with size and preview information
- Prompt analysis (length, tokens, unresolved variables)
- Detailed error messages with suggestions for all edge cases
- 14 comprehensive test cases covering all operations and error conditions

**Earlier Today - Identity Management Commands Migration** - All 5 commands successfully migrated:
- ✅ CREATE_IDENTITY - Create identity with comprehensive validation
- ✅ UPDATE_IDENTITY - Update identity with change tracking
- ✅ GET_IDENTITY - Get identity with enhanced error messages
- ✅ LIST_IDENTITIES - List all with filtering and sorting
- ✅ REMOVE_IDENTITY - Remove identity with undo support

**API Patterns Established**:
- Standardized list responses: `{items: [...], total: N, metadata: {...}}`
- Rich error messages with suggestions and available options
- Full object returns (no partial data)
- Change tracking for updates
- Undo support for deletions
- Comprehensive help documentation with examples

### Next Session TODO
1. **Continue Command Migration** - Priority 5: System Control (3 commands)
   - RELOAD_MODULE - Reload module
   - RELOAD_DAEMON - Hot reload daemon
   - SHUTDOWN - Graceful shutdown

3. **Test Pattern**: Use `tests/test_migrated_commands.py` as template
4. **Migration Pattern**: See template in `daemon/REFACTORING_TODO.md`
5. **Key Files**:
   - `daemon/command_registry.py` - Command registration system
   - `daemon/models.py` - Parameter models (check COMMAND_PARAMETER_MAP)
   - `daemon/commands/` - Individual command handlers
   - `daemon/base_manager.py` - Base manager with decorators

## Recent Changes (2025-06-23)

### Command Migration Progress - Phase 2 (PM Session)
- **Migrated 6 additional commands** bringing total to 13/29 (45%)
- **Agent Management Commands**:
  - REGISTER_AGENT: Now uses standardized `create_agent()` API
  - GET_AGENTS: Uses `list_agents()` API with consistent response format
  - SPAWN_AGENT: Enhanced with full agent object returns and selection metadata
  - ROUTE_TASK: Comprehensive routing with actual message delivery via message bus
- **Message Bus Commands**:
  - SUBSCRIBE: Rich error messages and subscription status reporting
  - PUBLISH: Enhanced validation and event-specific response structures
- **API Improvements**:
  - Standardized response structures (full objects, not just IDs)
  - Rich error messages with suggestions and context
  - Comprehensive help text with examples
  - Pydantic validation for all parameters
- **Created test suite**: `tests/test_migrated_commands.py` for validation
- **Removed Fallbacks**:
  - Renamed `command_schemas.py` to `legacy_command_schemas.py` to prevent confusion
  - Fixed parameter model conflicts (SpawnAgentParameters, SetSharedParameters)
  - Removed old handler mappings from command_handler.py
  - SET_SHARED now properly accepts any JSON value, not just strings
- **Test Results**: 100% success rate (10/10 functional tests pass, 4/4 error tests correctly fail)

### Earlier Today - Major Daemon Refactoring
- **Major Daemon Refactoring**: Comprehensive refactoring to eliminate if/elif chains and improve code quality
  - Added Pydantic models for type-safe command/response validation
  - Implemented base manager pattern to eliminate code duplication
  - Replaced 50+ line if/elif chains with strategy pattern
  - Created command registry for self-registering commands
  - Centralized file operations with retry logic
  - Achieved ~35% code reduction with better patterns
  - Added packages: pydantic (v2.5.0+), structlog (v24.1.0+), tenacity (v8.2.0+)
  - See `daemon/REFACTORING_SUMMARY.md` for full details

- **Command Registry Integration** (2025-06-23 PM):
  - Created `daemon/commands/` directory for individual command handlers
  - Integrated command registry into `command_handler._route_command()`
  - Registry checks first, falls back to legacy handlers
  - Commands use `@command_handler` decorator for auto-registration
  - Each command is now a separate class with validation and help
  - Progress: 7/29 commands migrated (24%):
    - Process Control: CLEANUP, SPAWN
    - System Status: HEALTH_CHECK, GET_COMMANDS, GET_PROCESSES
    - State Management: SET_SHARED, GET_SHARED

- **Manager API Standardization** (2025-06-23 PM):
  - Standardized all manager APIs for simpervisor migration:
    - `list_x()` → List[Dict] for listing all
    - `get_x(id)` → Optional[Dict] for getting one
    - `create_x(data)` → str for creating (return ID)
    - `update_x(id, data)` → bool for updating
    - `remove_x(id)` → bool for deleting
    - `clear_x()` → int for clearing all (return count)
  - Fixed ClaudeProcessManager: `running_processes` → `processes`
  - Updated all managers with standardized methods
  - Ready for simpervisor migration in future session

## Recent Changes (2025-06-21)
- **JSON Prefix Removal**: Renamed classes to remove redundant "JSON" prefixes:
  - `JSONCommandBuilder` → `CommandBuilder`
  - `JSONResponseHandler` → `ResponseHandler`
  - `JSONConnectionManager` → `ConnectionManager`
  - `JSONCommandHandlers` → `CommandHandlers`
  - `json_handlers` instance → `handlers`
  - `command_json` variables → `command_str` (when it's the serialized string)
  - `JSONSCHEMA_AVAILABLE` → `SCHEMA_VALIDATION_AVAILABLE`
- These changes improve clarity by removing redundant naming since the entire protocol is JSON-based

## Architecture

### Core Components
- **daemon.py**: Modular async daemon with multi-agent coordination capabilities
- **daemon/**: Modular daemon architecture (core, state_manager, agent_manager, etc.)
- **chat.py**: Simple interface for chatting with Claude
- **claude_modules/**: Python modules for extending daemon functionality
- **prompts/**: Prompt composition system for modular prompt building

### How It Works
1. Daemon receives commands via Unix socket
2. Spawns: `claude --model sonnet --print --output-format json --allowedTools "..." --resume sessionId`
3. Logs all sessions to `claude_logs/<session-id>.jsonl` in JSONL format
4. Uses `--resume sessionId` for conversation continuity

### Daemon Command System
**Unified SPAWN Command** (as of 2025-06-21):
- Format: `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>`
- Examples:
  - `SPAWN:sync:claude::sonnet::Hello world`
  - `SPAWN:async:claude:session123:sonnet:agent1:Complex task`

**Command Organization**:
- Total: ~20 commands organized into functional groups
- Groups: Process Spawning, Agent Management, Communication & Events, State Management, System Management
- Aliases available: `S:` → `SPAWN:`, `RM:` → `RELOAD_MODULE:`, `SA:` → `SPAWN_AGENT:`, etc.
- Use `GET_COMMANDS` to discover all available commands dynamically

**GET_COMMANDS Response** (enhanced 2025-06-21):
```json
{
  "commands": { /* flat list of all commands */ },
  "grouped_commands": { /* commands organized by functional area */ },
  "total_commands": 20,
  "groups": ["Process Spawning", "Agent Management", ...]
}
```

### Prompt Composition System
**Architecture**:
- **composer.py**: Composition engine using simple string replacement
- **components/**: Reusable markdown templates with `{{variable}}` placeholders
- **compositions/**: YAML recipes defining which components to include

**How Claude Agents Use It**:
1. Call `GET_COMMANDS` to get available daemon commands
2. Pass commands as `daemon_commands` context to prompt composer
3. Composer replaces `{{daemon_commands}}` with stringified JSON

**Known Limitation**: 
- Template engine only does simple string replacement
- Handlebars syntax (`{{#each}}`) in components doesn't work
- Despite this, Claude agents still receive command info as JSON string

### Tool Usage Signaling (Added 2025-06-21)
**Implementation**:
- Agent profiles can set `enable_tools: true/false` to control tool access
- When enabled, agents spawn with `--allowedTools` flag
- Tool signaling component instructs agents to use `[TOOL_USE]` markers
- Command handler checks agent profile for tool settings

**Components**:
- `prompts/components/tool_signaling.md` - Tool usage instructions
- `claude_agent_default.yaml` - Updated to include tool signaling
- Enhanced logging captures tool_calls from Claude output

### Composition Discovery System (Added 2025-06-21)
**Implementation**:
- Added 5 new daemon commands for composition discovery
- Commands: GET_COMPOSITIONS, GET_COMPOSITION, VALIDATE_COMPOSITION, LIST_COMPONENTS, COMPOSE_PROMPT
- All commands validated with JSON schemas in SYSTEM_STATUS category
- Created `prompts/discovery.py` module for unified discovery interface

**Features**:
- List all compositions with metadata filtering
- Get detailed composition information including components
- Validate context against composition requirements
- List all available components organized by directory
- Compose prompts directly via daemon
- Fallback to direct file access if daemon unavailable

**Usage**:
- `GET_COMPOSITIONS` - Returns all compositions with metadata
- `GET_COMPOSITION:name` - Returns full composition details
- `VALIDATE_COMPOSITION:name:context` - Validates context completeness
- `LIST_COMPONENTS` - Returns all components grouped by directory
- `COMPOSE_PROMPT:composition:context` - Composes and returns prompt

**Discovery Module** (`prompts/discovery.py`):
- Provides high-level API for composition discovery
- Supports finding compositions by capability, role, or task
- Includes CLI interface for exploration
- Enables dynamic composition selection by agents

**Dynamic Composition Selection** (Completed 2025-06-21):
- Created `prompts/composition_selector.py` with intelligent scoring algorithm
- Multi-factor scoring: role match (30%), capabilities (25%), task relevance (25%), style (10%), quality (10%)
- Integrated into `daemon/agent_process.py` - agents now dynamically select compositions
- Performance-optimized with 5-minute TTL cache
- Created `orchestrate_v3.py` with full dynamic discovery
- Agents adapt their prompts based on role, capabilities, and current task

### Multi-Agent Infrastructure Status
**Implementation**: Core components operational with recent architectural improvements
- **Agent Registry**: `REGISTER_AGENT`, `GET_AGENTS` commands available
- **Inter-Agent Communication**: Message bus system with event-driven architecture
  - `PUBLISH:from_agent:event_type:json_payload` for sending messages
  - `SUBSCRIBE:agent_id:event_type1,event_type2` for receiving messages
  - `AGENT_CONNECTION:connect|disconnect:agent_id` (new unified command)
- **Shared State Store**: `SET_SHARED`/`GET_SHARED` with file persistence in `shared_state/`
- **Agent Templates**: 15+ profiles in `agent_profiles/` including multi_agent_orchestrator, research_specialist, software_developer, data_analyst, debater, teacher, etc.
- **Task Distribution**: `ROUTE_TASK` with capability-based routing
- **Process Spawning**: `SPAWN_AGENT:profile:task:context:agent_id` for profile-based agent creation

**Key Architectural Principles**:
- **Event-Driven**: No polling, timers, or wait loops - all communication via message bus events
- **SPAWN_AGENT vs SPAWN**: SPAWN_AGENT provides profile templating and auto-registration, justifying its separate existence
- **Command Consolidation**: Recent cleanup removed legacy commands and added aliases

## File Organization (Claude Code Standards)

### Directory Structure
```
ksi/
├── daemon.py, chat.py          # Core system files
├── claude_modules/             # Python extensions
├── autonomous_experiments/     # Autonomous agent outputs
├── cognitive_data/             # Analysis input data
├── memory/                     # Knowledge management system
├── tests/                      # Test files
├── tools/                      # Development utilities
└── logs/                       # System logs
```

### Development Conventions
- **Tests**: Place in `tests/` directory
- **Tools**: Place in `tools/` directory  
- **Logs**: System logs go to `logs/`
- **Scripts**: Temporary scripts should be cleaned up or organized
- **Documentation**: Keep README.md focused on project basics

## Build/Test Commands
```bash
# Start system
python3 daemon.py
python3 chat.py

# Run tests  
python3 tests/test_daemon_protocol.py

# Monitor system
./tools/monitor_autonomous.py
```

## Key Development Principles
- Keep daemon minimal and focused
- Organize files by purpose and audience
- Clean up temporary files promptly
- Document significant changes in appropriate memory stores

## Integration Points
- **Memory system**: Check `memory/` for audience-specific knowledge
- **Autonomous experiments**: Results in `autonomous_experiments/`
- **Cognitive data**: Analysis inputs in `cognitive_data/`

## Known Issues & Fixes

### Monitor TUI Connection Issue (FIXED 2025-06-21)
**Problem**: Monitor would connect but display no data
**Root Cause**: The message bus requires agents to:
1. First call `AGENT_CONNECTION:connect:agent_id` to register the connection
2. Then call `SUBSCRIBE:agent_id:event_types` to subscribe to events

**Solution**: Modified monitor_tui.py to:
- Send AGENT_CONNECTION:connect command first
- Use separate connection for SUBSCRIBE command  
- Keep main connection exclusively for receiving messages
- Enable debug mode by default for troubleshooting

### Claude Node Connection Architecture Issue (FIXED 2025-06-21)
**Problem**: Claude nodes would connect, send 1-2 messages, then disconnect with "Broken pipe" errors
**Root Cause**: agent_process.py (formerly claude_node.py) was using the same connection for:
1. Receiving messages (reader connection from CONNECT_AGENT)
2. Sending commands (PUBLISH, etc.)

This caused the daemon to close the connection when it received a command on a message-receiving connection.

**Solution**: Modified agent_process.py to use separate connections:
- Main connection (`self.reader`/`self.writer`) - exclusively for receiving messages
- Temporary connections for each command send operation:
  - `send_message()` - opens new connection for PUBLISH:DIRECT_MESSAGE
  - `start_conversation()` - opens new connection for PUBLISH:CONVERSATION_INVITE
  - `_subscribe_to_events()` - opens new connection for SUBSCRIBE command

**Additional Fixes**:
- Added allowedTools parameter to Claude CLI command (comma-separated list)
- Fixed Claude output parsing for new CLI format (`type: result` with `result` field)
- Enhanced error handling for broken connections (ConnectionResetError, BrokenPipeError)
- Added detailed logging for Claude CLI failures

### Session 2025-06-21: Major Architecture Improvements

**Command System Unified**:
- Implemented unified SPAWN command: `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>`
- Consolidated AGENT_CONNECTION:connect|disconnect:agent_id (removed legacy CONNECT_AGENT/DISCONNECT_AGENT)
- Added command aliases: S: → SPAWN:, RM: → RELOAD_MODULE:, SA: → SPAWN_AGENT:, etc.
- Enhanced GET_COMMANDS with functional grouping and alias metadata
- Removed deprecated SEND_MESSAGE command (use PUBLISH instead)

**SPAWN_AGENT Fixed for Multi-Agent Support**:
- Problem: Was spawning raw Claude CLI processes that couldn't use message bus
- Solution: Now spawns agent_process.py processes via spawn_agent_process_async()
- Agents can now receive DIRECT_MESSAGE events and participate in conversations
- Cleaned up confusing node/agent terminology throughout

**All Daemon Infrastructure Issues Resolved**:
- GET_AGENTS, SET_SHARED, GET_SHARED all working properly
- Directory creation on startup fixed
- Command handlers executing correctly
- Proper error responses for all commands

**Session 2025-06-21 Additional Improvements**:
- Fixed [END] signal handling - agents now properly terminate
- Renamed claude_node.py to agent_process.py throughout codebase
- Updated CLAUDE.md with mandatory session start instructions
- Cleaned up project root: reduced from 15 to 3 essential .md files
- Organized documentation into docs/features/, docs/analysis/, docs/archive/
- Replaced start-daemon.sh with daemon_control.sh (start|stop|restart|status|health)
- Enhanced daemon commands with better self-documentation and workflow guidance
- Replaced hard-coded ConversationMode with composition-based system
- Created conversation mode compositions: debate, collaboration, teaching, brainstorm, analysis
- Built orchestrate_v2.py using composition-based conversation modes
- Enhanced error handling and logging in PromptComposer and agent_process.py

### Session 2025-06-21: Legacy Code Cleanup
**Backward Compatibility Removed**:
- Removed legacy SPAWN format detection from command_handler.py
- Removed deprecated CONNECT_AGENT/DISCONNECT_AGENT handlers
- Removed deprecated SEND_MESSAGE command handler
- Updated all code to use AGENT_CONNECTION:connect|disconnect instead of legacy commands
- Removed backward compatibility timestamp functions from timestamp_utils.py
- Removed tools/migrate_timestamps.py (no longer needed)
- Removed test_async_spawn.py (functionality covered by test_async_completion.py)
- Updated daemon/core.py to only recognize new AGENT_CONNECTION format

**Files Updated**:
- daemon/command_handler.py: Removed ~100 lines of legacy code
- daemon/timestamp_utils.py: Removed convenience functions
- monitor_tui.py, agent_process.py, claude_agent.py, chat_textual.py: Updated to new commands
- All test files updated to use new command format

### Session 2025-06-21: System Identity Management Implementation
**New Feature: Comprehensive Agent Identity System**:
- **Identity Manager**: Full identity lifecycle management in `daemon/identity_manager.py`
- **Automatic Identity Creation**: Agents create persistent identities on first connection
- **Identity Persistence**: Stored in `shared_state/identities.json` across sessions
- **CLI Management**: Complete CLI tool in `tools/identity_cli.py` for identity management
- **Daemon Integration**: 5 new commands (CREATE_IDENTITY, GET_IDENTITY, UPDATE_IDENTITY, LIST_IDENTITIES, REMOVE_IDENTITY)

**Identity Features**:
- Unique UUID per identity for reliable tracking
- Role-based display names and appearance (icons, color themes)
- Personality traits derived from agent capabilities
- Activity statistics (messages, conversations, tasks, tools used)
- Communication preferences and styling options
- Session history tracking

**Technical Implementation**:
- Modular design following KSI daemon architecture
- Event-driven integration with existing systems
- Comprehensive test coverage in `tests/test_identity_system.py`
- Documentation in `docs/features/identity_system.md`
- Enhanced agent_process.py with automatic identity creation
- Capability-to-trait mapping for personality generation

**Agent Profile Integration**:
- Seamless integration with existing agent profiles
- Automatic trait generation from capabilities
- Role-specific appearance defaults
- Preserved across conversation sessions

---
*For Claude Code interactive development sessions*