# KSI Events Reference

138 events | 20 namespaces | Generated: 2025-07-02

## Notation
- `param*` = required
- `param?` = optional
- `param=value` = default value
- `param:type` = typed parameter

## agent (18)

**agent:broadcast** (message?, sender="system") - Broadcast a message to all agents.
  `agent.agent_service.handle_broadcast`

**agent:create_identity** (agent_id*, identity?) - Create a new agent identity.
  `agent.agent_service.handle_create_identity`

**agent:discover_peers** (agent_id*, capabilities?, roles?) - Discover other agents and their capabilities.
  `agent.agent_service.handle_discover_peers`

**agent:get_capabilities** (agent_id*) - Get capabilities of an agent or all agents.
  `agent.agent_service.handle_get_capabilities`

**agent:get_identity** (agent_id*) - Get a specific agent identity.
  `agent.agent_service.handle_get_identity`

**agent:list** (status*) - List registered agents.
  `agent.agent_service.handle_list_agents`

**agent:list_identities** - List agent identities.
  `agent.agent_service.handle_list_identities`

**agent:negotiate_roles** (participants?, type="collaborative", context?) - Coordinate role negotiation between agents.
  `agent.agent_service.handle_negotiate_roles`

**agent:register** (agent_id*, info?) - Register an external agent.
  `agent.agent_service.handle_register_agent`

**agent:remove_identity** (agent_id*) - Remove an agent identity.
  `agent.agent_service.handle_remove_identity`

**agent:restart** (agent_id*) - Restart an agent.
  `agent.agent_service.handle_restart_agent`

**agent:route_task** (task?) - Route a task to an appropriate agent.
  `agent.agent_service.handle_route_task`

**agent:send_message** (agent_id*, message?) - Send a message to an agent.
  `agent.agent_service.handle_send_message`

**agent:spawn** - Spawn a new agent thread with optional profile.
  - agent_id*
  - profile*
  - profile_name*
  - composition*
  - session_id*
  - spawn_mode="fixed"
  - selection_context?
  - task*
  - enable_tools=false
  - permission_profile="standard"
  - sandbox_config?
  - permission_overrides?
  - config*
  - context*
  - _composition_selection*
  `agent.agent_service.handle_spawn_agent`

**agent:terminate** (agent_id*, force=false) - Terminate an agent thread.
  `agent.agent_service.handle_terminate_agent`

**agent:unregister** (agent_id*) - Unregister an agent.
  `agent.agent_service.handle_unregister_agent`

**agent:update_composition** (agent_id*, new_composition*, reason="Adaptation required") - Handle agent composition update request.
  `agent.agent_service.handle_update_composition`

**agent:update_identity** (agent_id*, updates?) - Update an agent identity.
  `agent.agent_service.handle_update_identity`

## api (1)

**api:schema** - Get complete API schema using direct function inspection.
  `daemon_core.handle_api_schema`

## async_state (7)

**async_state:delete** (namespace="default", key="") - Delete key from async state.
  `core.state.handle_async_delete`

**async_state:get** (namespace="default", key="") - Get value from async state.
  `core.state.handle_async_get`

**async_state:get_keys** (namespace="default") - Get all keys in a namespace.
  `core.state.handle_async_get_keys`

**async_state:pop** (namespace="default", queue_name="") - Pop value from async queue.
  `core.state.handle_async_pop`

**async_state:push** (namespace="default", queue_name="", value*) - Push value to async queue.
  `core.state.handle_async_push`

**async_state:queue_length** (namespace="default", queue_name="") - Get length of async queue.
  `core.state.handle_async_queue_length`

**async_state:set** (namespace="default", key="", value*) - Set value in async state.
  `core.state.handle_async_set`

## completion (8)

**completion:async** (session_id="default", model="unknown", request_id*) - Handle async completion requests with smart queueing.
  `completion.completion_service.handle_async_completion`

**completion:cancel** (request_id*) - Cancel an in-progress completion.
  `completion.completion_service.handle_cancel_completion`

**completion:cancelled** (timestamp="", correlation_id*) - Broadcast certain events to all connected clients.
  `transport.unix_socket.handle_broadcastable_event`

