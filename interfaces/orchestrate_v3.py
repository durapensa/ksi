#!/usr/bin/env python3
"""
Multi-Claude Orchestrator v3 - Using dynamic composition discovery
"""

import asyncio
import json
import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time
import os

# Add path for ksi_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_client import EventBasedClient
from ksi_common.config import config
from prompts.discovery import CompositionDiscovery
from prompts.composition_selector import CompositionSelector, SelectionContext

# Set up logging only if not already configured
def _setup_logging():
    """Configure logging only if root logger has no handlers (i.e., not already configured)"""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # Only configure if no other logging setup exists
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

# Configure logging conditionally
_setup_logging()
logger = logging.getLogger('orchestrator_v3')


class DynamicConversationModeManager:
    """Discover and manage conversation modes using composition discovery"""
    
    def __init__(self):
        self.discovery = CompositionDiscovery()
        self.selector = CompositionSelector()
        self.modes_cache = {}
        
    async def discover_conversation_modes(self) -> Dict[str, Dict]:
        """Discover all available conversation mode compositions"""
        if self.modes_cache:
            return self.modes_cache
            
        try:
            # Get all compositions
            all_compositions = await self.discovery.get_all_compositions(include_metadata=True)
            
            # Filter for conversation modes
            for name, comp_info in all_compositions.items():
                mode_name = comp_info.metadata.get('conversation_mode')
                if mode_name:
                    self.modes_cache[mode_name] = {
                        'composition': name,
                        'min_agents': comp_info.metadata.get('min_agents', 2),
                        'max_agents': comp_info.metadata.get('max_agents', 8),
                        'description': comp_info.description,
                        'metadata': comp_info.metadata,
                        'required_capabilities': comp_info.metadata.get('capabilities_required', [])
                    }
                    logger.info(f"Discovered conversation mode: {mode_name}")
                    
        except Exception as e:
            logger.error(f"Failed to discover conversation modes: {e}")
            # Fallback to basic modes
            self.modes_cache = {
                'debate': {
                    'composition': 'conversation_debate',
                    'min_agents': 2,
                    'max_agents': 4,
                    'description': 'Structured debate between agents'
                },
                'collaboration': {
                    'composition': 'conversation_collaboration',
                    'min_agents': 2,
                    'max_agents': 6,
                    'description': 'Collaborative problem solving'
                }
            }
            
        return self.modes_cache
    
    async def get_mode(self, name: str) -> Optional[Dict]:
        """Get conversation mode by name"""
        modes = await self.discover_conversation_modes()
        return modes.get(name.lower())
    
    async def list_modes(self) -> List[str]:
        """List available conversation modes"""
        modes = await self.discover_conversation_modes()
        return list(modes.keys())
    
    async def select_composition_for_agent(self, mode: str, role: str, 
                                         topic: str, capabilities: List[str]) -> str:
        """Select best composition for an agent in a conversation"""
        # Build selection context
        context = SelectionContext(
            agent_id=f"{mode}_{role}",
            role=role,
            capabilities=capabilities,
            task_description=f"Participate in {mode} conversation about {topic}",
            preferred_style=mode
        )
        
        # Select composition
        result = await self.selector.select_composition(context)
        logger.info(f"Selected '{result.composition_name}' for {role} agent (score: {result.score:.1f})")
        return result.composition_name


