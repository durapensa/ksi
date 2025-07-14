#!/usr/bin/env python3
"""
JSON Extraction Utilities

Extract JSON objects from text, particularly for parsing agent/LLM responses
that may contain embedded JSON for event emission.
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable
import asyncio
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("json_extraction")


def extract_json_objects(text: str, filter_func: Optional[Callable[[Dict], bool]] = None) -> List[Dict[str, Any]]:
    """
    Extract all valid JSON objects from text.
    
    Looks for JSON in various formats:
    - Code blocks: ```json ... ```
    - Plain JSON objects: {...}
    - Multiple JSON objects in a single response
    
    Args:
        text: Text to extract JSON from
        filter_func: Optional filter to apply to extracted objects
        
    Returns:
        List of extracted JSON objects
    """
    extracted = []
    
    # Pattern 1: JSON in code blocks
    code_block_pattern = r'```(?:json)?\s*(\{[^`]+\})\s*```'
    for match in re.finditer(code_block_pattern, text, re.DOTALL):
        try:
            obj = json.loads(match.group(1))
            if not filter_func or filter_func(obj):
                extracted.append(obj)
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse JSON in code block: {match.group(1)[:100]}...")
    
    # Pattern 2: Standalone JSON objects (with nested objects)
    # This regex handles nested braces
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    
    # Find all potential JSON objects
    for match in re.finditer(json_pattern, text):
        json_str = match.group(0)
        # Skip if this was already found in a code block
        if any(json_str in str(obj) for obj in extracted):
            continue
            
        try:
            obj = json.loads(json_str)
            if not filter_func or filter_func(obj):
                # Avoid duplicates
                if obj not in extracted:
                    extracted.append(obj)
        except json.JSONDecodeError:
            # Try to handle common issues like trailing commas
            try:
                # Remove trailing commas before closing braces/brackets
                cleaned = re.sub(r',\s*([}\]])', r'\1', json_str)
                obj = json.loads(cleaned)
                if not filter_func or filter_func(obj):
                    if obj not in extracted:
                        extracted.append(obj)
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse potential JSON: {json_str[:100]}...")
    
    return extracted


def extract_event_json(text: str) -> List[Dict[str, Any]]:
    """
    Extract JSON objects that look like event emissions.
    
    Looks for JSON objects with an 'event' field, which indicates
    an intent to emit an event to the KSI system.
    
    Args:
        text: Text to extract event JSON from
        
    Returns:
        List of event JSON objects
    """
    def is_event(obj: Dict) -> bool:
        return isinstance(obj, dict) and 'event' in obj
    
    return extract_json_objects(text, filter_func=is_event)


async def extract_and_emit_json_events(
    text: str, 
    event_emitter: Callable,
    context: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract JSON events from text and emit them asynchronously.
    
    This is designed to be called from completion service to automatically
    emit events found in agent responses.
    
    Args:
        text: Text containing potential JSON events
        event_emitter: Function to emit events (typically router.emit)
        context: Optional context to add to emitted events
        agent_id: Optional agent ID to track source
        
    Returns:
        List of events that were emitted
    """
    events = extract_event_json(text)
    emitted = []
    
    for event_obj in events:
        try:
            event_name = event_obj.get('event')
            event_data = event_obj.get('data', {})
            
            # Add metadata about extraction source
            if agent_id:
                event_data['_agent_id'] = agent_id
            event_data['_extracted_from_response'] = True
            
            # Add any additional context
            if context:
                event_data.setdefault('_context', {}).update(context)
            
            # Create emission context for agent-originated events
            emission_context = None
            if agent_id:
                emission_context = {
                    '_agent_id': agent_id  # Presence of _agent_id is the signal for observation
                }
            
            # Emit the event with proper context
            emission_result = await event_emitter(event_name, event_data, emission_context)
            
            # Pass through raw emission result to agent
            emitted.append({
                'event': event_name,
                'data': event_data,
                'emission_result': emission_result  # Raw passthrough
            })
            
            logger.info(f"Emitted {event_name} extracted from response", 
                       agent_id=agent_id,
                       event_name=event_name)
                       
        except Exception as e:
            logger.error(f"Failed to emit extracted event: {e}", 
                        event_obj=event_obj,
                        error=str(e))
            emitted.append({
                'event': event_obj.get('event'),
                'error': str(e),
                'status': 'failed'
            })
    
    if emitted:
        logger.debug(f"Extracted and processed {len(emitted)} events from response")
    
    return emitted


def extract_json_with_schema(
    text: str, 
    schema: Dict[str, Any],
    strict: bool = False
) -> List[Dict[str, Any]]:
    """
    Extract JSON objects that match a specific schema.
    
    Args:
        text: Text to extract JSON from
        schema: Expected schema (simple dict with required fields)
        strict: If True, all schema fields must be present
        
    Returns:
        List of JSON objects matching the schema
    """
    def matches_schema(obj: Dict) -> bool:
        if not isinstance(obj, dict):
            return False
            
        for key, expected_type in schema.items():
            if key not in obj:
                if strict:
                    return False
                continue
                
            # Simple type checking
            if expected_type and not isinstance(obj[key], expected_type):
                return False
                
        return True
    
    return extract_json_objects(text, filter_func=matches_schema)


# Convenience function for backwards compatibility with existing patterns
def extract_json_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first JSON object from markdown code blocks.
    
    This matches the pattern used in llm_judge.py and other modules.
    
    Args:
        text: Text potentially containing JSON in markdown
        
    Returns:
        First JSON object found, or None
    """
    objects = extract_json_objects(text)
    return objects[0] if objects else None