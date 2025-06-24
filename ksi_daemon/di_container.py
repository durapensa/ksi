#!/usr/bin/env python3
"""
Dependency Injection Container for KSI Daemon
Uses aioinject for async-first dependency management

Key principle: Handlers are stateless and created fresh per request.
Background workers and singleton patterns are handled by managers, not handlers.
"""

import aioinject
from typing import Optional, Type, Any
import logging

# Import all managers and services
from .session_and_shared_state_manager import SessionAndSharedStateManager as StateManager
from .completion_manager import CompletionManager
from .agent_profile_registry import AgentProfileRegistry as AgentManager
from .message_bus import MessageBus
from .agent_identity_registry import AgentIdentityRegistry as IdentityManager
from .hot_reload import HotReloadManager
from .timestamp_utils import TimestampManager
from .agent_orchestrator import AgentOrchestrator

# Import base handler class and context
from .command_registry import CommandHandler
from .handler_context import HandlerContext
from .commands.get_processes import GetProcessesHandler
from .commands.subscribe import SubscribeHandler
from .commands.publish import PublishHandler
from .commands.agent_connection import AgentConnectionHandler
from .commands.get_agents import GetAgentsHandler
from .commands.register_agent import RegisterAgentHandler
from .commands.set_agent_kv import SetAgentKVHandler
from .commands.get_agent_kv import GetAgentKVHandler
from .commands.send_message import SendMessageHandler
from .commands.list_identities import ListIdentitiesHandler
from .commands.get_identity import GetIdentityHandler
from .commands.create_identity import CreateIdentityHandler
from .commands.update_identity import UpdateIdentityHandler
from .commands.remove_identity import RemoveIdentityHandler
from .commands.cleanup import CleanupHandler
from .commands.reload_module import ReloadModuleHandler
from .commands.shutdown import ShutdownHandler
from .commands.get_commands import GetCommandsHandler
from .commands.message_bus_stats import MessageBusStatsHandler
from .commands.spawn_agent import SpawnAgentHandler
from .commands.route_task import RouteTaskHandler
from .commands.get_compositions import GetCompositionsHandler
from .commands.get_composition import GetCompositionHandler
from .commands.validate_composition import ValidateCompositionHandler
from .commands.list_components import ListComponentsHandler
from .commands.compose_prompt import ComposePromptHandler
from .commands.reload_daemon import ReloadDaemonHandler
from .commands.load_state import LoadStateHandler

logger = logging.getLogger(__name__)


