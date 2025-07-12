# KSI System Documentation

*Generated using enhanced discovery system with AST analysis*

## System Overview

- **Total Events**: 141
- **Namespaces**: 22
- **Capabilities**: agent, api, async_state, completion, composition, config, conversation, correlation, discovery, file, injection, ksi, message, message_bus, module, monitor, orchestration, permission, sandbox, state, system, transport

## Event Relationships

Events that trigger other events:

- **config:set** triggers: config:changed
- **config:reload** triggers: daemon:config_reload, plugins:reload, composition:reload
- **config:rollback** triggers: config:rolled_back

## Events by Namespace

### Agent

*18 events*

#### `agent:spawn`

**Summary**: Handle agent:spawn event

**Description**:

> Spawn a new agent thread with optional profile.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `profile` (Any, required): profile parameter
- `profile_name` (Any, required): profile_name parameter
- `composition` (Any, required): composition parameter
- `session_id` (Any, required): session_id parameter
- `spawn_mode` (Any, optional): spawn_mode parameter [default: fixed]
- `selection_context` (Any, optional): selection_context parameter
- `task` (Any, required): task parameter
- `_composition_selection` (Any, required): _composition_selection parameter
- `enable_tools` (Any, optional): enable_tools parameter [default: False]
- `context` (Any, required): context parameter
- `config` (Any, required): config parameter
- `permission_profile` (Any, optional): permission_profile parameter [default: standard]
- `sandbox_config` (Any, optional): sandbox_config parameter
- `permission_overrides` (Any, optional): permission_overrides parameter

**Complexity**: High (16)

**Has Side Effects**: Yes

---

#### `agent:terminate`

**Summary**: Handle agent:terminate event

**Description**:

> Terminate an agent thread.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `force` (Any, optional): force parameter [default: False]

**Has Side Effects**: Yes

---

#### `agent:restart`

**Summary**: Handle agent:restart event

**Description**:

> Restart an agent.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `agent:register`

**Summary**: Handle agent:register event

**Description**:

> Register an external agent.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `info` (Any, optional): info parameter

**Has Side Effects**: Yes

---

#### `agent:unregister`

**Summary**: Handle agent:unregister event

**Description**:

> Unregister an agent.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `agent:list`

**Summary**: Handle agent:list event

**Description**:

> List registered agents.

**Parameters**:

- `status` (Any, required): status parameter

**Has Side Effects**: Yes

---

#### `agent:create_identity`

**Summary**: Handle agent:create_identity event

**Description**:

> Create a new agent identity.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `identity` (Any, optional): identity parameter

**Has Side Effects**: Yes

---

#### `agent:update_identity`

**Summary**: Handle agent:update_identity event

**Description**:

> Update an agent identity.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `updates` (Any, optional): updates parameter

**Has Side Effects**: Yes

---

#### `agent:remove_identity`

**Summary**: Handle agent:remove_identity event

**Description**:

> Remove an agent identity.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `agent:list_identities`

**Summary**: Handle agent:list_identities event

**Description**:

> List agent identities.

**Has Side Effects**: Yes

---

#### `agent:get_identity`

**Summary**: Handle agent:get_identity event

**Description**:

> Get a specific agent identity.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `agent:route_task`

**Summary**: Handle agent:route_task event

**Description**:

> Route a task to an appropriate agent.

**Parameters**:

- `task` (Any, optional): task parameter

**Has Side Effects**: Yes

---

#### `agent:get_capabilities`

**Summary**: Handle agent:get_capabilities event

**Description**:

> Get capabilities of an agent or all agents.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `agent:send_message`

**Summary**: Handle agent:send_message event

**Description**:

> Send a message to an agent.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `message` (Any, optional): message parameter

**Has Side Effects**: Yes

---

#### `agent:broadcast`

**Summary**: Handle agent:broadcast event

**Description**:

> Broadcast a message to all agents.

**Parameters**:

- `message` (Any, optional): message parameter
- `sender` (Any, optional): sender parameter [default: system]

**Has Side Effects**: Yes

---

#### `agent:update_composition`

**Summary**: Handle agent:update_composition event

**Description**:

> Handle agent composition update request.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `new_composition` (Any, required): new_composition parameter
- `reason` (Any, optional): reason parameter [default: Adaptation required]

**Has Side Effects**: Yes

---

#### `agent:discover_peers`

**Summary**: Handle agent:discover_peers event

**Description**:

> Discover other agents and their capabilities.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `capabilities` (Any, optional): capabilities parameter
- `roles` (Any, optional): roles parameter

**Has Side Effects**: Yes

---

#### `agent:negotiate_roles`

**Summary**: Handle agent:negotiate_roles event

**Description**:

> Coordinate role negotiation between agents.

**Parameters**:

- `participants` (Any, optional): participants parameter
- `type` (Any, optional): type parameter [default: collaborative]
- `context` (Any, optional): context parameter

**Has Side Effects**: Yes

---

### Api

*1 events*

#### `api:schema`

**Summary**: Handle api:schema event

**Description**:

> Get complete API schema using direct function inspection.

**Has Side Effects**: Yes

---

### Async_State

*7 events*

#### `async_state:get`

**Summary**: Handle async_state:get event

**Description**:

> Get value from async state.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `key` (Any, optional): key parameter [default: ]

**Has Side Effects**: Yes

---

#### `async_state:set`

**Summary**: Handle async_state:set event

**Description**:

> Set value in async state.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `key` (Any, optional): key parameter [default: ]
- `value` (Any, required): value parameter

**Has Side Effects**: Yes

---

#### `async_state:delete`

**Summary**: Handle async_state:delete event

**Description**:

> Delete key from async state.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `key` (Any, optional): key parameter [default: ]

**Has Side Effects**: Yes

---

#### `async_state:push`

**Summary**: Handle async_state:push event

**Description**:

> Push value to async queue.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `queue_name` (Any, optional): queue_name parameter [default: ]
- `value` (Any, required): value parameter

**Has Side Effects**: Yes

---

#### `async_state:pop`

**Summary**: Handle async_state:pop event

**Description**:

> Pop value from async queue.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `queue_name` (Any, optional): queue_name parameter [default: ]

**Has Side Effects**: Yes

---

#### `async_state:get_keys`

**Summary**: Handle async_state:get_keys event

**Description**:

> Get all keys in a namespace.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]

**Has Side Effects**: Yes

---

#### `async_state:queue_length`

**Summary**: Handle async_state:queue_length event

**Description**:

> Get length of async queue.

**Parameters**:

- `namespace` (Any, optional): namespace parameter [default: default]
- `queue_name` (Any, optional): queue_name parameter [default: ]

