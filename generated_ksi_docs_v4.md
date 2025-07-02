# KSI Event Documentation

Generated: 2025-07-02T09:39:21.376951

Total Events: 138
Namespaces: 20

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

**Summary**: Broadcast a message to all agents.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_broadcast` (async)

**Parameters**:
- message - message parameter
- sender [default: system] - sender parameter

---

### agent:create_identity

**Summary**: Create a new agent identity.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_create_identity` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- identity - identity parameter

---

### agent:discover_peers

**Summary**: Discover other agents and their capabilities.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_discover_peers` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- capabilities - capabilities parameter
- roles - roles parameter

---

### agent:get_capabilities

**Summary**: Get capabilities of an agent or all agents.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_get_capabilities` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### agent:get_identity

**Summary**: Get a specific agent identity.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_get_identity` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### agent:list

**Summary**: List registered agents.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_list_agents` (async)

**Parameters**:
- status [required] - status parameter

---

### agent:list_identities

**Summary**: List agent identities.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_list_identities` (async)

**Parameters**:
None

---

### agent:negotiate_roles

**Summary**: Coordinate role negotiation between agents.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_negotiate_roles` (async)

**Parameters**:
- participants - participants parameter
- type [default: collaborative] - type parameter
- context - context parameter

---

### agent:register

**Summary**: Register an external agent.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_register_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- info - info parameter

---

### agent:remove_identity

**Summary**: Remove an agent identity.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_remove_identity` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### agent:restart

**Summary**: Restart an agent.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_restart_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### agent:route_task

**Summary**: Route a task to an appropriate agent.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_route_task` (async)

**Parameters**:
- task - task parameter

---

### agent:send_message

**Summary**: Send a message to an agent.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_send_message` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- message - message parameter

---

### agent:spawn

**Summary**: Spawn a new agent thread with optional profile.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_spawn_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- profile [required] - profile parameter
- profile_name [required] - profile_name parameter
- composition [required] - composition parameter
- session_id [required] - session_id parameter
- spawn_mode [default: fixed] - spawn_mode parameter
- selection_context - selection_context parameter
- task [required] - task parameter
- enable_tools [default: False] - enable_tools parameter
- permission_profile [default: standard]
  permission_profile parameter
- sandbox_config - sandbox_config parameter
- permission_overrides - permission_overrides parameter
- config [required] - config parameter
- context [required] - context parameter
- _composition_selection [required] - _composition_selection parameter

---

### agent:terminate

**Summary**: Terminate an agent thread.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_terminate_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- force [default: False] - force parameter

---

### agent:unregister

**Summary**: Unregister an agent.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_unregister_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### agent:update_composition

**Summary**: Handle agent composition update request.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_update_composition` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- new_composition [required] - new_composition parameter
- reason [default: Adaptation required] - reason parameter

---

### agent:update_identity

**Summary**: Update an agent identity.

**Module**: `ksi_daemon.agent.agent_service`
**Handler**: `handle_update_identity` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- updates - updates parameter

---

## api

**1 events**

### api:schema

**Summary**: Get complete API schema using direct function inspection.

**Module**: `ksi_daemon.daemon_core`
**Handler**: `handle_api_schema` (async)

**Parameters**:
None

---

## async_state

**7 events**

### async_state:delete

**Summary**: Delete key from async state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_delete` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- key [default: ] - key parameter

---

### async_state:get

**Summary**: Get value from async state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_get` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- key [default: ] - key parameter

---

### async_state:get_keys

**Summary**: Get all keys in a namespace.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_get_keys` (async)

**Parameters**:
- namespace [default: default] - namespace parameter

---

### async_state:pop

**Summary**: Pop value from async queue.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_pop` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- queue_name [default: ] - queue_name parameter

---

### async_state:push

**Summary**: Push value to async queue.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_push` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- queue_name [default: ] - queue_name parameter
- value [required] - value parameter

---

### async_state:queue_length

**Summary**: Get length of async queue.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_queue_length` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- queue_name [default: ] - queue_name parameter

---

### async_state:set

