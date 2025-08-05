"""DSPy Language Model adapter using KSI agents."""

import asyncio
from typing import List, Dict, Any, Optional, Union
import json
import logging
import uuid

import dspy
from dspy.clients.lm import LM
from dspy.primitives.prediction import Prediction

from ksi_daemon.event_system import get_router
from ksi_common.timestamps import timestamp_utc
from ksi_common.event_utils import extract_single_response


logger = logging.getLogger(__name__)


class KSIAgentLanguageModel(LM):
    """DSPy Language Model that uses KSI agents for completions."""
    
    def __init__(
        self,
        model: str = None,
        optimization_context: str = "dspy_optimization",
        **kwargs
    ):
        """Initialize KSI Agent LM adapter.
        
        Args:
            model: Model name (e.g., "claude-cli/sonnet")
            optimization_context: Context name for optimization agents
            **kwargs: Additional model configuration
        """
        self.model = model or "claude-cli/sonnet"
        self.optimization_context = optimization_context
        # Ensure DSPy expected kwargs are present
        self.kwargs = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "model": self.model,
            **kwargs  # Allow overrides
        }
        self.router = None  # Will be set when event system is available
        self.agent_pool: Dict[str, str] = {}  # Maps context to agent_id
        self.history = []
        
        # DSPy expects these attributes
        self.provider = "ksi-agent"
        self.request = self._request
        self.basic_request = self._basic_request
    
    def _get_router(self):
        """Get event router lazily to avoid initialization issues."""
        if self.router is None:
            self.router = get_router()
        return self.router
    
    async def _get_or_create_agent(self, context_key: str) -> str:
        """Get existing agent or create new one for the given context."""
        if context_key in self.agent_pool:
            return self.agent_pool[context_key]
        
        router = self._get_router()
        
        # Create optimization-specific agent
        agent_config = {
            "profile": f"optimization_{context_key}",
            "composition": "personas/optimization_assistant",
            "config": {
                "model": self.model.replace("claude-cli/", ""),  # Extract just model name
                "role": "assistant",
                "enable_tools": False,  # DSPy doesn't need tools
                "expanded_capabilities": ["reasoning", "analysis"],
                "allowed_events": [],  # No event emission needed
            },
            "metadata": {
                "purpose": "dspy_optimization",
                "context": context_key,
                "created_by": "optimization_service",
                "created_at": timestamp_utc()
            }
        }
        
        # Spawn agent
        result_list = await router.emit("agent:spawn", agent_config)
        result = extract_single_response(result_list)
        
        if isinstance(result, dict) and "agent_id" in result:
            agent_id = result["agent_id"]
            self.agent_pool[context_key] = agent_id
            logger.info(f"Created optimization agent {agent_id} for context {context_key}")
            return agent_id
        else:
            raise RuntimeError(f"Failed to spawn optimization agent: {result}")
    
    def __call__(self, prompt=None, messages=None, **kwargs):
        """Make completion request through KSI agent - sync wrapper for DSPy."""
        # DSPy can call with either prompt or messages
        if messages:
            # Convert messages format to prompt
            prompt = self._messages_to_prompt(messages)
        
        # Ensure temperature is set (defensive programming)
        kwargs.setdefault("temperature", 0.7)
        
        # For now, return a mock response to bypass async issues
        # TODO: Implement proper async bridge or run DSPy in separate process
        logger.warning("Using mock response for DSPy optimization - async bridge pending")
        return [f"Optimized instruction for prompt: {prompt[:50]}..."]
    
    async def __acall__(self, prompt=None, messages=None, **kwargs):
        """Native async method for DSPy - preferred when using DSPy's async features."""
        # DSPy can call with either prompt or messages
        if messages:
            # Convert messages format to prompt
            prompt = self._messages_to_prompt(messages)
        
        # Ensure temperature is set
        kwargs.setdefault("temperature", 0.7)
        
        # Direct async call
        return await self._async_request(prompt, **kwargs)
    
    async def _async_request(self, prompt: str, **kwargs) -> List[str]:
        """Make async completion request through KSI agent."""
        router = self._get_router()
        
        # Determine context for agent pooling
        context_key = kwargs.get("context", self.optimization_context)
        
        # Get or create agent for this context
        agent_id = await self._get_or_create_agent(context_key)
        
        # Make completion request through agent
        try:
            result_list = await router.emit("completion:async", {
                "agent_id": agent_id,
                "prompt": prompt,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1000),
                "timeout": kwargs.get("timeout", 300),  # 5 minute default
            })
            result = extract_single_response(result_list)
            
            if isinstance(result, dict):
                if "error" in result:
                    raise RuntimeError(f"Agent completion error: {result['error']}")
                
                # Extract response
                response = result.get("response", "")
                
                # DSPy expects a list of completions
                return [response]
            else:
                raise RuntimeError(f"Unexpected completion result: {result}")
                
        except Exception as e:
            logger.error(f"KSI agent completion failed: {e}")
            raise
    
    def _request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make request and return full response dict (for DSPy internals)."""
        completions = asyncio.run(self._async_request(prompt, **kwargs))
        
        # Return DSPy-compatible response format
        return {
            "choices": [
                {"text": completion} for completion in completions
            ],
            "model": self.model,
            "usage": {}  # KSI doesn't track token usage currently
        }
    
    def _basic_request(self, prompt: str, **kwargs) -> List[str]:
        """Make basic request returning just completions list."""
        return asyncio.run(self._async_request(prompt, **kwargs))
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a single prompt."""
        prompt_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def inspect_history(self, n: int = 1) -> List[Dict[str, Any]]:
        """Return last n items from history (for debugging)."""
        return self.history[-n:] if self.history else []


    async def cleanup(self):
        """Cleanup optimization agents when done."""
        router = self._get_router()
        
        for context_key, agent_id in self.agent_pool.items():
            try:
                # Terminate agent
                result_list = await router.emit("agent:terminate", {
                    "agent_id": agent_id
                })
                result = extract_single_response(result_list)
                logger.info(f"Terminated optimization agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to terminate agent {agent_id}: {e}")
        
        self.agent_pool.clear()