class MultiClaudeOrchestratorV3:
    """Orchestrate conversations with dynamic composition discovery"""
    
    def __init__(self):
        self.client = EventBasedClient(client_id="orchestrator_v3")
        self.conversation_id = None
        self.mode_manager = DynamicConversationModeManager()
        self.connected = False
        
    async def ensure_daemon_running(self) -> bool:
        """Check if daemon is running and accessible"""
        try:
            if not self.connected:
                await self.client.connect()
                self.connected = True
            
            # Health check via event
            health = await self.client.request_event("system:health", {})
            return health.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Daemon is not running or accessible: {e}")
            logger.error("Start with: ./daemon_control.py start")
            return False
    
    async def _send_event(self, event_name: str, data: dict = None) -> dict:
        """Send event to daemon and get response"""
        try:
            if not self.connected:
                await self.client.connect()
                self.connected = True
            
            return await self.client.request_event(event_name, data or {})
        except Exception as e:
            logger.error(f"Failed to send event: {e}")
            return {"error": str(e)}
    
    def determine_agent_role(self, mode: str, agent_index: int) -> Tuple[str, List[str]]:
        """Determine role and capabilities for agent based on mode and index"""
        role_mappings = {
            'debate': [
                ('proponent', ['argumentation', 'persuasion', 'research']),
                ('opponent', ['critical_thinking', 'counterargument', 'analysis']),
                ('moderator', ['summarization', 'fairness', 'time_management']),
                ('judge', ['evaluation', 'decision_making', 'objectivity'])
            ],
            'collaboration': [
                ('researcher', ['research', 'information_gathering', 'fact_checking']),
                ('analyst', ['analysis', 'pattern_recognition', 'synthesis']),
                ('strategist', ['planning', 'decision_making', 'optimization']),
                ('coordinator', ['organization', 'communication', 'delegation'])
            ],
            'teaching': [
                ('teacher', ['explanation', 'patience', 'adaptation']),
                ('student', ['questioning', 'learning', 'comprehension']),
                ('assistant', ['support', 'clarification', 'examples'])
            ],
            'brainstorm': [
                ('ideator', ['creativity', 'innovation', 'lateral_thinking']),
                ('developer', ['elaboration', 'refinement', 'feasibility']),
                ('critic', ['evaluation', 'risk_assessment', 'improvement'])
            ],
            'analysis': [
                ('data_analyst', ['statistics', 'visualization', 'interpretation']),
                ('domain_expert', ['context', 'expertise', 'validation']),
                ('synthesizer', ['integration', 'conclusion', 'recommendation'])
            ]
        }
        
        roles = role_mappings.get(mode, [('participant', ['general'])])
        if agent_index < len(roles):
            return roles[agent_index]
        else:
            # Cycle through roles if more agents than roles
            role_index = agent_index % len(roles)
            return roles[role_index]
    
    async def get_composition_for_agent(self, mode: str, agent_index: int, topic: str) -> str:
        """Get appropriate composition for agent based on mode and role"""
        role, capabilities = self.determine_agent_role(mode, agent_index)
        
        # Map roles to existing compositions
        role_to_composition = {
            # Debate roles
            'proponent': 'debater',
            'opponent': 'debater',
            'moderator': 'base_agent',
            'judge': 'critic',
            # Collaboration roles
            'researcher': 'base_agent',
            'analyst': 'base_agent',
            'strategist': 'base_agent',
            'coordinator': 'collaborator',
            # Teaching roles
            'teacher': 'teacher',
            'student': 'student',
            'assistant': 'base_agent',
            # Brainstorm roles
            'ideator': 'creative',
            'developer': 'creative',
            'critic': 'critic',
            # Analysis roles
            'data_analyst': 'base_agent',
            'domain_expert': 'base_agent',
            'synthesizer': 'base_agent',
            # Default
            'participant': 'base_agent'
        }
        
        composition = role_to_composition.get(role, 'base_agent')
        logger.info(f"Selected composition '{composition}' for role '{role}'")
        return composition
    
    async def start_conversation(self, topic: str, mode: str = "collaboration", 
                               num_agents: int = 2, human_observer: bool = True) -> bool:
        """Start a multi-agent conversation with dynamic composition selection"""
        
        # Validate mode
        mode_config = await self.mode_manager.get_mode(mode)
        if not mode_config:
            available = await self.mode_manager.list_modes()
            logger.error(f"Unknown mode '{mode}'. Available: {', '.join(available)}")
            return False
        
        # Validate agent count
        if num_agents < mode_config['min_agents'] or num_agents > mode_config['max_agents']:
            logger.error(f"Mode '{mode}' requires {mode_config['min_agents']}-{mode_config['max_agents']} agents")
            return False
        
        # Generate conversation ID
        self.conversation_id = f"{mode}_{int(time.time())}"
        
        logger.info(f"Starting {mode} conversation about: {topic}")
        logger.info(f"Using dynamic composition selection")
        logger.info(f"Participants: {num_agents} agents")
        
        # Start agents with dynamically selected compositions
        agent_ids = []
        for i in range(num_agents):
            composition_name = await self.get_composition_for_agent(mode, i, topic)
            agent_id = f"{mode}_{i+1}"
            agent_ids.append(agent_id)
            
            # Determine agent-specific context
            role, _ = self.determine_agent_role(mode, i)
            
            # Use SPAWN_AGENT with composition-aware profile
            initial_task = f"Join {mode} conversation about: {topic}"
            context = json.dumps({
                'conversation_mode': mode,
                'topic': topic,
                'participant_number': i + 1,
                'agent_role': role
            })
            
            # Build spawn params with composition
            spawn_params = {
                "composition": composition_name,
                "task": initial_task,
                "context": context,
                "agent_id": agent_id
            }
            
            result = await self._send_event("agent:spawn", spawn_params)
            
            if result.get('error'):
                logger.error(f"Failed to start agent {agent_id}: {result['error']}")
                return False
            elif result.get('process_id'):
                logger.info(f"Started {role} agent {agent_id} (process_id: {result['process_id']})")
            
        # Give agents time to connect and subscribe
        logger.info("Waiting for agents to initialize...")
        await asyncio.sleep(3)
        
        # Initiate the conversation
        starter_message = f"Let's begin our {mode} session about: {topic}"
        
        # Send initial broadcast via event
        broadcast_data = {
            'sender': 'orchestrator',
            'topic': 'BROADCAST',
            'payload': {
                'content': starter_message,
                'conversation_id': self.conversation_id
            }
        }
        await self._send_event("message:publish", broadcast_data)
        
        logger.info(f"Conversation started with ID: {self.conversation_id}")
        logger.info("Agents are now conversing autonomously...")
        logger.info("Monitor with: python interfaces/monitor_tui.py")
        
        if human_observer:
            logger.info("Press Ctrl+C to end the conversation")
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                logger.info("\nEnding conversation...")
        
        return True
    
    async def stop_conversation(self):
        """Stop the conversation by sending shutdown signals"""
        if not self.conversation_id:
            return
        
        logger.info("Sending shutdown signal to all agents...")
        
        # Broadcast END signal via event
        end_data = {
            'sender': 'orchestrator',
            'topic': 'BROADCAST',
            'payload': {
                'content': '[END]',
                'conversation_id': self.conversation_id
            }
        }
        await self._send_event("message:publish", end_data)
        
        # Give agents time to shut down gracefully
        await asyncio.sleep(2)
        
        # Clean up temporary profiles
        temp_profiles_dir = config.agent_profiles_temp_dir
        if temp_profiles_dir.exists():
            for profile_path in temp_profiles_dir.glob('temp_*'):
                try:
                    profile_path.unlink()
                except OSError:
                    pass