class DaemonContainer:
    """Container for all daemon dependencies"""
    
    def __init__(self):
        self.container = aioinject.Container()
        self._core_daemon = None
        self._setup_managers()
    
    def set_core_daemon(self, core_daemon):
        """Set the core daemon reference (needed for handlers)"""
        self._core_daemon = core_daemon
    
    def _setup_managers(self):
        """Register all manager services as singletons"""
        # Core managers - these are stateful singletons
        self.container.register(aioinject.Singleton(StateManager))
        self.container.register(aioinject.Singleton(MessageBus))
        self.container.register(aioinject.Singleton(IdentityManager))
        self.container.register(aioinject.Singleton(TimestampManager))
        
        # Factory for CompletionManager with typed return
        async def create_completion_manager(state_manager: StateManager) -> CompletionManager:
            """Factory for CompletionManager with dependencies"""
            return CompletionManager(state_manager)
        
        # Factory for AgentManager  
        async def create_agent_manager(completion_manager: CompletionManager) -> AgentManager:
            """Factory for AgentManager with dependencies"""
            return AgentManager(completion_manager)
        
        # Factory for HotReloadManager
        def create_hot_reload_manager(
            state_manager: StateManager,
            agent_manager: AgentManager
        ) -> HotReloadManager:
            """Factory for HotReloadManager with dependencies"""
            # HotReloadManager needs core_daemon which we'll set later
            if not self._core_daemon:
                raise RuntimeError("Core daemon not set in DI container")
            return HotReloadManager(self._core_daemon, state_manager, agent_manager)
        
        # Factory for AgentOrchestrator with circular dependency handling
        async def create_agent_orchestrator(
            message_bus: MessageBus,
            state_manager: StateManager,
            completion_manager: CompletionManager
        ) -> AgentOrchestrator:
            """Factory for AgentOrchestrator with dependencies"""
            ao = AgentOrchestrator(message_bus, state_manager)
            # Wire up circular dependency
            ao.completion_manager = completion_manager
            completion_manager.agent_orchestrator = ao
            return ao
        
        # Register factories as singletons
        self.container.register(aioinject.Singleton(create_completion_manager))
        self.container.register(aioinject.Singleton(create_agent_manager))
        self.container.register(aioinject.Singleton(create_hot_reload_manager))  
        self.container.register(aioinject.Singleton(create_agent_orchestrator))
    
    def create_handler_factory(self, handler_class: Type[CommandHandler]):
        """Create a factory function for a command handler"""
        # Define the factory with proper type annotations
        async def handler_factory(
            state_manager: StateManager,
            completion_manager: CompletionManager,
            agent_manager: AgentManager,
            message_bus: MessageBus,
            identity_manager: IdentityManager,
            hot_reload_manager: HotReloadManager,
            timestamp_manager: TimestampManager
        ) -> CommandHandler:
            """Factory for command handler with all dependencies"""
            # Create properly typed context object
            context = HandlerContext(
                core_daemon=self._core_daemon,
                state_manager=state_manager,
                completion_manager=completion_manager,
                agent_manager=agent_manager,
                message_bus=message_bus,
                identity_manager=identity_manager,
                hot_reload_manager=hot_reload_manager,
                timestamp_manager=timestamp_manager
            )
            
            handler = handler_class(context)
            
            # NO initialize() call - handlers should be stateless!
            # If a handler needs background work, that belongs in a manager
            
            return handler
        
        # Set the function name for debugging
        handler_factory.__name__ = f"create_{handler_class.__name__}"
        return handler_factory
    
    async def create_handler(self, handler_class: Type[CommandHandler]) -> Optional[CommandHandler]:
        """Create a fresh handler instance with injected dependencies"""
        async with self.container.context() as ctx:
            try:
                # Get all required services
                state_manager = await ctx.resolve(StateManager)
                completion_manager = await ctx.resolve(CompletionManager)
                agent_manager = await ctx.resolve(AgentManager)
                message_bus = await ctx.resolve(MessageBus)
                identity_manager = await ctx.resolve(IdentityManager)
                hot_reload_manager = await ctx.resolve(HotReloadManager)
                timestamp_manager = await ctx.resolve(TimestampManager)
                
                # Create properly typed context object
                context = HandlerContext(
                    core_daemon=self._core_daemon,
                    state_manager=state_manager,
                    completion_manager=completion_manager,
                    agent_manager=agent_manager,
                    message_bus=message_bus,
                    identity_manager=identity_manager,
                    hot_reload_manager=hot_reload_manager,
                    timestamp_manager=timestamp_manager
                )
                
                # Create and return handler - no initialization!
                return handler_class(context)
                
            except Exception as e:
                logger.error(f"Failed to create handler {handler_class.__name__}: {e}")
                return None
    
    async def get_service(self, service_name):
        """Get a service instance by name or class"""
        async with self.container.context() as ctx:
            # Map string names to classes
            service_map = {
                'StateManager': StateManager,
                'CompletionManager': CompletionManager,
                'AgentManager': AgentManager,
                'MessageBus': MessageBus,
                'IdentityManager': IdentityManager,
                'HotReloadManager': HotReloadManager,
                'TimestampManager': TimestampManager,
                'AgentOrchestrator': AgentOrchestrator
            }
            
            # Handle both string names and classes
            if isinstance(service_name, str):
                service_class = service_map.get(service_name)
                if not service_class:
                    raise ValueError(f"Unknown service: {service_name}")
            else:
                service_class = service_name
            
            return await ctx.resolve(service_class)
    
    async def initialize_services(self):
        """Initialize all singleton services"""
        async with self.container.context() as ctx:
            # Resolve core services to ensure they're initialized
            await ctx.resolve(StateManager)
            await ctx.resolve(MessageBus)
            await ctx.resolve(IdentityManager)
            await ctx.resolve(CompletionManager)
            await ctx.resolve(AgentManager)
            
            logger.info("All services initialized via DI container")


# Global container instance
daemon_container = DaemonContainer()