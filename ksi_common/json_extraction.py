#!/usr/bin/env python3
"""
JSON Extraction Utilities

Extract JSON objects from text, particularly for parsing agent/LLM responses
that may contain embedded JSON for event emission.
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
import asyncio
from ksi_common.logging import get_bound_logger
from ksi_common.json_utils import JSONExtractor, JSONParseError

logger = get_bound_logger("json_extraction")


# Global extractor instance using enhanced balanced brace parsing
_extractor = JSONExtractor()

def extract_json_objects(text: str, filter_func: Optional[Callable[[Dict], bool]] = None) -> List[Dict[str, Any]]:
    """
    Extract all valid JSON objects from text using enhanced balanced brace parsing.
    
    This function now uses the improved JSONExtractor from json_utils.py that can handle
    deeply nested JSON objects using balanced brace parsing instead of regex patterns.
    
    Looks for JSON in various formats:
    - Code blocks: ```json ... ```
    - Plain JSON objects: {...} (with arbitrary nesting levels)
    - Multiple JSON objects in a single response
    
    Args:
        text: Text to extract JSON from
        filter_func: Optional filter to apply to extracted objects
        
    Returns:
        List of extracted JSON objects
    """
    try:
        return _extractor.extract_json_objects(text, filter_func=filter_func)
    except Exception as e:
        logger.error(f"Error during JSON extraction: {e}")
        return []


def _suggest_fix(json_str: str, error: json.JSONDecodeError) -> str:
    """Provide helpful suggestions for common JSON errors."""
    error_msg = str(error).lower()
    
    if 'expecting property name' in error_msg and "'" in json_str:
        return "Use double quotes for JSON strings, not single quotes"
    elif 'extra data' in error_msg:
        return "Multiple JSON objects found - ensure they're in an array or separate them"
    elif 'expecting value' in error_msg and json_str.rstrip().endswith(','):
        return "Remove trailing comma before closing brace/bracket"
    elif 'unterminated string' in error_msg:
        return "Check for missing closing quotes in strings"
    else:
        return "Ensure valid JSON syntax - use a JSON validator"


def extract_json_objects_with_errors(text: str, filter_func: Optional[Callable[[Dict], bool]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract valid JSON objects and collect parsing errors using enhanced balanced brace parsing.
    
    This function now uses the improved JSONExtractor from json_utils.py that can handle
    deeply nested JSON objects and provides better error reporting.
    
    Returns:
        Tuple of (valid_objects, errors)
        where errors contain pattern, error message, and suggested fixes
    """
    try:
        return _extractor.extract_json_objects_with_errors(text, filter_func=filter_func)
    except Exception as e:
        logger.error(f"Error during JSON extraction with errors: {e}")
        return [], [{'error': str(e), 'suggestion': 'Check JSON extraction system', 'location': 'system'}]


def extract_event_json(text: str) -> List[Dict[str, Any]]:
    """
    Extract JSON objects that look like event emissions using enhanced balanced brace parsing.
    
    Looks for JSON objects with an 'event' field, which indicates
    an intent to emit an event to the KSI system.
    
    Args:
        text: Text to extract event JSON from
        
    Returns:
        List of event JSON objects
    """
    try:
        return _extractor.extract_event_json(text)
    except Exception as e:
        logger.error(f"Error during event JSON extraction: {e}")
        return []


async def extract_and_emit_json_events(
    text: str, 
    event_emitter: Callable,
    context: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract JSON events from text and emit them asynchronously with error feedback.
    
    This is designed to be called from completion service to automatically
    emit events found in agent responses. Provides detailed feedback for malformed JSON.
    
    Args:
        text: Text containing potential JSON events
        event_emitter: Function to emit events (typically router.emit)
        context: Optional context to add to emitted events
        agent_id: Optional agent ID to track source
        
    Returns:
        List of events that were emitted
    """
    # Use enhanced extraction with error collection
    def is_event(obj: Dict) -> bool:
        return isinstance(obj, dict) and 'event' in obj
    
    valid_events, parse_errors = extract_json_objects_with_errors(text, filter_func=is_event)
    emitted = []
    
    # Process valid events
    for event_obj in valid_events:
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
            
            # Debug: Log what emission_result actually contains
            logger.debug(f"Emission result for {event_name}: type={type(emission_result)}, value={emission_result}")
            
            # Route event result back to originator if this agent has originator context
            if agent_id:
                try:
                    # Import the route_to_originator function
                    from ksi_daemon.agent.agent_service import route_to_originator
                    await route_to_originator(agent_id, event_name, emission_result)
                except Exception as route_error:
                    logger.debug(f"Failed to route event {event_name} to originator: {route_error}")
                    # Don't fail the whole process if routing fails
            
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
    
    # Handle parsing errors by providing feedback to the originating agent
    if parse_errors and agent_id:
        try:
            error_details = []
            for error in parse_errors:
                if error.get('suggestion'):
                    error_details.append(f"• {error['suggestion']} (Found: {error.get('json_str', 'pattern')})")
                else:
                    error_details.append(f"• JSON parsing error: {error.get('error', 'Unknown error')}")
            
            feedback_content = "=== JSON EXTRACTION FEEDBACK ===\n"
            if emitted:
                feedback_content += f"Successfully extracted {len(emitted)} valid JSON events\n\n"
            
            if error_details:
                feedback_content += f"Found {len(error_details)} malformed JSON patterns:\n"
                feedback_content += "\n".join(error_details) + "\n\n"
                feedback_content += "Correct format: {\"event\": \"namespace:action\", \"data\": {...}}"
                
                # Send error feedback back to the originating agent
                try:
                    await event_emitter("agent:json_extraction_error", {
                        'agent_id': agent_id,
                        'error_count': len(parse_errors),
                        'feedback': feedback_content,
                        'errors': parse_errors,
                        '_extracted_from_response': True,
                        '_context': context or {}
                    })
                    logger.info(f"Sent JSON extraction error feedback to agent {agent_id}")
                except Exception as feedback_error:
                    logger.error(f"Failed to send JSON extraction error feedback to agent {agent_id}: {feedback_error}")
                
                # Log the parsing errors
                logger.warning(f"JSON parsing errors in agent response", 
                             agent_id=agent_id, 
                             error_count=len(parse_errors))
                             
        except Exception as e:
            logger.error(f"Failed to generate JSON error feedback: {e}")
    
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