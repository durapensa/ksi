# Composition & Permission Flow Analysis

## Current State - Overly Complex

### 1. Multiple Sources of Truth for Allowed Tools

**Composition Profile** (`base_multi_agent.yaml`):
```yaml
ksi_tools:
  allowed_tools: [
    "agent:spawn",
    "message:publish", 
    # ... explicit event list
  ]
```

**Permission Profile** (`trusted.yaml`):
```yaml
tools:
  allowed: null  # All tools allowed
  disallowed: ["Task"]
```

**MCP Server** (queries permissions again):
```python
# Gets permissions from daemon
# Filters tools based on allowed_tools/modules
```

### 2. Disconnected Flow

When spawning an agent:

1. **Composition Service** returns:
   - `agent_config.capabilities` (descriptive)
   - `ksi_tools.allowed_tools` (specific events)
   - `permissions.profile` (e.g., "trusted")
   - `permissions.overrides.capabilities` (e.g., agent_messaging: true)

2. **Agent Service** only extracts:
   - `capabilities` → stored but not used
   - `tools` → stored but `ksi_tools` is ignored!
   - `permissions.profile` → used to set permissions

3. **When making completion**, agent service:
   - Queries `permission:get_agent`
   - Gets `permissions.tools.allowed` from permission profile
   - Ignores the `ksi_tools.allowed_tools` from composition!

4. **MCP Server** then:
   - Queries permissions AGAIN
   - Filters based on permission profile, not composition

### 3. The Problems

1. **Duplication**: Same tool lists in multiple places
2. **Ignored Data**: Composition's `ksi_tools.allowed_tools` is never used
3. **Confusion**: Which takes precedence - composition or permission profile?
4. **Complexity**: Too many layers doing similar filtering

## Proposed Simplification

### Option A: Composition-Driven (Recommended)

**Principle**: Compositions define everything, permissions are just security boundaries

1. **Composition defines allowed_tools explicitly**:
   ```yaml
   allowed_tools: ["agent:spawn", "message:publish", ...]
   permission_profile: "trusted"  # Just for filesystem/resource limits
   ```

2. **Agent service**:
   - Stores allowed_tools from composition
   - Sets permission profile for security boundaries only

3. **Completion/MCP**:
   - Uses allowed_tools from agent's stored config
   - No redundant permission queries

### Option B: Permission-Driven

**Principle**: Permissions define everything, compositions just set permission level

1. **Composition only specifies permission profile**:
   ```yaml
   permission_profile: "multi_agent"  # Has all needed tools
   ```

2. **Permission profiles have richer tool definitions**:
   ```yaml
   # multi_agent permission profile
   tools:
     allowed: ["agent:*", "message:*", "state:*", ...]
   ```

3. **Everything queries permissions consistently**

### Option C: Capability-Based Auto-Mapping

**Principle**: High-level capabilities auto-expand to tools

1. **Composition declares capabilities**:
   ```yaml
   capabilities:
     agent_messaging: true  # Auto-adds message:* tools
     spawn_agents: true     # Auto-adds agent:spawn, etc.
   ```

2. **System has capability→tools mapping**:
   ```python
   CAPABILITY_TOOLS = {
     "agent_messaging": ["message:subscribe", "message:publish", ...],
     "spawn_agents": ["agent:spawn", "agent:terminate", ...]
   }
   ```

3. **Single source of truth for mappings**

## My Recommendation

**Option A (Composition-Driven)** because:
1. Explicit is better than implicit
2. Compositions already define the tools (we just ignore them)
3. Permissions should be about security, not functionality
4. Reduces queries and layers

## Implementation Changes Needed

1. **Fix agent_service.py**:
   - Extract `ksi_tools.allowed_tools` instead of generic `tools`
   - Store in agent config
   - Pass to completions

2. **Simplify permission profiles**:
   - Remove tool lists
   - Focus on security boundaries (filesystem, resources)

3. **Update MCP server**:
   - Use allowed_tools from agent config
   - Stop re-querying permissions

4. **Clean up duplications**:
   - One place for tool lists (compositions)
   - One place for security (permissions)

Would you like me to implement Option A to simplify this system?