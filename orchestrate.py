#!/usr/bin/env python3
"""
Multi-Claude Orchestrator - Start and manage Claude-to-Claude conversations
"""

import asyncio
import json
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
# import subprocess  # No longer needed - daemon handles process spawning
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('orchestrator')


class ConversationMode:
    """Define different conversation modes and their setups"""
    
    DEBATE = {
        'name': 'debate',
        'min_agents': 2,
        'max_agents': 4,
        'profiles': ['debater', 'debater'],
        'system_prompts': [
            "You are participating in a debate. Take a strong position and defend it with logic and evidence.",
            "You are participating in a debate. Take an opposing position and challenge arguments critically."
        ],
        'starter_template': "Let's debate: {topic}\n\nI'll argue FOR this position."
    }
    
    COLLABORATION = {
        'name': 'collaboration',
        'min_agents': 2,
        'max_agents': 6,
        'profiles': ['collaborator', 'collaborator'],
        'system_prompts': [
            "You are part of a collaborative team. Build on others' ideas and contribute constructively.",
            "You are part of a collaborative team. Help synthesize ideas and find creative solutions."
        ],
        'starter_template': "Let's work together on: {topic}\n\nWhat aspects should we consider?"
    }
    
    TEACHING = {
        'name': 'teaching',
        'min_agents': 2,
        'max_agents': 3,
        'profiles': ['teacher', 'student'],
        'system_prompts': [
            "You are a teacher. Explain concepts clearly and guide the learning process.",
            "You are a student. Ask clarifying questions and engage actively with the material."
        ],
        'starter_template': "I'd like to learn about: {topic}\n\nCan you help me understand this?"
    }
    
    BRAINSTORM = {
        'name': 'brainstorm',
        'min_agents': 3,
        'max_agents': 8,
        'profiles': ['creative', 'creative', 'critic'],
        'system_prompts': [
            "You are in a brainstorming session. Generate creative ideas without judgment.",
            "You are in a brainstorming session. Build on others' ideas and explore possibilities.",
            "You are in a brainstorming session. Help refine ideas and identify promising directions."
        ],
        'starter_template': "Let's brainstorm about: {topic}\n\nNo idea is too wild!"
    }
    
    ANALYSIS = {
        'name': 'analysis',
        'min_agents': 2,
        'max_agents': 5,
        'profiles': ['analyst', 'researcher'],
        'system_prompts': [
            "You are an analyst. Break down complex problems systematically.",
            "You are a researcher. Gather relevant information and identify patterns."
        ],
        'starter_template': "Let's analyze: {topic}\n\nWhat are the key factors to consider?"
    }
    
    @classmethod
    def get_mode(cls, name: str) -> Optional[Dict]:
        """Get conversation mode by name"""
        modes = {
            'debate': cls.DEBATE,
            'collaboration': cls.COLLABORATION,
            'teaching': cls.TEACHING,
            'brainstorm': cls.BRAINSTORM,
            'analysis': cls.ANALYSIS
        }
        return modes.get(name.lower())