**Summary**: Set value in async state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_async_set` (async)

**Parameters**:
- namespace [default: default] - namespace parameter
- key [default: ] - key parameter
- value [required] - value parameter

---

## completion

**8 events**

### completion:async

**Summary**: Handle async completion requests with smart queueing.

**Module**: `ksi_daemon.completion.completion_service`
**Handler**: `handle_async_completion` (async)

**Parameters**:
- session_id [default: default] - session_id parameter
- model [default: unknown] - model parameter
- request_id [required] - request_id parameter

---

### completion:cancel

**Summary**: Cancel an in-progress completion.

**Module**: `ksi_daemon.completion.completion_service`
**Handler**: `handle_cancel_completion` (async)

**Parameters**:
- request_id [required] - request_id parameter

---

### completion:cancelled

**Summary**: Broadcast certain events to all connected clients.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_broadcastable_event` (async)

**Parameters**:
- timestamp [default: ] - timestamp parameter
- correlation_id [required] - correlation_id parameter

---

### completion:error

**Summary**: Broadcast certain events to all connected clients.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_broadcastable_event` (async)

**Parameters**:
- timestamp [default: ] - timestamp parameter
- correlation_id [required] - correlation_id parameter

---

### completion:progress

**Summary**: Broadcast certain events to all connected clients.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_broadcastable_event` (async)

**Parameters**:
- timestamp [default: ] - timestamp parameter
- correlation_id [required] - correlation_id parameter

---

### completion:result

**Summary**: Broadcast certain events to all connected clients.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_broadcastable_event` (async)

**Parameters**:
- timestamp [default: ] - timestamp parameter
- correlation_id [required] - correlation_id parameter

---

### completion:session_status

**Summary**: Get detailed status for a specific session.

**Module**: `ksi_daemon.completion.completion_service`
**Handler**: `handle_session_status` (async)

**Parameters**:
- session_id [required] - session_id parameter

---

### completion:status

**Summary**: Get status of all active completions.

**Module**: `ksi_daemon.completion.completion_service`
**Handler**: `handle_completion_status` (async)

**Parameters**:
None

---

## composition

**19 events**

### composition:capabilities

**Summary**: Get available KSI capabilities from declarative schema.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_get_capabilities` (async)

**Parameters**:
- group [required] - group parameter

---

### composition:compose

**Summary**: Handle generic composition request.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_compose` (async)

**Parameters**:
- name [required] - name parameter
- type [required] - type parameter
- variables - variables parameter

---

### composition:create

**Summary**: Handle runtime composition creation.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_create_composition` (async)

**Parameters**:
- name [required] - name parameter
- type [default: profile] - type parameter
- extends [default: base_agent] - extends parameter
- description - description parameter
- author [default: dynamic_agent] - author parameter
- metadata - metadata parameter
- config - config parameter
- role [default: assistant] - role parameter
- model [default: sonnet] - model parameter
- capabilities - capabilities parameter
- tools - tools parameter
- agent_id [required] - agent_id parameter
- prompt [required] - prompt parameter
- components [required] - components parameter

---

### composition:discover

**Summary**: Discover available compositions using index with optional metadata filtering.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_discover` (async)

**Parameters**:
- metadata_filter [required] - metadata_filter parameter

---

### composition:get

**Summary**: Get a composition definition.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_get` (async)

**Parameters**:
- name [required] - name parameter
- type [required] - type parameter

---

### composition:get_metadata

**Summary**: Get metadata for a composition.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_get_metadata` (async)

**Parameters**:
- full_name [required] - full_name parameter

---

### composition:get_path

**Summary**: Get the file path for a composition.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_get_path` (async)

**Parameters**:
- full_name [required] - full_name parameter

---

### composition:index_file

**Summary**: Index a single composition file.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_index_file` (async)

**Parameters**:
- file_path [required] - file_path parameter

---

### composition:list

**Summary**: List all compositions of a given type.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_list` (async)

**Parameters**:
- type [default: all] - type parameter

---

### composition:load_bulk

**Summary**: Universal bulk loading for agent efficiency.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_load_bulk` (async)

**Parameters**:
- names - names parameter

---

### composition:load_tree

**Summary**: Universal tree loading based on composition's declared strategy.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_load_tree` (async)

**Parameters**:
- name [required] - name parameter
- max_depth [default: 5] - max_depth parameter

---

### composition:profile