**Has Side Effects**: Yes

---

### Completion

*8 events*

#### `completion:cancelled`

**Summary**: Handle completion:result event

**Description**:

> Broadcast certain events to all connected clients.

**Parameters**:

- `timestamp` (Any, optional): timestamp parameter [default: ]
- `correlation_id` (Any, required): correlation_id parameter

**Has Side Effects**: Yes

---

#### `completion:error`

**Summary**: Handle completion:result event

**Description**:

> Broadcast certain events to all connected clients.

**Parameters**:

- `timestamp` (Any, optional): timestamp parameter [default: ]
- `correlation_id` (Any, required): correlation_id parameter

**Has Side Effects**: Yes

---

#### `completion:progress`

**Summary**: Handle completion:result event

**Description**:

> Broadcast certain events to all connected clients.

**Parameters**:

- `timestamp` (Any, optional): timestamp parameter [default: ]
- `correlation_id` (Any, required): correlation_id parameter

**Has Side Effects**: Yes

---

#### `completion:result`

**Summary**: Handle completion:result event

**Description**:

> Broadcast certain events to all connected clients.

**Parameters**:

- `timestamp` (Any, optional): timestamp parameter [default: ]
- `correlation_id` (Any, required): correlation_id parameter

**Has Side Effects**: Yes

---

#### `completion:async`

**Summary**: Handle completion:async event

**Description**:

> Handle async completion requests with smart queueing.
> 
> Uses hybrid approach:
> - Event-driven for multi-session parallelism
> - Queue-based for per-session fork prevention

**Parameters**:

- `request_id` (Any, required): request_id parameter
- `session_id` (Any, optional): session_id parameter [default: default]
- `model` (Any, optional): model parameter [default: unknown]

**Has Side Effects**: Yes

---

#### `completion:cancel`

**Summary**: Cancel an in-progress completion

**Description**:

> Cancel an in-progress completion.

**Parameters**:

- `request_id` (str, required): request_id parameter

**Typical Duration**: 100ms
**Has Side Effects**: Yes

---

#### `completion:status`

**Summary**: Get status of all active completions

**Description**:

> Get status of all active completions.

**Typical Duration**: 50ms

---

#### `completion:session_status`

**Summary**: Get detailed status for a specific session

**Description**:

> Get detailed status for a specific session.

**Parameters**:

- `session_id` (str, required): session_id parameter

**Typical Duration**: 100ms

---

### Composition

*19 events*

#### `composition:compose`

**Summary**: Handle composition:compose event

**Description**:

> Handle generic composition request.

**Parameters**:

- `name` (Any, required): name parameter
- `type` (Any, required): type parameter
- `variables` (Any, optional): variables parameter

**Has Side Effects**: Yes

---

#### `composition:profile`

**Summary**: Handle composition:profile event

**Description**:

> Handle profile composition request.

**Parameters**:

- `name` (Any, required): name parameter
- `variables` (Any, optional): variables parameter

**Has Side Effects**: Yes

---

#### `composition:prompt`

**Summary**: Handle composition:prompt event

**Description**:

> Handle prompt composition request.

**Parameters**:

- `name` (Any, required): name parameter
- `variables` (Any, optional): variables parameter

**Has Side Effects**: Yes

---

#### `composition:validate`

**Summary**: Handle composition:validate event

**Description**:

> Validate a composition.

**Parameters**:

- `name` (Any, required): name parameter
- `type` (Any, required): type parameter

**Has Side Effects**: Yes

---

#### `composition:discover`

**Summary**: Handle composition:discover event

**Description**:

> Discover available compositions using index with optional metadata filtering.

**Parameters**:

- `metadata_filter` (Any, required): metadata_filter parameter

**Complexity**: High (11)

**Has Side Effects**: Yes

---

#### `composition:list`

**Summary**: Handle composition:list event

**Description**:

> List all compositions of a given type.

**Parameters**:

- `type` (Any, optional): type parameter [default: all]

**Has Side Effects**: Yes

---

#### `composition:get`

**Summary**: Handle composition:get event

**Description**:

> Get a composition definition.

**Parameters**:

- `name` (Any, required): name parameter
- `type` (Any, required): type parameter

**Has Side Effects**: Yes

---

#### `composition:reload`

**Summary**: Handle composition:reload event

**Description**:

> Reload compositions by rebuilding index.

**Has Side Effects**: Yes

---

#### `composition:load_tree`

**Summary**: Handle composition:load_tree event

**Description**:

> Universal tree loading based on composition's declared strategy.

**Parameters**:

- `name` (Any, required): name parameter
- `max_depth` (Any, optional): max_depth parameter [default: 5]

**Complexity**: High (11)

**Has Side Effects**: Yes

---

#### `composition:load_bulk`

**Summary**: Handle composition:load_bulk event

**Description**:

> Universal bulk loading for agent efficiency.

**Parameters**:

- `names` (Any, optional): names parameter

**Has Side Effects**: Yes

---

#### `composition:select`

**Summary**: Handle composition:select event

**Description**:

> Handle intelligent composition selection using sophisticated scoring algorithm.

**Parameters**:

- `agent_id` (Any, optional): agent_id parameter [default: unknown]
- `role` (Any, required): role parameter
- `capabilities` (Any, optional): capabilities parameter
- `task_description` (Any, required): task_description parameter
- `preferred_style` (Any, required): preferred_style parameter
- `context_variables` (Any, optional): context_variables parameter
- `requirements` (Any, optional): requirements parameter
- `max_suggestions` (Any, optional): max_suggestions parameter [default: 1]

**Has Side Effects**: Yes

---

#### `composition:suggest`

**Summary**: Handle composition:suggest event

**Description**:

> Get top N composition suggestions for the given context.

**Parameters**:

- `agent_id` (Any, optional): agent_id parameter [default: unknown]
- `role` (Any, required): role parameter
- `capabilities` (Any, optional): capabilities parameter
- `task_description` (Any, required): task_description parameter
- `preferred_style` (Any, required): preferred_style parameter
- `context_variables` (Any, optional): context_variables parameter
- `requirements` (Any, optional): requirements parameter
- `max_suggestions` (Any, optional): max_suggestions parameter [default: 3]

**Has Side Effects**: Yes

---

#### `composition:validate_context`

**Summary**: Handle composition:validate_context event

**Description**:

> Validate that a composition will work with the given context.

**Parameters**:

- `composition_name` (Any, required): composition_name parameter
- `context` (Any, optional): context parameter

**Complexity**: High (21)

**Has Side Effects**: Yes

---

#### `composition:capabilities`

