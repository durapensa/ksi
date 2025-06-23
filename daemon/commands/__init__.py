#!/usr/bin/env python3
"""
Command handlers package - Individual command implementations
Each command is a separate class using the command registry pattern
"""

# Import all command handlers to ensure registration
# Migration from json_handlers.py completed - legacy files removed

from .cleanup import CleanupHandler
from .completion import CompletionHandler
from .health_check import HealthCheckHandler
from .get_commands import GetCommandsHandler
from .get_processes import GetProcessesHandler
from .set_agent_kv import SetAgentKVHandler
from .get_agent_kv import GetAgentKVHandler
from .register_agent import RegisterAgentHandler
from .get_agents import GetAgentsHandler
from .spawn_agent import SpawnAgentHandler
from .route_task import RouteTaskHandler
from .subscribe import SubscribeHandler
from .publish import PublishHandler
from .list_identities import ListIdentitiesHandler
from .get_identity import GetIdentityHandler
from .create_identity import CreateIdentityHandler
from .update_identity import UpdateIdentityHandler
from .remove_identity import RemoveIdentityHandler
from .get_compositions import GetCompositionsHandler
from .get_composition import GetCompositionHandler
from .validate_composition import ValidateCompositionHandler
from .list_components import ListComponentsHandler
from .compose_prompt import ComposePromptHandler
from .send_message import SendMessageHandler
from .reload_module import ReloadModuleHandler
from .agent_connection import AgentConnectionHandler
from .load_state import LoadStateHandler
from .message_bus_stats import MessageBusStatsHandler
from .reload_daemon import ReloadDaemonHandler
from .shutdown import ShutdownHandler

__all__ = [
    'CleanupHandler', 
    'CompletionHandler',
    'HealthCheckHandler',
    'GetCommandsHandler',
    'GetProcessesHandler',
    'SetAgentKVHandler',
    'GetAgentKVHandler',
    'RegisterAgentHandler',
    'GetAgentsHandler',
    'SpawnAgentHandler',
    'RouteTaskHandler',
    'SubscribeHandler',
    'PublishHandler',
    'ListIdentitiesHandler',
    'GetIdentityHandler',
    'CreateIdentityHandler',
    'UpdateIdentityHandler',
    'RemoveIdentityHandler',
    'GetCompositionsHandler',
    'GetCompositionHandler',
    'ValidateCompositionHandler',
    'ListComponentsHandler',
    'ComposePromptHandler',
    'SendMessageHandler',
    'ReloadModuleHandler',
    'AgentConnectionHandler',
    'LoadStateHandler',
    'MessageBusStatsHandler',
    'ReloadDaemonHandler',
    'ShutdownHandler'
]