**completion:error** (timestamp="", correlation_id*) - Broadcast certain events to all connected clients.
  `transport.unix_socket.handle_broadcastable_event`

**completion:progress** (timestamp="", correlation_id*) - Broadcast certain events to all connected clients.
  `transport.unix_socket.handle_broadcastable_event`

**completion:result** (timestamp="", correlation_id*) - Broadcast certain events to all connected clients.
  `transport.unix_socket.handle_broadcastable_event`

**completion:session_status** (session_id*) - Get detailed status for a specific session.
  `completion.completion_service.handle_session_status`

**completion:status** - Get status of all active completions.
  `completion.completion_service.handle_completion_status`

## composition (19)

**composition:capabilities** (group*) - Get available KSI capabilities from declarative schema.
  `composition.composition_service.handle_get_capabilities`

**composition:compose** (name*, type*, variables?) - Handle generic composition request.
  `composition.composition_service.handle_compose`

**composition:create** - Handle runtime composition creation.
  - name*
  - type="profile"
  - extends="base_agent"
  - description?
  - author="dynamic_agent"
  - metadata?
  - config?
  - role="assistant"
  - model="sonnet"
  - capabilities?
  - tools?
  - agent_id*
  - prompt*
  - components*
  `composition.composition_service.handle_create_composition`

**composition:discover** (metadata_filter*) - Discover available compositions using index with optional metadata filtering.
  `composition.composition_service.handle_discover`

**composition:get** (name*, type*) - Get a composition definition.
  `composition.composition_service.handle_get`

**composition:get_metadata** (full_name*) - Get metadata for a composition.
  `composition.composition_service.handle_get_metadata`

**composition:get_path** (full_name*) - Get the file path for a composition.
  `composition.composition_service.handle_get_path`

**composition:index_file** (file_path*) - Index a single composition file.
  `composition.composition_service.handle_index_file`

**composition:list** (type="all") - List all compositions of a given type.
  `composition.composition_service.handle_list`

**composition:load_bulk** (names?) - Universal bulk loading for agent efficiency.
  `composition.composition_service.handle_load_bulk`

**composition:load_tree** (name*, max_depth=5) - Universal tree loading based on composition's declared strategy.
  `composition.composition_service.handle_load_tree`

**composition:profile** (name*, variables?) - Handle profile composition request.
  `composition.composition_service.handle_compose_profile`

**composition:prompt** (name*, variables?) - Handle prompt composition request.
  `composition.composition_service.handle_compose_prompt`

**composition:rebuild_index** (repository_id="local") - Rebuild the composition index.
  `composition.composition_service.handle_rebuild_index`

**composition:reload** - Reload compositions by rebuilding index.
  `composition.composition_service.handle_reload`

**composition:select** - Handle intelligent composition selection using sophisticated scoring algorithm.
  - agent_id="unknown"
  - role*
  - capabilities?
  - task_description*
  - preferred_style*
  - context_variables?
  - requirements?
  - max_suggestions=1
  `composition.composition_service.handle_select_composition`

**composition:suggest** - Get top N composition suggestions for the given context.
  - agent_id="unknown"
  - role*
  - capabilities?
  - task_description*
  - preferred_style*
  - context_variables?
  - requirements?
  - max_suggestions=3
  `composition.composition_service.handle_suggest_compositions`

**composition:validate** (name*, type*) - Validate a composition.
  `composition.composition_service.handle_validate`

**composition:validate_context** (composition_name*, context?) - Validate that a composition will work with the given context.
  `composition.composition_service.handle_validate_context`

## config (6)

**config:backup** (config_type:str*, file_path:str?, backup_name:str?) - Create manual backup of configuration.
  `config.config_service.handle_backup`

**config:get** (key:str*, config_type:str*, file_path:str?) - Get configuration value or entire config file.
  `config.config_service.handle_get`

**config:reload** (component:str*) - Reload configuration components.
  → daemon:config_reload, plugins:reload, composition:reload
  `config.config_service.handle_reload`