**Summary**: Handle composition:capabilities event

**Description**:

> Get available KSI capabilities from declarative schema.

**Parameters**:

- `group` (Any, required): group parameter

**Has Side Effects**: Yes

---

#### `composition:get_path`

**Summary**: Handle composition:get_path event

**Description**:

> Get the file path for a composition.

**Parameters**:

- `full_name` (Any, required): full_name parameter

**Has Side Effects**: Yes

---

#### `composition:get_metadata`

**Summary**: Handle composition:get_metadata event

**Description**:

> Get metadata for a composition.

**Parameters**:

- `full_name` (Any, required): full_name parameter

**Has Side Effects**: Yes

---

#### `composition:rebuild_index`

**Summary**: Handle composition:rebuild_index event

**Description**:

> Rebuild the composition index.

**Parameters**:

- `repository_id` (Any, optional): repository_id parameter [default: local]

**Has Side Effects**: Yes

---

#### `composition:index_file`

**Summary**: Handle composition:index_file event

**Description**:

> Index a single composition file.

**Parameters**:

- `file_path` (Any, required): file_path parameter

**Has Side Effects**: Yes

---

#### `composition:create`

**Summary**: Handle composition:create event

**Description**:

> Handle runtime composition creation.

**Parameters**:

- `name` (Any, required): name parameter
- `type` (Any, optional): type parameter [default: profile]
- `extends` (Any, optional): extends parameter [default: base_agent]
- `description` (Any, optional): description parameter
- `author` (Any, optional): author parameter [default: dynamic_agent]
- `metadata` (Any, optional): metadata parameter
- `components` (Any, required): components parameter
- `config` (Any, optional): config parameter
- `role` (Any, optional): role parameter [default: assistant]
- `model` (Any, optional): model parameter [default: sonnet]
- `capabilities` (Any, optional): capabilities parameter
- `tools` (Any, optional): tools parameter
- `prompt` (Any, required): prompt parameter
- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

### Config

*6 events*

#### `config:get`

**Summary**: Handle config:get event

**Description**:

> Get configuration value or entire config file.
> 
> Args:
>     key (str): Configuration key path (e.g., 'daemon.log_level') (required)
>     config_type (str): Type of config ('daemon', 'composition', 'schema', 'capabilities')
>     file_path (str): Specific config file path (optional)
> 
> Returns:
>     Dictionary with configuration value and metadata
> 
> Example:
>     {"key": "daemon.log_level", "config_type": "daemon"}

**Parameters**:

- `key` (str, required): Configuration key path (e.g., 'daemon.log_level') (required) [default: ]
- `config_type` (str, required): Type of config ('daemon', 'composition', 'schema', 'capabilities') [default: daemon]
- `file_path` (str, optional): Specific config file path (optional)

**Has Side Effects**: Yes

---

#### `config:set`

**Summary**: Handle config:set event

**Description**:

> Set configuration value with automatic backup.
> 
> Args:
>     key (str): Configuration key path (e.g., 'daemon.log_level') (required)
>     value (any): Value to set (required)
>     config_type (str): Type of config ('daemon', 'composition', 'schema', 'capabilities')
>     file_path (str): Specific config file path (optional)
>     create_backup (bool): Create backup before modification (default: true)
> 
> Returns:
>     Dictionary with status and backup info
> 
> Example:
>     {"key": "daemon.log_level", "value": "DEBUG", "config_type": "daemon"}

**Parameters**:

- `key` (str, required): Configuration key path (e.g., 'daemon.log_level') (required) [default: ]
- `value` (any, required): Value to set (required)
- `config_type` (str, required): Type of config ('daemon', 'composition', 'schema', 'capabilities') [default: daemon]
- `file_path` (str, optional): Specific config file path (optional)
- `create_backup` (bool, optional): Create backup before modification (default: true) [default: true]

**Complexity**: High (17)

**Triggers**:
- config:changed

**Has Side Effects**: Yes

---

#### `config:validate`

**Summary**: Handle config:validate event

**Description**:

> Validate configuration file syntax and schema.
> 
> Args:
>     config_type (str): Type of config to validate ('daemon', 'composition', 'schema', 'capabilities')
>     file_path (str): Specific config file path (optional)
>     schema_path (str): Path to validation schema (optional)
> 
> Returns:
>     Dictionary with validation results
> 
> Example:
>     {"config_type": "composition", "file_path": "profiles/developer.yaml"}

**Parameters**:

- `config_type` (str, required): Type of config to validate ('daemon', 'composition', 'schema', 'capabilities') [default: daemon]
- `file_path` (str, optional): Specific config file path (optional)
- `schema_path` (str, optional): Path to validation schema (optional)

**Has Side Effects**: Yes

---

#### `config:reload`

**Summary**: Handle config:reload event

**Description**:

> Reload configuration components.
> 
> Args:
>     component (str): Component to reload ('daemon', 'plugins', 'compositions', 'all')
> 
> Returns:
>     Dictionary with reload status
> 
> Example:
>     {"component": "compositions"}

**Parameters**:

- `component` (str, required): Component to reload ('daemon', 'plugins', 'compositions', 'all') [default: all]

**Triggers**:
- daemon:config_reload
- plugins:reload
- composition:reload

**Has Side Effects**: Yes

---

#### `config:backup`

**Summary**: Handle config:backup event

**Description**:

> Create manual backup of configuration.
> 
> Args:
>     config_type (str): Type of config to backup (required)
>     file_path (str): Specific config file path (optional)
>     backup_name (str): Custom backup name (optional)
> 
> Returns:
>     Dictionary with backup status and metadata
> 
> Example:
>     {"config_type": "daemon", "backup_name": "before_update"}

**Parameters**:

- `config_type` (str, required): Type of config to backup (required) [default: ]
- `file_path` (str, optional): Specific config file path (optional)
- `backup_name` (str, optional): Custom backup name (optional)

**Has Side Effects**: Yes

---

#### `config:rollback`

**Summary**: Handle config:rollback event

**Description**:

> Rollback configuration to previous backup.
> 
> Args:
>     config_type (str): Type of config to rollback (required)
>     file_path (str): Specific config file path (optional)
>     backup_name (str): Specific backup to restore (optional, uses latest if not provided)
> 
> Returns:
>     Dictionary with rollback status and metadata
> 
> Example:
>     {"config_type": "daemon", "backup_name": "before_update"}

**Parameters**:

- `config_type` (str, required): Type of config to rollback (required) [default: ]
- `file_path` (str, optional): Specific config file path (optional)
- `backup_name` (str, optional): Specific backup to restore (optional, uses latest if not provided)

**Complexity**: High (14)