**Summary**: Handle profile composition request.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_compose_profile` (async)

**Parameters**:
- name [required] - name parameter
- variables - variables parameter

---

### composition:prompt

**Summary**: Handle prompt composition request.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_compose_prompt` (async)

**Parameters**:
- name [required] - name parameter
- variables - variables parameter

---

### composition:rebuild_index

**Summary**: Rebuild the composition index.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_rebuild_index` (async)

**Parameters**:
- repository_id [default: local] - repository_id parameter

---

### composition:reload

**Summary**: Reload compositions by rebuilding index.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_reload` (async)

**Parameters**:
None

---

### composition:select

**Summary**: Handle intelligent composition selection using sophisticated scoring algorithm.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_select_composition` (async)

**Parameters**:
- agent_id [default: unknown] - agent_id parameter
- role [required] - role parameter
- capabilities - capabilities parameter
- task_description [required] - task_description parameter
- preferred_style [required] - preferred_style parameter
- context_variables - context_variables parameter
- requirements - requirements parameter
- max_suggestions [default: 1] - max_suggestions parameter

---

### composition:suggest

**Summary**: Get top N composition suggestions for the given context.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_suggest_compositions` (async)

**Parameters**:
- agent_id [default: unknown] - agent_id parameter
- role [required] - role parameter
- capabilities - capabilities parameter
- task_description [required] - task_description parameter
- preferred_style [required] - preferred_style parameter
- context_variables - context_variables parameter
- requirements - requirements parameter
- max_suggestions [default: 3] - max_suggestions parameter

---

### composition:validate

**Summary**: Validate a composition.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_validate` (async)

**Parameters**:
- name [required] - name parameter
- type [required] - type parameter

---

### composition:validate_context

**Summary**: Validate that a composition will work with the given context.

**Module**: `ksi_daemon.composition.composition_service`
**Handler**: `handle_validate_context` (async)

**Parameters**:
- composition_name [required] - composition_name parameter
- context - context parameter

---

## config

**6 events**

### config:backup

**Summary**: Create manual backup of configuration.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_backup` (async)

**Parameters**:
- config_type (str) [required] - Type of config to backup (required)
- file_path (str) - Specific config file path (optional)
- backup_name (str) - Custom backup name (optional)

---

### config:get

**Summary**: Get configuration value or entire config file.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_get` (async)

**Parameters**:
- key (str) [required] - Configuration key path (e.g., 'daemon.log_level') (required)
- config_type (str) [required] - Type of config ('daemon', 'composition', 'schema', 'capabilities')
- file_path (str) - Specific config file path (optional)

---

### config:reload

**Summary**: Reload configuration components.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_reload` (async)

**Parameters**:
- component (str) [required] - Component to reload ('daemon', 'plugins', 'compositions', 'all')

**Triggers**:
- daemon:config_reload
- plugins:reload
- composition:reload

---

### config:rollback

**Summary**: Rollback configuration to previous backup.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_rollback` (async)

**Parameters**:
- config_type (str) [required] - Type of config to rollback (required)
- file_path (str) - Specific config file path (optional)
- backup_name (str) - Specific backup to restore (optional, uses latest if not provided)

**Triggers**:
- config:rolled_back

---

### config:set

**Summary**: Set configuration value with automatic backup.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_set` (async)

**Parameters**:
- key (str) [required] - Configuration key path (e.g., 'daemon.log_level') (required)
- value (any) [required] - Value to set (required)
- config_type (str) [required] - Type of config ('daemon', 'composition', 'schema', 'capabilities')
- file_path (str) - Specific config file path (optional)
- create_backup (bool) [required] - Create backup before modification (default: true)

**Triggers**:
- config:changed

---

### config:validate

**Summary**: Validate configuration file syntax and schema.

**Module**: `ksi_daemon.config.config_service`
**Handler**: `handle_validate` (async)

**Parameters**:
- config_type (str) [required] - Type of config to validate ('daemon', 'composition', 'schema', 'capabilities')
- file_path (str) - Specific config file path (optional)
- schema_path (str) - Path to validation schema (optional)

---

## conversation

**10 events**

### conversation:acquire_lock

**Summary**: Acquire lock for a conversation.

**Module**: `ksi_daemon.conversation.conversation_lock`
**Handler**: `handle_acquire_lock` (async)

