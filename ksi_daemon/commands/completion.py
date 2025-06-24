#!/usr/bin/env python3
"""
COMPLETION command handler - Stateless version following aioinject patterns

This handler is truly stateless:
- No background workers
- No queues
- Just validates input and delegates to CompletionManager
- Returns immediate acknowledgment
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
    """Stateless handler for COMPLETION command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Handle completion request by delegating to CompletionManager"""
        command_name = full_command.get('command', 'COMPLETION')
        
        # Validate parameters
        try:
            params = CompletionParameters(**parameters)
        except ValidationError as e:
            return SocketResponse.error(command_name, "INVALID_PARAMETERS", str(e))
        
        # Check if completion manager is available
        if not self.completion_manager:
            return SocketResponse.error(command_name, "SERVICE_UNAVAILABLE", "Completion manager not available")
        
        # Generate request ID
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        # Start async completion in CompletionManager
        # The manager should handle all the complexity (queuing, workers, etc.)
        asyncio.create_task(self._delegate_to_manager(request_id, params))
        
        # Return immediate acknowledgment
        ack = CompletionAcknowledgment(
            request_id=request_id,
            status='processing',
            queue_position=0
        )
        
        logger.info(f"Delegated completion {request_id} to manager for client {params.client_id}")
        
        return SocketResponse.success(command_name, ack.model_dump())
    
    async def _delegate_to_manager(self, request_id: str, params: CompletionParameters):
        """Delegate completion to manager and publish results"""
        try:
            # Let CompletionManager handle the actual completion
            result = await self.completion_manager.create_completion(
                prompt=params.prompt,
                model=params.model,
                session_id=params.session_id,
                agent_id=params.agent_id,
                enable_tools=True
            )
            
            # Publish success result via message bus
            await self._publish_result(request_id, params.client_id, result)
            
        except Exception as e:
            logger.error(f"Completion {request_id} failed: {e}")
            await self._publish_error(request_id, params.client_id, str(e))
    
    async def _publish_result(self, request_id: str, client_id: str, result: Dict[str, Any]):
        """Publish completion result to message bus"""
        if not self.message_bus:
            logger.error("Message bus not available")
            return
        
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,
            'result': {
                'response': result.get('result', ''),  # Claude CLI returns 'result' not 'response'
                'session_id': result.get('sessionId') or result.get('session_id'),
                'model': result.get('model', 'sonnet'),
                'usage': result.get('usage'),
                'duration_ms': result.get('duration_ms', 0)
            }
        }
        
        await self.message_bus.publish(
            from_agent='completion_handler',
            event_type='COMPLETION_RESULT',
            payload=payload
        )
        
        logger.info(f"Published completion result for {request_id} to client {client_id}")
    
    async def _publish_error(self, request_id: str, client_id: str, error: str):
        """Publish completion error to message bus"""
        if not self.message_bus:
            logger.error("Message bus not available")
            return
        
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,
            'result': {
                'error': error,
                'code': 'COMPLETION_FAILED'
            }
        }
        
        await self.message_bus.publish(
            from_agent='completion_handler',
            event_type='COMPLETION_RESULT',
            payload=payload
        )
        
        logger.info(f"Published completion error for {request_id} to client {client_id}")