**Triggers**:
- config:rolled_back

**Has Side Effects**: Yes

---

### Conversation

*10 events*

#### `conversation:list`

**Summary**: Handle conversation:list event

**Description**:

> List available conversations with metadata.

**Parameters**:

- `limit` (Any, optional): limit parameter [default: 100]
- `offset` (Any, optional): offset parameter [default: 0]
- `sort_by` (Any, optional): sort_by parameter [default: last_timestamp]
- `reverse` (Any, optional): reverse parameter [default: True]
- `start_date` (Any, required): start_date parameter
- `end_date` (Any, required): end_date parameter

**Complexity**: High (13)

**Has Side Effects**: Yes

---

#### `conversation:search`

**Summary**: Handle conversation:search event

**Description**:

> Search conversations by content.

**Parameters**:

- `query` (Any, optional): query parameter [default: ]
- `limit` (Any, optional): limit parameter [default: 50]
- `search_in` (Any, optional): search_in parameter

**Complexity**: High (21)

**Has Side Effects**: Yes

---

#### `conversation:get`

**Summary**: Handle conversation:get event

**Description**:

> Get a specific conversation with full message history.

**Parameters**:

- `session_id` (Any, required): session_id parameter
- `limit` (Any, optional): limit parameter [default: 1000]
- `offset` (Any, optional): offset parameter [default: 0]
- `conversation_id` (Any, required): conversation_id parameter

**Complexity**: High (14)

**Has Side Effects**: Yes

---

#### `conversation:export`

**Summary**: Handle conversation:export event

**Description**:

> Export conversation to markdown or JSON format.

**Parameters**:

- `session_id` (Any, required): session_id parameter
- `format` (Any, optional): format parameter [default: markdown]

**Complexity**: High (12)

**File Operations**:
- writelines (file)

**Has Side Effects**: Yes

---

#### `conversation:stats`

**Summary**: Handle conversation:stats event

**Description**:

> Get statistics about conversations.

**Has Side Effects**: Yes

---

#### `conversation:active`

**Summary**: Handle conversation:active event

**Description**:

> Find active conversations from recent COMPLETION_RESULT messages.

**Parameters**:

- `max_lines` (Any, optional): max_lines parameter [default: 100]
- `max_age_hours` (Any, optional): max_age_hours parameter [default: 2160]

**Complexity**: High (13)

**File Operations**:
- read (file)

**Has Side Effects**: Yes

---

#### `conversation:acquire_lock`

**Summary**: Handle conversation:acquire_lock event

**Description**:

> Acquire lock for a conversation.

**Parameters**:

- `request_id` (Any, required): request_id parameter
- `conversation_id` (Any, required): conversation_id parameter
- `metadata` (Any, optional): metadata parameter

**Has Side Effects**: Yes

---

#### `conversation:release_lock`

**Summary**: Handle conversation:release_lock event

**Description**:

> Release a conversation lock.

**Parameters**:

- `request_id` (Any, required): request_id parameter

**Has Side Effects**: Yes

---

#### `conversation:fork_detected`

**Summary**: Handle conversation:fork_detected event

**Description**:

> Handle fork detection.

**Parameters**:

- `request_id` (Any, required): request_id parameter
- `expected_conversation_id` (Any, required): expected_conversation_id parameter
- `actual_conversation_id` (Any, required): actual_conversation_id parameter

**Has Side Effects**: Yes

---

#### `conversation:lock_status`

**Summary**: Handle conversation:lock_status event

**Description**:

> Get lock status for a conversation.

**Parameters**:

- `conversation_id` (Any, required): conversation_id parameter

**Has Side Effects**: Yes

---

### Correlation

*6 events*

#### `correlation:trace`

**Summary**: Handle correlation:trace event

**Description**:

> Get a specific correlation trace.
> 
> Parameters:
>     correlation_id: The correlation ID to retrieve trace for
> 
> Returns:
>     Trace information including timing, data, and children

**Parameters**:

- `correlation_id` (Any, required): The correlation ID to retrieve trace for

**Has Side Effects**: Yes

---

#### `correlation:chain`

**Summary**: Handle correlation:chain event

**Description**:

> Get the full trace chain for a correlation ID.
> 
> Parameters:
>     correlation_id: The correlation ID to retrieve chain for
> 
> Returns:
>     Full chain of traces from root to leaf

**Parameters**:

- `correlation_id` (Any, required): The correlation ID to retrieve chain for

**Has Side Effects**: Yes

---

#### `correlation:tree`

**Summary**: Handle correlation:tree event

**Description**:

> Get the full trace tree for a correlation ID.
> 
> Parameters:
>     correlation_id: The correlation ID to retrieve tree for
> 
> Returns:
>     Hierarchical tree of all related traces

**Parameters**:

- `correlation_id` (Any, required): The correlation ID to retrieve tree for

**Has Side Effects**: Yes

---

#### `correlation:stats`

**Summary**: Handle correlation:stats event

**Description**:

> Get correlation tracking statistics.
> 
> Returns:
>     Statistics about active and completed traces

**Has Side Effects**: Yes

---

#### `correlation:cleanup`

**Summary**: Handle correlation:cleanup event

**Description**:

> Clean up old correlation traces.
> 
> Parameters:
>     max_age_hours: Maximum age in hours for traces to keep (default: 24)
> 
> Returns:
>     Number of traces cleaned up

**Parameters**:

- `max_age_hours` (Any, optional): Maximum age in hours for traces to keep (default: 24) [default: 24]

**Has Side Effects**: Yes

---

#### `correlation:current`

**Summary**: Handle correlation:current event

**Description**:

> Get current correlation context.
> 
> Returns:
>     Current and parent correlation IDs

**Has Side Effects**: Yes

---

### Discovery

*1 events*

#### `discovery:usage`

**Summary**: Handle discovery:usage event

**Description**:

> Get discovery data formatted for specific usage patterns.
> 
> Parameters:
>     pattern: Usage pattern ("full", "by_module", "event_names", "parameters", 
>              "capabilities", "reference", "implementation", "relationships")
>     filter: Optional filters (namespace, module, event)
>     format: Output format for some patterns (markdown, json)

**Parameters**:

- `pattern` (Any, required): Usage pattern ("full", "by_module", "event_names", "parameters", "capabilities", "reference", "implementation", "relationships") [default: full]
- `filter` (Any, optional): Optional filters (namespace, module, event)
- `format` (Any, required): Output format for some patterns (markdown, json) [default: json]

**Has Side Effects**: Yes

---

### File

*6 events*

#### `file:read`

**Summary**: Handle file:read event

**Description**:

> Read a file with safety validation.
> 
> Args:
>     path (str): The file path to read (required)
>     encoding (str): File encoding (default: utf-8)
>     binary (bool): Read as binary data (default: false)
> 
> Returns:
>     Dictionary with content, size, encoding, and metadata
> 
> Example:
>     {"path": "var/logs/daemon/daemon.log", "encoding": "utf-8"}

**Parameters**:

- `path` (str, required): The file path to read (required) [default: ]
- `encoding` (str, optional): File encoding (default: utf-8) [default: utf-8]
- `binary` (bool, optional): Read as binary data (default: false) [default: false]

**File Operations**:
- read (file)
- read (file)

**Has Side Effects**: Yes

---

#### `file:write`

**Summary**: Handle file:write event

**Description**:

> Write to a file with automatic backup.
> 
> Args:
>     path (str): The file path to write (required)
>     content (str): The content to write (required)
>     encoding (str): File encoding (default: utf-8)
>     create_backup (bool): Create backup before writing (default: true)
>     binary (bool): Write binary data (content should be hex string) (default: false)
> 
> Returns:
>     Dictionary with status, backup info, and file metadata
> 
> Example:
>     {"path": "var/temp/output.txt", "content": "Hello World", "create_backup": true}

**Parameters**:

- `path` (str, required): The file path to write (required) [default: ]
- `content` (str, required): The content to write (required) [default: ]
- `encoding` (str, optional): File encoding (default: utf-8) [default: utf-8]
- `create_backup` (bool, optional): Create backup before writing (default: true) [default: true]
- `binary` (bool, optional): Write binary data (content should be hex string) (default: false) [default: false]

**File Operations**:
- write (file)
- write (file)

**Has Side Effects**: Yes

---

#### `file:backup`

**Summary**: Handle file:backup event

**Description**:

> Create a manual backup of a file.
> 
> Args:
>     path (str): The file path to backup (required)
>     backup_name (str): Custom backup name (optional, auto-generated if not provided)
> 
> Returns:
>     Dictionary with backup status and metadata
> 
> Example:
>     {"path": "important_file.yaml", "backup_name": "before_edit"}

**Parameters**:

- `path` (str, required): The file path to backup (required) [default: ]
- `backup_name` (str, optional): Custom backup name (optional, auto-generated if not provided)

**Has Side Effects**: Yes

---

#### `file:rollback`

**Summary**: Handle file:rollback event

**Description**:

> Rollback a file to a previous backup.
> 
> Args:
>     path (str): The file path to rollback (required)
>     backup_name (str): Specific backup to restore (optional, uses latest if not provided)
> 
> Returns:
>     Dictionary with rollback status and metadata
> 
> Example:
>     {"path": "config.yaml", "backup_name": "before_edit"}

**Parameters**:

- `path` (str, required): The file path to rollback (required) [default: ]
- `backup_name` (str, optional): Specific backup to restore (optional, uses latest if not provided)

**Complexity**: High (15)

**File Operations**:
- read (file)

**Has Side Effects**: Yes

---

#### `file:list`

**Summary**: Handle file:list event

**Description**:

> List files in a directory with filtering.
> 
> Args:
>     path (str): The directory path to list (required)
>     pattern (str): Filename pattern to match (optional)
>     recursive (bool): Include subdirectories (default: false)
>     include_hidden (bool): Include hidden files (default: false)
> 
> Returns:
>     Dictionary with files array and metadata
> 
> Example:
>     {"path": "var/logs", "pattern": "*.log", "recursive": true}

**Parameters**:

- `path` (str, required): The directory path to list (required) [default: ]
- `pattern` (str, optional): Filename pattern to match (optional) [default: *]
- `recursive` (bool, optional): Include subdirectories (default: false) [default: false]
- `include_hidden` (bool, optional): Include hidden files (default: false) [default: false]

**Has Side Effects**: Yes

---

#### `file:validate`

**Summary**: Handle file:validate event

**Description**:

> Validate file access and properties.
> 
> Args:
>     path (str): The file path to validate (required)
>     check_writable (bool): Check if file is writable (default: false)
>     check_content (str): Validate file contains specific content (optional)
> 
> Returns:
>     Dictionary with validation results
> 
> Example:
>     {"path": "config.yaml", "check_writable": true, "check_content": "version:"}

**Parameters**:

- `path` (str, required): The file path to validate (required) [default: ]
- `check_writable` (bool, optional): Check if file is writable (default: false) [default: false]
- `check_content` (str, optional): Validate file contains specific content (optional)

**File Operations**:
- read (file)

**Has Side Effects**: Yes

---

### Injection

*8 events*

#### `injection:status`

**Summary**: Handle injection:status event

**Description**:

> Get injection router status.

**Has Side Effects**: Yes

---

#### `injection:inject`

**Summary**: Handle injection:inject event

**Description**:

> Handle unified injection request.

**Parameters**:

- `mode` (Any, optional): mode parameter [default: next]
- `position` (Any, optional): position parameter [default: before_prompt]
- `content` (Any, optional): content parameter [default: ]
- `session_id` (Any, required): session_id parameter
- `priority` (Any, optional): priority parameter [default: normal]
- `metadata` (Any, optional): metadata parameter

**Has Side Effects**: Yes

---

#### `injection:queue`

**Summary**: Handle injection:queue event

**Description**:

> Handle queue injection metadata request from completion service.

**Has Side Effects**: Yes

---

#### `injection:batch`

**Summary**: Handle injection:batch event

**Description**:

> Handle batch injection request.

**Parameters**:

- `injections` (Any, optional): injections parameter

**Has Side Effects**: Yes

---

#### `injection:list`

**Summary**: Handle injection:list event

**Description**:

> Handle list injections request.

**Parameters**:

- `session_id` (Any, required): session_id parameter

**Has Side Effects**: Yes

---

#### `injection:clear`

**Summary**: Handle injection:clear event

**Description**:

> Handle clear injections request.

**Parameters**:

- `session_id` (Any, required): session_id parameter
- `mode` (Any, required): mode parameter

**Has Side Effects**: Yes

---

#### `injection:process_result`

**Summary**: Handle injection:process_result event

**Description**:

> Process a completion result for injection - explicitly called by completion service.

**Parameters**:

- `request_id` (Any, required): request_id parameter
- `result` (Any, optional): result parameter
- `injection_metadata` (Any, optional): injection_metadata parameter

**Complexity**: High (14)

**Has Side Effects**: Yes

---

#### `injection:execute`

**Summary**: Handle injection:execute event

**Description**:

> Execute a queued injection by creating a new completion request.

**Parameters**:

