"""
KSI Claude Code Integration Tools

This package provides Python tools for Claude Code to interact with the KSI
multi-agent system through its event-driven architecture.

Core Tools:
- AgentSpawnTool: Spawn agents and manage conversations
- ObservationTool: Monitor agent behavior in real-time
- StateManagementTool: Manage shared state via key-value store
- CompositionTool: Work with agent compositions and capabilities
- ConversationTool: Manage and query agent conversations
- ConversationEngineeringTool: Guide agents through structured conversations

Example Usage:
    from ksi_claude_code import AgentSpawnTool, ObservationTool
    
    # Spawn an agent
    agent_tool = AgentSpawnTool()
    result = await agent_tool.spawn_agent(
        prompt="Research quantum computing",
        profile="researcher"
    )
    
    # Observe its progress
    observer = ObservationTool()
    subscription = await observer.subscribe(
        target_agent=result["session_id"],
        event_patterns=["agent:progress:*"]
    )
    
    async for event in observer.stream_observations(subscription["subscription_id"]):
        print(f"Progress: {event}")
"""

from .ksi_base_tool import KSIBaseTool, KSIResponse
from .agent_spawn_tool import AgentSpawnTool
from .observation_tools import ObservationTool, ObservationSubscription
from .state_management_tools import StateManagementTool, StateQueryTool, StateWriteTool
from .composition_tools import CompositionTool
from .conversation_tools import ConversationTool
from .conversation_engineering_tools import (
    ConversationEngineeringTool,
    ConversationPhase,
    ConversationGuide
)

# Version
__version__ = "2.0.0"

# Public API
__all__ = [
    # Base
    "KSIBaseTool",
    "KSIResponse",
    
    # Core Tools
    "AgentSpawnTool",
    "ObservationTool",
    "ObservationSubscription",
    "StateManagementTool",
    "StateQueryTool",
    "StateWriteTool",
    "CompositionTool",
    "ConversationTool",
    "ConversationEngineeringTool",
    
    # Data Classes
    "ConversationPhase",
    "ConversationGuide",
]