**Parameters**:
- request_id [required] - request_id parameter
- conversation_id [required] - conversation_id parameter
- metadata - metadata parameter

---

### conversation:active

**Summary**: Find active conversations from recent COMPLETION_RESULT messages.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_active_conversations` (async)

**Parameters**:
- max_lines [default: 100] - max_lines parameter
- max_age_hours [default: 2160] - max_age_hours parameter

---

### conversation:export

**Summary**: Export conversation to markdown or JSON format.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_export_conversation` (async)

**Parameters**:
- session_id [required] - session_id parameter
- format [default: markdown] - format parameter

---

### conversation:fork_detected

**Summary**: Handle fork detection.

**Module**: `ksi_daemon.conversation.conversation_lock`
**Handler**: `handle_fork_detected` (async)

**Parameters**:
- request_id [required] - request_id parameter
- expected_conversation_id [required] - expected_conversation_id parameter
- actual_conversation_id [required] - actual_conversation_id parameter

---

### conversation:get

**Summary**: Get a specific conversation with full message history.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_get_conversation` (async)

**Parameters**:
- session_id [required] - session_id parameter
- limit [default: 1000] - limit parameter
- offset [default: 0] - offset parameter
- conversation_id [required] - conversation_id parameter

---

### conversation:list

**Summary**: List available conversations with metadata.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_list_conversations` (async)

**Parameters**:
- limit [default: 100] - limit parameter
- offset [default: 0] - offset parameter
- sort_by [default: last_timestamp] - sort_by parameter
- reverse [default: True] - reverse parameter
- start_date [required] - start_date parameter
- end_date [required] - end_date parameter

---

### conversation:lock_status

**Summary**: Get lock status for a conversation.

**Module**: `ksi_daemon.conversation.conversation_lock`
**Handler**: `handle_lock_status` (async)

**Parameters**:
- conversation_id [required] - conversation_id parameter

---

### conversation:release_lock

**Summary**: Release a conversation lock.

**Module**: `ksi_daemon.conversation.conversation_lock`
**Handler**: `handle_release_lock` (async)

**Parameters**:
- request_id [required] - request_id parameter

---

### conversation:search

**Summary**: Search conversations by content.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_search_conversations` (async)

**Parameters**:
- query [default: ] - query parameter
- limit [default: 50] - limit parameter
- search_in - search_in parameter

---

### conversation:stats

**Summary**: Get statistics about conversations.

**Module**: `ksi_daemon.conversation.conversation_service`
**Handler**: `handle_conversation_stats` (async)

**Parameters**:
None

---

## correlation

**6 events**

### correlation:chain

**Summary**: Get the full trace chain for a correlation ID.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_get_trace_chain` (async)

**Parameters**:
- correlation_id [required] - The correlation ID to retrieve chain for

---

### correlation:cleanup

**Summary**: Clean up old correlation traces.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_cleanup` (async)

**Parameters**:
- max_age_hours [required] - Maximum age in hours for traces to keep (default: 24)

---

### correlation:current

**Summary**: Get current correlation context.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_get_current` (async)

**Parameters**:
None

---

### correlation:stats

**Summary**: Get correlation tracking statistics.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_get_stats` (async)

**Parameters**:
None

---

### correlation:trace

**Summary**: Get a specific correlation trace.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_get_trace` (async)

**Parameters**:
- correlation_id [required] - The correlation ID to retrieve trace for

---

### correlation:tree

**Summary**: Get the full trace tree for a correlation ID.

**Module**: `ksi_daemon.core.correlation`
**Handler**: `handle_get_trace_tree` (async)

**Parameters**:
- correlation_id [required] - The correlation ID to retrieve tree for

---

## file

**6 events**

### file:backup

**Summary**: Create a manual backup of a file.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_backup` (async)

**Parameters**:
- path (str) [required] - The file path to backup (required)
- backup_name (str) - Custom backup name (optional, auto-generated if not provided)

---

### file:list

**Summary**: List files in a directory with filtering.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_list` (async)

**Parameters**:
- path (str) [required] - The directory path to list (required)
- pattern (str) [default: *] - Filename pattern to match (optional)
- recursive (bool) [required] - Include subdirectories (default: false)
- include_hidden (bool) [required] - Include hidden files (default: false)

---

### file:read