async def main():
    parser = argparse.ArgumentParser(description="Orchestrate multi-Claude conversations with dynamic composition")
    parser.add_argument("topic", nargs='?', help="Topic for the conversation")
    parser.add_argument("--mode", default="collaboration", 
                       help="Conversation mode (discovered dynamically)")
    parser.add_argument("--agents", type=int, default=2, help="Number of agents")
    parser.add_argument("--no-wait", action="store_true", 
                       help="Don't wait (for programmatic use)")
    parser.add_argument("--list-modes", action="store_true",
                       help="List available conversation modes")
    
    args = parser.parse_args()
    
    orchestrator = MultiClaudeOrchestratorV3()
    
    # List modes if requested
    if args.list_modes:
        modes = await orchestrator.mode_manager.list_modes()
        print("Available conversation modes:")
        for mode in modes:
            mode_config = await orchestrator.mode_manager.get_mode(mode)
            print(f"  - {mode}: {mode_config.get('description', 'No description')}")
        return
    
    # Ensure daemon is running
    if not await orchestrator.ensure_daemon_running():
        logger.error("Please start the daemon first")
        return
    
    # Start conversation
    success = await orchestrator.start_conversation(
        args.topic, 
        args.mode, 
        args.agents,
        human_observer=not args.no_wait
    )
    
    if success:
        await orchestrator.stop_conversation()
        logger.info("Conversation ended")
    
    # Cleanup
    if orchestrator.connected:
        await orchestrator.client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())