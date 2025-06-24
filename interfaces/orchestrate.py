#!/usr/bin/env python3
"""
Multi-Claude Orchestrator v2 - Using composition-based conversation modes
"""

import asyncio
import json
import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
import os

# Add path for daemon client utilities
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_daemon.client import CommandBuilder, ResponseHandler

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
logger = logging.getLogger('orchestrator')


class ConversationModeManager:
    """Load and manage conversation modes from compositions"""
    
    def __init__(self, compositions_path: str = "prompts/compositions"):
        self.compositions_path = Path(compositions_path)
        self.modes = {}
        self._load_conversation_modes()
    
    def _load_conversation_modes(self):
        """Load all conversation mode compositions"""
        for comp_file in self.compositions_path.glob("conversation_*.yaml"):
            try:
                with open(comp_file) as f:
                    composition = yaml.safe_load(f)
                    
                metadata = composition.get('metadata', {})
                mode_name = metadata.get('conversation_mode')
                
                if mode_name:
                    self.modes[mode_name] = {
                        'composition': composition['name'],
                        'min_agents': metadata.get('min_agents', 2),
                        'max_agents': metadata.get('max_agents', 8),
                        'description': composition.get('description', ''),
                        'metadata': metadata
                    }
                    logger.info(f"Loaded conversation mode: {mode_name}")
                    
            except Exception as e:
                logger.error(f"Failed to load {comp_file}: {e}")
    
    def get_mode(self, name: str) -> Optional[Dict]:
        """Get conversation mode by name"""
        return self.modes.get(name.lower())
    
    def list_modes(self) -> List[str]:
        """List available conversation modes"""
        return list(self.modes.keys())


