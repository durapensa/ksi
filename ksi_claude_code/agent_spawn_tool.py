"""
KSI Agent Spawn Tool for Claude Code

Allows Claude Code to spawn agents via the completion:async event and manage conversations.
"""
from typing import Dict, Any, Optional, List
from .ksi_base_tool import KSIBaseTool
import logging

logger = logging.getLogger(__name__)


class AgentSpawnTool(KSIBaseTool):
    """Spawn and manage KSI agents through conversations"""
    
    name = "ksi_agent_spawn"
    description = "Spawn agents and continue conversations with them"
    
    async def spawn_agent(
        self,
        prompt: str,
        profile: str = "base_single_agent",
        model: str = "claude-cli/sonnet",
        timeout: Optional[float] = 60.0
    ) -> Dict[str, Any]:
        """
        Spawn a new agent via completion:async event
        
        Args:
            prompt: Initial prompt for the agent
            profile: Composition/profile name (e.g., 'researcher', 'base_multi_agent')
            model: Model to use (default: claude-cli/sonnet)
            timeout: Timeout for the operation
            
        Returns:
            Dictionary containing:
            - request_id: Request tracking ID
            - session_id: Session ID for continuing conversation
            - success: Whether spawn succeeded
            
        Raises:
            RuntimeError: If agent spawn fails
        """
        # Build spawn data for completion:async
        spawn_data = {
            "prompt": prompt,
            "model": model,
            "profile": profile  # Profile passed in metadata for composition selection
        }
        
        logger.info(f"Spawning agent with profile '{profile}' via completion:async")
        
        # Send completion:async event to spawn agent
        response = await self.send_event(
            "completion:async", 
            spawn_data,
            timeout=timeout
        )
        
        if not response.get("success", False):
            error_msg = response.get("error", "Unknown error")
            logger.error(f"Failed to spawn agent: {error_msg}")
            raise RuntimeError(f"Failed to spawn agent: {error_msg}")
        
        # Extract key fields
        result = {
            "request_id": response.get("request_id"),
            "session_id": response.get("session_id"),
            "success": True
        }
        
        logger.info(f"Successfully spawned agent with session_id: {result['session_id']}")
        
        return result
    
    async def continue_conversation(
        self,
        session_id: str,
        prompt: str,
        model: str = "claude-cli/sonnet",
        timeout: Optional[float] = 60.0
    ) -> Dict[str, Any]:
        """
        Continue a conversation with an existing agent
        
        Args:
            session_id: Session ID from previous response
            prompt: Next prompt in the conversation
            model: Model to use (should match original)
            timeout: Timeout for the operation
            
        Returns:
            Dictionary containing:
            - request_id: New request tracking ID
            - session_id: NEW session ID for next continuation
            - success: Whether continuation succeeded
            
        Note:
            KSI returns a NEW session_id with each response for continuation
        """
        # Build continuation data
        continuation_data = {
            "prompt": prompt,
            "model": model,
            "session_id": session_id  # Previous session ID for context
        }
        
        logger.info(f"Continuing conversation with session_id: {session_id}")
        
        # Send completion:async event to continue
        response = await self.send_event(
            "completion:async",
            continuation_data,
            timeout=timeout
        )
        
        if not response.get("success", False):
            error_msg = response.get("error", "Unknown error")
            logger.error(f"Failed to continue conversation: {error_msg}")
            raise RuntimeError(f"Failed to continue conversation: {error_msg}")
        
        # Extract key fields - note NEW session_id
        result = {
            "request_id": response.get("request_id"),
            "session_id": response.get("session_id"),  # NEW session ID!
            "success": True
        }
        
        logger.info(f"Continued conversation, new session_id: {result['session_id']}")
        
        return result
    
    async def spawn_coordinator(
        self,
        task: str,
        model: str = "claude-cli/sonnet"
    ) -> Dict[str, Any]:
        """
        Spawn a coordinator agent with multi-agent capabilities
        
        Args:
            task: Task description for the coordinator
            model: Model to use
            
        Returns:
            Spawn result with session_id for continuation
        """
        prompt = f"""You are a coordinator agent with the ability to spawn other agents.
        
Your task: {task}

You have the spawn_agents capability, which means you can create specialized agents
to help with different aspects of the task. Use this capability wisely to delegate
work to appropriate specialists.

Start by analyzing the task and determining what specialized agents you need."""

        return await self.spawn_agent(
            prompt=prompt,
            profile="base_multi_agent",  # Has spawn_agents capability
            model=model
        )
    
    async def check_response_ready(
        self,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Check if an async response is ready
        
        Args:
            request_id: Request ID to check
            
        Returns:
            Dictionary with status and response data if ready
        """
        result = await self.send_event(
            "completion:status",
            {"request_id": request_id}
        )
        
        return result
    
    async def get_agent_response(
        self,
        request_id: str,
        session_id: str
    ) -> Optional[str]:
        """
        Get the response from an agent (if ready)
        
        Args:
            request_id: Request ID to check
            session_id: Session ID for the response file
            
        Returns:
            Response text if available, None otherwise
        """
        # Check if response is ready
        status = await self.check_response_ready(request_id)
        
        if not status.get("ready", False):
            return None
        
        # In real implementation, would read from response file
        # Path would be: config.responses_dir / f"{session_id}.jsonl"
        return status.get("response", "")
    
    async def spawn_team(
        self,
        coordinator_session: str,
        team_description: str
    ) -> Dict[str, Any]:
        """
        Guide a coordinator to spawn a team
        
        Args:
            coordinator_session: Session ID of coordinator agent
            team_description: Description of team to create
            
        Returns:
            Continuation result
        """
        prompt = f"""Please spawn a team to handle this task:

{team_description}

Create appropriate specialist agents and coordinate their work. Report back
when you've spawned the team members."""
        
        return await self.continue_conversation(
            session_id=coordinator_session,
            prompt=prompt
        )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Prompt for the agent"
                    },
                    "profile": {
                        "type": "string",
                        "description": "Agent profile/composition name",
                        "enum": [
                            "base_single_agent",
                            "base_multi_agent",
                            "researcher",
                            "developer",
                            "coordinator",
                            "architect"
                        ]
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use",
                        "default": "claude-cli/sonnet"
                    }
                },
                "required": ["prompt"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute tool operation based on parameters"""
        # If session_id provided, it's a continuation
        if "session_id" in kwargs:
            return await self.continue_conversation(**kwargs)
        else:
            # Otherwise spawn new agent
            return await self.spawn_agent(**kwargs)