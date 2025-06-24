#!/usr/bin/env python3
"""
COMPLETION command handler - Simplified stateless version
No background workers, no queues - just handle the request and return
"""

import asyncio
import logging
import uuid
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, CompletionParameters, CompletionAcknowledgment
from ..manager_framework import log_operation
from pydantic import ValidationError

logger = logging.getLogger('daemon')

@command_handler("COMPLETION")
class CompletionHandler(CommandHandler):
    """Handles COMPLETION command for async Claude interactions"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Handle completion request asynchronously"""
        # Get the actual command name used
        command_name = full_command.get('command', 'COMPLETION')
        
        # Validate parameters
        try:
            params = CompletionParameters(**parameters)
        except ValidationError as e:
            return SocketResponse.error(command_name, "INVALID_PARAMETERS", str(e))
        
        # Generate request ID
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        # The completion manager should handle async processing
        # We'll start the completion and return immediately
        if not self.completion_manager:
            return SocketResponse.error(command_name, "SERVICE_UNAVAILABLE", "Completion manager not available")
        
        # Start async completion (non-blocking)
        asyncio.create_task(self._process_completion_async(request_id, params))
        
        # Return immediate acknowledgment
        ack = CompletionAcknowledgment(
            request_id=request_id,
            status='processing',
            queue_position=0  # No queue in simplified version
        )
        
        logger.info(f"Started async completion {request_id} for client {params.client_id}")
        
        return SocketResponse.success(command_name, ack.model_dump())
    
    async def _process_completion_async(self, request_id: str, params: CompletionParameters):
        """Process completion asynchronously and publish result"""
        logger.info(f"Processing completion {request_id} for client {params.client_id}")
        
        try:
            # Determine routing method
            if params.agent_id:
                result = await self._completion_via_agent(params)
            else:
                result = await self._completion_direct(params)
            
            # Publish success result
            await self._publish_result(request_id, params.client_id, result)
            
        except Exception as e:
            logger.error(f"Completion {request_id} failed: {e}")
            # Publish error result
            await self._publish_error(request_id, params.client_id, str(e))
    
    async def _completion_via_agent(self, params: CompletionParameters) -> Dict[str, Any]:
        """Handle completion through an agent"""
        if not self.completion_manager or not hasattr(self.completion_manager, 'agent_orchestrator'):
            raise ValueError("Multi-agent orchestrator not available")
        
        orchestrator = self.completion_manager.agent_orchestrator
        if not orchestrator:
            raise ValueError("Multi-agent orchestrator not initialized")
        
        # Check if agent exists
        if params.agent_id not in orchestrator.agents:
            raise ValueError(f"Agent '{params.agent_id}' not found")
        
        agent = orchestrator.agents[params.agent_id]
        
        # Send prompt to agent and get response
        response = await agent.send_prompt(params.prompt, params.session_id)
        return response
    
    async def _completion_direct(self, params: CompletionParameters) -> Dict[str, Any]:
        """Handle direct completion without agent"""
        # Use completion manager to handle LiteLLM call
        result = await self.completion_manager.create_completion(
            prompt=params.prompt,
            model=params.model,
            session_id=params.session_id,
            timeout=params.timeout
        )
        
        return result
    
    async def _publish_result(self, request_id: str, client_id: str, result: Dict[str, Any]):
        """Publish completion result to message bus"""
        if not self.message_bus:
            logger.error("Message bus not available for completion result")
            return
        
        # Build the result payload
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,  # Target for direct delivery
            'timestamp': None,  # Let message bus handle timestamps
            'result': {
                'response': result.get('response', ''),
                'session_id': result.get('session_id'),
                'model': result.get('model', 'sonnet'),
                'usage': result.get('usage'),
                'duration_ms': result.get('duration_ms', 0)
            }
        }
        
        # Use targeted delivery if available
        if hasattr(self.message_bus, 'publish_targeted'):
            await self.message_bus.publish_targeted(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                target=client_id,
                payload=payload
            )
        else:
            # Standard publish
            await self.message_bus.publish(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                payload=payload
            )
        
        logger.info(f"Published completion result for {request_id} to client {client_id}")
    
    async def _publish_error(self, request_id: str, client_id: str, error: str):
        """Publish completion error to message bus"""
        if not self.message_bus:
            logger.error("Message bus not available for completion error")
            return
        
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,
            'timestamp': None,
            'result': {
                'error': error,
                'code': 'COMPLETION_FAILED'
            }
        }
        
        # Use targeted delivery if available
        if hasattr(self.message_bus, 'publish_targeted'):
            await self.message_bus.publish_targeted(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                target=client_id,
                payload=payload
            )
        else:
            await self.message_bus.publish(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                payload=payload
            )
        
        logger.info(f"Published completion error for {request_id} to client {client_id}")