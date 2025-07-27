"""
KSI Tool Use Adapter

Converts ksi_tool_use format to standard KSI events.
"""

import json
import re
from typing import Dict, List, Optional, Tuple


def is_ksi_tool_use(data: dict) -> bool:
    """Check if a JSON object is in ksi_tool_use format."""
    return (
        isinstance(data, dict) and
        data.get("type") == "ksi_tool_use" and
        "id" in data and
        "name" in data and
        "input" in data
    )


def convert_ksi_tool_use_to_event(tool_use_block: dict) -> dict:
    """
    Convert ksi_tool_use format to standard KSI event.
    
    Args:
        tool_use_block: Dict with structure:
            {
                "type": "ksi_tool_use",
                "id": "ksiu_...",
                "name": "event_name",
                "input": {...}
            }
    
    Returns:
        Standard KSI event dict:
            {
                "event": "event_name",
                "data": {...},
                "_tool_use_id": "ksiu_...",
                "_extracted_via": "ksi_tool_use"
            }
    """
    return {
        "event": tool_use_block["name"],
        "data": tool_use_block["input"],
        "_tool_use_id": tool_use_block["id"],
        "_extracted_via": "ksi_tool_use"
    }


def extract_ksi_events(text: str) -> List[Tuple[dict, str]]:
    """
    Extract both legacy and tool-use format KSI events from text.
    
    This is the main 2-path extraction function that handles:
    1. Legacy format: {"event": "...", "data": {...}}
    2. Tool use format: {"type": "ksi_tool_use", ...}
    
    Args:
        text: Text potentially containing JSON events
        
    Returns:
        List of tuples (event_dict, format_type) where format_type is "legacy" or "tool_use"
    """
    events = []
    
    # Use balanced brace approach for multiline JSON
    i = 0
    while i < len(text):
        if text[i] == '{':
            start = i
            brace_count = 0
            while i < len(text):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start:i+1]
                        try:
                            data = json.loads(json_str)
                            
                            # Path 2: Tool use format (check first)
                            if is_ksi_tool_use(data):
                                event = convert_ksi_tool_use_to_event(data)
                                events.append((event, "tool_use"))
                            
                            # Path 1: Legacy format
                            elif isinstance(data, dict) and "event" in data and "data" in data:
                                events.append((data, "legacy"))
                                
                        except json.JSONDecodeError:
                            # Skip malformed JSON
                            pass
                        break
                i += 1
        i += 1
    
    return events


def extract_tool_use_blocks(text: str) -> List[dict]:
    """
    Extract only ksi_tool_use blocks from text.
    
    Args:
        text: Text potentially containing ksi_tool_use blocks
        
    Returns:
        List of ksi_tool_use dictionaries
    """
    blocks = []
    
    # More specific pattern for tool use blocks
    pattern = r'\{\s*"type"\s*:\s*"ksi_tool_use"[^}]+\}'
    
    for match in re.finditer(pattern, text, re.DOTALL):
        try:
            # Ensure we capture the complete JSON object
            start = match.start()
            brace_count = 0
            i = start
            
            while i < len(text):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start:i+1]
                        data = json.loads(json_str)
                        if is_ksi_tool_use(data):
                            blocks.append(data)
                        break
                i += 1
                
        except (json.JSONDecodeError, IndexError):
            continue
    
    return blocks


def validate_event_data(event_name: str, data: dict) -> Tuple[bool, Optional[str]]:
    """
    Basic validation of event data structure.
    
    Args:
        event_name: Name of the KSI event
        data: Event data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Add event-specific validation rules here
    common_validations = {
        "composition:create_component": ["name", "content"],
        "agent:status": ["agent_id", "status"],
        "state:entity:create": ["type", "id"],
        "message:send": ["to", "message"],
    }
    
    if event_name in common_validations:
        required_fields = common_validations[event_name]
        missing = [field for field in required_fields if field not in data]
        
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
    
    return True, None


# Example usage functions for agents
def format_ksi_tool_use(event_name: str, data: dict, id_suffix: Optional[str] = None) -> str:
    """
    Helper to format a ksi_tool_use block.
    
    Args:
        event_name: KSI event name
        data: Event data
        id_suffix: Optional suffix for ID generation
        
    Returns:
        JSON string in ksi_tool_use format
    """
    import time
    
    if id_suffix is None:
        id_suffix = str(int(time.time() * 1000))[-6:]
    
    tool_use = {
        "type": "ksi_tool_use",
        "id": f"ksiu_{id_suffix}",
        "name": event_name,
        "input": data
    }
    
    return json.dumps(tool_use, indent=2)