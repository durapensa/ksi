#!/usr/bin/env python3
"""
Command handlers package - Individual command implementations
Each command is a separate class using the command registry pattern
"""

# Import all command handlers to ensure registration
# These will be added as we migrate commands from json_handlers.py

from .cleanup import CleanupHandler
from .completion import CompletionHandler
from .health_check import HealthCheckHandler
from .get_commands import GetCommandsHandler
from .get_processes import GetProcessesHandler
from .set_shared import SetSharedHandler
from .get_shared import GetSharedHandler
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

__all__ = [
    'CleanupHandler', 
    'CompletionHandler',
    'HealthCheckHandler',
    'GetCommandsHandler',
    'GetProcessesHandler',
    'SetSharedHandler',
    'GetSharedHandler',
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
    'SendMessageHandler'
]