**config:rollback** (config_type:str*, file_path:str?, backup_name:str?) - Rollback configuration to previous backup.
  → config:rolled_back
  `config.config_service.handle_rollback`

**config:set** - Set configuration value with automatic backup.
  - key:str*: Configuration key path (e.g., 'daemon.log_level') (required)
  - value:any*: Value to set (required)
  - config_type:str*: Type of config ('daemon', 'composition', 'schema', 'capabilities')
  - file_path:str?: Specific config file path (optional)
  - create_backup:bool*: Create backup before modification (default: true)
  → config:changed
  `config.config_service.handle_set`

**config:validate** (config_type:str*, file_path:str?, schema_path:str?) - Validate configuration file syntax and schema.
  `config.config_service.handle_validate`

## conversation (10)

**conversation:acquire_lock** (request_id*, conversation_id*, metadata?) - Acquire lock for a conversation.
  `conversation.conversation_lock.handle_acquire_lock`

**conversation:active** (max_lines=100, max_age_hours=2160) - Find active conversations from recent COMPLETION_RESULT messages.
  `conversation.conversation_service.handle_active_conversations`

**conversation:export** (session_id*, format="markdown") - Export conversation to markdown or JSON format.
  `conversation.conversation_service.handle_export_conversation`

**conversation:fork_detected** (request_id*, expected_conversation_id*, actual_conversation_id*) - Handle fork detection.
  `conversation.conversation_lock.handle_fork_detected`

**conversation:get** - Get a specific conversation with full message history.
  - session_id*
  - limit=1000
  - offset=0
  - conversation_id*
  `conversation.conversation_service.handle_get_conversation`

**conversation:list** - List available conversations with metadata.
  - limit=100
  - offset=0
  - sort_by="last_timestamp"
  - reverse=true
  - start_date*
  - end_date*
  `conversation.conversation_service.handle_list_conversations`

**conversation:lock_status** (conversation_id*) - Get lock status for a conversation.
  `conversation.conversation_lock.handle_lock_status`

**conversation:release_lock** (request_id*) - Release a conversation lock.
  `conversation.conversation_lock.handle_release_lock`

**conversation:search** (query="", limit=50, search_in?) - Search conversations by content.
  `conversation.conversation_service.handle_search_conversations`

**conversation:stats** - Get statistics about conversations.
  `conversation.conversation_service.handle_conversation_stats`

## correlation (6)

**correlation:chain** (correlation_id*) - Get the full trace chain for a correlation ID.
  `core.correlation.handle_get_trace_chain`

**correlation:cleanup** (max_age_hours*) - Clean up old correlation traces.
  `core.correlation.handle_cleanup`

**correlation:current** - Get current correlation context.
  `core.correlation.handle_get_current`

**correlation:stats** - Get correlation tracking statistics.
  `core.correlation.handle_get_stats`

**correlation:trace** (correlation_id*) - Get a specific correlation trace.
  `core.correlation.handle_get_trace`

**correlation:tree** (correlation_id*) - Get the full trace tree for a correlation ID.
  `core.correlation.handle_get_trace_tree`

## file (6)

**file:backup** (path:str*, backup_name:str?) - Create a manual backup of a file.
  `file.file_service.handle_backup`

**file:list** - List files in a directory with filtering.
  - path:str*: The directory path to list (required)
  - pattern:str="*": Filename pattern to match (optional)
  - recursive:bool*: Include subdirectories (default: false)
  - include_hidden:bool*: Include hidden files (default: false)
  `file.file_service.handle_list`

**file:read** (path:str*, encoding:str*, binary:bool*) - Read a file with safety validation.
  `file.file_service.handle_read`

**file:rollback** (path:str*, backup_name:str?) - Rollback a file to a previous backup.
  `file.file_service.handle_rollback`

**file:validate** (path:str*, check_writable:bool*, check_content:str?) - Validate file access and properties.
  `file.file_service.handle_validate`

**file:write** - Write to a file with automatic backup.
  - path:str*: The file path to write (required)
  - content:str*: The content to write (required)
  - encoding:str*: File encoding (default: utf-8)
  - create_backup:bool*: Create backup before writing (default: true)
  - binary:bool*: Write binary data (content should be hex string) (default: false)
  `file.file_service.handle_write`

