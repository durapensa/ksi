#!/usr/bin/env python3
"""
Enhanced Plugin Utilities for KSI

Provides richer metadata decorators and introspection capabilities
to help Claude agents better understand and use KSI events.
"""

from typing import Dict, Any, List, Optional, Callable, Set
from functools import wraps
from dataclasses import dataclass
from enum import Enum
import inspect


class EventCategory(Enum):
    """Categories to help Claude understand event purposes."""
    CORE = "core"              # Essential operations (completion, health)
    CONVERSATION = "conversation"  # Conversation management
    STATE = "state"            # Persistent state management
    AGENT = "agent"            # Multi-agent coordination
    MONITORING = "monitoring"   # System monitoring
    ADVANCED = "advanced"      # Advanced features (injection, orchestration)
    INTERNAL = "internal"      # Internal system events


@dataclass
class EventRelationship:
    """Describes relationships between events."""
    triggers: List[str] = None        # Events this might trigger
    triggered_by: List[str] = None    # Events that might trigger this
    related: List[str] = None         # Related events (same workflow)
    response_event: Optional[str] = None  # Expected response event
    cancel_event: Optional[str] = None    # Event to cancel this operation


@dataclass
class EventCost:
    """Describes cost implications of an event."""
    has_cost: bool = False
    cost_type: Optional[str] = None  # "llm", "compute", "storage"
    typical_cost_usd: Optional[float] = None
    cost_factors: List[str] = None   # ["prompt_length", "model_type"]


@dataclass
class EventTiming:
    """Describes timing characteristics."""
    is_async: bool = False
    typical_duration_ms: Optional[int] = None
    timeout_ms: Optional[int] = None
    is_streaming: bool = False


@dataclass
class EventExample:
    """Rich example with context."""
    description: str
    scenario: str  # "new_conversation", "continue_conversation", etc.
    data: Dict[str, Any]
    expected_response: Optional[Dict[str, Any]] = None
    common_errors: List[str] = None


class EnhancedEventMetadata:
    """Container for all enhanced metadata."""
    
    def __init__(self):
        self.category: EventCategory = EventCategory.CORE
        self.tags: Set[str] = set()
        self.relationships: EventRelationship = EventRelationship()
        self.cost: EventCost = EventCost()
        self.timing: EventTiming = EventTiming()
        self.examples: List[EventExample] = []
        self.common_errors: List[Dict[str, str]] = []
        self.best_practices: List[str] = []
        self.warnings: List[str] = []
        self.see_also: List[str] = []  # Related documentation/events
        
        # Workflow information
        self.workflow_position: Optional[str] = None  # "start", "middle", "end"
        self.workflow_name: Optional[str] = None  # "completion_flow"
        
        # Parameter hints for Claude
        self.parameter_hints: Dict[str, str] = {}  # param_name -> hint
        self.parameter_relationships: Dict[str, List[str]] = {}  # param dependencies


