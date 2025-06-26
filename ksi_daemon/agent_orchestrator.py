#!/usr/bin/env python3
"""
AgentOrchestrator - Manages multiple in-process AgentConversationRuntimes
Replaces subprocess-based agent management with efficient in-process coordination
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any

from .agent_conversation_runtime import AgentConversationRuntime
from ksi_common import TimestampManager
from .logging_config import get_logger, log_event, agent_context
from .event_taxonomy import AGENT_EVENTS, format_agent_event

logger = get_logger(__name__)

class AgentOrchestrator:
    """Orchestrates multiple in-process agent controllers"""
    
    def __init__(self, message_bus, state_manager=None):
        self.message_bus = message_bus
        self.state_manager = state_manager
        
        # Agent management
        self.agents: Dict[str, AgentConversationRuntime] = {}
        self.agent_tasks: Dict[str, asyncio.Task] = {}
        
        # Message routing
        self.message_subscriptions: Dict[str, List[str]] = {}  # event_type -> [agent_ids]
        
        # Statistics
        self.total_agents_spawned = 0
        self.active_conversations = 0
        
        logger.info("MultiAgentOrchestrator initialized")
    
    async def spawn_agent(self, agent_id: str, profile_name: str) -> str:
        """Spawn a new in-process agent controller"""
        try:
            # Generate unique agent ID if not provided
            if not agent_id:
                agent_id = f"agent_{uuid.uuid4().hex[:8]}"
            
            # Check if agent already exists
            if agent_id in self.agents:
                logger.warning(f"Agent {agent_id} already exists")
                return agent_id
            
            # Create agent controller
            agent = AgentConversationRuntime(
                agent_id=agent_id,
                profile_name=profile_name,
                message_bus=self.message_bus,
                state_manager=self.state_manager,
                orchestrator=self
            )
            
            # Start the agent
            agent_task = await agent.start()
            
            # Track agent and its task
            self.agents[agent_id] = agent
            self.agent_tasks[agent_id] = agent_task
            self.total_agents_spawned += 1
            
            logger.info(f"Spawned in-process agent {agent_id} with profile {profile_name}")
            
            # Notify via message bus if possible
            await self._notify_agent_spawned(agent_id, profile_name)
            
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to spawn agent {agent_id}: {e}")
            raise
    
    async def terminate_agent(self, agent_id: str) -> bool:
        """Terminate an agent and clean up resources"""
        async with agent_context(agent_id) as _:
            try:
                if agent_id not in self.agents:
                    log_event(logger, "agent.terminate_not_found",
                             **format_agent_event("agent.terminate_not_found", agent_id))
                    return False
                
                log_event(logger, "agent.terminate_initiated",
                         **format_agent_event("agent.terminate_initiated", agent_id))
                
                # Stop the agent
                agent = self.agents[agent_id]
                await agent.stop()
                
                # Cancel the agent task
                if agent_id in self.agent_tasks:
                    task = self.agent_tasks[agent_id]
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    del self.agent_tasks[agent_id]
                
                # Remove from tracking
                del self.agents[agent_id]
                
                # Clean up subscriptions
                self._clean_agent_subscriptions(agent_id)
                
                log_event(logger, "agent.terminated",
                         **format_agent_event("agent.terminated", agent_id,
                                             remaining_agents=len(self.agents)))
                
                # Notify via message bus
                await self._notify_agent_terminated(agent_id)
                
                return True
                
            except Exception as e:
                log_event(logger, "agent.terminate_failed",
                         **format_agent_event("agent.terminate_failed", agent_id,
                                             error=str(e),
                                             error_type=type(e).__name__))
                return False
    
    async def send_message_to_agent(self, agent_id: str, message: Dict[str, Any]) -> bool:
        """Send message directly to specific agent"""
        async with agent_context(agent_id) as _:
            try:
                if agent_id not in self.agents:
                    log_event(logger, "agent.message_delivery_failed",
                             **format_agent_event("agent.message_delivery_failed", agent_id,
                                                 reason="agent_not_found"))
                    return False
                
                agent = self.agents[agent_id]
                await agent.send_message(message)
                
                log_event(logger, "agent.message_delivered",
                         **format_agent_event("agent.message_delivered", agent_id,
                                             message_type=message.get("type", "unknown")))
                return True
                
            except Exception as e:
                log_event(logger, "agent.message_delivery_failed",
                         **format_agent_event("agent.message_delivery_failed", agent_id,
                                             error=str(e),
                                             error_type=type(e).__name__))
                return False
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_agent: Optional[str] = None) -> int:
        """Broadcast message to all active agents"""
        delivered = 0
        total_agents = len(self.agents) - (1 if exclude_agent else 0)
        
        log_event(logger, "agent.broadcast_initiated",
                 message_type=message.get("type", "unknown"),
                 target_agent_count=total_agents,
                 exclude_agent=exclude_agent)
        
        for agent_id, agent in self.agents.items():
            if exclude_agent and agent_id == exclude_agent:
                continue
                
            try:
                await agent.send_message(message)
                delivered += 1
            except Exception as e:
                log_event(logger, "agent.broadcast_delivery_failed",
                         **format_agent_event("agent.broadcast_delivery_failed", agent_id,
                                             error=str(e),
                                             error_type=type(e).__name__))
        
        log_event(logger, "agent.broadcast_completed",
                 message_type=message.get("type", "unknown"),
                 delivered_count=delivered,
                 target_count=total_agents,
                 success_rate=delivered/total_agents if total_agents > 0 else 1.0)
        return delivered
    
    async def subscribe_agent(self, agent_id: str, event_types: List[str]):
        """Subscribe agent to specific event types"""
        if agent_id not in self.agents:
            logger.warning(f"Cannot subscribe non-existent agent {agent_id}")
            return
        
        for event_type in event_types:
            if event_type not in self.message_subscriptions:
                self.message_subscriptions[event_type] = []
            
            if agent_id not in self.message_subscriptions[event_type]:
                self.message_subscriptions[event_type].append(agent_id)
        
        logger.info(f"Agent {agent_id} subscribed to events: {event_types}")
    
    async def handle_agent_message(self, from_agent: str, event_type: str, payload: Dict[str, Any]):
        """Handle message published by an agent (from simplified message bus interface)"""
        try:
            # Route message to subscribed agents
            if event_type in self.message_subscriptions:
                recipients = self.message_subscriptions[event_type]
                
                message = {
                    'type': event_type,
                    'from': from_agent,
                    'timestamp': TimestampManager.format_for_message_bus(),
                    **payload
                }
                
                delivered = 0
                for recipient_id in recipients:
                    if recipient_id != from_agent:  # Don't send to self
                        if await self.send_message_to_agent(recipient_id, message):
                            delivered += 1
                
                logger.info(f"Routed {event_type} from {from_agent} to {delivered} agents")
            
            # Also handle special orchestration events
            await self._handle_orchestration_event(from_agent, event_type, payload)
            
        except Exception as e:
            logger.error(f"Error handling agent message from {from_agent}: {e}")
    
    async def _handle_orchestration_event(self, from_agent: str, event_type: str, payload: Dict[str, Any]):
        """Handle special orchestration events"""
        try:
            if event_type == 'DEBATE_OPENING':
                # Start a debate by finding opposing agent
                await self._handle_debate_opening(from_agent, payload)
            elif event_type == 'COLLABORATION_REQUEST':
                # Find agents for collaboration
                await self._handle_collaboration_request(from_agent, payload)
            elif event_type == 'AGENT_ERROR':
                # Log agent errors
                logger.warning(f"Agent {from_agent} reported error: {payload.get('error')}")
        
        except Exception as e:
            logger.error(f"Error in orchestration event handling: {e}")
    
    async def _handle_debate_opening(self, from_agent: str, payload: Dict[str, Any]):
        """Handle debate opening by finding opposing debater"""
        # Find other debater agents
        debater_agents = [
            agent_id for agent_id, agent in self.agents.items()
            if agent.profile_name == 'debater' and agent_id != from_agent
        ]
        
        if debater_agents:
            opposing_agent = debater_agents[0]  # Take first available
            message = {
                'type': 'DEBATE_OPENING',
                'from': from_agent,
                'content': payload.get('content', ''),
                'debate_topic': payload.get('debate_topic', 'General discussion')
            }
            await self.send_message_to_agent(opposing_agent, message)
            logger.info(f"Started debate between {from_agent} and {opposing_agent}")
    
    async def _handle_collaboration_request(self, from_agent: str, payload: Dict[str, Any]):
        """Handle collaboration request by routing to relevant agents"""
        # For now, broadcast to all non-requesting agents
        # Could be made smarter based on agent capabilities/roles
        message = {
            'type': 'COLLABORATION_REQUEST',
            'from': from_agent,
            'content': payload.get('content', ''),
            'collaboration_type': payload.get('collaboration_type', 'general')
        }
        await self.broadcast_message(message, exclude_agent=from_agent)
    
    def _clean_agent_subscriptions(self, agent_id: str):
        """Remove agent from all subscriptions"""
        for event_type, subscribers in self.message_subscriptions.items():
            if agent_id in subscribers:
                subscribers.remove(agent_id)
    
    async def _notify_agent_spawned(self, agent_id: str, profile_name: str):
        """Notify other components that agent was spawned"""
        try:
            # Add to message bus using simplified interface if available
            if hasattr(self.message_bus, 'publish_simple'):
                await self.message_bus.publish_simple(
                    from_agent='orchestrator',
                    event_type='AGENT_SPAWNED',
                    payload={
                        'agent_id': agent_id,
                        'profile': profile_name,
                        'timestamp': TimestampManager.format_for_message_bus()
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to notify agent spawn: {e}")
    
    async def _notify_agent_terminated(self, agent_id: str):
        """Notify other components that agent was terminated"""
        try:
            if hasattr(self.message_bus, 'publish_simple'):
                await self.message_bus.publish_simple(
                    from_agent='orchestrator',
                    event_type='AGENT_TERMINATED',
                    payload={
                        'agent_id': agent_id,
                        'timestamp': TimestampManager.format_for_message_bus()
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to notify agent termination: {e}")
    
    # Public interface for daemon integration
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all active agents with their status"""
        agents_list = []
        
        for agent_id, agent in self.agents.items():
            status = agent.get_status()
            status['task_running'] = agent_id in self.agent_tasks and not self.agent_tasks[agent_id].done()
            agents_list.append(status)
        
        return agents_list
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific agent"""
        if agent_id in self.agents:
            return self.agents[agent_id].get_status()
        return None
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            'active_agents': len(self.agents),
            'total_spawned': self.total_agents_spawned,
            'agent_tasks': len(self.agent_tasks),
            'subscriptions': {
                event_type: len(subscribers) 
                for event_type, subscribers in self.message_subscriptions.items()
            }
        }
    
    async def shutdown(self):
        """Shutdown all agents and clean up"""
        logger.info("Shutting down MultiAgentOrchestrator")
        
        # Terminate all agents
        agent_ids = list(self.agents.keys())
        for agent_id in agent_ids:
            await self.terminate_agent(agent_id)
        
        logger.info("MultiAgentOrchestrator shutdown complete")