**Summary**: Read a file with safety validation.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_read` (async)

**Parameters**:
- path (str) [required] - The file path to read (required)
- encoding (str) [required] - File encoding (default: utf-8)
- binary (bool) [required] - Read as binary data (default: false)

---

### file:rollback

**Summary**: Rollback a file to a previous backup.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_rollback` (async)

**Parameters**:
- path (str) [required] - The file path to rollback (required)
- backup_name (str) - Specific backup to restore (optional, uses latest if not provided)

---

### file:validate

**Summary**: Validate file access and properties.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_validate` (async)

**Parameters**:
- path (str) [required] - The file path to validate (required)
- check_writable (bool) [required] - Check if file is writable (default: false)
- check_content (str) - Validate file contains specific content (optional)

---

### file:write

**Summary**: Write to a file with automatic backup.

**Module**: `ksi_daemon.file.file_service`
**Handler**: `handle_write` (async)

**Parameters**:
- path (str) [required] - The file path to write (required)
- content (str) [required] - The content to write (required)
- encoding (str) [required] - File encoding (default: utf-8)
- create_backup (bool) [required] - Create backup before writing (default: true)
- binary (bool) [required] - Write binary data (content should be hex string) (default: false)

---

## injection

**8 events**

### injection:batch

**Summary**: Handle batch injection request.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_batch` (async)

**Parameters**:
- injections - injections parameter

---

### injection:clear

**Summary**: Handle clear injections request.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_clear` (async)

**Parameters**:
- session_id [required] - session_id parameter
- mode [required] - mode parameter

---

### injection:execute

**Summary**: Execute a queued injection by creating a new completion request.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `execute_injection` (async)

**Parameters**:
- session_id [required] - session_id parameter
- content [required] - content parameter
- request_id [required] - request_id parameter
- target_sessions - target_sessions parameter
- model [default: claude-cli/sonnet] - model parameter
- priority [default: normal] - priority parameter
- injection_type [default: system_reminder]
  injection_type parameter

---

### injection:inject

**Summary**: Handle unified injection request.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_inject` (async)

**Parameters**:
- mode [default: next] - mode parameter
- position [default: before_prompt] - position parameter
- content [default: ] - content parameter
- session_id [required] - session_id parameter
- priority [default: normal] - priority parameter
- metadata - metadata parameter

---

### injection:list

**Summary**: Handle list injections request.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_list` (async)

**Parameters**:
- session_id [required] - session_id parameter

---

### injection:process_result

**Summary**: Process a completion result for injection - explicitly called by completion service.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_process_result` (async)

**Parameters**:
- request_id [required] - request_id parameter
- result - result parameter
- injection_metadata - injection_metadata parameter

---

### injection:queue

**Summary**: Handle queue injection metadata request from completion service.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_queue` (async)

**Parameters**:
None

---

### injection:status

**Summary**: Get injection router status.

**Module**: `ksi_daemon.injection.injection_router`
**Handler**: `handle_injection_status` (async)

**Parameters**:
None

---

## message

**6 events**

### message:connect

**Summary**: Handle agent connection.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_connect_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### message:disconnect

**Summary**: Handle agent disconnection.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_disconnect_agent` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### message:publish

**Summary**: Handle message publication.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_publish` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- event_type [required] - event_type parameter
- message - message parameter

---

### message:subscribe

**Summary**: Handle subscription request.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_subscribe` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- event_types - event_types parameter

---

### message:subscriptions

**Summary**: Get subscription information.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_get_subscriptions` (async)

**Parameters**:
- agent_id [required] - agent_id parameter

---

### message:unsubscribe

**Summary**: Handle unsubscription request.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_unsubscribe` (async)

**Parameters**:
- agent_id [required] - agent_id parameter
- event_types - event_types parameter

---

## message_bus

**1 events**

### message_bus:stats

**Summary**: Get message bus statistics.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_get_stats` (async)

**Parameters**:
None

---

## module

**3 events**

### module:events

**Summary**: List all registered events and patterns.

**Module**: `ksi_daemon.daemon_core`
**Handler**: `handle_list_events` (async)

**Parameters**:
None

---

### module:inspect

**Summary**: Inspect a specific module using direct function metadata.

**Module**: `ksi_daemon.daemon_core`
**Handler**: `handle_inspect_module` (async)

**Parameters**:
- module_name [required] - module_name parameter

---

### module:list

**Summary**: List all loaded modules.

**Module**: `ksi_daemon.daemon_core`
**Handler**: `handle_list_modules` (async)

**Parameters**:
None

---

## monitor

**8 events**

### monitor:clear_log

**Summary**: Clear event log (admin operation).

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_clear_log` (async)

