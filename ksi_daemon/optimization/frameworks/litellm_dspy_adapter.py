"""Direct LiteLLM adapter for DSPy optimization - bypasses agent overhead.

This adapter provides a clean, synchronous interface between DSPy and KSI's
LiteLLM providers (claude-cli, gemini-cli) without the complexity of the
full completion service. Designed specifically for optimization workloads
where we don't need session management, agent persistence, or retry queues.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Union

# Disable LiteLLM's HTTP request for model pricing on startup
import os
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'true'

import litellm
from dspy.clients.lm import LM

# Import KSI's custom providers to ensure registration
from ksi_daemon.completion import claude_cli_litellm_provider
from ksi_daemon.completion import gemini_cli_litellm_provider

logger = logging.getLogger(__name__)


class KSILiteLLMDSPyAdapter(LM):
    """Direct LiteLLM adapter for DSPy optimization - bypasses agent overhead.
    
    This adapter:
    - Uses LiteLLM directly without going through KSI's completion service
    - Maintains compatibility with KSI's custom providers (claude-cli, gemini-cli)
    - Provides sync interface that DSPy expects
    - Avoids unnecessary agent spawning and session management
    - Perfect for optimization workloads that need simple, fast completions
    """
    
    def __init__(
        self, 
        model: str = "claude-cli/sonnet",
        sandbox_dir: Optional[str] = None,
        **kwargs
    ):
        """Initialize the adapter with model and configuration.
        
        Args:
            model: Model name (e.g., "claude-cli/sonnet", "claude-cli/opus")
            sandbox_dir: Optional sandbox directory for CLI models
            **kwargs: Additional parameters for LiteLLM
        """
        self.model = model
        self.sandbox_dir = sandbox_dir
        
        # Default parameters for optimization
        self.kwargs = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "timeout": 300,  # 5 minutes default for optimization
            **kwargs  # Allow overrides
        }
        
        # Track history for debugging
        self.history = []
        
        # DSPy compatibility attributes
        self.provider = "ksi-litellm"
        self.request = self._request
        self.basic_request = self._basic_request
        
        logger.info(f"KSI LiteLLM adapter initialized with model: {model}")
    
    def __call__(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> List[str]:
        """Make completion request - sync interface for DSPy.
        
        Args:
            prompt: Single prompt string
            messages: OpenAI-style messages list
            **kwargs: Additional parameters
            
        Returns:
            List of completion strings (DSPy expects list)
        """
        # Convert prompt to messages if needed
        if prompt and not messages:
            messages = [{"role": "user", "content": prompt}]
        elif not messages:
            raise ValueError("Either prompt or messages must be provided")
        
        # Merge kwargs
        call_kwargs = {**self.kwargs, **kwargs}
        
        # Add KSI-specific parameters if using CLI models
        if self.model.startswith(("claude-cli/", "gemini-cli/")):
            if "extra_body" not in call_kwargs:
                call_kwargs["extra_body"] = {}
            if "ksi" not in call_kwargs["extra_body"]:
                call_kwargs["extra_body"]["ksi"] = {}
            
            # Add sandbox_dir if provided
            if self.sandbox_dir:
                call_kwargs["extra_body"]["ksi"]["sandbox_dir"] = self.sandbox_dir
        
        try:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use async version
                future = asyncio.run_coroutine_threadsafe(
                    self._acompletion(messages, call_kwargs),
                    loop
                )
                response = future.result(timeout=call_kwargs.get("timeout", 300))
            except RuntimeError:
                # No event loop, use sync version
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    **call_kwargs
                )
            
            # Extract response content
            content = response.choices[0].message.content
            
            # For Claude CLI models, unwrap the JSON response if needed
            if self.model.startswith("claude-cli/"):
                try:
                    # Check if this is a wrapped Claude CLI response
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "type" in parsed and "result" in parsed:
                        # This is a wrapped response, extract the actual result
                        actual_content = parsed["result"]
                        # If the result is a JSON string, parse it again
                        if isinstance(actual_content, str) and actual_content.strip().startswith("{"):
                            try:
                                json.loads(actual_content)  # Validate it's JSON
                                content = actual_content  # Use the unwrapped JSON
                            except:
                                # Not valid JSON, use as-is
                                content = actual_content
                        else:
                            content = actual_content
                except (json.JSONDecodeError, KeyError):
                    # Not wrapped JSON or parsing failed, use original content
                    pass
            
            # Track in history
            self.history.append({
                "messages": messages,
                "response": content,
                "model": self.model
            })
            
            # Return as list (DSPy expects this)
            return [content]
            
        except Exception as e:
            logger.error(f"LiteLLM completion error: {e}")
            raise
    
    async def _acompletion(
        self, 
        messages: List[Dict[str, str]], 
        kwargs: Dict[str, Any]
    ) -> Any:
        """Async completion for when we're in an async context."""
        return await litellm.acompletion(
            model=self.model,
            messages=messages,
            **kwargs
        )
    
    def _request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make request and return full response dict (for DSPy internals)."""
        completions = self(prompt, **kwargs)
        
        # Return DSPy-compatible response format
        return {
            "choices": [{"text": completion} for completion in completions],
            "model": self.model,
            "usage": {}  # KSI doesn't track usage currently
        }
    
    def _basic_request(self, prompt: str, **kwargs) -> List[str]:
        """Make basic request returning just completions list."""
        return self(prompt, **kwargs)
    
    def inspect_history(self, n: int = 1) -> List[Dict[str, Any]]:
        """Return last n items from history (for debugging)."""
        return self.history[-n:] if self.history else []


class KSIAsyncLiteLLMDSPyAdapter(KSILiteLLMDSPyAdapter):
    """Async-native version for use in async contexts."""
    
    async def __call__(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> List[str]:
        """Async completion interface."""
        # Convert prompt to messages if needed
        if prompt and not messages:
            messages = [{"role": "user", "content": prompt}]
        elif not messages:
            raise ValueError("Either prompt or messages must be provided")
        
        # Merge kwargs
        call_kwargs = {**self.kwargs, **kwargs}
        
        # Add KSI parameters for CLI models
        if self.model.startswith(("claude-cli/", "gemini-cli/")):
            if "extra_body" not in call_kwargs:
                call_kwargs["extra_body"] = {}
            if "ksi" not in call_kwargs["extra_body"]:
                call_kwargs["extra_body"]["ksi"] = {}
            
            if self.sandbox_dir:
                call_kwargs["extra_body"]["ksi"]["sandbox_dir"] = self.sandbox_dir
        
        # Direct async call
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            **call_kwargs
        )
        
        # Extract content
        content = response.choices[0].message.content
        
        # For Claude CLI models, unwrap the JSON response if needed
        if self.model.startswith("claude-cli/"):
            try:
                # Check if this is a wrapped Claude CLI response
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "type" in parsed and "result" in parsed:
                    # This is a wrapped response, extract the actual result
                    actual_content = parsed["result"]
                    # If the result is a JSON string, parse it again
                    if isinstance(actual_content, str) and actual_content.strip().startswith("{"):
                        try:
                            json.loads(actual_content)  # Validate it's JSON
                            content = actual_content  # Use the unwrapped JSON
                        except:
                            # Not valid JSON, use as-is
                            content = actual_content
                    else:
                        content = actual_content
            except (json.JSONDecodeError, KeyError):
                # Not wrapped JSON or parsing failed, use original content
                pass
        
        # Track in history
        self.history.append({
            "messages": messages,
            "response": content,
            "model": self.model
        })
        
        return [content]


def configure_dspy_with_litellm(
    prompt_model: Optional[str] = None,
    task_model: Optional[str] = None,
    sandbox_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Configure DSPy to use direct LiteLLM integration.
    
    Args:
        prompt_model: Model for prompt optimization (e.g., "claude-cli/opus")
        task_model: Model for task execution (e.g., "claude-cli/sonnet")
        sandbox_dir: Optional sandbox directory for CLI models
        
    Returns:
        Dict with configured language models
    """
    import dspy
    from ksi_common.config import config
    
    # Use config defaults if not specified
    if prompt_model is None:
        prompt_model = config.optimization_prompt_model or "claude-cli/opus"
    
    if task_model is None:
        task_model = config.optimization_task_model or "claude-cli/sonnet"
    
    # Create direct LiteLLM adapters
    prompt_lm = KSILiteLLMDSPyAdapter(
        model=prompt_model,
        sandbox_dir=sandbox_dir,
        temperature=0.1  # Lower temperature for prompt optimization
    )
    
    task_lm = KSILiteLLMDSPyAdapter(
        model=task_model,
        sandbox_dir=sandbox_dir,
        temperature=0.7  # Higher temperature for task variety
    )
    
    # Configure DSPy with task model as default
    dspy.configure(lm=task_lm)
    
    logger.info(
        f"DSPy configured with direct LiteLLM - "
        f"prompt: {prompt_model}, task: {task_model}"
    )
    
    return {
        "prompt_model": prompt_lm,
        "task_model": task_lm
    }