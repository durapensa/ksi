#!/usr/bin/env python3
"""
ROUTE_TASK command handler - Route tasks to the most suitable available agent
"""

import asyncio
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel, Field

class RouteTaskParameters(BaseModel):
    """Parameters for ROUTE_TASK command"""
    task: str = Field(..., description="Task description to route")
    required_capabilities: List[str] = Field([], description="Required capabilities for the task")
    context: str = Field("", description="Additional context for the task")
    prefer_agent_id: str = Field(None, description="Preferred agent ID if available")

@command_handler("ROUTE_TASK")
class RouteTaskHandler(CommandHandler):
    """Handles ROUTE_TASK command - routes tasks based on agent capabilities"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute task routing with capability matching"""
        # Validate parameters
        try:
            params = RouteTaskParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error("ROUTE_TASK", "INVALID_PARAMETERS", str(e))
        
        # Check if agent manager is available
        if not self.context.agent_manager:
            return ResponseFactory.error("ROUTE_TASK", "NO_AGENT_MANAGER", "Agent manager not available")
        
        # Use agent manager to find the best agent
        routing_result = await self.context.agent_manager.route_task(
            task=params.task,
            required_capabilities=params.required_capabilities,
            context=params.context
        )
        
        # Check routing result status
        if routing_result['status'] == 'no_suitable_agent':
            return ResponseFactory.success("ROUTE_TASK", {
                'status': 'no_suitable_agent',
                'reason': 'No agents have the required capabilities',
                'required_capabilities': params.required_capabilities,
                'suggestion': 'Consider spawning a specialist agent with these capabilities',
                'available_agents': self.context.agent_manager.list_agents()
            })
        
        if routing_result['status'] == 'no_available_agent':
            return ResponseFactory.success("ROUTE_TASK", {
                'status': 'no_available_agent', 
                'reason': 'All suitable agents are busy',
                'suitable_agents': routing_result.get('suitable_agents', []),
                'suggestion': routing_result.get('suggestion', 'Wait for agents to become available or spawn a new one')
            })
        
        # Task was successfully routed
        assigned_agent = routing_result['assigned_agent']
        
        # Now actually deliver the task via message bus if available
        delivery_status = None
        if self.context.message_bus:
            # Publish task assignment event
            delivery_result = await self.context.message_bus.publish(
                from_agent="system",
                event_type="TASK_ASSIGNMENT",
                payload={
                    'to': assigned_agent,
                    'task': params.task,
                    'context': params.context,
                    'required_capabilities': params.required_capabilities,
                    'routing_metadata': {
                        'match_score': routing_result.get('match_score', 0),
                        'agent_role': routing_result.get('agent_role', 'unknown')
                    }
                }
            )
            delivery_status = delivery_result.get('status', 'unknown')
        else:
            delivery_status = 'no_message_bus'
        
        # Get full agent details
        agent_details = self.context.agent_manager.get_agent(assigned_agent)
        
        # Return comprehensive routing information
        return ResponseFactory.success("ROUTE_TASK", {
            'routing': {
                'status': 'routed',
                'assigned_agent': {
                    'id': assigned_agent,
                    'role': routing_result.get('agent_role', agent_details.get('role') if agent_details else 'unknown'),
                    'capabilities': agent_details.get('capabilities', []) if agent_details else [],
                    'match_score': routing_result.get('match_score', 0),
                    'status': agent_details.get('status', 'unknown') if agent_details else 'unknown'
                }
            },
            'task': {
                'description': params.task,
                'context': params.context,
                'required_capabilities': params.required_capabilities
            },
            'delivery': {
                'status': delivery_status,
                'message': routing_result.get('message', f"TASK_ASSIGNMENT: {params.task}")
            }
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "ROUTE_TASK",
            "description": "Route a task to the most suitable available agent based on required capabilities",
            "parameters": {
                "task": {
                    "type": "string",
                    "description": "Task description to route",
                    "required": True
                },
                "required_capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required capabilities for the task",
                    "optional": True,
                    "default": []
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the task",
                    "optional": True,
                    "default": ""
                },
                "prefer_agent_id": {
                    "type": "string",
                    "description": "Preferred agent ID if available",
                    "optional": True
                }
            },
            "examples": [
                {
                    "task": "Analyze the latest sales data and generate insights",
                    "required_capabilities": ["data_analysis", "visualization"],
                    "context": "Focus on Q4 2024 performance metrics"
                },
                {
                    "task": "Debug the authentication module",
                    "required_capabilities": ["debugging", "security"],
                    "prefer_agent_id": "dev_agent_001"
                }
            ],
            "response_examples": [
                {
                    "description": "Successful routing",
                    "routing": {
                        "status": "routed",
                        "assigned_agent": {
                            "id": "analyst_001",
                            "role": "data_analyst",
                            "capabilities": ["data_analysis", "visualization", "reporting"],
                            "match_score": 2
                        }
                    }
                },
                {
                    "description": "No suitable agent",
                    "status": "no_suitable_agent",
                    "reason": "No agents have the required capabilities",
                    "suggestion": "Consider spawning a specialist agent with these capabilities"
                }
            ]
        }