**Parameters**:
None

---

### monitor:get_correlation_chain

**Summary**: Get all events in a correlation chain.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_get_correlation_chain` (async)

**Parameters**:
- correlation_id [required] - Correlation ID to trace
- include_memory [required] - Include events from memory buffer (default True)

---

### monitor:get_events

**Summary**: Query event log with filtering and pagination.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_get_events` (async)

**Parameters**:
- event_patterns [required] - List of event name patterns (supports wildcards)
- client_id [required] - Filter by specific client
- since [required] - Start time (ISO string or timestamp)
- until [required] - End time (ISO string or timestamp)
- limit [required] - Maximum number of events to return
- reverse [required] - Return newest first (default True)

---

### monitor:get_session_events

**Summary**: Get all events for a specific session.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_get_session_events` (async)

**Parameters**:
- session_id [required] - Session ID to query
- include_memory [required] - Include events from memory buffer (default True)
- reverse [required] - Sort newest first (default True)

---

### monitor:get_stats

**Summary**: Get event log statistics.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_get_stats` (async)

**Parameters**:
None

---

### monitor:query

**Summary**: Execute custom SQL query against event database.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_query` (async)

**Parameters**:
- query [required] - SQL query string
- params - Optional query parameters (tuple)
- limit [required] - Maximum results (default 1000)

---

### monitor:subscribe

**Summary**: Subscribe to real-time event stream.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_subscribe` (async)

**Parameters**:
- client_id [required] - Client identifier
- event_patterns [required] - List of event name patterns (supports wildcards)
- writer [required] - Transport writer reference

---

### monitor:unsubscribe

**Summary**: Unsubscribe from event stream.

**Module**: `ksi_daemon.core.monitor`
**Handler**: `handle_unsubscribe` (async)

**Parameters**:
- client_id [required] - Client identifier

---

## orchestration

**7 events**

### orchestration:get_instance

**Summary**: Get detailed information about an orchestration instance.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_get_instance` (async)

**Parameters**:
- orchestration_id [required] - orchestration_id parameter

---

### orchestration:list_patterns

**Summary**: List available orchestration patterns.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_list_patterns` (async)

**Parameters**:
None

---

### orchestration:load_pattern

**Summary**: Load and validate an orchestration pattern.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_load_pattern` (async)

**Parameters**:
- pattern [required] - pattern parameter

---

### orchestration:message

**Summary**: Route a message within an orchestration.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_orchestration_message` (async)

**Parameters**:
None

---

### orchestration:start

**Summary**: Start a new orchestration.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_orchestration_start` (async)

**Parameters**:
- pattern [required] - pattern parameter
- vars - vars parameter

---

### orchestration:status

**Summary**: Get orchestration status.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_orchestration_status` (async)

**Parameters**:
- orchestration_id [required] - orchestration_id parameter

---

### orchestration:terminate

**Summary**: Manually terminate an orchestration.

**Module**: `ksi_daemon.orchestration.orchestration_service`
**Handler**: `handle_orchestration_terminate` (async)

**Parameters**:
- orchestration_id [required] - orchestration_id parameter

---

## permission

**6 events**

### permission:get_agent

**Summary**: Get permissions for a specific agent.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_get_agent_permissions` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID to query permissions for

---

### permission:get_profile

**Summary**: Get details of a specific permission profile.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_get_profile` (async)

**Parameters**:
- level (str) [required] - The permission level/profile name (one of: restricted, standard, trusted, researcher)

---

### permission:list_profiles

**Summary**: List available permission profiles.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_list_profiles` (async)

**Parameters**:
None

---

### permission:remove_agent

**Summary**: Remove permissions for an agent.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_remove_agent_permissions` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID to remove permissions for

---

### permission:set_agent

