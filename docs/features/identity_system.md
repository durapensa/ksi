# System Identity Management

The KSI daemon system includes a comprehensive identity management system that provides persistent identities for Claude agents, enabling better distinction between different agent instances in multi-agent conversations.

## Features

### Core Identity Components
- **Unique Identity UUID**: Every agent gets a persistent identifier
- **Display Names**: Human-readable names for easy identification
- **Role-based Attributes**: Specialized roles like researcher, coder, debater
- **Personality Traits**: Characteristics derived from agent capabilities
- **Visual Appearance**: Icons, color themes, and styling preferences
- **Activity Statistics**: Message counts, conversation participation, tool usage
- **Session History**: Track of all sessions and interactions

### Automatic Identity Creation
- Agents automatically create identities when they first connect
- Identities are derived from agent profiles and capabilities
- Existing identities are preserved across sessions
- Identity information persists in `shared_state/identities.json`

## Identity Structure

```json
{
  "identity_uuid": "unique-identifier",
  "agent_id": "agent-123", 
  "display_name": "ResearchBot-Pro",
  "role": "researcher",
  "personality_traits": ["analytical", "thorough", "curious"],
  "appearance": {
    "icon": "🧑‍🔬",
    "avatar_style": "academic", 
    "color_theme": "blue"
  },
  "preferences": {
    "communication_style": "professional",
    "verbosity": "moderate",
    "formality": "balanced"
  },
  "stats": {
    "messages_sent": 42,
    "conversations_participated": 7,
    "tasks_completed": 15,
    "tools_used": ["WebSearch", "Read", "Write"]
  },
  "sessions": [
    {"session_id": "sess-123", "started_at": "2025-06-21T19:00:00Z"}
  ]
}
```

## Daemon Commands

### CREATE_IDENTITY
Create a new identity for an agent.
```
CREATE_IDENTITY:agent_id:display_name:role:personality_traits_json
```

### GET_IDENTITY  
Retrieve identity information for an agent.
```
GET_IDENTITY:agent_id
```

### UPDATE_IDENTITY
Update identity fields.
```
UPDATE_IDENTITY:agent_id:updates_json
```

### LIST_IDENTITIES
List all agent identities.
```
LIST_IDENTITIES
```

### REMOVE_IDENTITY
Remove an agent's identity.
```
REMOVE_IDENTITY:agent_id
```

## CLI Tools

### Identity CLI
Use `tools/identity_cli.py` to manage identities from the command line:

```bash
# List all identities
python3 tools/identity_cli.py list

# Show detailed identity info
python3 tools/identity_cli.py show agent-123

# Create new identity  
python3 tools/identity_cli.py create bot-456 "ResearchBot" researcher

# Update identity fields
python3 tools/identity_cli.py update bot-456 style academic
python3 tools/identity_cli.py update bot-456 traits '["analytical", "thorough"]'

# Remove identity
python3 tools/identity_cli.py remove bot-456
```

## Integration with Agent Profiles

The identity system integrates with existing agent profiles:

- **Role**: Derived from profile `role` field
- **Display Name**: Generated from role + agent ID
- **Personality Traits**: Mapped from profile `capabilities`
- **Appearance**: Role-specific icons and color themes
- **Preferences**: Can be customized per profile

### Trait Mapping
Capabilities are automatically mapped to personality traits:
- `web_search` → research-oriented
- `coding` → logical  
- `debugging` → systematic
- `analysis` → analytical
- `collaboration` → cooperative
- And more...

## Persistence and Sessions

- Identities persist across daemon restarts
- Session history is automatically tracked
- Activity statistics are updated in real-time
- Cross-session conversation continuity is maintained

## Usage in Multi-Agent Conversations

When agents participate in conversations, their identities provide:
- Visual distinction through icons and colors
- Personality context for better interactions
- Communication style preferences
- Historical context and statistics

## Testing

Run the identity system tests:
```bash
python3 tests/test_identity_system.py
```

This validates:
- Identity creation and retrieval
- Update operations
- Listing and removal
- Data persistence
- Error handling

## Architecture

The identity system is implemented as a modular component:
- `daemon/identity_manager.py` - Core identity management
- `tools/identity_cli.py` - Command-line interface
- `tests/test_identity_system.py` - Comprehensive tests

Integration points:
- `agent_process.py` - Automatic identity creation
- `command_handler.py` - Daemon command routing
- `daemon/__init__.py` - Dependency injection

The system follows the KSI daemon's modular architecture and event-driven principles.