#!/usr/bin/env python3
"""Data extraction service for converting state entities to various formats."""

import json
import csv
import io
from typing import Dict, List, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import event_response_builder
from ksi_daemon.core.state import get_state_manager


@event_handler("data:extract")
def handle_data_extract(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract state entities and format as requested.
    
    Extraction spec format:
    {
        "entity_type": "phase_measurement",
        "filters": {"parameter": "communication"},  # optional
        "fields": ["field1", "field2"],  # optional, defaults to all
        "output_format": "csv",  # or "json", "jsonl"
        "limit": 100  # optional
    }
    """
    spec = data.get("extraction_spec", {})
    
    # Handle case where extraction_spec is passed as JSON string
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError:
            return event_response_builder.error_response("Invalid JSON in extraction_spec")
    
    # Validate spec
    if not spec.get("entity_type"):
        return event_response_builder.error_response("entity_type is required in extraction_spec")
    
    # Get state manager
    try:
        state_manager = get_state_manager()
    except RuntimeError:
        return event_response_builder.error_response("State manager not available")
    
    # Query entities - note: query_entities is async, so we need to handle it
    import asyncio
    
    entity_type = spec["entity_type"]
    limit = spec.get("limit", 100)
    where = spec.get("filters")
    
    # Execute query
    loop = asyncio.new_event_loop()
    try:
        entities = loop.run_until_complete(
            state_manager.query_entities(entity_type=entity_type, where=where, limit=limit)
        )
        result = {"status": "success", "entities": entities}
    except Exception as e:
        result = {"status": "error", "error": str(e)}
    finally:
        loop.close()
    
    if result["status"] != "success":
        return event_response_builder.error_response(f"Failed to query entities: {result.get('error', 'Unknown error')}")
    
    entities = result.get("entities", [])
    
    # Extract specified fields or all properties
    fields = spec.get("fields")
    output_format = spec.get("output_format", "json")
    
    # Format data
    if output_format == "csv":
        formatted_data = format_as_csv(entities, fields)
    elif output_format == "jsonl":
        formatted_data = format_as_jsonl(entities, fields)
    else:  # Default to json
        formatted_data = format_as_json(entities, fields)
    
    return {
        "status": "success",
        "extraction_spec": spec,
        "record_count": len(entities),
        "output_format": output_format,
        "data": formatted_data,
        "metadata": {
            "entity_type": spec["entity_type"],
            "fields_extracted": fields or "all"
        }
    }


def format_as_csv(entities: List[Dict], fields: Optional[List[str]] = None) -> str:
    """Convert entities to CSV format."""
    if not entities:
        return ""
    
    # Determine fields to include
    if not fields:
        # Get all unique fields from all entities
        all_fields = set()
        for entity in entities:
            props = entity.get("properties", {})
            all_fields.update(props.keys())
        fields = ["entity_id", "created_at"] + sorted(list(all_fields))
    else:
        # When specific fields requested, still include entity_id and created_at
        if "entity_id" not in fields:
            fields = ["entity_id"] + fields
        if "created_at" not in fields:
            fields = ["entity_id", "created_at"] + fields[1:]
    
    # Create CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    
    for entity in entities:
        row = {}
        props = entity.get("properties", {})
        for field in fields:
            if field == "entity_id":
                row[field] = entity.get("entity_id", "")
            elif field == "created_at":
                row[field] = entity.get("created_at", "")
            elif field in props:
                value = props[field]
                # Handle nested structures
                if isinstance(value, (dict, list)):
                    row[field] = json.dumps(value)
                else:
                    row[field] = value
            else:
                row[field] = ""
        writer.writerow(row)
    
    return output.getvalue()


def format_as_jsonl(entities: List[Dict], fields: Optional[List[str]] = None) -> str:
    """Convert entities to JSONL format."""
    lines = []
    for entity in entities:
        if fields:
            filtered = {
                "entity_id": entity.get("entity_id"),
                "created_at": entity.get("created_at")
            }
            props = entity.get("properties", {})
            for field in fields:
                if field in props:
                    filtered[field] = props[field]
            lines.append(json.dumps(filtered))
        else:
            lines.append(json.dumps(entity))
    return "\n".join(lines)


def format_as_json(entities: List[Dict], fields: Optional[List[str]] = None) -> List[Dict]:
    """Convert entities to JSON format (already dict, just filter fields)."""
    if not fields:
        return entities
    
    filtered_entities = []
    for entity in entities:
        filtered = {
            "entity_id": entity.get("entity_id"),
            "created_at": entity.get("created_at")
        }
        props = entity.get("properties", {})
        for field in fields:
            if field in props:
                filtered[field] = props[field]
        filtered_entities.append(filtered)
    
    return filtered_entities