class KSIAsyncAgentLanguageModel(KSIAgentLanguageModel):
    """Async-native version of KSI Agent Language Model for use in async contexts."""
    
    async def __call__(self, prompt=None, messages=None, **kwargs):
        """Make async completion request."""
        if messages:
            prompt = self._messages_to_prompt(messages)
        
        return await self._async_request(prompt, **kwargs)
    
    async def request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Async version of request method."""
        completions = await self._async_request(prompt, **kwargs)
        
        return {
            "choices": [
                {"text": completion} for completion in completions
            ],
            "model": self.model,
            "usage": {}
        }
    
    async def basic_request(self, prompt: str, **kwargs) -> List[str]:
        """Async version of basic_request method."""
        return await self._async_request(prompt, **kwargs)


def configure_dspy_for_ksi(
    prompt_model: Optional[str] = None,
    task_model: Optional[str] = None,
    optimization_context: str = "dspy_optimization"
) -> Dict[str, Any]:
    """Configure DSPy to use KSI's agent system for completions.
    
    Args:
        prompt_model: Model for generating prompts (e.g., "claude-cli/opus")
        task_model: Model for task execution (e.g., "claude-cli/sonnet")
        optimization_context: Context name for optimization agents
        
    Returns:
        Dict with configured language models
    """
    # Use config defaults if not specified
    if prompt_model is None:
        from ksi_common.config import config
        prompt_model = config.optimization_prompt_model
    
    if task_model is None:
        from ksi_common.config import config
        task_model = config.optimization_task_model
    
    # Create KSI agent language models
    task_lm = KSIAgentLanguageModel(
        model=task_model, 
        optimization_context=f"{optimization_context}_task"
    )
    
    prompt_lm = KSIAgentLanguageModel(
        model=prompt_model,
        optimization_context=f"{optimization_context}_prompt"
    )
    
    # Configure DSPy with task model as default
    dspy.configure(lm=task_lm)
    
    logger.info(f"DSPy configured with KSI agent system - task: {task_model}, prompt: {prompt_model}")
    
    # Return the models for use in optimizers that need different models
    return {
        "prompt_model": prompt_lm,
        "task_model": task_lm
    }