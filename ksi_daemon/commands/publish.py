#!/usr/bin/env python3
"""
PUBLISH command handler - Publish events to the message bus
"""

import asyncio
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, PublishParameters
from ..manager_framework import log_operation

@command_handler("PUBLISH")
class PublishHandler(CommandHandler):
    """Handles PUBLISH command for message bus event publishing"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute event publishing"""
        # Validate parameters
        try:
            params = PublishParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("PUBLISH", "INVALID_PARAMETERS", str(e))
        
        # Check if message bus is available
        if not self.context.message_bus:
            return SocketResponse.error("PUBLISH", "NO_MESSAGE_BUS", "Message bus not available")
        
        # Publish the event
        result = await self.context.message_bus.publish(
            from_agent=params.from_agent,
            event_type=params.event_type,
            payload=params.payload
        )
        
        # Enhance result with additional context
        enhanced_result = {
            'event': {
                'type': params.event_type,
                'from': params.from_agent,
                'payload_size': len(str(params.payload))
            },
            'delivery': result
        }
        
        # Add event-specific information
        if params.event_type == 'DIRECT_MESSAGE':
            enhanced_result['event']['to'] = params.payload.get('to', 'unknown')
            enhanced_result['event']['message_preview'] = params.payload.get('message', '')[:100]
        elif params.event_type == 'TASK_ASSIGNMENT':
            enhanced_result['event']['task'] = params.payload.get('task', 'unknown')
            enhanced_result['event']['assigned_to'] = params.payload.get('to', 'auto-select')
        elif params.event_type == 'BROADCAST':
            # For broadcasts, show how many agents received it
            if 'delivered' in result:
                enhanced_result['event']['recipients_count'] = len(result['delivered'])
        
        # Add message bus statistics
        if hasattr(self.context.message_bus, 'subscriptions'):
            total_subscribers = sum(len(subs) for subs in self.context.message_bus.subscriptions.values())
            enhanced_result['message_bus_stats'] = {
                'total_connections': len(self.context.message_bus.connections),
                'total_subscribers': total_subscribers,
                'event_types_active': len(self.context.message_bus.subscriptions)
            }
        
        return SocketResponse.success("PUBLISH", enhanced_result)
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "PUBLISH",
            "description": "Publish an event to the message bus for distribution to subscribers",
            "parameters": {
                "from_agent": {
                    "type": "string",
                    "description": "Agent ID publishing the event",
                    "required": True
                },
                "event_type": {
                    "type": "string",
                    "description": "Type of event to publish",
                    "required": True,
                    "enum": [
                        "DIRECT_MESSAGE",
                        "BROADCAST", 
                        "TASK_ASSIGNMENT",
                        "CONVERSATION_INVITE",
                        "AGENT_STATUS",
                        "SYSTEM_EVENT"
                    ]
                },
                "payload": {
                    "type": "object",
                    "description": "Event payload data (structure depends on event type)",
                    "required": True
                }
            },
            "payload_structures": {
                "DIRECT_MESSAGE": {
                    "to": "Target agent ID (required)",
                    "message": "Message content",
                    "metadata": "Optional metadata"
                },
                "BROADCAST": {
                    "message": "Broadcast message",
                    "priority": "Message priority (optional)"
                },
                "TASK_ASSIGNMENT": {
                    "to": "Target agent ID (optional, auto-select if not provided)",
                    "task": "Task description (required)",
                    "context": "Task context",
                    "required_capabilities": "List of required capabilities"
                },
                "CONVERSATION_INVITE": {
                    "conversation_id": "Unique conversation ID",
                    "participants": "List of invited agent IDs",
                    "topic": "Conversation topic"
                }
            },
            "examples": [
                {
                    "from_agent": "coordinator_001",
                    "event_type": "DIRECT_MESSAGE",
                    "payload": {
                        "to": "analyzer_002",
                        "message": "Please analyze the latest dataset",
                        "priority": "high"
                    }
                },
                {
                    "from_agent": "system",
                    "event_type": "BROADCAST",
                    "payload": {
                        "message": "System maintenance scheduled for 2 AM",
                        "type": "announcement"
                    }
                },
                {
                    "from_agent": "task_router",
                    "event_type": "TASK_ASSIGNMENT",
                    "payload": {
                        "task": "Review security logs for anomalies",
                        "required_capabilities": ["security", "log_analysis"],
                        "context": "Focus on authentication failures"
                    }
                }
            ]
        }