class MultiClaudeOrchestrator:
    """Orchestrate conversations between multiple Claude agents"""
    
    def __init__(self):
        self.daemon_socket = Path("sockets/claude_daemon.sock")
        self.conversation_id = None
        self.mode_manager = ConversationModeManager()
        
    async def ensure_daemon_running(self) -> bool:
        """Check if daemon is running and accessible"""
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.daemon_socket))
            # Use JSON protocol for health check
            health_cmd = CommandBuilder.build_command("HEALTH_CHECK")
            command_str = json.dumps(health_cmd) + '\n'
            writer.write(command_str.encode())
            await writer.drain()
            
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response:
                try:
                    result = json.loads(response.decode().strip())
                    return ResponseHandler.check_success(result) and \
                           ResponseHandler.get_result_data(result).get("status") == "healthy"
                except:
                    return False
            return False
        except:
            logger.error("Daemon is not running. Start with: ./daemon_control.sh start")
            return False
    
    async def _send_daemon_command(self, command: str) -> dict:
        """Send command to daemon and get response"""
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.daemon_socket))
            
            if not command.endswith('\n'):
                command += '\n'
            
            writer.write(command.encode())
            await writer.drain()
            
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response:
                response_str = response.decode().strip()
                if response_str == "HEALTHY":
                    return {"status": "healthy"}
                try:
                    return json.loads(response_str)
                except json.JSONDecodeError:
                    return {"response": response_str}
            return {}
            
        except Exception as e:
            logger.error(f"Error communicating with daemon: {e}")
            return {"error": str(e)}
    
    def determine_agent_role(self, mode_name: str, agent_index: int) -> tuple[str, str]:
        """Determine agent role and composition based on mode and index"""
        # Role assignment logic based on conversation mode
        role_assignments = {
            'debate': lambda i: ('debater', f'conversation_debate'),
            'collaboration': lambda i: ('collaborator', f'conversation_collaboration'),
            'teaching': lambda i: ('teacher' if i == 0 else 'student', f'conversation_teaching'),
            'brainstorm': lambda i: ('creative' if i < 2 else 'critic', f'conversation_brainstorm'),
            'analysis': lambda i: ('analyst' if i % 2 == 0 else 'researcher', f'conversation_analysis')
        }
        
        if mode_name in role_assignments:
            role, composition = role_assignments[mode_name](agent_index)
            return role, composition
        
        # Default fallback
        return 'participant', 'claude_agent_default'
    
    def create_agent_profile(self, mode_name: str, agent_index: int) -> Dict:
        """Create agent profile for composition-based system"""
        role, composition = self.determine_agent_role(mode_name, agent_index)
        
        profile = {
            'model': 'sonnet',
            'role': role,
            'composition': composition,
            'enable_tools': False  # Conversation agents don't need tools
        }
        
        # Save profile
        profile_path = Path(f'agent_profiles/temp_{mode_name}_{agent_index}.json')
        profile_path.parent.mkdir(exist_ok=True)
        
        with open(profile_path, 'w') as f:
            json.dump(profile, f, indent=2)
        
        return profile
    
    async def start_conversation(self, topic: str, mode: str = 'collaboration', 
                               num_agents: int = 2, human_observer: bool = True):
        """Start a multi-Claude conversation using compositions"""
        
        # Get conversation mode
        mode_config = self.mode_manager.get_mode(mode)
        if not mode_config:
            logger.error(f"Unknown mode: {mode}")
            logger.info(f"Available modes: {', '.join(self.mode_manager.list_modes())}")
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
        logger.info(f"Using composition: {mode_config['composition']}")
        
        # Create agent profiles and spawn agents
        agent_ids = []
        for i in range(num_agents):
            profile = self.create_agent_profile(mode, i)
            agent_id = f"{mode}_{i+1}"
            profile_name = f'temp_{mode}_{i}'
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
            
            # Build JSON SPAWN_AGENT command
            spawn_params = {
                "profile_name": profile_name,
                "task": initial_task,
                "context": context,
                "agent_id": agent_id
            }
            spawn_cmd = CommandBuilder.build_command("SPAWN_AGENT", spawn_params)
            command_str = json.dumps(spawn_cmd) + '\n'
            
            result = await self._send_daemon_command(command_str)
            
            if result.get('error'):
                logger.error(f"Failed to start agent {agent_id}: {result['error']}")
                return False
            elif result.get('process_id'):
                logger.info(f"Started {role} agent {agent_id} (process_id: {result['process_id']})")
            
        # Give agents time to connect and subscribe
        logger.info("Waiting for agents to initialize...")
        await asyncio.sleep(3)
        
        # Initiate the conversation
        starter_agent = agent_ids[0]
        starter_message = f"Let's begin our {mode} session about: {topic}"
        
        # Send initial broadcast to all agents
        # Build JSON PUBLISH command for broadcast
        broadcast_payload = {
            'content': starter_message,
            'conversation_id': self.conversation_id
        }
        broadcast_cmd = CommandBuilder.build_publish_command("orchestrator", "BROADCAST", broadcast_payload)
        broadcast_command_str = json.dumps(broadcast_cmd) + '\n'
        await self._send_daemon_command(broadcast_command_str)
        
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
        
        # Broadcast END signal
        # Build JSON PUBLISH command for END signal
        end_payload = {
            'content': '[END]',
            'conversation_id': self.conversation_id
        }
        end_cmd = CommandBuilder.build_publish_command("orchestrator", "BROADCAST", end_payload)
        end_command_str = json.dumps(end_cmd) + '\n'
        await self._send_daemon_command(end_command_str)
        
        # Give agents time to shut down gracefully
        await asyncio.sleep(2)


async def main():
    parser = argparse.ArgumentParser(description="Orchestrate multi-Claude conversations")
    parser.add_argument("topic", help="Topic for the conversation")
    parser.add_argument("--mode", default="collaboration", 
                       help="Conversation mode (debate, collaboration, teaching, brainstorm, analysis)")
    parser.add_argument("--agents", type=int, default=2, help="Number of agents")
    parser.add_argument("--no-wait", action="store_true", 
                       help="Don't wait (for programmatic use)")
    
    args = parser.parse_args()
    
    orchestrator = MultiClaudeOrchestrator()
    
    # List available modes if requested
    if args.topic.lower() == "list-modes":
        print("Available conversation modes:")
        for mode in orchestrator.mode_manager.list_modes():
            mode_config = orchestrator.mode_manager.get_mode(mode)
            print(f"  - {mode}: {mode_config['description']}")
            print(f"    Agents: {mode_config['min_agents']}-{mode_config['max_agents']}")
        return
    
    try:
        success = await orchestrator.start_conversation(
            topic=args.topic,
            mode=args.mode,
            num_agents=args.agents,
            human_observer=not args.no_wait
        )
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\nConversation interrupted")
    finally:
        await orchestrator.stop_conversation()


if __name__ == "__main__":
    asyncio.run(main())