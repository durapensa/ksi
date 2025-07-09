# Session Tracker Refactoring Design

## Problem Statement
The current SessionManager violates a core KSI principle: **Never create session IDs**. Only claude-cli can create session IDs. The `get_or_create_session` method implies KSI can create sessions, which is fundamentally wrong.

## Current Issues
1. When `session_id=None`, SessionManager creates a "session" with ID `None`
2. This fake session can never be completed because claude-cli returns a real session_id
3. Result: "Completing request for unknown session" warnings
4. The name "SessionManager" implies it manages sessions, but it should only track them

## New Design: ConversationTracker

### Core Principles
1. **Never create session IDs** - only track ones from claude-cli
2. **Track requests and sessions separately**
3. **Handle session_id=None as "pending session assignment"**
4. **Maintain agent → session mapping for conversation continuity**

### Data Structures
```python
class RequestState:
    """Tracks a completion request."""
    request_id: str
    agent_id: Optional[str]
    session_id: Optional[str]  # None = pending, filled when claude-cli responds
    status: str  # "pending", "active", "completed", "failed"
    created_at: datetime
    
class SessionMetadata:
    """Tracks metadata for REAL sessions from claude-cli."""
    session_id: str  # Real session_id from claude-cli
    agent_id: Optional[str]  # Which agent owns this session
    last_activity: datetime
    request_count: int
    lock_status: Optional[LockInfo]
```

### Key Methods

#### Before (SessionManager)
```python
def get_or_create_session(session_id: str) -> SessionState  # WRONG!
def register_request(session_id: str, request_id: str, agent_id: str)
def complete_request(session_id: str, request_id: str)
```

#### After (ConversationTracker)
```python
def track_request(request_id: str, agent_id: Optional[str], session_id: Optional[str])
def update_request_session(request_id: str, session_id: str)  # When claude-cli returns
def complete_request(request_id: str)
def get_agent_session(agent_id: str) -> Optional[str]  # For continuity
```

### Flow Examples

#### New Conversation (session_id=None)
1. Request arrives: `track_request(req123, agent456, None)`
2. Claude-cli returns: `session_id=abc789`
3. Update tracking: `update_request_session(req123, abc789)`
4. Update agent mapping: agent456 → abc789
5. Complete: `complete_request(req123)`

#### Continuing Conversation
1. Get current session: `session_id = get_agent_session(agent456)` → abc789
2. Request arrives: `track_request(req124, agent456, abc789)`
3. Claude-cli returns NEW session: `session_id=def012`
4. Update tracking: `update_request_session(req124, def012)`
5. Update agent mapping: agent456 → def012 (for next request)
6. Complete: `complete_request(req124)`

### Benefits
1. Clear separation: requests vs sessions
2. No fake sessions with ID=None
3. Proper handling of claude-cli's session management
4. Better naming reflects actual responsibility

### Migration Steps
1. Create new ConversationTracker class
2. Update completion_service to use new API
3. Remove old SessionManager
4. Update all references

## Questions for Discussion
1. Should we keep the name "ConversationTracker" or prefer "RequestTracker"?
2. How should we handle conversation locks with this new design?
3. Should we track session history (agent456 used sessions [abc789, def012, ...])?