**Summary**: Set permissions for an agent.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_set_agent_permissions` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID to set permissions for
- permissions (dict) - Full permission object (optional)
- profile (str) [default: restricted] - Base profile to use (optional, defaults: restricted)
- overrides (dict) - Permission overrides to apply (optional)

---

### permission:validate_spawn

**Summary**: Validate if parent can spawn child with given permissions.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_validate_spawn` (async)

**Parameters**:
- parent_id (str) [required] - The parent agent ID
- child_permissions (dict) [required] - The requested permissions for the child agent

---

## sandbox

**5 events**

### sandbox:create

**Summary**: Create a new sandbox for an agent.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_create_sandbox` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID
- config (dict) - Sandbox configuration (optional)

---

### sandbox:get

**Summary**: Get sandbox information for an agent.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_get_sandbox` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID

---

### sandbox:list

**Summary**: List all active sandboxes.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_list_sandboxes` (async)

**Parameters**:
None

---

### sandbox:remove

**Summary**: Remove an agent's sandbox.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_remove_sandbox` (async)

**Parameters**:
- agent_id (str) [required] - The agent ID
- force (bool) [default: False] - Force removal even with nested children (optional, default: false)

---

### sandbox:stats

**Summary**: Get sandbox statistics.

**Module**: `ksi_daemon.permissions.permission_service`
**Handler**: `handle_sandbox_stats` (async)

**Parameters**:
None

---

## state

**4 events**

### state:delete

**Summary**: Delete a key from shared state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_delete` (async)

**Parameters**:
- namespace (str) [required] - The namespace to delete from (default: "global")
- key (str) [required] - The key to delete (required)

---

### state:get

**Summary**: Get a value from shared state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_get` (async)

**Parameters**:
- namespace (str) [required] - The namespace to get from (default: "global")
- key (str) [required] - The key to retrieve (required)

---

### state:list

**Summary**: List keys in shared state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_list` (async)

**Parameters**:
- namespace (str) - Filter by namespace (optional)
- pattern (str) - Filter by pattern (optional, supports * wildcard)

---

### state:set

**Summary**: Set a value in shared state.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_set` (async)

**Parameters**:
- namespace (str) [required] - The namespace to set in (default: "global")
- key (str) [required] - The key to set (required)
- value (any) [required] - The value to store (required)
- metadata (dict) - Optional metadata to attach (default: {})

---

## system

**7 events**

### system:context

**Summary**: Receive infrastructure context - state manager is available.

**Module**: `ksi_daemon.core.state`
**Handler**: `handle_context` (async)

**Parameters**:
None

---

### system:discover

**Summary**: Universal discovery endpoint - everything you need to understand KSI.

**Module**: `ksi_daemon.core.discovery`
**Handler**: `handle_discover` (async)

**Parameters**:
- detail [required] - Include parameters and triggers (default: True)
- namespace - Filter by namespace (optional)
- event - Get details for specific event (optional)

---

### system:health

**Summary**: System health check including module status.

**Module**: `ksi_daemon.daemon_core`
**Handler**: `handle_system_health` (async)

**Parameters**:
None

---

### system:help

**Summary**: Get detailed help for a specific event.

**Module**: `ksi_daemon.core.discovery`
**Handler**: `handle_help` (async)

**Parameters**:
- event [required] - The event name to get help for (required)

---

### system:ready

**Summary**: Return long-running server task to keep daemon alive.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_ready` (async)

**Parameters**:
None

---

### system:shutdown

**Summary**: Clean up on shutdown.

**Module**: `ksi_daemon.core.health`
**Handler**: `handle_shutdown` (async)

**Parameters**:
None

---

### system:startup

**Summary**: Initialize health check plugin.

**Module**: `ksi_daemon.core.health`
**Handler**: `handle_startup` (async)

**Parameters**:
None

---

## transport

**2 events**

### transport:create

**Summary**: Create Unix socket transport if requested.

**Module**: `ksi_daemon.transport.unix_socket`
**Handler**: `handle_create_transport` (async)

**Parameters**:
- transport_type [required] - transport_type parameter
- config - config parameter

---

### transport:message

**Summary**: Handle legacy transport:message events by converting them.

**Module**: `ksi_daemon.messaging.message_bus`
**Handler**: `handle_transport_message` (async)

**Parameters**:
- command [required] - command parameter
- parameters - parameters parameter

---