def enhanced_event_handler(
    event_name: str,
    category: EventCategory = EventCategory.CORE,
    tags: List[str] = None,
    async_response: bool = False,
    response_event: Optional[str] = None,
    typical_duration_ms: Optional[int] = None,
    has_cost: bool = False,
    workflow: Optional[str] = None,
    best_practices: List[str] = None,
    warnings: List[str] = None
):
    """
    Enhanced event handler decorator with rich metadata.
    
    Example:
        @enhanced_event_handler(
            "completion:async",
            category=EventCategory.CORE,
            tags=["llm", "async"],
            async_response=True,
            response_event="completion:result",
            typical_duration_ms=5000,
            has_cost=True,
            best_practices=["Always include request_id for tracking"],
            warnings=["Results may arrive out of order in high load"]
        )
        def handle_completion_async(data):
            ...
    """
    def decorator(func):
        # Create rich metadata
        metadata = EnhancedEventMetadata()
        metadata.category = category
        metadata.tags = set(tags or [])
        metadata.timing.is_async = async_response
        metadata.timing.typical_duration_ms = typical_duration_ms
        metadata.cost.has_cost = has_cost
        metadata.relationships.response_event = response_event
        metadata.workflow_name = workflow
        metadata.best_practices = best_practices or []
        metadata.warnings = warnings or []
        
        # Extract from docstring
        docstring = inspect.getdoc(func) or ""
        
        # Store both standard and enhanced metadata
        func._ksi_event_name = event_name
        func._ksi_enhanced_metadata = metadata
        
        # Also create standard metadata for compatibility
        func._ksi_event_metadata = {
            'event': event_name,
            'summary': docstring.split('\n')[0] if docstring else "",
            'parameters': _parse_parameters_from_docstring(docstring),
            'examples': _parse_examples_from_docstring(docstring),
            # Enhanced fields
            'category': category.value,
            'tags': list(metadata.tags),
            'async': async_response,
            'response_event': response_event,
            'typical_duration_ms': typical_duration_ms,
            'has_cost': has_cost,
            'best_practices': metadata.best_practices,
            'warnings': metadata.warnings
        }
        
        return func
    
    return decorator


def event_relationships(
    triggers: List[str] = None,
    triggered_by: List[str] = None,
    related: List[str] = None,
    cancel_with: Optional[str] = None
):
    """Decorator to add relationship information."""
    def decorator(func):
        if hasattr(func, '_ksi_enhanced_metadata'):
            func._ksi_enhanced_metadata.relationships.triggers = triggers
            func._ksi_enhanced_metadata.relationships.triggered_by = triggered_by
            func._ksi_enhanced_metadata.relationships.related = related
            func._ksi_enhanced_metadata.relationships.cancel_event = cancel_with
        return func
    return decorator


def event_examples(*examples: EventExample):
    """Decorator to add rich examples."""
    def decorator(func):
        if hasattr(func, '_ksi_enhanced_metadata'):
            func._ksi_enhanced_metadata.examples.extend(examples)
            
            # Also add to standard metadata
            if hasattr(func, '_ksi_event_metadata'):
                func._ksi_event_metadata['examples'] = [
                    {
                        'description': ex.description,
                        'data': ex.data,
                        'scenario': ex.scenario
                    }
                    for ex in examples
                ]
        return func
    return decorator


def event_errors(*errors: Dict[str, str]):
    """Decorator to document common errors."""
    def decorator(func):
        if hasattr(func, '_ksi_enhanced_metadata'):
            func._ksi_enhanced_metadata.common_errors.extend(errors)
            
            if hasattr(func, '_ksi_event_metadata'):
                func._ksi_event_metadata['common_errors'] = list(errors)
        return func
    return decorator


def parameter_hints(**hints: str):
    """
    Add hints for specific parameters to help Claude.
    
    Example:
        @parameter_hints(
            session_id="Omit for new conversation, include to continue",
            model="Use 'claude-cli/sonnet' for best results"
        )
    """
    def decorator(func):
        if hasattr(func, '_ksi_enhanced_metadata'):
            func._ksi_enhanced_metadata.parameter_hints.update(hints)
        return func
    return decorator


# Helper functions for parsing docstrings (reuse from original)
def _parse_parameters_from_docstring(docstring: str) -> Dict[str, Any]:
    """Parse parameters from docstring (same as original)."""
    # Implementation from original plugin_utils.py
    # ... (omitted for brevity)
    return {}


def _parse_examples_from_docstring(docstring: str) -> List[Dict[str, Any]]:
    """Parse examples from docstring (same as original)."""
    # Implementation from original plugin_utils.py
    # ... (omitted for brevity)
    return []