## injection (8)

**injection:batch** (injections?) - Handle batch injection request.
  `injection.injection_router.handle_injection_batch`

**injection:clear** (session_id*, mode*) - Handle clear injections request.
  `injection.injection_router.handle_injection_clear`

**injection:execute** - Execute a queued injection by creating a new completion request.
  - session_id*
  - content*
  - request_id*
  - target_sessions?
  - model="claude-cli/sonnet"
  - priority="normal"
  - injection_type="system_reminder"
  `injection.injection_router.execute_injection`

**injection:inject** - Handle unified injection request.
  - mode="next"
  - position="before_prompt"
  - content=""
  - session_id*
  - priority="normal"
  - metadata?
  `injection.injection_router.handle_injection_inject`

**injection:list** (session_id*) - Handle list injections request.
  `injection.injection_router.handle_injection_list`

**injection:process_result** (request_id*, result?, injection_metadata?) - Process a completion result for injection - explicitly called by completion service.
  `injection.injection_router.handle_injection_process_result`

**injection:queue** - Handle queue injection metadata request from completion service.
  `injection.injection_router.handle_injection_queue`

**injection:status** - Get injection router status.
  `injection.injection_router.handle_injection_status`

## message (6)

**message:connect** (agent_id*) - Handle agent connection.
  `messaging.message_bus.handle_connect_agent`

**message:disconnect** (agent_id*) - Handle agent disconnection.
  `messaging.message_bus.handle_disconnect_agent`

**message:publish** (agent_id*, event_type*, message?) - Handle message publication.
  `messaging.message_bus.handle_publish`

**message:subscribe** (agent_id*, event_types?) - Handle subscription request.
  `messaging.message_bus.handle_subscribe`

**message:subscriptions** (agent_id*) - Get subscription information.
  `messaging.message_bus.handle_get_subscriptions`

**message:unsubscribe** (agent_id*, event_types?) - Handle unsubscription request.
  `messaging.message_bus.handle_unsubscribe`

## message_bus (1)

**message_bus:stats** - Get message bus statistics.
  `messaging.message_bus.handle_get_stats`

## module (3)

**module:events** - List all registered events and patterns.
  `daemon_core.handle_list_events`

**module:inspect** (module_name*) - Inspect a specific module using direct function metadata.
  `daemon_core.handle_inspect_module`

**module:list** - List all loaded modules.
  `daemon_core.handle_list_modules`

## monitor (8)

**monitor:clear_log** - Clear event log (admin operation).
  `core.monitor.handle_clear_log`

**monitor:get_correlation_chain** (correlation_id*, include_memory*) - Get all events in a correlation chain.
  `core.monitor.handle_get_correlation_chain`

**monitor:get_events** - Query event log with filtering and pagination.
  - event_patterns*: List of event name patterns (supports wildcards)
  - client_id*: Filter by specific client
  - since*: Start time (ISO string or timestamp)
  - until*: End time (ISO string or timestamp)
  - limit*: Maximum number of events to return
  - reverse*: Return newest first (default True)
  `core.monitor.handle_get_events`

**monitor:get_session_events** (session_id*, include_memory*, reverse*) - Get all events for a specific session.
  `core.monitor.handle_get_session_events`

**monitor:get_stats** - Get event log statistics.
  `core.monitor.handle_get_stats`

**monitor:query** (query*, params?, limit*) - Execute custom SQL query against event database.
  `core.monitor.handle_query`

**monitor:subscribe** (client_id*, event_patterns*, writer*) - Subscribe to real-time event stream.
  `core.monitor.handle_subscribe`

**monitor:unsubscribe** (client_id*) - Unsubscribe from event stream.
  `core.monitor.handle_unsubscribe`

## orchestration (7)

**orchestration:get_instance** (orchestration_id*) - Get detailed information about an orchestration instance.
  `orchestration.orchestration_service.handle_get_instance`

