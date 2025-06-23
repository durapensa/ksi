#!/usr/bin/env python3
"""
JSON Command Schemas for Claude Daemon Protocol v2.0

Uses a pattern-based approach with 6 flexible schemas to cover all command types,
rather than individual schemas for each of the 20+ commands.
"""

import json
from typing import Dict, Any, List, Optional
from enum import Enum

class CommandType(Enum):
    """Command categories based on functional purpose"""
    PROCESS_CONTROL = "process_control"      # SPAWN, CLEANUP, RELOAD_MODULE
    AGENT_MANAGEMENT = "agent_management"    # REGISTER_AGENT, GET_AGENTS, SPAWN_AGENT, ROUTE_TASK
    MESSAGE_BUS = "message_bus"              # SUBSCRIBE, PUBLISH, AGENT_CONNECTION
    STATE_MANAGEMENT = "state_management"    # SET_SHARED, GET_SHARED, LOAD_STATE
    IDENTITY_MANAGEMENT = "identity_management"  # CREATE_IDENTITY, UPDATE_IDENTITY, etc.
    SYSTEM_STATUS = "system_status"          # HEALTH_CHECK, GET_COMMANDS, MESSAGE_BUS_STATS, GET_PROCESSES
    SYSTEM_CONTROL = "system_control"        # SHUTDOWN, RELOAD_DAEMON