- `session_id` (Any, required): session_id parameter
- `content` (Any, required): content parameter
- `request_id` (Any, required): request_id parameter
- `target_sessions` (Any, optional): target_sessions parameter
- `model` (Any, optional): model parameter [default: claude-cli/sonnet]
- `priority` (Any, optional): priority parameter [default: normal]
- `injection_type` (Any, optional): injection_type parameter [default: system_reminder]

**Has Side Effects**: Yes

---

### Ksi

*1 events*

#### `ksi:context:get`

**Summary**: Handle ksi:context:get event

**Description**:

> Get cached KSI context variable.

**Parameters**:

- `variable` (Any, required): variable parameter

**Has Side Effects**: Yes

---

### Message

*6 events*

#### `message:subscribe`

**Summary**: Handle message:subscribe event

**Description**:

> Handle subscription request.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `event_types` (Any, optional): event_types parameter

**Has Side Effects**: Yes

---

#### `message:unsubscribe`

**Summary**: Handle message:unsubscribe event

**Description**:

> Handle unsubscription request.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `event_types` (Any, optional): event_types parameter

**Has Side Effects**: Yes

---

#### `message:publish`

**Summary**: Handle message:publish event

**Description**:

> Handle message publication.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter
- `event_type` (Any, required): event_type parameter
- `message` (Any, optional): message parameter

**Has Side Effects**: Yes

---

#### `message:subscriptions`

**Summary**: Handle message:subscriptions event

**Description**:

> Get subscription information.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `message:connect`

**Summary**: Handle message:connect event

**Description**:

> Handle agent connection.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

#### `message:disconnect`

**Summary**: Handle message:disconnect event

**Description**:

> Handle agent disconnection.

**Parameters**:

- `agent_id` (Any, required): agent_id parameter

**Has Side Effects**: Yes

---

### Message_Bus

*1 events*

#### `message_bus:stats`

**Summary**: Handle message_bus:stats event

**Description**:

> Get message bus statistics.

**Has Side Effects**: Yes

---

### Module

*3 events*

#### `module:list`

**Summary**: Handle module:list event

**Description**:

> List all loaded modules.

**Has Side Effects**: Yes

---

#### `module:events`

**Summary**: Handle module:events event

**Description**:

> List all registered events and patterns.

**Has Side Effects**: Yes

---

#### `module:inspect`

**Summary**: Handle module:inspect event

**Description**:

> Inspect a specific module using direct function metadata.

**Parameters**:

- `module_name` (Any, required): module_name parameter

**Has Side Effects**: Yes

---

### Monitor

*8 events*

#### `monitor:get_events`

**Summary**: Handle monitor:get_events event

**Description**:

> Query event log with filtering and pagination.
> 
> Args:
>     data: Query parameters:
>         - event_patterns: List of event name patterns (supports wildcards)
>         - client_id: Filter by specific client  
>         - since: Start time (ISO string or timestamp)
>         - until: End time (ISO string or timestamp)
>         - limit: Maximum number of events to return
>         - reverse: Return newest first (default True)
> 
> Returns:
>     Dictionary with events list and metadata

**Parameters**:

- `event_patterns` (Any, required): event_patterns parameter
- `client_id` (Any, required): client_id parameter
- `since` (Any, required): since parameter
- `until` (Any, required): until parameter
- `limit` (Any, optional): limit parameter [default: 100]
- `reverse` (Any, optional): reverse parameter [default: True]
- `data` (Any, required): Query parameters: - event_patterns: List of event name patterns (supports wildcards) - client_id: Filter by specific client - since: Start time (ISO string or timestamp) - until: End time (ISO string or timestamp) - limit: Maximum number of events to return - reverse: Return newest first (default True)

**Has Side Effects**: Yes

---

#### `monitor:get_stats`

**Summary**: Handle monitor:get_stats event

**Description**:

> Get event log statistics.
> 
> Returns:
>     Dictionary with event log statistics

**Has Side Effects**: Yes

---

#### `monitor:clear_log`

**Summary**: Handle monitor:clear_log event

**Description**:

> Clear event log (admin operation).
> 
> Returns:
>     Confirmation of log clearing

**Has Side Effects**: Yes

---

#### `monitor:subscribe`

**Summary**: Handle monitor:subscribe event

**Description**:

> Subscribe to real-time event stream.
> 
> Note: In event system, context is passed through data
> 
> Args:
>     data: Subscription parameters:
>         - event_patterns: List of event name patterns (supports wildcards)
>         - filter_fn: Optional additional filter function
>         - client_id: Client identifier
>         - writer: Transport writer reference
> 
> Returns:
>     Subscription confirmation

**Parameters**:

- `client_id` (Any, required): client_id parameter
- `event_patterns` (Any, optional): event_patterns parameter
- `writer` (Any, required): writer parameter
- `data` (Any, required): Subscription parameters: - event_patterns: List of event name patterns (supports wildcards) - filter_fn: Optional additional filter function - client_id: Client identifier - writer: Transport writer reference

**Has Side Effects**: Yes

---

#### `monitor:unsubscribe`

**Summary**: Handle monitor:unsubscribe event

**Description**:

> Unsubscribe from event stream.
> 
> Args:
>     data: Unsubscribe parameters:
>         - client_id: Client identifier
> 
> Returns:
>     Unsubscribe confirmation

**Parameters**:

- `client_id` (Any, required): client_id parameter
- `data` (Any, required): Unsubscribe parameters: - client_id: Client identifier

**Has Side Effects**: Yes

---

#### `monitor:query`

**Summary**: Handle monitor:query event

**Description**:

> Execute custom SQL query against event database.
> 
> Args:
>     data: Query parameters:
>         - query: SQL query string
>         - params: Optional query parameters (tuple)
>         - limit: Maximum results (default 1000)
> 
> Returns:
>     Query results with metadata

**Parameters**:

- `query` (Any, required): query parameter
- `params` (Any, optional): params parameter
- `limit` (Any, optional): limit parameter [default: 1000]
- `data` (Any, required): Query parameters: - query: SQL query string - params: Optional query parameters (tuple) - limit: Maximum results (default 1000)

**Has Side Effects**: Yes

---

#### `monitor:get_session_events`

**Summary**: Handle monitor:get_session_events event

**Description**:

> Get all events for a specific session.
> 
> Args:
>     data: Query parameters:
>         - session_id: Session ID to query
>         - include_memory: Include events from memory buffer (default True)
>         - reverse: Sort newest first (default True)
> 
> Returns:
>     Events for the session

**Parameters**:

