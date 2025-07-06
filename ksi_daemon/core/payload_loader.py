#!/usr/bin/env python3
"""
Payload Loader - Load full event payloads from file storage.

Handles loading of large payloads that are stored in files rather than
inline in the event log. Currently supports completion responses with
plans to extend to other event types.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import aiofiles

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

logger = get_bound_logger("payload_loader")


async def load_event_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load full payload for an event if it was stored in a file.
    
    For events with stripped payloads, this function loads the full
    data from file storage and merges it with the event metadata.
    
    Args:
        event: Event dict from event log (may have stripped payloads)
        
    Returns:
        Event dict with full payloads loaded from files where applicable
    """
    event_name = event.get("event_name", "")
    event_data = event.get("data", {})
    
    # Handle completion responses
    if event_name in ["completion:response", "completion:result", "completion:complete"]:
        session_id = event_data.get("session_id")
        if session_id and _is_stripped(event_data.get("response")):
            # Load from response file
            full_response = await _load_completion_response(session_id)
            if full_response:
                # Merge full response data
                enriched_event = event.copy()
                enriched_event["data"] = {**event_data, **full_response}
                return enriched_event
    
    # Handle file read events
    elif event_name == "file:read":
        file_path = event_data.get("file_path")
        content = event_data.get("content")
        if file_path and _is_stripped(content):
            # For now, we can't reload file content as it may have changed
            # In future, we could store snapshots
            logger.debug(f"File content was stripped for {file_path}")
    
    # Handle agent spawn events with system prompts
    elif event_name == "agent:spawn":
        # Future: Load composed prompts from agent profile storage
        pass
    
    # Return original event if no file loading needed
    return event


async def _load_completion_response(session_id: str) -> Optional[Dict[str, Any]]:
    """Load completion response from session file."""
    response_file = config.responses_dir / f"{session_id}.jsonl"
    
    if not response_file.exists():
        logger.warning(f"Response file not found: {response_file}")
        return None
    
    try:
        # Read the last line (most recent response for session)
        async with aiofiles.open(response_file, 'r') as f:
            lines = await f.readlines()
            if lines:
                # Parse the last complete response
                last_line = lines[-1].strip()
                if last_line:
                    data = json.loads(last_line)
                    logger.debug(f"Loaded completion response from {response_file}")
                    return data
    except Exception as e:
        logger.error(f"Failed to load response file {response_file}: {e}")
    
    return None


def _is_stripped(value: Any) -> bool:
    """Check if a value was stripped by the event log."""
    if isinstance(value, str):
        return value.startswith("<stripped:") and value.endswith(">")
    return False


async def enrich_events_with_payloads(events: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Enrich a list of events by loading their file-based payloads.
    
    Args:
        events: List of events from event log
        
    Returns:
        List of events with full payloads loaded where applicable
    """
    enriched = []
    for event in events:
        enriched_event = await load_event_payload(event)
        enriched.append(enriched_event)
    return enriched