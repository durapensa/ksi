# KSI Event Documentation (Compact)

Generated: 2025-07-02T09:53:38.808046
Total Events: 138 | Namespaces: 20

## Parameter Format

Parameters are shown as: `[type, required, default, description]`
- When type is 'Any', it may be omitted in display
- When required is true, shown as '(required)'
- When required is false with a default, shown as '(default: value)'
- When required is false without default, shown as '(optional)'

## Table of Contents

- [agent](#agent) (18 events)
- [api](#api) (1 events)
- [async_state](#async_state) (7 events)
- [completion](#completion) (8 events)
- [composition](#composition) (19 events)
- [config](#config) (6 events)
- [conversation](#conversation) (10 events)
- [correlation](#correlation) (6 events)
- [file](#file) (6 events)
- [injection](#injection) (8 events)
- [message](#message) (6 events)
- [message_bus](#message_bus) (1 events)
- [module](#module) (3 events)
- [monitor](#monitor) (8 events)
- [orchestration](#orchestration) (7 events)
- [permission](#permission) (6 events)
- [sandbox](#sandbox) (5 events)
- [state](#state) (4 events)
- [system](#system) (7 events)
- [transport](#transport) (2 events)

---

## agent

**18 events**

### agent:broadcast

Broadcast a message to all agents.
*ksi_daemon.agent.agent_service.handle_broadcast*

**Parameters**:
- **message** (optional) - message parameter
- **sender** (default: system) - sender parameter

---

### agent:create_identity

Create a new agent identity.
*ksi_daemon.agent.agent_service.handle_create_identity*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **identity** (optional) - identity parameter

---

### agent:discover_peers

Discover other agents and their capabilities.
*ksi_daemon.agent.agent_service.handle_discover_peers*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **capabilities** (optional) - capabilities parameter
- **roles** (optional) - roles parameter

---

### agent:get_capabilities

Get capabilities of an agent or all agents.
*ksi_daemon.agent.agent_service.handle_get_capabilities*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### agent:get_identity

Get a specific agent identity.
*ksi_daemon.agent.agent_service.handle_get_identity*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### agent:list

List registered agents.
*ksi_daemon.agent.agent_service.handle_list_agents*

**Parameters**:
- **status** (required) - status parameter

---

### agent:list_identities

List agent identities.
*ksi_daemon.agent.agent_service.handle_list_identities*

---

### agent:negotiate_roles

Coordinate role negotiation between agents.
*ksi_daemon.agent.agent_service.handle_negotiate_roles*

**Parameters**:
- **participants** (optional) - participants parameter
- **type** (default: collaborative) - type parameter
- **context** (optional) - context parameter

---

### agent:register

Register an external agent.
*ksi_daemon.agent.agent_service.handle_register_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **info** (optional) - info parameter

---

### agent:remove_identity

Remove an agent identity.
*ksi_daemon.agent.agent_service.handle_remove_identity*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### agent:restart

Restart an agent.
*ksi_daemon.agent.agent_service.handle_restart_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### agent:route_task

Route a task to an appropriate agent.
*ksi_daemon.agent.agent_service.handle_route_task*

**Parameters**:
- **task** (optional) - task parameter

---

### agent:send_message

Send a message to an agent.
*ksi_daemon.agent.agent_service.handle_send_message*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **message** (optional) - message parameter

---

### agent:spawn

Spawn a new agent thread with optional profile.
*ksi_daemon.agent.agent_service.handle_spawn_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **profile** (required) - profile parameter
- **profile_name** (required) - profile_name parameter
- **composition** (required) - composition parameter
- **session_id** (required) - session_id parameter
- **spawn_mode** (default: fixed) - spawn_mode parameter
- **selection_context** (optional) - selection_context parameter
- **task** (required) - task parameter
- **enable_tools** (default: False) - enable_tools parameter
- **permission_profile** (default: standard) - permission_profile parameter
- **sandbox_config** (optional) - sandbox_config parameter
- **permission_overrides** (optional) - permission_overrides parameter
- **config** (required) - config parameter
- **context** (required) - context parameter
- **_composition_selection** (required) - _composition_selection parameter

---

### agent:terminate

Terminate an agent thread.
*ksi_daemon.agent.agent_service.handle_terminate_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **force** (default: False) - force parameter

---

### agent:unregister

Unregister an agent.
*ksi_daemon.agent.agent_service.handle_unregister_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### agent:update_composition

Handle agent composition update request.
*ksi_daemon.agent.agent_service.handle_update_composition*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **new_composition** (required) - new_composition parameter
- **reason** (default: Adaptation required) - reason parameter

---

### agent:update_identity

Update an agent identity.
*ksi_daemon.agent.agent_service.handle_update_identity*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **updates** (optional) - updates parameter

---

## api

**1 events**

### api:schema

Get complete API schema using direct function inspection.
*ksi_daemon.daemon_core.handle_api_schema*

---

## async_state

**7 events**

### async_state:delete

Delete key from async state.
*ksi_daemon.core.state.handle_async_delete*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **key** (default: "") - key parameter

---

### async_state:get

Get value from async state.
*ksi_daemon.core.state.handle_async_get*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **key** (default: "") - key parameter

---

### async_state:get_keys

Get all keys in a namespace.
*ksi_daemon.core.state.handle_async_get_keys*

**Parameters**:
- **namespace** (default: default) - namespace parameter

---

### async_state:pop

Pop value from async queue.
*ksi_daemon.core.state.handle_async_pop*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **queue_name** (default: "") - queue_name parameter

---

### async_state:push

Push value to async queue.
*ksi_daemon.core.state.handle_async_push*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **queue_name** (default: "") - queue_name parameter
- **value** (required) - value parameter

---

### async_state:queue_length

Get length of async queue.
*ksi_daemon.core.state.handle_async_queue_length*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **queue_name** (default: "") - queue_name parameter

---

### async_state:set

Set value in async state.
*ksi_daemon.core.state.handle_async_set*

**Parameters**:
- **namespace** (default: default) - namespace parameter
- **key** (default: "") - key parameter
- **value** (required) - value parameter

---

## completion

**8 events**

### completion:async

Handle async completion requests with smart queueing.
*ksi_daemon.completion.completion_service.handle_async_completion*

**Parameters**:
- **session_id** (default: default) - session_id parameter
- **model** (default: unknown) - model parameter
- **request_id** (required) - request_id parameter

---

### completion:cancel

Cancel an in-progress completion.
*ksi_daemon.completion.completion_service.handle_cancel_completion*

**Parameters**:
- **request_id** (required) - request_id parameter

---

### completion:cancelled

Broadcast certain events to all connected clients.
*ksi_daemon.transport.unix_socket.handle_broadcastable_event*

**Parameters**:
- **timestamp** (default: "") - timestamp parameter
- **correlation_id** (required) - correlation_id parameter

---

### completion:error

Broadcast certain events to all connected clients.
*ksi_daemon.transport.unix_socket.handle_broadcastable_event*

**Parameters**:
- **timestamp** (default: "") - timestamp parameter
- **correlation_id** (required) - correlation_id parameter

---

### completion:progress

Broadcast certain events to all connected clients.
*ksi_daemon.transport.unix_socket.handle_broadcastable_event*

**Parameters**:
- **timestamp** (default: "") - timestamp parameter
- **correlation_id** (required) - correlation_id parameter

---

### completion:result

Broadcast certain events to all connected clients.
*ksi_daemon.transport.unix_socket.handle_broadcastable_event*

**Parameters**:
- **timestamp** (default: "") - timestamp parameter
- **correlation_id** (required) - correlation_id parameter

---

### completion:session_status

Get detailed status for a specific session.
*ksi_daemon.completion.completion_service.handle_session_status*

**Parameters**:
- **session_id** (required) - session_id parameter

---

### completion:status

Get status of all active completions.
*ksi_daemon.completion.completion_service.handle_completion_status*

---

## composition

**19 events**

### composition:capabilities

Get available KSI capabilities from declarative schema.
*ksi_daemon.composition.composition_service.handle_get_capabilities*

**Parameters**:
- **group** (required) - group parameter

---

### composition:compose

Handle generic composition request.
*ksi_daemon.composition.composition_service.handle_compose*

**Parameters**:
- **name** (required) - name parameter
- **type** (required) - type parameter
- **variables** (optional) - variables parameter

---

### composition:create

Handle runtime composition creation.
*ksi_daemon.composition.composition_service.handle_create_composition*

**Parameters**:
- **name** (required) - name parameter
- **type** (default: profile) - type parameter
- **extends** (default: base_agent) - extends parameter
- **description** (optional) - description parameter
- **author** (default: dynamic_agent) - author parameter
- **metadata** (optional) - metadata parameter
- **config** (optional) - config parameter
- **role** (default: assistant) - role parameter
- **model** (default: sonnet) - model parameter
- **capabilities** (optional) - capabilities parameter
- **tools** (optional) - tools parameter
- **agent_id** (required) - agent_id parameter
- **prompt** (required) - prompt parameter
- **components** (required) - components parameter

---

### composition:discover

Discover available compositions using index with optional metadata filtering.
*ksi_daemon.composition.composition_service.handle_discover*

**Parameters**:
- **metadata_filter** (required) - metadata_filter parameter

---

### composition:get

Get a composition definition.
*ksi_daemon.composition.composition_service.handle_get*

**Parameters**:
- **name** (required) - name parameter
- **type** (required) - type parameter

---

### composition:get_metadata

Get metadata for a composition.
*ksi_daemon.composition.composition_service.handle_get_metadata*

**Parameters**:
- **full_name** (required) - full_name parameter

---

### composition:get_path

Get the file path for a composition.
*ksi_daemon.composition.composition_service.handle_get_path*

**Parameters**:
- **full_name** (required) - full_name parameter

---

### composition:index_file

Index a single composition file.
*ksi_daemon.composition.composition_service.handle_index_file*

**Parameters**:
- **file_path** (required) - file_path parameter

---

### composition:list

List all compositions of a given type.
*ksi_daemon.composition.composition_service.handle_list*

**Parameters**:
- **type** (default: all) - type parameter

---

### composition:load_bulk

Universal bulk loading for agent efficiency.
*ksi_daemon.composition.composition_service.handle_load_bulk*

**Parameters**:
- **names** (optional) - names parameter

---

### composition:load_tree

Universal tree loading based on composition's declared strategy.
*ksi_daemon.composition.composition_service.handle_load_tree*

**Parameters**:
- **name** (required) - name parameter
- **max_depth** (default: 5) - max_depth parameter

---

### composition:profile

Handle profile composition request.
*ksi_daemon.composition.composition_service.handle_compose_profile*

**Parameters**:
- **name** (required) - name parameter
- **variables** (optional) - variables parameter

---

### composition:prompt

Handle prompt composition request.
*ksi_daemon.composition.composition_service.handle_compose_prompt*

**Parameters**:
- **name** (required) - name parameter
- **variables** (optional) - variables parameter

---

### composition:rebuild_index

Rebuild the composition index.
*ksi_daemon.composition.composition_service.handle_rebuild_index*

**Parameters**:
- **repository_id** (default: local) - repository_id parameter

---

### composition:reload

Reload compositions by rebuilding index.
*ksi_daemon.composition.composition_service.handle_reload*

---

### composition:select

Handle intelligent composition selection using sophisticated scoring algorithm.
*ksi_daemon.composition.composition_service.handle_select_composition*

**Parameters**:
- **agent_id** (default: unknown) - agent_id parameter
- **role** (required) - role parameter
- **capabilities** (optional) - capabilities parameter
- **task_description** (required) - task_description parameter
- **preferred_style** (required) - preferred_style parameter
- **context_variables** (optional) - context_variables parameter
- **requirements** (optional) - requirements parameter
- **max_suggestions** (default: 1) - max_suggestions parameter

---

### composition:suggest

Get top N composition suggestions for the given context.
*ksi_daemon.composition.composition_service.handle_suggest_compositions*

**Parameters**:
- **agent_id** (default: unknown) - agent_id parameter
- **role** (required) - role parameter
- **capabilities** (optional) - capabilities parameter
- **task_description** (required) - task_description parameter
- **preferred_style** (required) - preferred_style parameter
- **context_variables** (optional) - context_variables parameter
- **requirements** (optional) - requirements parameter
- **max_suggestions** (default: 3) - max_suggestions parameter

---

### composition:validate

Validate a composition.
*ksi_daemon.composition.composition_service.handle_validate*

**Parameters**:
- **name** (required) - name parameter
- **type** (required) - type parameter

---

### composition:validate_context

Validate that a composition will work with the given context.
*ksi_daemon.composition.composition_service.handle_validate_context*

**Parameters**:
- **composition_name** (required) - composition_name parameter
- **context** (optional) - context parameter

---

## config

**6 events**

### config:backup

Create manual backup of configuration.
*ksi_daemon.config.config_service.handle_backup*

**Parameters**:
- **config_type** `str` (required) - Type of config to backup (required)
- **file_path** `str` (optional) - Specific config file path (optional)
- **backup_name** `str` (optional) - Custom backup name (optional)

---

### config:get

Get configuration value or entire config file.
*ksi_daemon.config.config_service.handle_get*

**Parameters**:
- **key** `str` (required) - Configuration key path (e.g., 'daemon.log_level') (required)
- **config_type** `str` (required) - Type of config ('daemon', 'composition', 'schema', 'capabilities')
- **file_path** `str` (optional) - Specific config file path (optional)

---

### config:reload

Reload configuration components.
*ksi_daemon.config.config_service.handle_reload*

**Parameters**:
- **component** `str` (required) - Component to reload ('daemon', 'plugins', 'compositions', 'all')

**Triggers**: daemon:config_reload, plugins:reload, composition:reload

---

### config:rollback

Rollback configuration to previous backup.
*ksi_daemon.config.config_service.handle_rollback*

**Parameters**:
- **config_type** `str` (required) - Type of config to rollback (required)
- **file_path** `str` (optional) - Specific config file path (optional)
- **backup_name** `str` (optional) - Specific backup to restore (optional, uses latest if not provided)

**Triggers**: config:rolled_back

---

### config:set

Set configuration value with automatic backup.
*ksi_daemon.config.config_service.handle_set*

**Parameters**:
- **key** `str` (required) - Configuration key path (e.g., 'daemon.log_level') (required)
- **value** `any` (required) - Value to set (required)
- **config_type** `str` (required) - Type of config ('daemon', 'composition', 'schema', 'capabilities')
- **file_path** `str` (optional) - Specific config file path (optional)
- **create_backup** `bool` (required) - Create backup before modification (default: true)

**Triggers**: config:changed

---

### config:validate

Validate configuration file syntax and schema.
*ksi_daemon.config.config_service.handle_validate*

**Parameters**:
- **config_type** `str` (required) - Type of config to validate ('daemon', 'composition', 'schema', 'capabilities')
- **file_path** `str` (optional) - Specific config file path (optional)
- **schema_path** `str` (optional) - Path to validation schema (optional)

---

## conversation

**10 events**

### conversation:acquire_lock

Acquire lock for a conversation.
*ksi_daemon.conversation.conversation_lock.handle_acquire_lock*

**Parameters**:
- **request_id** (required) - request_id parameter
- **conversation_id** (required) - conversation_id parameter
- **metadata** (optional) - metadata parameter

---

### conversation:active

Find active conversations from recent COMPLETION_RESULT messages.
*ksi_daemon.conversation.conversation_service.handle_active_conversations*

**Parameters**:
- **max_lines** (default: 100) - max_lines parameter
- **max_age_hours** (default: 2160) - max_age_hours parameter

---

### conversation:export

Export conversation to markdown or JSON format.
*ksi_daemon.conversation.conversation_service.handle_export_conversation*

**Parameters**:
- **session_id** (required) - session_id parameter
- **format** (default: markdown) - format parameter

---

### conversation:fork_detected

Handle fork detection.
*ksi_daemon.conversation.conversation_lock.handle_fork_detected*

**Parameters**:
- **request_id** (required) - request_id parameter
- **expected_conversation_id** (required) - expected_conversation_id parameter
- **actual_conversation_id** (required) - actual_conversation_id parameter

---

### conversation:get

Get a specific conversation with full message history.
*ksi_daemon.conversation.conversation_service.handle_get_conversation*

**Parameters**:
- **session_id** (required) - session_id parameter
- **limit** (default: 1000) - limit parameter
- **offset** (default: 0) - offset parameter
- **conversation_id** (required) - conversation_id parameter

---

### conversation:list

List available conversations with metadata.
*ksi_daemon.conversation.conversation_service.handle_list_conversations*

**Parameters**:
- **limit** (default: 100) - limit parameter
- **offset** (default: 0) - offset parameter
- **sort_by** (default: last_timestamp) - sort_by parameter
- **reverse** (default: True) - reverse parameter
- **start_date** (required) - start_date parameter
- **end_date** (required) - end_date parameter

---

### conversation:lock_status

Get lock status for a conversation.
*ksi_daemon.conversation.conversation_lock.handle_lock_status*

**Parameters**:
- **conversation_id** (required) - conversation_id parameter

---

### conversation:release_lock

Release a conversation lock.
*ksi_daemon.conversation.conversation_lock.handle_release_lock*

**Parameters**:
- **request_id** (required) - request_id parameter

---

### conversation:search

Search conversations by content.
*ksi_daemon.conversation.conversation_service.handle_search_conversations*

**Parameters**:
- **query** (default: "") - query parameter
- **limit** (default: 50) - limit parameter
- **search_in** (optional) - search_in parameter

---

### conversation:stats

Get statistics about conversations.
*ksi_daemon.conversation.conversation_service.handle_conversation_stats*

---

## correlation

**6 events**

### correlation:chain

Get the full trace chain for a correlation ID.
*ksi_daemon.core.correlation.handle_get_trace_chain*

**Parameters**:
- **correlation_id** (required) - The correlation ID to retrieve chain for

---

### correlation:cleanup

Clean up old correlation traces.
*ksi_daemon.core.correlation.handle_cleanup*

**Parameters**:
- **max_age_hours** (required) - Maximum age in hours for traces to keep (default: 24)

---

### correlation:current

Get current correlation context.
*ksi_daemon.core.correlation.handle_get_current*

---

### correlation:stats

Get correlation tracking statistics.
*ksi_daemon.core.correlation.handle_get_stats*

---

### correlation:trace

Get a specific correlation trace.
*ksi_daemon.core.correlation.handle_get_trace*

**Parameters**:
- **correlation_id** (required) - The correlation ID to retrieve trace for

---

### correlation:tree

Get the full trace tree for a correlation ID.
*ksi_daemon.core.correlation.handle_get_trace_tree*

**Parameters**:
- **correlation_id** (required) - The correlation ID to retrieve tree for

---

## file

**6 events**

### file:backup

Create a manual backup of a file.
*ksi_daemon.file.file_service.handle_backup*

**Parameters**:
- **path** `str` (required) - The file path to backup (required)
- **backup_name** `str` (optional) - Custom backup name (optional, auto-generated if not provided)

---

### file:list

List files in a directory with filtering.
*ksi_daemon.file.file_service.handle_list*

**Parameters**:
- **path** `str` (required) - The directory path to list (required)
- **pattern** `str` (default: *) - Filename pattern to match (optional)
- **recursive** `bool` (required) - Include subdirectories (default: false)
- **include_hidden** `bool` (required) - Include hidden files (default: false)

---

### file:read

Read a file with safety validation.
*ksi_daemon.file.file_service.handle_read*

**Parameters**:
- **path** `str` (required) - The file path to read (required)
- **encoding** `str` (required) - File encoding (default: utf-8)
- **binary** `bool` (required) - Read as binary data (default: false)

---

### file:rollback

Rollback a file to a previous backup.
*ksi_daemon.file.file_service.handle_rollback*

**Parameters**:
- **path** `str` (required) - The file path to rollback (required)
- **backup_name** `str` (optional) - Specific backup to restore (optional, uses latest if not provided)

---

### file:validate

Validate file access and properties.
*ksi_daemon.file.file_service.handle_validate*

**Parameters**:
- **path** `str` (required) - The file path to validate (required)
- **check_writable** `bool` (required) - Check if file is writable (default: false)
- **check_content** `str` (optional) - Validate file contains specific content (optional)

---

### file:write

Write to a file with automatic backup.
*ksi_daemon.file.file_service.handle_write*

**Parameters**:
- **path** `str` (required) - The file path to write (required)
- **content** `str` (required) - The content to write (required)
- **encoding** `str` (required) - File encoding (default: utf-8)
- **create_backup** `bool` (required) - Create backup before writing (default: true)
- **binary** `bool` (required) - Write binary data (content should be hex string) (default: false)

---

## injection

**8 events**

### injection:batch

Handle batch injection request.
*ksi_daemon.injection.injection_router.handle_injection_batch*

**Parameters**:
- **injections** (optional) - injections parameter

---

### injection:clear

Handle clear injections request.
*ksi_daemon.injection.injection_router.handle_injection_clear*

**Parameters**:
- **session_id** (required) - session_id parameter
- **mode** (required) - mode parameter

---

### injection:execute

Execute a queued injection by creating a new completion request.
*ksi_daemon.injection.injection_router.execute_injection*

**Parameters**:
- **session_id** (required) - session_id parameter
- **content** (required) - content parameter
- **request_id** (required) - request_id parameter
- **target_sessions** (optional) - target_sessions parameter
- **model** (default: claude-cli/sonnet) - model parameter
- **priority** (default: normal) - priority parameter
- **injection_type** (default: system_reminder) - injection_type parameter

---

### injection:inject

Handle unified injection request.
*ksi_daemon.injection.injection_router.handle_injection_inject*

**Parameters**:
- **mode** (default: next) - mode parameter
- **position** (default: before_prompt) - position parameter
- **content** (default: "") - content parameter
- **session_id** (required) - session_id parameter
- **priority** (default: normal) - priority parameter
- **metadata** (optional) - metadata parameter

---

### injection:list

Handle list injections request.
*ksi_daemon.injection.injection_router.handle_injection_list*

**Parameters**:
- **session_id** (required) - session_id parameter

---

### injection:process_result

Process a completion result for injection - explicitly called by completion service.
*ksi_daemon.injection.injection_router.handle_injection_process_result*

**Parameters**:
- **request_id** (required) - request_id parameter
- **result** (optional) - result parameter
- **injection_metadata** (optional) - injection_metadata parameter

---

### injection:queue

Handle queue injection metadata request from completion service.
*ksi_daemon.injection.injection_router.handle_injection_queue*

---

### injection:status

Get injection router status.
*ksi_daemon.injection.injection_router.handle_injection_status*

---

## message

**6 events**

### message:connect

Handle agent connection.
*ksi_daemon.messaging.message_bus.handle_connect_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### message:disconnect

Handle agent disconnection.
*ksi_daemon.messaging.message_bus.handle_disconnect_agent*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### message:publish

Handle message publication.
*ksi_daemon.messaging.message_bus.handle_publish*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **event_type** (required) - event_type parameter
- **message** (optional) - message parameter

---

### message:subscribe

Handle subscription request.
*ksi_daemon.messaging.message_bus.handle_subscribe*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **event_types** (optional) - event_types parameter

---

### message:subscriptions

Get subscription information.
*ksi_daemon.messaging.message_bus.handle_get_subscriptions*

**Parameters**:
- **agent_id** (required) - agent_id parameter

---

### message:unsubscribe

Handle unsubscription request.
*ksi_daemon.messaging.message_bus.handle_unsubscribe*

**Parameters**:
- **agent_id** (required) - agent_id parameter
- **event_types** (optional) - event_types parameter

---

## message_bus

**1 events**

### message_bus:stats

Get message bus statistics.
*ksi_daemon.messaging.message_bus.handle_get_stats*

---

## module

**3 events**

### module:events

List all registered events and patterns.
*ksi_daemon.daemon_core.handle_list_events*

---

### module:inspect

Inspect a specific module using direct function metadata.
*ksi_daemon.daemon_core.handle_inspect_module*

**Parameters**:
- **module_name** (required) - module_name parameter

---

### module:list

List all loaded modules.
*ksi_daemon.daemon_core.handle_list_modules*

---

## monitor

**8 events**

### monitor:clear_log

Clear event log (admin operation).
*ksi_daemon.core.monitor.handle_clear_log*

---

### monitor:get_correlation_chain

Get all events in a correlation chain.
*ksi_daemon.core.monitor.handle_get_correlation_chain*

**Parameters**:
- **correlation_id** (required) - Correlation ID to trace
- **include_memory** (required) - Include events from memory buffer (default True)

---

### monitor:get_events

Query event log with filtering and pagination.
*ksi_daemon.core.monitor.handle_get_events*

**Parameters**:
- **event_patterns** (required) - List of event name patterns (supports wildcards)
- **client_id** (required) - Filter by specific client
- **since** (required) - Start time (ISO string or timestamp)
- **until** (required) - End time (ISO string or timestamp)
- **limit** (required) - Maximum number of events to return
- **reverse** (required) - Return newest first (default True)

---

### monitor:get_session_events

Get all events for a specific session.
*ksi_daemon.core.monitor.handle_get_session_events*

**Parameters**:
- **session_id** (required) - Session ID to query
- **include_memory** (required) - Include events from memory buffer (default True)
- **reverse** (required) - Sort newest first (default True)

---

### monitor:get_stats

Get event log statistics.
*ksi_daemon.core.monitor.handle_get_stats*

---

### monitor:query

Execute custom SQL query against event database.
*ksi_daemon.core.monitor.handle_query*

**Parameters**:
- **query** (required) - SQL query string
- **params** (optional) - Optional query parameters (tuple)
- **limit** (required) - Maximum results (default 1000)

---

### monitor:subscribe

Subscribe to real-time event stream.
*ksi_daemon.core.monitor.handle_subscribe*

**Parameters**:
- **client_id** (required) - Client identifier
- **event_patterns** (required) - List of event name patterns (supports wildcards)
- **writer** (required) - Transport writer reference

---

### monitor:unsubscribe

Unsubscribe from event stream.
*ksi_daemon.core.monitor.handle_unsubscribe*

**Parameters**:
- **client_id** (required) - Client identifier

---

## orchestration

**7 events**

### orchestration:get_instance

Get detailed information about an orchestration instance.
*ksi_daemon.orchestration.orchestration_service.handle_get_instance*

**Parameters**:
- **orchestration_id** (required) - orchestration_id parameter

---

### orchestration:list_patterns

List available orchestration patterns.
*ksi_daemon.orchestration.orchestration_service.handle_list_patterns*

---

### orchestration:load_pattern

Load and validate an orchestration pattern.
*ksi_daemon.orchestration.orchestration_service.handle_load_pattern*

**Parameters**:
- **pattern** (required) - pattern parameter

---

### orchestration:message

Route a message within an orchestration.
*ksi_daemon.orchestration.orchestration_service.handle_orchestration_message*

---

### orchestration:start

Start a new orchestration.
*ksi_daemon.orchestration.orchestration_service.handle_orchestration_start*

**Parameters**:
- **pattern** (required) - pattern parameter
- **vars** (optional) - vars parameter

---

### orchestration:status

Get orchestration status.
*ksi_daemon.orchestration.orchestration_service.handle_orchestration_status*

**Parameters**:
- **orchestration_id** (required) - orchestration_id parameter

---

### orchestration:terminate

Manually terminate an orchestration.
*ksi_daemon.orchestration.orchestration_service.handle_orchestration_terminate*

**Parameters**:
- **orchestration_id** (required) - orchestration_id parameter

---

## permission

**6 events**

### permission:get_agent

Get permissions for a specific agent.
*ksi_daemon.permissions.permission_service.handle_get_agent_permissions*

**Parameters**:
- **agent_id** `str` (required) - The agent ID to query permissions for

---

### permission:get_profile

Get details of a specific permission profile.
*ksi_daemon.permissions.permission_service.handle_get_profile*

**Parameters**:
- **level** `str` (required) - The permission level/profile name (one of: restricted, standard, trusted, researcher)

---

### permission:list_profiles

List available permission profiles.
*ksi_daemon.permissions.permission_service.handle_list_profiles*

---

### permission:remove_agent

Remove permissions for an agent.
*ksi_daemon.permissions.permission_service.handle_remove_agent_permissions*

**Parameters**:
- **agent_id** `str` (required) - The agent ID to remove permissions for

---

### permission:set_agent

Set permissions for an agent.
*ksi_daemon.permissions.permission_service.handle_set_agent_permissions*

**Parameters**:
- **agent_id** `str` (required) - The agent ID to set permissions for
- **permissions** `dict` (optional) - Full permission object (optional)
- **profile** `str` (default: restricted) - Base profile to use (optional, defaults: restricted)
- **overrides** `dict` (optional) - Permission overrides to apply (optional)

---

### permission:validate_spawn

Validate if parent can spawn child with given permissions.
*ksi_daemon.permissions.permission_service.handle_validate_spawn*

**Parameters**:
- **parent_id** `str` (required) - The parent agent ID
- **child_permissions** `dict` (required) - The requested permissions for the child agent

---

## sandbox

**5 events**

### sandbox:create

Create a new sandbox for an agent.
*ksi_daemon.permissions.permission_service.handle_create_sandbox*

**Parameters**:
- **agent_id** `str` (required) - The agent ID
- **config** `dict` (optional) - Sandbox configuration (optional)

---

### sandbox:get

Get sandbox information for an agent.
*ksi_daemon.permissions.permission_service.handle_get_sandbox*

**Parameters**:
- **agent_id** `str` (required) - The agent ID

---

### sandbox:list

List all active sandboxes.
*ksi_daemon.permissions.permission_service.handle_list_sandboxes*

---

### sandbox:remove

Remove an agent's sandbox.
*ksi_daemon.permissions.permission_service.handle_remove_sandbox*

**Parameters**:
- **agent_id** `str` (required) - The agent ID
- **force** `bool` (default: False) - Force removal even with nested children (optional, default: false)

---

### sandbox:stats

Get sandbox statistics.
*ksi_daemon.permissions.permission_service.handle_sandbox_stats*

---

## state

**4 events**

### state:delete

Delete a key from shared state.
*ksi_daemon.core.state.handle_delete*

**Parameters**:
- **namespace** `str` (required) - The namespace to delete from (default: "global")
- **key** `str` (required) - The key to delete (required)

---

### state:get

Get a value from shared state.
*ksi_daemon.core.state.handle_get*

**Parameters**:
- **namespace** `str` (required) - The namespace to get from (default: "global")
- **key** `str` (required) - The key to retrieve (required)

---

### state:list

List keys in shared state.
*ksi_daemon.core.state.handle_list*

**Parameters**:
- **namespace** `str` (optional) - Filter by namespace (optional)
- **pattern** `str` (optional) - Filter by pattern (optional, supports * wildcard)

---

### state:set

Set a value in shared state.
*ksi_daemon.core.state.handle_set*

**Parameters**:
- **namespace** `str` (required) - The namespace to set in (default: "global")
- **key** `str` (required) - The key to set (required)
- **value** `any` (required) - The value to store (required)
- **metadata** `dict` (optional) - Optional metadata to attach (default: {})

---

## system

**7 events**

### system:context

Receive infrastructure context - state manager is available.
*ksi_daemon.core.state.handle_context*

---

### system:discover

Universal discovery endpoint - everything you need to understand KSI.
*ksi_daemon.core.discovery.handle_discover*

**Parameters**:
- **detail** (required) - Include parameters and triggers (default: True)
- **namespace** (optional) - Filter by namespace (optional)
- **event** (optional) - Get details for specific event (optional)

---

### system:health

System health check including module status.
*ksi_daemon.daemon_core.handle_system_health*

---

### system:help

Get detailed help for a specific event.
*ksi_daemon.core.discovery.handle_help*

**Parameters**:
- **event** (required) - The event name to get help for (required)

---

### system:ready

Return long-running server task to keep daemon alive.
*ksi_daemon.transport.unix_socket.handle_ready*

---

### system:shutdown

Clean up on shutdown.
*ksi_daemon.core.health.handle_shutdown*

---

### system:startup

Initialize health check plugin.
*ksi_daemon.core.health.handle_startup*

---

## transport

**2 events**

### transport:create

Create Unix socket transport if requested.
*ksi_daemon.transport.unix_socket.handle_create_transport*

**Parameters**:
- **transport_type** (required) - transport_type parameter
- **config** (optional) - config parameter

---

### transport:message

Handle legacy transport:message events by converting them.
*ksi_daemon.messaging.message_bus.handle_transport_message*

**Parameters**:
- **command** (required) - command parameter
- **parameters** (optional) - parameters parameter

---