# Base schema that all commands inherit from
BASE_COMMAND_SCHEMA = {
    "type": "object",
    "required": ["command", "version"],
    "properties": {
        "command": {
            "type": "string",
            "description": "The command name"
        },
        "version": {
            "type": "string", 
            "enum": ["2.0"],
            "description": "Protocol version"
        },
        "parameters": {
            "type": "object",
            "description": "Command-specific parameters",
            "default": {}
        },
        "metadata": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string", "format": "date-time"},
                "client_id": {"type": "string"},
                "request_id": {"type": "string"}
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}

# Process Control Commands Schema
PROCESS_CONTROL_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # SPAWN command
                {
                    "properties": {
                        "command": {"const": "SPAWN"},
                        "parameters": {
                            "type": "object",
                            "required": ["mode", "type", "prompt"],
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "enum": ["sync", "async"],
                                    "description": "Execution mode"
                                },
                                "type": {
                                    "type": "string", 
                                    "enum": ["claude"],
                                    "description": "Process type"
                                },
                                "session_id": {
                                    "type": ["string", "null"],
                                    "description": "Optional session ID for conversation continuity"
                                },
                                "model": {
                                    "type": "string",
                                    "default": "sonnet",
                                    "description": "Claude model to use"
                                },
                                "agent_id": {
                                    "type": ["string", "null"],
                                    "description": "Optional agent identifier"
                                },
                                "prompt": {
                                    "type": "string",
                                    "description": "The prompt to send to Claude"
                                },
                                "enable_tools": {
                                    "type": "boolean",
                                    "default": True,
                                    "description": "Whether to enable tool usage"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # CLEANUP command
                {
                    "properties": {
                        "command": {"const": "CLEANUP"},
                        "parameters": {
                            "type": "object",
                            "required": ["cleanup_type"],
                            "properties": {
                                "cleanup_type": {
                                    "type": "string",
                                    "description": "Type of cleanup to perform"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # RELOAD_MODULE command
                {
                    "properties": {
                        "command": {"const": "RELOAD_MODULE"},
                        "parameters": {
                            "type": "object",
                            "required": ["module_name"],
                            "properties": {
                                "module_name": {
                                    "type": "string",
                                    "description": "Name of module to reload"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# Agent Management Commands Schema
AGENT_MANAGEMENT_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # REGISTER_AGENT command
                {
                    "properties": {
                        "command": {"const": "REGISTER_AGENT"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id", "role"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Unique agent identifier"
                                },
                                "role": {
                                    "type": "string",
                                    "description": "Agent role or function"
                                },
                                "capabilities": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of agent capabilities",
                                    "default": []
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # GET_AGENTS command
                {
                    "properties": {
                        "command": {"const": "GET_AGENTS"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                },
                # SPAWN_AGENT command (updated for new API)
                {
                    "properties": {
                        "command": {"const": "SPAWN_AGENT"},
                        "parameters": {
                            "type": "object",
                            "required": ["task"],
                            "properties": {
                                "task": {
                                    "type": "string",
                                    "description": "Initial task for the agent"
                                },
                                "profile_name": {
                                    "type": ["string", "null"],
                                    "description": "Agent profile name (fallback if composition selection fails)"
                                },
                                "agent_id": {
                                    "type": ["string", "null"],
                                    "description": "Unique agent identifier (auto-generated if not provided)"
                                },
                                "context": {
                                    "type": "string",
                                    "description": "Additional context for the agent",
                                    "default": ""
                                },
                                "role": {
                                    "type": ["string", "null"],
                                    "description": "Role hint for composition selection"
                                },
                                "capabilities": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Required capabilities for composition selection",
                                    "default": []
                                },
                                "model": {
                                    "type": "string",
                                    "description": "Claude model to use",
                                    "default": "sonnet"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # ROUTE_TASK command
                {
                    "properties": {
                        "command": {"const": "ROUTE_TASK"},
                        "parameters": {
                            "type": "object",
                            "required": ["task"],
                            "properties": {
                                "task": {
                                    "type": "string",
                                    "description": "Task to be routed"
                                },
                                "required_capabilities": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Required agent capabilities",
                                    "default": []
                                },
                                "context": {
                                    "type": "string",
                                    "description": "Additional task context",
                                    "default": ""
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# Message Bus Commands Schema
MESSAGE_BUS_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # SUBSCRIBE command
                {
                    "properties": {
                        "command": {"const": "SUBSCRIBE"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id", "event_types"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent subscribing to events"
                                },
                                "event_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of event types to subscribe to"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # PUBLISH command
                {
                    "properties": {
                        "command": {"const": "PUBLISH"},
                        "parameters": {
                            "type": "object",
                            "required": ["from_agent", "event_type", "payload"],
                            "properties": {
                                "from_agent": {
                                    "type": "string",
                                    "description": "Agent publishing the event"
                                },
                                "event_type": {
                                    "type": "string",
                                    "description": "Type of event being published"
                                },
                                "payload": {
                                    "type": "object",
                                    "description": "Event payload data"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # AGENT_CONNECTION command
                {
                    "properties": {
                        "command": {"const": "AGENT_CONNECTION"},
                        "parameters": {
                            "type": "object",
                            "required": ["action", "agent_id"],
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["connect", "disconnect"],
                                    "description": "Connection action"
                                },
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent identifier"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # MESSAGE_BUS_STATS command
                {
                    "properties": {
                        "command": {"const": "MESSAGE_BUS_STATS"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# State Management Commands Schema
STATE_MANAGEMENT_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # SET_SHARED command
                {
                    "properties": {
                        "command": {"const": "SET_SHARED"},
                        "parameters": {
                            "type": "object",
                            "required": ["key", "value"],
                            "properties": {
                                "key": {
                                    "type": "string",
                                    "description": "State key identifier"
                                },
                                "value": {
                                    "description": "State value (any JSON type)"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # GET_SHARED command
                {
                    "properties": {
                        "command": {"const": "GET_SHARED"},
                        "parameters": {
                            "type": "object",
                            "required": ["key"],
                            "properties": {
                                "key": {
                                    "type": "string",
                                    "description": "State key to retrieve"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # LOAD_STATE command
                {
                    "properties": {
                        "command": {"const": "LOAD_STATE"},
                        "parameters": {
                            "type": "object",
                            "required": ["state_data"],
                            "properties": {
                                "state_data": {
                                    "type": "object",
                                    "description": "State data to load"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# Identity Management Commands Schema
IDENTITY_MANAGEMENT_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # CREATE_IDENTITY command
                {
                    "properties": {
                        "command": {"const": "CREATE_IDENTITY"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent identifier"
                                },
                                "display_name": {
                                    "type": ["string", "null"],
                                    "description": "Human-readable display name"
                                },
                                "role": {
                                    "type": ["string", "null"],
                                    "description": "Agent role or function"
                                },
                                "personality_traits": {
                                    "type": ["object", "null"],
                                    "description": "Personality traits data"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # UPDATE_IDENTITY command
                {
                    "properties": {
                        "command": {"const": "UPDATE_IDENTITY"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id", "updates"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent identifier"
                                },
                                "updates": {
                                    "type": "object",
                                    "description": "Identity updates to apply"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # GET_IDENTITY command
                {
                    "properties": {
                        "command": {"const": "GET_IDENTITY"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent identifier"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # LIST_IDENTITIES command
                {
                    "properties": {
                        "command": {"const": "LIST_IDENTITIES"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                },
                # REMOVE_IDENTITY command
                {
                    "properties": {
                        "command": {"const": "REMOVE_IDENTITY"},
                        "parameters": {
                            "type": "object",
                            "required": ["agent_id"],
                            "properties": {
                                "agent_id": {
                                    "type": "string",
                                    "description": "Agent identifier"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# System Status Commands Schema
SYSTEM_STATUS_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "oneOf": [
                # HEALTH_CHECK command
                {
                    "properties": {
                        "command": {"const": "HEALTH_CHECK"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                },
                # GET_COMMANDS command
                {
                    "properties": {
                        "command": {"const": "GET_COMMANDS"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                },
                # GET_PROCESSES command
                {
                    "properties": {
                        "command": {"const": "GET_PROCESSES"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False
                        }
                    }
                },
                # GET_COMPOSITIONS command
                {
                    "properties": {
                        "command": {"const": "GET_COMPOSITIONS"},
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "include_metadata": {
                                    "type": "boolean",
                                    "default": True,
                                    "description": "Include composition metadata"
                                },
                                "category": {
                                    "type": ["string", "null"],
                                    "description": "Filter by category"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # GET_COMPOSITION command
                {
                    "properties": {
                        "command": {"const": "GET_COMPOSITION"},
                        "parameters": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Composition name"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # VALIDATE_COMPOSITION command
                {
                    "properties": {
                        "command": {"const": "VALIDATE_COMPOSITION"},
                        "parameters": {
                            "type": "object",
                            "required": ["name", "context"],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Composition name"
                                },
                                "context": {
                                    "type": "object",
                                    "description": "Context to validate"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # LIST_COMPONENTS command
                {
                    "properties": {
                        "command": {"const": "LIST_COMPONENTS"},
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "directory": {
                                    "type": ["string", "null"],
                                    "description": "Filter by directory"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                },
                # COMPOSE_PROMPT command
                {
                    "properties": {
                        "command": {"const": "COMPOSE_PROMPT"},
                        "parameters": {
                            "type": "object",
                            "required": ["composition", "context"],
                            "properties": {
                                "composition": {
                                    "type": "string",
                                    "description": "Composition name"
                                },
                                "context": {
                                    "type": "object",
                                    "description": "Context for composition"
                                }
                            },
                            "additionalProperties": False
                        }
                    }
                }
            ]
        }
    ]
}

# System Control Commands Schema
SYSTEM_CONTROL_SCHEMA = {
    "allOf": [
        BASE_COMMAND_SCHEMA,
        {
            "properties": {
                "command": {
                    "enum": ["SHUTDOWN", "RELOAD_DAEMON"]
                },
                "parameters": {
                    "type": "object",
                    "additionalProperties": False
                }
            }
        }
    ]
}

# Standard response schema - ALL responses use this format
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["status", "command"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["success", "error"],
            "description": "Operation result status"
        },
        "command": {
            "type": "string",
            "description": "The command that was executed"
        },
        "result": {
            "type": ["object", "string", "array", "number", "boolean", "null"],
            "description": "Command-specific result data"
        },
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "string"}
            },
            "additionalProperties": False,
            "description": "Error information if status is error"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string", "format": "date-time"},
                "processing_time_ms": {"type": "number"},
                "daemon_version": {"type": "string"},
                "request_id": {"type": "string"}
            },
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}

# Master schema that validates against the appropriate functional group
COMMAND_SCHEMA = {
    "oneOf": [
        PROCESS_CONTROL_SCHEMA,
        AGENT_MANAGEMENT_SCHEMA,
        MESSAGE_BUS_SCHEMA,
        STATE_MANAGEMENT_SCHEMA,
        IDENTITY_MANAGEMENT_SCHEMA,
        SYSTEM_STATUS_SCHEMA,
        SYSTEM_CONTROL_SCHEMA
    ]
}

# Command to functional group mapping for efficient validation
COMMAND_MAPPINGS = {
    # Process Control
    "SPAWN": CommandType.PROCESS_CONTROL,
    "CLEANUP": CommandType.PROCESS_CONTROL,
    "RELOAD_MODULE": CommandType.PROCESS_CONTROL,
    
    # Agent Management
    "REGISTER_AGENT": CommandType.AGENT_MANAGEMENT,
    "GET_AGENTS": CommandType.AGENT_MANAGEMENT,
    "SPAWN_AGENT": CommandType.AGENT_MANAGEMENT,
    "ROUTE_TASK": CommandType.AGENT_MANAGEMENT,
    
    # Message Bus
    "SUBSCRIBE": CommandType.MESSAGE_BUS,
    "PUBLISH": CommandType.MESSAGE_BUS,
    "AGENT_CONNECTION": CommandType.MESSAGE_BUS,
    "MESSAGE_BUS_STATS": CommandType.MESSAGE_BUS,
    
    # State Management
    "SET_SHARED": CommandType.STATE_MANAGEMENT,
    "GET_SHARED": CommandType.STATE_MANAGEMENT,
    "LOAD_STATE": CommandType.STATE_MANAGEMENT,
    
    # Identity Management
    "CREATE_IDENTITY": CommandType.IDENTITY_MANAGEMENT,
    "UPDATE_IDENTITY": CommandType.IDENTITY_MANAGEMENT,
    "GET_IDENTITY": CommandType.IDENTITY_MANAGEMENT,
    "LIST_IDENTITIES": CommandType.IDENTITY_MANAGEMENT,
    "REMOVE_IDENTITY": CommandType.IDENTITY_MANAGEMENT,
    
    # System Status
    "HEALTH_CHECK": CommandType.SYSTEM_STATUS,
    "GET_COMMANDS": CommandType.SYSTEM_STATUS,
    "GET_PROCESSES": CommandType.SYSTEM_STATUS,
    "GET_COMPOSITIONS": CommandType.SYSTEM_STATUS,
    "GET_COMPOSITION": CommandType.SYSTEM_STATUS,
    "VALIDATE_COMPOSITION": CommandType.SYSTEM_STATUS,
    "LIST_COMPONENTS": CommandType.SYSTEM_STATUS,
    "COMPOSE_PROMPT": CommandType.SYSTEM_STATUS,
    
    # System Control
    "SHUTDOWN": CommandType.SYSTEM_CONTROL,
    "RELOAD_DAEMON": CommandType.SYSTEM_CONTROL
}

# Schema group mappings for validation routing
SCHEMA_MAPPINGS = {
    CommandType.PROCESS_CONTROL: PROCESS_CONTROL_SCHEMA,
    CommandType.AGENT_MANAGEMENT: AGENT_MANAGEMENT_SCHEMA,
    CommandType.MESSAGE_BUS: MESSAGE_BUS_SCHEMA,
    CommandType.STATE_MANAGEMENT: STATE_MANAGEMENT_SCHEMA,
    CommandType.IDENTITY_MANAGEMENT: IDENTITY_MANAGEMENT_SCHEMA,
    CommandType.SYSTEM_STATUS: SYSTEM_STATUS_SCHEMA,
    CommandType.SYSTEM_CONTROL: SYSTEM_CONTROL_SCHEMA
}

def get_schema_for_command(command: str) -> Dict[str, Any]:
    """Get the appropriate schema for a specific command"""
    command_type = COMMAND_MAPPINGS.get(command)
    
    if command_type in SCHEMA_MAPPINGS:
        return SCHEMA_MAPPINGS[command_type]
    else:
        raise ValueError(f"Unknown command: {command}")

def get_command_type(command: str) -> CommandType:
    """Get the functional type for a command"""
    command_type = COMMAND_MAPPINGS.get(command)
    if command_type is None:
        raise ValueError(f"Unknown command: {command}")
    return command_type

def validate_command(command_data: Dict[str, Any]) -> bool:
    """Validate a command against its schema"""
    try:
        import jsonschema
        jsonschema.validate(command_data, COMMAND_SCHEMA)
        return True
    except Exception:
        return False