#!/usr/bin/env python3
"""
Enhanced JSON Extraction with Better Error Feedback

Provides detailed feedback for both successful and failed JSON extraction attempts,
helping agents understand and correct malformed JSON.
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
import asyncio
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("json_extraction_v2")


def extract_json_objects_with_errors(text: str, filter_func: Optional[Callable[[Dict], bool]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract valid JSON objects and collect parsing errors.
    
    Returns:
        Tuple of (valid_objects, errors)
        where errors contain pattern, error message, and attempted fix suggestions
    """
    extracted = []
    errors = []
    
    # Pattern 1: JSON in code blocks
    code_block_pattern = r'```(?:json)?\s*(\{[^`]+\})\s*```'
    for match in re.finditer(code_block_pattern, text, re.DOTALL):
        json_str = match.group(1)
        try:
            obj = json.loads(json_str)
            if not filter_func or filter_func(obj):
                extracted.append(obj)
        except json.JSONDecodeError as e:
            errors.append({
                'pattern': json_str[:100] + ('...' if len(json_str) > 100 else ''),
                'error': str(e),
                'location': 'code_block',
                'suggestion': _suggest_fix(json_str, e)
            })
    
    # Pattern 2: Standalone JSON objects
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    
    for match in re.finditer(json_pattern, text):
        json_str = match.group(0)
        # Skip if already found in code block
        if any(json_str in str(obj) for obj in extracted):
            continue
            
        try:
            obj = json.loads(json_str)
            if not filter_func or filter_func(obj):
                if obj not in extracted:
                    extracted.append(obj)
        except json.JSONDecodeError as e:
            # Try common fixes
            fixed = False
            
            # Fix 1: Remove trailing commas
            try:
                cleaned = re.sub(r',\s*([}\]])', r'\1', json_str)
                obj = json.loads(cleaned)
                if not filter_func or filter_func(obj):
                    if obj not in extracted:
                        extracted.append(obj)
                        fixed = True
            except:
                pass
            
            # Fix 2: Convert single quotes to double quotes
            if not fixed:
                try:
                    # Careful conversion - only quotes around keys/values
                    converted = re.sub(r"'([^']*)'", r'"\1"', json_str)
                    obj = json.loads(converted)
                    if not filter_func or filter_func(obj):
                        if obj not in extracted:
                            extracted.append(obj)
                            fixed = True
                except:
                    pass
            
            if not fixed:
                errors.append({
                    'pattern': json_str[:100] + ('...' if len(json_str) > 100 else ''),
                    'error': str(e),
                    'location': 'inline',
                    'suggestion': _suggest_fix(json_str, e)
                })
    
    return extracted, errors


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


async def extract_and_emit_json_events_v2(
    text: str, 
    event_emitter: Callable,
    context: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Enhanced extraction with detailed error feedback.
    
    Returns:
        Tuple of (successful_emissions, parsing_errors)
    """
    # First extract with error collection
    def is_event(obj: Dict) -> bool:
        return isinstance(obj, dict) and 'event' in obj
    
    valid_events, parse_errors = extract_json_objects_with_errors(text, filter_func=is_event)
    
    # Process valid events
    emitted = []
    for event_obj in valid_events:
        try:
            event_name = event_obj.get('event')
            event_data = event_obj.get('data', {})
            
            # Add metadata
            if agent_id:
                event_data['_agent_id'] = agent_id
            event_data['_extracted_from_response'] = True
            
            if context:
                event_data.setdefault('_context', {}).update(context)
            
            # Create emission context
            emission_context = None
            if agent_id:
                emission_context = {'_agent_id': agent_id}
            
            # Emit the event
            emission_result = await event_emitter(event_name, event_data, emission_context)
            
            emitted.append({
                'event': event_name,
                'data': event_data,
                'emission_result': emission_result,
                'status': 'success'
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
                'status': 'emission_failed',
                'raw_object': event_obj
            })
    
    # Log summary
    if emitted or parse_errors:
        logger.info(f"JSON extraction complete",
                   valid_count=len(emitted),
                   error_count=len(parse_errors),
                   agent_id=agent_id)
    
    return emitted, parse_errors


def format_extraction_feedback(emitted: List[Dict], parse_errors: List[Dict]) -> str:
    """Format comprehensive feedback for agents about extraction results."""
    feedback = "=== JSON EVENT EXTRACTION RESULTS ===\n\n"
    
    if emitted:
        feedback += f"✓ Successfully processed {len(emitted)} event(s):\n"
        feedback += json.dumps(emitted, indent=2)
        feedback += "\n\n"
    
    if parse_errors:
        feedback += f"⚠️ Failed to parse {len(parse_errors)} JSON pattern(s):\n\n"
        for i, error in enumerate(parse_errors, 1):
            feedback += f"{i}. Pattern: {error['pattern']}\n"
            feedback += f"   Error: {error['error']}\n"
            feedback += f"   Location: {error['location']}\n"
            feedback += f"   Suggestion: {error['suggestion']}\n\n"
        
        feedback += "Tips for valid JSON:\n"
        feedback += "- Use double quotes for strings: \"key\": \"value\"\n"
        feedback += "- No trailing commas: {\"a\": 1, \"b\": 2}\n"
        feedback += "- Proper event format: {\"event\": \"name\", \"data\": {...}}\n"
    
    if not emitted and not parse_errors:
        feedback += "No JSON event patterns detected in response.\n"
        feedback += "To emit events, include: {\"event\": \"event:name\", \"data\": {...}}\n"
    
    return feedback