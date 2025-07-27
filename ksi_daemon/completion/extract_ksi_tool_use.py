"""
KSI Tool Use Extraction for Completion Service

Extracts ksi_tool_use format events from completion responses.
"""

import re
import json
from typing import List, Dict, Any, Optional, Callable
from ksi_common.logging import get_bound_logger
from ksi_common.tool_use_adapter import (
    extract_ksi_events,
    validate_event_data,
    is_ksi_tool_use
)

logger = get_bound_logger("ksi_tool_use_extraction")


async def extract_and_emit_ksi_tool_use_events(
    text: str,
    event_emitter: Callable,
    context: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract and emit events in ksi_tool_use format.
    
    This function specifically handles the new tool-use-inspired format:
    {
        "type": "ksi_tool_use",
        "id": "ksiu_...",
        "name": "event_name",
        "input": {...}
    }
    
    Args:
        text: Text containing potential ksi_tool_use blocks
        event_emitter: Function to emit events
        context: Optional context to add to emitted events
        agent_id: Optional agent ID to track source
        
    Returns:
        List of events that were emitted in tool use format
    """
    emitted = []
    
    # Extract events using the dual-path adapter
    extracted_events = extract_ksi_events(text)
    
    # Process only tool use format events
    for event_tuple, format_type in extracted_events:
        if format_type != "tool_use":
            continue  # Skip legacy format (handled by existing extraction)
            
        try:
            event_name = event_tuple.get('event')
            event_data = event_tuple.get('data', {})
            tool_use_id = event_tuple.get('_tool_use_id')
            
            # Validate event data
            is_valid, error_msg = validate_event_data(event_name, event_data)
            if not is_valid:
                logger.warning(
                    f"Invalid ksi_tool_use event data: {error_msg}",
                    event_name=event_name,
                    tool_use_id=tool_use_id
                )
                continue
            
            # Add metadata
            if agent_id:
                event_data['_agent_id'] = agent_id
            event_data['_extracted_from_response'] = True
            event_data['_extracted_via'] = 'ksi_tool_use'
            event_data['_tool_use_id'] = tool_use_id
            
            # Add context metadata
            if context:
                for key in ['_orchestration_id', 'orchestration_id']:
                    if key in context:
                        event_data['_orchestration_id'] = context[key]
                        break
                
                for key in ['_orchestration_depth', 'orchestration_depth']:
                    if key in context:
                        event_data['_orchestration_depth'] = context[key]
                        break
                
                event_data.setdefault('_context', {}).update(context)
            
            # Create emission context
            emission_context = None
            if agent_id:
                emission_context = {'_agent_id': agent_id}
            
            # Emit the event
            emission_result = await event_emitter(event_name, event_data, emission_context)
            
            logger.info(
                f"Emitted ksi_tool_use event {event_name}",
                agent_id=agent_id,
                event_name=event_name,
                tool_use_id=tool_use_id
            )
            
            # Route to originator if needed
            if agent_id:
                try:
                    from ksi_daemon.agent.agent_service import route_to_originator
                    await route_to_originator(agent_id, event_name, emission_result)
                except Exception as e:
                    logger.debug(f"Failed to route to originator: {e}")
            
            # Track emitted event
            emitted.append({
                'event': event_name,
                'data': event_data,
                'tool_use_id': tool_use_id,
                'format': 'ksi_tool_use',
                'emission_result': emission_result
            })
            
        except Exception as e:
            logger.error(
                f"Failed to process ksi_tool_use event: {e}",
                error=str(e),
                agent_id=agent_id
            )
    
    return emitted


def count_ksi_tool_use_blocks(text: str) -> int:
    """Count the number of ksi_tool_use blocks in text."""
    pattern = r'\{\s*"type"\s*:\s*"ksi_tool_use"'
    return len(re.findall(pattern, text))


def has_ksi_tool_use_events(text: str) -> bool:
    """Check if text contains any ksi_tool_use events."""
    return count_ksi_tool_use_blocks(text) > 0