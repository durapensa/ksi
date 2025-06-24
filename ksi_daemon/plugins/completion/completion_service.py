#!/usr/bin/env python3
"""
Completion Service Plugin

Provides LLM completion functionality as a plugin service.
Handles completion requests through events rather than direct method calls.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

import litellm

from ...plugin_base import BasePlugin, hookimpl
from ...plugin_types import PluginInfo
from ...timestamp_utils import TimestampManager
from ...config import config
from ...event_taxonomy import CLAUDE_EVENTS, format_claude_event

# Import claude_cli_litellm_provider to ensure provider registration
import claude_cli_litellm_provider

logger = logging.getLogger(__name__)


class CompletionServicePlugin(BasePlugin):
    """Service plugin for handling LLM completions."""
    
    def __init__(self):
        super().__init__(
            name="completion_service",
            version="1.0.0",
            description="LLM completion service using LiteLLM",
            author="KSI Team",
            namespaces=["completion"]
        )
        
        # Track active completions
        self.active_completions: Dict[str, Dict[str, Any]] = {}
        
        # Plugin context references
        self._event_bus = None
        self._state_manager = None
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        config.ensure_directories()
        # Legacy directories for agent profiles
        os.makedirs('agent_profiles', exist_ok=True)
    
    @hookimpl
    def ksi_startup(self):
        """Initialize completion service on startup."""
        logger.info("Completion service plugin starting")
        self._ensure_directories()
        return {"status": "completion_service_ready"}
    
    @hookimpl
    def ksi_plugin_context(self, context):
        """Receive plugin context with event bus and state manager."""
        self._event_bus = context.get("event_bus")
        self._state_manager = context.get("state_manager")
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle completion-related events."""
        
        if event_name == "completion:request":
            # Synchronous completion request
            return asyncio.run(self._handle_completion_request(data))
        
        elif event_name == "completion:async":
            # Asynchronous completion request
            request_id = self._handle_async_completion(data)
            return {"request_id": request_id, "status": "processing"}
        
        elif event_name == "completion:cancel":
            # Cancel an active completion
            request_id = data.get("request_id")
            if request_id in self.active_completions:
                # TODO: Implement cancellation logic
                del self.active_completions[request_id]
                return {"status": "cancelled"}
            return {"status": "not_found"}
        
        elif event_name == "completion:status":
            # Get status of active completions
            return {
                "active_count": len(self.active_completions),
                "active_requests": list(self.active_completions.keys())
            }
        
        return None
    
    async def _handle_completion_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle synchronous completion request.
        
        Args:
            data: Request data containing prompt, model, session_id, etc.
            
        Returns:
            Completion result or error
        """
        prompt = data.get("prompt", "")
        session_id = data.get("session_id")
        model = data.get("model", "sonnet")
        agent_id = data.get("agent_id")
        enable_tools = data.get("enable_tools", True)
        client_id = data.get("client_id")
        
        try:
            # Prepare LiteLLM call
            messages = [{"role": "user", "content": prompt}]
            kwargs = {
                "model": f"claude-cli/{model}",
                "messages": messages
            }
            
            # Add session resumption if provided
            if session_id:
                kwargs["session_id"] = session_id
            
            # Add tools if enabled
            if enable_tools:
                kwargs["tools"] = self._get_default_tools()
            
            # Emit completion started event
            if self._event_bus:
                await self._event_bus.publish("completion:started", {
                    "session_id": session_id,
                    "model": model,
                    "client_id": client_id,
                    "agent_id": agent_id
                })
            
            # Call LiteLLM
            response = await litellm.acompletion(**kwargs)
            
            # Process response
            output = self._process_litellm_response(response, prompt, session_id, model, agent_id)
            
            # Emit completion result event
            if self._event_bus and client_id:
                await self._event_bus.publish("completion:result", {
                    "client_id": client_id,
                    "request_id": data.get("request_id"),
                    "result": output
                })
            
            return output
            
        except FileNotFoundError as e:
            error_response = {
                'error': 'claude executable not found in PATH',
                'details': str(e)
            }
            
            # Emit error event
            if self._event_bus and client_id:
                await self._event_bus.publish("completion:error", {
                    "client_id": client_id,
                    "request_id": data.get("request_id"),
                    "error": error_response
                })
            
            return error_response
            
        except Exception as e:
            error_response = {
                'error': f'Failed to complete: {type(e).__name__}',
                'details': str(e)
            }
            
            # Emit error event
            if self._event_bus and client_id:
                await self._event_bus.publish("completion:error", {
                    "client_id": client_id,
                    "request_id": data.get("request_id"),
                    "error": error_response
                })
            
            return error_response
    
    def _handle_async_completion(self, data: Dict[str, Any]) -> str:
        """
        Handle asynchronous completion request.
        
        Args:
            data: Request data
            
        Returns:
            Request ID for tracking
        """
        request_id = str(uuid.uuid4())[:8]
        
        # Track the request
        self.active_completions[request_id] = {
            'data': data,
            'started_at': TimestampManager.format_for_logging()
        }
        
        # Schedule async processing
        asyncio.create_task(self._process_async_completion(request_id, data))
        
        return request_id
    
    async def _process_async_completion(self, request_id: str, data: Dict[str, Any]):
        """Process async completion in background."""
        try:
            # Process the completion
            result = await self._handle_completion_request(data)
            
            # Emit completion done event
            if self._event_bus:
                await self._event_bus.publish("completion:done", {
                    "request_id": request_id,
                    "result": result,
                    "client_id": data.get("client_id")
                })
            
        except Exception as e:
            logger.error(f"Error in async completion {request_id}: {e}")
            
            # Emit error event
            if self._event_bus:
                await self._event_bus.publish("completion:error", {
                    "request_id": request_id,
                    "error": str(e),
                    "client_id": data.get("client_id")
                })
        
        finally:
            # Clean up tracking
            if request_id in self.active_completions:
                del self.active_completions[request_id]
    
    def _process_litellm_response(self, response: Any, prompt: str, 
                                  session_id: Optional[str], model: str,
                                  agent_id: Optional[str]) -> Dict[str, Any]:
        """Process LiteLLM response into standard format."""
        # Extract Claude CLI response from LiteLLM response
        if hasattr(response, '_claude_metadata'):
            output = response._claude_metadata.copy()
        else:
            # Fallback: construct from LiteLLM response
            content = response.choices[0].message.content
            output = {
                "result": content,
                "message": {
                    "content": [{"text": content}]
                },
                "type": "assistant"
            }
        
        # Check for stderr in response
        if hasattr(response, '_stderr') and response._stderr:
            output['stderr'] = response._stderr
        
        # Save to file for debugging
        output_file = 'sockets/claude_last_output.json'
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        # Extract session_id
        new_session_id = output.get('sessionId') or output.get('session_id')
        
        # Log to JSONL
        if new_session_id:
            self._log_conversation(new_session_id, prompt, output)
            
            # Update session tracking
            if self._state_manager:
                asyncio.create_task(
                    self._update_session_state(new_session_id, output)
                )
        
        return output
    
    def _log_conversation(self, session_id: str, prompt: str, output: Dict[str, Any]):
        """Log conversation to JSONL file."""
        log_file = str(config.session_log_dir / f'{session_id}.jsonl')
        
        # Log human input
        human_entry = {
            "timestamp": TimestampManager.format_for_logging(),
            "type": "human",
            "content": prompt
        }
        with open(log_file, 'a') as f:
            f.write(json.dumps(human_entry) + '\n')
        
        # Log Claude output
        claude_entry = output.copy()
        claude_entry["timestamp"] = TimestampManager.format_for_logging()
        claude_entry["type"] = "claude"
        with open(log_file, 'a') as f:
            f.write(json.dumps(claude_entry) + '\n')
        
        # Update latest symlink
        latest_link = str(config.session_log_dir / 'latest.jsonl')
        if os.path.exists(latest_link):
            os.unlink(latest_link)
        os.symlink(f'{session_id}.jsonl', latest_link)
        
        # Save session ID for easy resumption
        session_file = 'sockets/last_session_id'
        with open(session_file, 'w') as f:
            f.write(session_id)
    
    async def _update_session_state(self, session_id: str, output: Dict[str, Any]):
        """Update session state through event."""
        if self._event_bus:
            await self._event_bus.publish("state:update_session", {
                "session_id": session_id,
                "data": output
            })
    
    def _get_default_tools(self) -> List[Dict[str, Any]]:
        """Get default tool list for Claude."""
        return [
            {"type": "function", "function": {"name": "Task"}},
            {"type": "function", "function": {"name": "Bash"}},
            {"type": "function", "function": {"name": "Glob"}},
            {"type": "function", "function": {"name": "Grep"}},
            {"type": "function", "function": {"name": "LS"}},
            {"type": "function", "function": {"name": "Read"}},
            {"type": "function", "function": {"name": "Edit"}},
            {"type": "function", "function": {"name": "MultiEdit"}},
            {"type": "function", "function": {"name": "Write"}},
            {"type": "function", "function": {"name": "WebFetch"}},
            {"type": "function", "function": {"name": "WebSearch"}}
        ]
    
    @hookimpl
    def ksi_shutdown(self):
        """Clean up on shutdown."""
        # Cancel any active completions
        active_count = len(self.active_completions)
        self.active_completions.clear()
        
        return {
            "status": "completion_service_stopped",
            "cancelled_completions": active_count
        }


# Plugin instance
plugin = CompletionServicePlugin()

# Module-level hooks that delegate to plugin instance
@hookimpl
def ksi_startup(config):
    """Initialize completion service on startup."""
    return plugin.ksi_startup()

@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle completion-related events."""
    return plugin.ksi_handle_event(event_name, data, context)

@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    return plugin.ksi_shutdown()

# Module-level marker for plugin discovery
ksi_plugin = True