- `session_id` (Any, required): session_id parameter
- `include_memory` (Any, optional): include_memory parameter [default: True]
- `reverse` (Any, optional): reverse parameter [default: True]
- `data` (Any, required): Query parameters: - session_id: Session ID to query - include_memory: Include events from memory buffer (default True) - reverse: Sort newest first (default True)

**Has Side Effects**: Yes

---

#### `monitor:get_correlation_chain`

**Summary**: Handle monitor:get_correlation_chain event

**Description**:

> Get all events in a correlation chain.
> 
> Args:
>     data: Query parameters:
>         - correlation_id: Correlation ID to trace
>         - include_memory: Include events from memory buffer (default True)
> 
> Returns:
>     Events in the correlation chain

**Parameters**:

- `correlation_id` (Any, required): correlation_id parameter
- `include_memory` (Any, optional): include_memory parameter [default: True]
- `data` (Any, required): Query parameters: - correlation_id: Correlation ID to trace - include_memory: Include events from memory buffer (default True)

**Has Side Effects**: Yes

---

### Orchestration

*7 events*

#### `orchestration:start`

**Summary**: Handle orchestration:start event

**Description**:

> Start a new orchestration.

**Parameters**:

- `pattern` (Any, required): pattern parameter
- `vars` (Any, optional): vars parameter

**Has Side Effects**: Yes

---

#### `orchestration:message`

**Summary**: Handle orchestration:message event

**Description**:

> Route a message within an orchestration.

**Has Side Effects**: Yes

---

#### `orchestration:status`

**Summary**: Handle orchestration:status event

**Description**:

> Get orchestration status.

**Parameters**:

- `orchestration_id` (Any, required): orchestration_id parameter

**Has Side Effects**: Yes

---

#### `orchestration:terminate`

**Summary**: Handle orchestration:terminate event

**Description**:

> Manually terminate an orchestration.

**Parameters**:

- `orchestration_id` (Any, required): orchestration_id parameter

**Has Side Effects**: Yes

---

#### `orchestration:list_patterns`

**Summary**: Handle orchestration:list_patterns event

**Description**:

> List available orchestration patterns.

**Has Side Effects**: Yes

---

#### `orchestration:load_pattern`

**Summary**: Handle orchestration:load_pattern event

**Description**:

> Load and validate an orchestration pattern.

**Parameters**:

- `pattern` (Any, required): pattern parameter

**Has Side Effects**: Yes

---

#### `orchestration:get_instance`

**Summary**: Handle orchestration:get_instance event

**Description**:

> Get detailed information about an orchestration instance.

**Parameters**:

- `orchestration_id` (Any, required): orchestration_id parameter

**Has Side Effects**: Yes

---

### Permission

*6 events*

#### `permission:get_profile`

**Summary**: Handle permission:get_profile event

**Description**:

> Get details of a specific permission profile.
> 
> Args:
>     level (str): The permission level/profile name (one of: restricted, standard, trusted, researcher)
> 
> Returns:
>     profile: The permission profile details

**Parameters**:

- `level` (str, required): The permission level/profile name (one of: restricted, standard, trusted, researcher)

**Has Side Effects**: Yes

---

#### `permission:set_agent`

**Summary**: Handle permission:set_agent event

**Description**:

> Set permissions for an agent.
> 
> Args:
>     agent_id (str): The agent ID to set permissions for
>     profile (str): Base profile to use (optional, defaults: restricted)
>     permissions (dict): Full permission object (optional)
>     overrides (dict): Permission overrides to apply (optional)
> 
> Returns:
>     agent_id: The agent ID
>     permissions: The applied permissions

**Parameters**:

- `agent_id` (str, required): The agent ID to set permissions for
- `permissions` (dict, optional): Full permission object (optional)
- `profile` (str, optional): Base profile to use (optional, defaults: restricted) [default: restricted]
- `overrides` (dict, optional): Permission overrides to apply (optional)

**Has Side Effects**: Yes

---

#### `permission:validate_spawn`

**Summary**: Handle permission:validate_spawn event

**Description**:

> Validate if parent can spawn child with given permissions.
> 
> Args:
>     parent_id (str): The parent agent ID
>     child_permissions (dict): The requested permissions for the child agent
> 
> Returns:
>     valid: Whether the spawn is allowed
>     parent_id: The parent agent ID

**Parameters**:

- `parent_id` (str, required): The parent agent ID
- `child_permissions` (dict, required): The requested permissions for the child agent

**Has Side Effects**: Yes

---

#### `permission:get_agent`

**Summary**: Handle permission:get_agent event

**Description**:

> Get permissions for a specific agent.
> 
> Args:
>     agent_id (str): The agent ID to query permissions for
> 
> Returns:
>     agent_id: The agent ID
>     permissions: The agent's permissions

**Parameters**:

- `agent_id` (str, required): The agent ID to query permissions for

**Has Side Effects**: Yes

---

#### `permission:remove_agent`

**Summary**: Handle permission:remove_agent event

**Description**:

> Remove permissions for an agent.
> 
> Args:
>     agent_id (str): The agent ID to remove permissions for
> 
> Returns:
>     agent_id: The agent ID
>     status: Removal status (removed)

**Parameters**:

- `agent_id` (str, required): The agent ID to remove permissions for

**Has Side Effects**: Yes

---

#### `permission:list_profiles`

**Summary**: Handle permission:list_profiles event

**Description**:

> List available permission profiles.
> 
> Returns:
>     profiles: Dictionary containing all permission profiles with their tools and capabilities

**Has Side Effects**: Yes

---

### Sandbox

*5 events*

#### `sandbox:create`

**Summary**: Handle sandbox:create event

**Description**:

> Create a new sandbox for an agent.
> 
> Args:
>     agent_id (str): The agent ID
>     config (dict): Sandbox configuration (optional)
>         mode (str): Sandbox isolation mode (optional, default: isolated, allowed: isolated, shared, readonly)
>         parent_agent_id (str): Parent agent for nested sandboxes (optional)
>         session_id (str): Session ID for shared sandboxes (optional)
>         parent_share (str): Parent sharing mode (optional)
>         session_share (bool): Enable session sharing (optional)
> 
> Returns:
>     agent_id: The agent ID
>     sandbox: The created sandbox details

**Parameters**:

- `agent_id` (str, required): The agent ID
- `config` (dict, optional): Sandbox configuration (optional)
- `mode` (str, optional): Sandbox isolation mode (optional, default: isolated, allowed: isolated, shared, readonly) [default: isolated]
- `parent_agent_id` (str, optional): Parent agent for nested sandboxes (optional)
- `session_id` (str, optional): Session ID for shared sandboxes (optional)
- `parent_share` (str, optional): Parent sharing mode (optional)
- `session_share` (bool, optional): Enable session sharing (optional)

