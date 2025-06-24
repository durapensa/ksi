#!/usr/bin/env python3
"""
COMPLETION command handler - Async completion requests via LiteLLM

All completions are now async - returns immediately with request_id,
results delivered via messaging.sock as COMPLETION_RESULT events.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, CompletionParameters, CompletionAcknowledgment
from ..manager_framework import log_operation
from pydantic import ValidationError

logger = logging.getLogger('daemon')

@command_handler("COMPLETION")
class CompletionHandler(CommandHandler):
    """Handles COMPLETION command for async Claude interactions"""
    
    def __init__(self, command_handler_context):
        super().__init__(command_handler_context)
        self.completion_queue = asyncio.Queue()
        self.worker_task = None
    
    async def initialize(self, context):
        """Initialize handler with context and start worker"""
        await super().initialize(context)
        # Start background worker for processing completions
        self.worker_task = asyncio.create_task(self._completion_worker())
    
    async def cleanup(self):
        """Clean up worker task"""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Queue completion request and return immediately"""
        # Get the actual command name used
        command_name = full_command.get('command', 'COMPLETION')
        
        # Validate parameters
        try:
            params = CompletionParameters(**parameters)
        except ValidationError as e:
            return SocketResponse.error(command_name, "INVALID_PARAMETERS", str(e))
        
        # Generate request ID
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        
        # Queue the completion work
        await self.completion_queue.put({
            'request_id': request_id,
            'params': params,
            'queued_at': self.context.timestamp_manager.timestamp_utc() if hasattr(self.context, 'timestamp_manager') else None
        })
        
        # Return immediate acknowledgment
        ack = CompletionAcknowledgment(
            request_id=request_id,
            status='queued',
            queue_position=self.completion_queue.qsize()
        )
        
        logger.info(f"Queued completion request {request_id} for client {params.client_id}")
        
        return SocketResponse.success(command_name, ack.model_dump())
    
    async def _completion_worker(self):
        """Background worker that processes completion requests"""
        logger.info("Completion worker started")
        
        while True:
            try:
                # Get next completion request
                work = await self.completion_queue.get()
                
                # Process the completion
                await self._process_completion(work)
                
            except asyncio.CancelledError:
                logger.info("Completion worker shutting down")
                break
            except Exception as e:
                logger.error(f"Error in completion worker: {e}", exc_info=True)
                # Continue processing other requests
    
    async def _process_completion(self, work: Dict[str, Any]):
        """Process a single completion request"""
        request_id = work['request_id']
        params = work['params']
        
        logger.info(f"Processing completion {request_id} for client {params.client_id}")
        
        try:
            # Check if we should route through an agent
            if params.agent_id:
                result = await self._completion_via_agent(params)
            else:
                result = await self._completion_direct(params)
            
            # Publish success result to message bus
            await self._publish_result(request_id, params.client_id, result)
            
        except Exception as e:
            logger.error(f"Completion {request_id} failed: {e}")
            # Publish error result to message bus
            await self._publish_error(request_id, params.client_id, str(e))
    
    async def _completion_via_agent(self, params: CompletionParameters) -> Dict[str, Any]:
        """Handle completion through an agent"""
        if not self.context.completion_manager or not hasattr(self.context.completion_manager, 'agent_orchestrator'):
            raise ValueError("Multi-agent orchestrator not available")
        
        orchestrator = self.context.completion_manager.agent_orchestrator
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
        if not self.context.completion_manager:
            raise ValueError("Completion manager not available")
        
        # Use completion manager to handle LiteLLM call
        result = await self.context.completion_manager.create_completion(
            prompt=params.prompt,
            model=params.model,
            session_id=params.session_id,
            timeout=params.timeout
        )
        
        return result
    
    async def _publish_result(self, request_id: str, client_id: str, result: Dict[str, Any]):
        """Publish completion result to message bus with targeted delivery"""
        if not self.context.message_bus:
            logger.error("Message bus not available for completion result")
            return
        
        # Build the result payload
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,  # Target for direct delivery
            'timestamp': self.context.timestamp_manager.timestamp_utc() if hasattr(self.context, 'timestamp_manager') else None,
            'result': {
                'response': result.get('response', ''),
                'session_id': result.get('session_id'),
                'model': result.get('model', 'sonnet'),
                'usage': result.get('usage'),
                'duration_ms': result.get('duration_ms', 0)
            }
        }
        
        # Use targeted delivery if available
        if hasattr(self.context.message_bus, 'publish_targeted'):
            # Enhanced message bus with targeted delivery
            await self.context.message_bus.publish_targeted(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                target=client_id,
                payload=payload
            )
        else:
            # Fallback to standard publish (will use DIRECT_MESSAGE routing)
            await self.context.message_bus.publish(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                payload=payload
            )
        
        logger.info(f"Published completion result for {request_id} directly to client {client_id}")
    
    async def _publish_error(self, request_id: str, client_id: str, error: str):
        """Publish completion error to message bus with targeted delivery"""
        if not self.context.message_bus:
            logger.error("Message bus not available for completion error")
            return
        
        # Build the error payload
        payload = {
            'request_id': request_id,
            'client_id': client_id,
            'to': client_id,  # Target for direct delivery
            'timestamp': self.context.timestamp_manager.timestamp_utc() if hasattr(self.context, 'timestamp_manager') else None,
            'result': {
                'error': error,
                'code': 'COMPLETION_FAILED'
            }
        }
        
        # Use targeted delivery if available
        if hasattr(self.context.message_bus, 'publish_targeted'):
            # Enhanced message bus with targeted delivery
            await self.context.message_bus.publish_targeted(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                target=client_id,
                payload=payload
            )
        else:
            # Fallback to standard publish (will use DIRECT_MESSAGE routing)
            await self.context.message_bus.publish(
                from_agent='completion_handler',
                event_type='COMPLETION_RESULT',
                payload=payload
            )
        
        logger.info(f"Published completion error for {request_id} directly to client {client_id}")