**orchestration:list_patterns** - List available orchestration patterns.
  `orchestration.orchestration_service.handle_list_patterns`

**orchestration:load_pattern** (pattern*) - Load and validate an orchestration pattern.
  `orchestration.orchestration_service.handle_load_pattern`

**orchestration:message** - Route a message within an orchestration.
  `orchestration.orchestration_service.handle_orchestration_message`

**orchestration:start** (pattern*, vars?) - Start a new orchestration.
  `orchestration.orchestration_service.handle_orchestration_start`

**orchestration:status** (orchestration_id*) - Get orchestration status.
  `orchestration.orchestration_service.handle_orchestration_status`

**orchestration:terminate** (orchestration_id*) - Manually terminate an orchestration.
  `orchestration.orchestration_service.handle_orchestration_terminate`

## permission (6)

**permission:get_agent** (agent_id:str*) - Get permissions for a specific agent.
  `permissions.permission_service.handle_get_agent_permissions`

**permission:get_profile** (level:str*) - Get details of a specific permission profile.
  `permissions.permission_service.handle_get_profile`

**permission:list_profiles** - List available permission profiles.
  `permissions.permission_service.handle_list_profiles`

**permission:remove_agent** (agent_id:str*) - Remove permissions for an agent.
  `permissions.permission_service.handle_remove_agent_permissions`

**permission:set_agent** - Set permissions for an agent.
  - agent_id:str*: The agent ID to set permissions for
  - permissions:dict?: Full permission object (optional)
  - profile:str="restricted": Base profile to use (optional, defaults: restricted)
  - overrides:dict?: Permission overrides to apply (optional)
  `permissions.permission_service.handle_set_agent_permissions`

**permission:validate_spawn** (parent_id:str*, child_permissions:dict*) - Validate if parent can spawn child with given permissions.
  `permissions.permission_service.handle_validate_spawn`

## sandbox (5)

**sandbox:create** (agent_id:str*, config:dict?) - Create a new sandbox for an agent.
  `permissions.permission_service.handle_create_sandbox`

**sandbox:get** (agent_id:str*) - Get sandbox information for an agent.
  `permissions.permission_service.handle_get_sandbox`

**sandbox:list** - List all active sandboxes.
  `permissions.permission_service.handle_list_sandboxes`

**sandbox:remove** (agent_id:str*, force:bool=false) - Remove an agent's sandbox.
  `permissions.permission_service.handle_remove_sandbox`

**sandbox:stats** - Get sandbox statistics.
  `permissions.permission_service.handle_sandbox_stats`

## state (4)

**state:delete** (namespace:str*, key:str*) - Delete a key from shared state.
  `core.state.handle_delete`

**state:get** (namespace:str*, key:str*) - Get a value from shared state.
  `core.state.handle_get`

**state:list** (namespace:str?, pattern:str?) - List keys in shared state.
  `core.state.handle_list`

**state:set** - Set a value in shared state.
  - namespace:str*: The namespace to set in (default: "global")
  - key:str*: The key to set (required)
  - value:any*: The value to store (required)
  - metadata:dict?: Optional metadata to attach (default: {})
  `core.state.handle_set`

## system (7)

**system:context** - Receive infrastructure context - state manager is available.
  `core.state.handle_context`

**system:discover** (detail*, namespace?, event?) - Universal discovery endpoint - everything you need to understand KSI.
  `core.discovery.handle_discover`

**system:health** - System health check including module status.
  `daemon_core.handle_system_health`

**system:help** (event*) - Get detailed help for a specific event.
  `core.discovery.handle_help`

**system:ready** - Return long-running server task to keep daemon alive.
  `transport.unix_socket.handle_ready`

**system:shutdown** - Clean up on shutdown.
  `core.health.handle_shutdown`

**system:startup** - Initialize health check plugin.
  `core.health.handle_startup`

## transport (2)

**transport:create** (transport_type*, config?) - Create Unix socket transport if requested.
  `transport.unix_socket.handle_create_transport`

**transport:message** (command*, parameters?) - Handle legacy transport:message events by converting them.
  `messaging.message_bus.handle_transport_message`