# Workflow definitions to help Claude understand event sequences
WORKFLOW_DEFINITIONS = {
    "completion_flow": {
        "description": "Standard LLM completion workflow",
        "steps": [
            {
                "event": "completion:async",
                "description": "Start completion request",
                "outputs": ["request_id"]
            },
            {
                "event": "completion:status",
                "description": "Check completion status (optional)",
                "inputs": ["request_id"],
                "optional": True
            },
            {
                "event": "completion:result",
                "description": "Receive completion result (automatic)",
                "inputs": ["request_id"],
                "automatic": True
            }
        ],
        "cancel": "completion:cancel"
    },
    
    "conversation_management": {
        "description": "Managing conversations and sessions",
        "steps": [
            {
                "event": "conversation:list",
                "description": "Find existing conversations"
            },
            {
                "event": "conversation:get",
                "description": "Load specific conversation",
                "inputs": ["session_id"]
            },
            {
                "event": "completion:async",
                "description": "Continue conversation",
                "inputs": ["session_id", "prompt"]
            }
        ]
    },
    
    "state_management": {
        "description": "Persistent state storage",
        "steps": [
            {
                "event": "state:set",
                "description": "Store state value",
                "inputs": ["key", "value", "namespace"]
            },
            {
                "event": "state:get",
                "description": "Retrieve state value",
                "inputs": ["key", "namespace"]
            },
            {
                "event": "state:list",
                "description": "List keys in namespace",
                "inputs": ["namespace"]
            }
        ]
    }
}


def generate_claude_friendly_docs(event_metadata: Dict[str, Any]) -> str:
    """
    Generate Claude-optimized documentation from event metadata.
    
    This could be used to create even better prompts that include
    workflow information, timing expectations, cost implications, etc.
    """
    doc = f"# Event: {event_metadata['event']}\n\n"
    
    # Category and tags
    doc += f"**Category**: {event_metadata.get('category', 'general')}\n"
    if event_metadata.get('tags'):
        doc += f"**Tags**: {', '.join(event_metadata['tags'])}\n"
    
    doc += f"\n{event_metadata.get('summary', 'No description')}\n\n"
    
    # Timing information
    if event_metadata.get('async'):
        doc += "⚡ **Async Event**: Returns immediately with a request_id\n"
        if event_metadata.get('response_event'):
            doc += f"   Response arrives via: `{event_metadata['response_event']}`\n"
        if event_metadata.get('typical_duration_ms'):
            doc += f"   Typical duration: {event_metadata['typical_duration_ms']}ms\n"
    
    # Cost information
    if event_metadata.get('has_cost'):
        doc += "💰 **Has Cost**: This event may incur charges\n"
    
    # Parameters
    if event_metadata.get('parameters'):
        doc += "\n## Parameters\n\n"
        for name, info in event_metadata['parameters'].items():
            req = "required" if info.get('required') else "optional"
            doc += f"- **{name}** ({info.get('type', 'any')}, {req}): "
            doc += f"{info.get('description', name)}\n"
            
            # Add parameter hints if available
            if hints := event_metadata.get('parameter_hints', {}).get(name):
                doc += f"  💡 *Hint: {hints}*\n"
    
    # Examples
    if event_metadata.get('examples'):
        doc += "\n## Examples\n\n"
        for ex in event_metadata['examples']:
            if ex.get('scenario'):
                doc += f"### Scenario: {ex['scenario']}\n"
            doc += f"{ex.get('description', 'Example')}\n"
            doc += "```json\n"
            doc += json.dumps({
                "event": event_metadata['event'],
                "data": ex.get('data', {})
            }, indent=2)
            doc += "\n```\n\n"
    
    # Best practices
    if event_metadata.get('best_practices'):
        doc += "\n## Best Practices\n\n"
        for practice in event_metadata['best_practices']:
            doc += f"- {practice}\n"
    
    # Warnings
    if event_metadata.get('warnings'):
        doc += "\n## ⚠️ Warnings\n\n"
        for warning in event_metadata['warnings']:
            doc += f"- {warning}\n"
    
    # Related events
    if event_metadata.get('related_events'):
        doc += "\n## Related Events\n\n"
        for event in event_metadata['related_events']:
            doc += f"- `{event}`\n"
    
    return doc