**Has Side Effects**: Yes

---

#### `sandbox:get`

**Summary**: Handle sandbox:get event

**Description**:

> Get sandbox information for an agent.
> 
> Args:
>     agent_id (str): The agent ID
> 
> Returns:
>     agent_id: The agent ID
>     sandbox: The sandbox details

**Parameters**:

- `agent_id` (str, required): The agent ID

**Has Side Effects**: Yes

---

#### `sandbox:remove`

**Summary**: Handle sandbox:remove event

**Description**:

> Remove an agent's sandbox.
> 
> Args:
>     agent_id (str): The agent ID
>     force (bool): Force removal even with nested children (optional, default: false)
> 
> Returns:
>     agent_id: The agent ID
>     removed: Whether the sandbox was removed

**Parameters**:

- `agent_id` (str, required): The agent ID
- `force` (bool, optional): Force removal even with nested children (optional, default: false) [default: false]

**Has Side Effects**: Yes

---

#### `sandbox:list`

**Summary**: Handle sandbox:list event

**Description**:

> List all active sandboxes.
> 
> Returns:
>     sandboxes: List of active sandbox details
>     count: Total number of sandboxes

**Has Side Effects**: Yes

---

#### `sandbox:stats`

**Summary**: Handle sandbox:stats event

**Description**:

> Get sandbox statistics.
> 
> Returns:
>     stats: Sandbox usage statistics

**Has Side Effects**: Yes

---

### State

*4 events*

#### `state:get`

**Summary**: Handle state:get event

**Description**:

> Get a value from shared state.
> 
> Args:
>     namespace (str): The namespace to get from (default: "global")
>     key (str): The key to retrieve (required)
> 
> Returns:
>     Dictionary with value, found status, namespace, and key
> 
> Example:
>     {"namespace": "agent", "key": "session_data"}

**Parameters**:

- `namespace` (str, optional): The namespace to get from (default: "global") [default: global]
- `key` (str, required): The key to retrieve (required) [default: ]

**Has Side Effects**: Yes

---

#### `state:set`

**Summary**: Handle state:set event

**Description**:

> Set a value in shared state.
> 
> Args:
>     namespace (str): The namespace to set in (default: "global")
>     key (str): The key to set (required)
>     value (any): The value to store (required)
>     metadata (dict): Optional metadata to attach (default: {})
> 
> Returns:
>     Dictionary with status, namespace, and key
> 
> Example:
>     {"namespace": "agent", "key": "config", "value": {"model": "claude-2"}}

**Parameters**:

- `namespace` (str, optional): The namespace to set in (default: "global") [default: global]
- `key` (str, required): The key to set (required) [default: ]
- `value` (any, required): The value to store (required)
- `metadata` (dict, optional): Optional metadata to attach (default: {}) [default: {}]

**Has Side Effects**: Yes

---

#### `state:delete`

**Summary**: Handle state:delete event

**Description**:

> Delete a key from shared state.
> 
> Args:
>     namespace (str): The namespace to delete from (default: "global")
>     key (str): The key to delete (required)
> 
> Returns:
>     Dictionary with status, namespace, and key

**Parameters**:

- `namespace` (str, optional): The namespace to delete from (default: "global") [default: global]
- `key` (str, required): The key to delete (required) [default: ]

**Has Side Effects**: Yes

---

#### `state:list`

**Summary**: Handle state:list event

**Description**:

> List keys in shared state.
> 
> Args:
>     namespace (str): Filter by namespace (optional)
>     pattern (str): Filter by pattern (optional, supports * wildcard)
> 
> Returns:
>     Dictionary with list of keys

**Parameters**:

- `namespace` (str, optional): Filter by namespace (optional)
- `pattern` (str, optional): Filter by pattern (optional, supports * wildcard)

**Has Side Effects**: Yes

---

### System

*8 events*

#### `system:context`

**Summary**: Handle system:context event

**Description**:

> Receive infrastructure context - state manager is available.

**Has Side Effects**: Yes

---

#### `system:health`

**Summary**: Handle system:health event

**Description**:

> System health check including module status.

**Has Side Effects**: Yes

---

#### `system:startup`

**Summary**: Handle system:startup event

**Description**:

> Initialize health check plugin.

**Parameters**:

- `config` (Dict[str, Any], required): config parameter

**Has Side Effects**: Yes

---

#### `system:shutdown`

**Summary**: Handle system:shutdown event

**Description**:

> Clean up on shutdown.

**Has Side Effects**: Yes

---

#### `system:discover`

**Summary**: Handle system:discover event

**Description**:

> Discover all available events in the system.
> 
> Parameters:
>     namespace: Optional namespace filter (e.g., "agent", "completion")
>     include_internal: Include internal system events (default: False)
>     detail: Level of detail ("summary", "parameters", "full", "cached") (default: "summary")
> 
> Returns:
>     Dictionary with available events grouped by namespace

**Parameters**:

- `namespace` (Any, optional): Optional namespace filter (e.g., "agent", "completion")
- `include_internal` (Any, optional): Include internal system events (default: False) [default: False]
- `detail` (Any, optional): Level of detail ("summary", "parameters", "full", "cached") (default: "summary") [default: summary]

**Complexity**: High (15)

**Has Side Effects**: Yes

---

#### `system:help`

**Summary**: Handle system:help event

**Description**:

> Get detailed help for a specific event.
> 
> Args:
>     event (str): The event name to get help for (required)
> 
> Returns:
>     Detailed event documentation including parameters and examples

**Parameters**:

- `event` (str, required): The event name to get help for (required)

**Complexity**: High (15)

**Has Side Effects**: Yes

---

#### `system:capabilities`

**Summary**: Handle system:capabilities event

**Description**:

> Get a summary of daemon capabilities.

**Has Side Effects**: Yes

---

#### `system:ready`

**Summary**: Handle system:ready event

**Description**:

> Return long-running server task to keep daemon alive.

**Has Side Effects**: Yes

---

### Transport

*2 events*

#### `transport:create`

**Summary**: Handle transport:create event

**Description**:

> Create Unix socket transport if requested.

**Parameters**:

- `transport_type` (Any, required): transport_type parameter
- `config` (Any, optional): config parameter

**Has Side Effects**: Yes

---

#### `transport:message`

**Summary**: Handle transport:message event

**Description**:

> Handle legacy transport:message events by converting them.

**Parameters**:

- `command` (Any, required): command parameter
- `parameters` (Any, optional): parameters parameter

**Has Side Effects**: Yes

---