class MultiClaudeOrchestrator:
    """Orchestrate multi-Claude conversations"""
    
    def __init__(self, daemon_socket: str = 'sockets/claude_daemon.sock'):
        self.daemon_socket = daemon_socket
        self.conversation_id: Optional[str] = None
        # Note: Process tracking now handled by daemon, not subprocess
        
    async def ensure_daemon_running(self) -> bool:
        """Check if daemon is running, start if needed"""
        try:
            # Try to connect to daemon
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            # Send health check
            writer.write(b"HEALTH_CHECK\n")
            await writer.drain()
            
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response.strip() == b"HEALTHY":
                logger.info("Daemon is running")
                return True
                
        except (FileNotFoundError, ConnectionRefusedError):
            logger.info("Daemon not running, starting it...")
            
            # Start daemon
            daemon_process = subprocess.Popen(
                ['python3', 'daemon.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for daemon to start
            await asyncio.sleep(2)
            
            # Check if started successfully
            if daemon_process.poll() is None:
                logger.info("Daemon started successfully")
                return True
            else:
                logger.error("Failed to start daemon")
                return False
                
        return False
    
    async def _send_daemon_command(self, command: str) -> dict:
        """Send command to daemon and get response"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            if not command.endswith('\n'):
                command += '\n'
            writer.write(command.encode())
            await writer.drain()
            
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response:
                return json.loads(response.decode().strip())
            return {}
            
        except Exception as e:
            logger.error(f"Error communicating with daemon: {e}")
            return {'error': str(e)}
    
    def create_agent_profile(self, mode_config: Dict, agent_index: int) -> Dict:
        """Create agent profile for a specific role"""
        profile = {
            'model': 'sonnet',
            'role': mode_config['profiles'][agent_index % len(mode_config['profiles'])],
            'capabilities': ['conversation', 'analysis', 'reasoning'],
            'system_prompt': mode_config['system_prompts'][agent_index % len(mode_config['system_prompts'])]
        }
        
        # Save profile temporarily
        profile_path = Path(f'agent_profiles/temp_{mode_config["name"]}_{agent_index}.json')
        profile_path.parent.mkdir(exist_ok=True)
        
        with open(profile_path, 'w') as f:
            json.dump(profile, f, indent=2)
        
        return profile
    
    async def start_conversation(self, topic: str, mode: str = 'collaboration', 
                               num_agents: int = 2, human_observer: bool = True):
        """Start a multi-Claude conversation"""
        
        # Get conversation mode
        mode_config = ConversationMode.get_mode(mode)
        if not mode_config:
            logger.error(f"Unknown mode: {mode}")
            return False
        
        # Validate number of agents
        if num_agents < mode_config['min_agents']:
            num_agents = mode_config['min_agents']
            logger.info(f"Adjusted to minimum {num_agents} agents for {mode} mode")
        elif num_agents > mode_config['max_agents']:
            num_agents = mode_config['max_agents']
            logger.info(f"Adjusted to maximum {num_agents} agents for {mode} mode")
        
        # Ensure daemon is running
        if not await self.ensure_daemon_running():
            return False
        
        # Generate conversation ID
        self.conversation_id = f"conv_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Starting {mode} conversation: '{topic}' with {num_agents} agents")
        
        # Create agent profiles and spawn agents via daemon SPAWN_AGENT command
        agent_ids = []
        for i in range(num_agents):
            profile = self.create_agent_profile(mode_config, i)
            agent_id = f"{mode}_{i+1}"
            profile_name = f'temp_{mode_config["name"]}_{i}'
            agent_ids.append(agent_id)
            
            # Use daemon SPAWN_AGENT command instead of spawning separate processes
            # Format: "SPAWN_AGENT:profile_name:task:context:agent_id"
            initial_task = f"You are participating in a {mode} conversation about: {topic}"
            context = f"conversation_mode={mode},topic={topic},participant_number={i+1}"
            command = f"SPAWN_AGENT:{profile_name}:{initial_task}:{context}:{agent_id}"
            
            result = await self._send_daemon_command(command)
            
            if result.get('error'):
                logger.error(f"Failed to start agent {agent_id}: {result['error']}")
                return False
            elif result.get('process_id'):
                logger.info(f"Started agent {agent_id} (process_id: {result['process_id']})")
            else:
                logger.warning(f"Agent {agent_id} start status unclear: {result}")
                
        # No subprocess tracking needed - daemon manages agent lifecycle
        
        # Wait for agents to connect
        await asyncio.sleep(3)
        
        # Start the conversation
        if agent_ids:
            await self.initiate_conversation(agent_ids[0], agent_ids[1:], topic, mode_config)
        
        # If human observer, start monitor
        if human_observer:
            logger.info("Starting TUI monitor for observation...")
            # This would launch the TUI monitor (to be implemented)
        
        return True
    
    async def initiate_conversation(self, initiator: str, participants: List[str], 
                                   topic: str, mode_config: Dict):
        """Initiate the conversation between agents"""
        try:
            # Connect to daemon to send initial message
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            # Prepare initial message
            starter_message = mode_config['starter_template'].format(topic=topic)
            
            # Send message from first agent to second
            if participants:
                message = {
                    'to': participants[0],
                    'content': starter_message,
                    'conversation_id': self.conversation_id
                }
                
                command = f"PUBLISH:{initiator}:DIRECT_MESSAGE:{json.dumps(message)}\n"
                writer.write(command.encode())
                await writer.drain()
                
                logger.info(f"Conversation initiated: {initiator} -> {participants[0]}")
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            logger.error(f"Failed to initiate conversation: {e}")
    
    async def monitor_conversation(self):
        """Monitor the ongoing conversation"""
        # Monitor via daemon agent registry
        try:
            while True:
                await asyncio.sleep(5)
                
                # Query daemon for agent status
                result = await self._send_daemon_command("GET_AGENTS")
                if result.get('error'):
                    logger.error(f"Error getting agent status: {result['error']}")
                    break
                
                agents = result.get('agents', {})
                # Count active agents in our conversation
                active_agents = [a for a in agents.values() if a.get('status') == 'active']
                
                if not active_agents:
                    logger.info("All conversation agents have stopped")
                    break
                else:
                    logger.info(f"Monitoring {len(active_agents)} active conversation agents...")
                    
        except KeyboardInterrupt:
            logger.info("Stopping conversation...")
    
    def cleanup(self):
        """Clean up resources"""
        # Note: Process cleanup now handled by daemon process manager
        # Nodes will be cleaned up when daemon shuts down or processes complete
        
        # Clean up temporary profiles
        for profile in Path('agent_profiles').glob('temp_*.json'):
            profile.unlink()
        
        logger.info("Cleanup complete")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Orchestrate multi-Claude conversations')
    parser.add_argument('topic', help='Topic for conversation')
    parser.add_argument('--mode', default='collaboration', 
                       choices=['debate', 'collaboration', 'teaching', 'brainstorm', 'analysis'],
                       help='Conversation mode')
    parser.add_argument('--agents', type=int, default=2, help='Number of agents')
    parser.add_argument('--no-monitor', action='store_true', help='Run without TUI monitor')
    parser.add_argument('--socket', default='sockets/claude_daemon.sock', help='Daemon socket')
    
    args = parser.parse_args()
    
    orchestrator = MultiClaudeOrchestrator(args.socket)
    
    try:
        # Start conversation
        success = await orchestrator.start_conversation(
            topic=args.topic,
            mode=args.mode,
            num_agents=args.agents,
            human_observer=not args.no_monitor
        )
        
        if success:
            # Monitor conversation
            await orchestrator.monitor_conversation()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        orchestrator.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
