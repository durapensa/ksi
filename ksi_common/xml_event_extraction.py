#!/usr/bin/env python3
"""
XML Event Extraction for KSI Tool Use Pattern

Extracts KSI events from XML-formatted tool use blocks, providing a more
reliable alternative to direct JSON emission.
"""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("xml_event_extraction")


def extract_xml_events(text: str) -> List[Dict[str, Any]]:
    """
    Extract KSI events from XML-formatted tool use blocks.
    
    Looks for patterns like:
    <ksi:emit>
      <ksi:event>namespace:action</ksi:event>
      <ksi:data>
        <field>value</field>
      </ksi:data>
    </ksi:emit>
    
    Args:
        text: Text containing XML-formatted events
        
    Returns:
        List of extracted event dictionaries
    """
    events = []
    
    # Find all ksi:emit blocks
    # Using a more flexible pattern that handles whitespace and newlines
    pattern = r'<ksi:emit>\s*(.+?)\s*</ksi:emit>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        try:
            # Wrap in a root element with namespace declaration for parsing
            xml_content = f'<root xmlns:ksi="http://ksi.local">{match}</root>'
            root = ET.fromstring(xml_content)
            
            # Define namespace
            ns = {'ksi': 'http://ksi.local'}
            
            # Extract event name
            event_elem = root.find('.//ksi:event', ns)
            if event_elem is None:
                # Try without namespace
                event_elem = root.find('.//event')
            
            if event_elem is None or not event_elem.text:
                logger.warning("No event name found in ksi:emit block")
                continue
                
            event_name = event_elem.text.strip()
            
            # Extract data
            data_elem = root.find('.//ksi:data', ns)
            if data_elem is None:
                # Try without namespace
                data_elem = root.find('.//data')
            
            event_data = {}
            if data_elem is not None:
                event_data = _parse_xml_data(data_elem)
            
            events.append({
                'event': event_name,
                'data': event_data
            })
            
            logger.debug(f"Extracted XML event: {event_name}")
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML event: {e}")
        except Exception as e:
            logger.error(f"Error extracting XML event: {e}")
    
    return events


def _parse_xml_data(element: ET.Element) -> Dict[str, Any]:
    """
    Parse XML element into a dictionary.
    
    Handles nested structures and converts to appropriate Python types.
    
    Args:
        element: XML element to parse
        
    Returns:
        Dictionary representation of the XML data
    """
    result = {}
    
    # Process all child elements
    for child in element:
        # Remove namespace if present
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        # Check if this element has children
        if len(child) > 0:
            # Nested structure
            result[tag] = _parse_xml_data(child)
        else:
            # Leaf node with text content
            if child.text:
                # Try to convert to appropriate type
                value = child.text.strip()
                
                # Try boolean
                if value.lower() in ('true', 'false'):
                    result[tag] = value.lower() == 'true'
                # Try integer
                elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                    result[tag] = int(value)
                # Try float
                elif _is_float(value):
                    result[tag] = float(value)
                else:
                    # Keep as string
                    result[tag] = value
            else:
                result[tag] = None
    
    return result


def _is_float(value: str) -> bool:
    """
    Check if a string can be converted to float.
    
    Args:
        value: String to check
        
    Returns:
        True if string represents a float
    """
    try:
        float(value)
        return '.' in value  # Only treat as float if it has decimal point
    except ValueError:
        return False


def extract_xml_events_with_errors(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract XML events and collect parsing errors.
    
    Returns:
        Tuple of (valid_events, errors)
    """
    valid_events = []
    errors = []
    
    # Find all potential ksi:emit blocks including malformed ones
    # First try to find properly formatted blocks
    valid_events = extract_xml_events(text)
    
    # Look for common XML formatting errors
    # Missing closing tags
    incomplete_pattern = r'<ksi:emit>(?:(?!</ksi:emit>).)*$'
    if re.search(incomplete_pattern, text, re.DOTALL):
        errors.append({
            'error': 'Unclosed <ksi:emit> tag',
            'suggestion': 'Ensure all <ksi:emit> tags have matching </ksi:emit> closing tags'
        })
    
    # Malformed event names
    malformed_event = r'<ksi:event>\s*[^:]+\s*</ksi:event>'
    if re.search(malformed_event, text):
        errors.append({
            'error': 'Invalid event name format',
            'suggestion': 'Event names should use namespace:action format (e.g., agent:status)'
        })
    
    return valid_events, errors


async def extract_and_emit_xml_events(
    text: str,
    event_emitter,
    context: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract XML events from text and emit them.
    
    Similar to extract_and_emit_json_events but for XML format.
    
    Args:
        text: Text containing XML events
        event_emitter: Function to emit events
        context: Optional context to add to events
        agent_id: Optional agent ID to track source
        
    Returns:
        List of events that were emitted
    """
    valid_events, errors = extract_xml_events_with_errors(text)
    emitted = []
    
    # Process valid events
    for event_obj in valid_events:
        try:
            event_name = event_obj['event']
            event_data = event_obj.get('data', {})
            
            # Add metadata about extraction source
            if agent_id:
                event_data['_agent_id'] = agent_id
            event_data['_extracted_from_xml'] = True
            
            # Add context if provided
            if context:
                # Propagate orchestration metadata
                for key in ['_orchestration_id', '_orchestration_depth', '_parent_agent_id', '_root_orchestration_id']:
                    if key in context:
                        event_data[key] = context[key]
            
            # Emit the event
            emission_result = await event_emitter(event_name, event_data, {'_agent_id': agent_id} if agent_id else None)
            
            emitted.append({
                'event': event_name,
                'data': event_data,
                'emission_result': emission_result
            })
            
            logger.info(f"Emitted {event_name} extracted from XML", agent_id=agent_id)
            
        except Exception as e:
            logger.error(f"Failed to emit XML event: {e}", event_obj=event_obj)
            emitted.append({
                'event': event_obj.get('event'),
                'error': str(e),
                'status': 'failed'
            })
    
    # Send error feedback if needed
    if errors and agent_id:
        try:
            error_details = [f"• {err['suggestion']}" for err in errors if 'suggestion' in err]
            
            if error_details:
                feedback_content = "=== XML EVENT EXTRACTION FEEDBACK ===\n"
                if emitted:
                    feedback_content += f"Successfully extracted {len(emitted)} valid XML events\n\n"
                
                feedback_content += f"Found {len(errors)} XML formatting issues:\n"
                feedback_content += "\n".join(error_details)
                
                await event_emitter("agent:xml_extraction_error", {
                    'agent_id': agent_id,
                    'error_count': len(errors),
                    'feedback': feedback_content,
                    'errors': errors
                })
                
                logger.info(f"Sent XML extraction error feedback to agent {agent_id}")
                
        except Exception as e:
            logger.error(f"Failed to send XML error feedback: {e}")
    
    return emitted