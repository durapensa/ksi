#!/usr/bin/env python3
"""
Foreach Transformer Support

Enables transformers to emit to multiple targets by iterating over collections.
This is the key to replacing the orchestration system with pure routing patterns.
"""

from typing import Any, Dict, List, Optional, Union
import logging

from .template_utils import resolve_path

logger = logging.getLogger("foreach_transformer")


def extract_foreach_items(data: Dict[str, Any], foreach_path: str) -> List[Any]:
    """
    Extract items to iterate over from the data using a path expression.
    
    Args:
        data: The event data containing the collection
        foreach_path: Path to the collection (e.g., "data.agents", "team_members")
        
    Returns:
        List of items to iterate over, or empty list if not found
    """
    try:
        # Use template path extraction for consistency
        items = resolve_path(foreach_path, data)
        
        # Ensure we have a list
        if items is None:
            return []
        elif isinstance(items, list):
            return items
        elif isinstance(items, dict):
            # If it's a dict, iterate over values (common pattern)
            return list(items.values())
        else:
            # Single item - wrap in list
            return [items]
            
    except Exception as e:
        logger.warning(f"Failed to extract foreach items from path '{foreach_path}': {e}")
        return []


def prepare_foreach_context(
    item: Any,
    index: int,
    total: int,
    original_data: Dict[str, Any],
    original_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Prepare the context for a single foreach iteration.
    
    Args:
        item: The current item being processed
        index: The index of the current item (0-based)
        total: Total number of items in the collection
        original_data: The original event data
        original_context: The original transformer context
        
    Returns:
        Enhanced context for this iteration
    """
    # Create foreach-specific context
    foreach_context = {
        # Current item data
        "item": item,
        "index": index,
        "total": total,
        "is_first": index == 0,
        "is_last": index == total - 1,
        
        # Original data remains accessible
        "data": original_data,
        
        # Preserve original context
        **original_context
    }
    
    # If item is a dict, also make its fields directly accessible
    if isinstance(item, dict):
        # Add item fields with item_ prefix to avoid conflicts
        for key, value in item.items():
            foreach_context[f"item_{key}"] = value
    
    return foreach_context


def should_process_foreach_transformer(transformer: Dict[str, Any]) -> bool:
    """
    Check if a transformer should be processed as a foreach transformer.
    
    Args:
        transformer: The transformer configuration
        
    Returns:
        True if this is a foreach transformer
    """
    return 'foreach' in transformer and transformer.get('foreach')


async def process_foreach_transformer(
    transformer: Dict[str, Any],
    event: str,
    data: Dict[str, Any],
    context: Optional[Dict[str, Any]],
    emit_func,
    apply_mapping_func,
    prepare_context_func
) -> List[Any]:
    """
    Process a foreach transformer by iterating over items and emitting to target for each.
    
    Args:
        transformer: The transformer configuration with 'foreach' field
        event: The source event name
        data: The event data
        context: The event context
        emit_func: Function to emit events (async)
        apply_mapping_func: Function to apply mapping transformations
        prepare_context_func: Function to prepare transformer context
        
    Returns:
        List of results from all emissions
    """
    foreach_path = transformer.get('foreach', '')
    target = transformer.get('target')
    
    if not target:
        logger.error(f"Foreach transformer missing target for {event}")
        return []
    
    # Extract items to iterate over
    items = extract_foreach_items(data, foreach_path)
    
    if not items:
        logger.debug(f"No items found for foreach path '{foreach_path}' in {event}")
        return []
    
    logger.info(f"Processing foreach transformer: {event} -> {target} for {len(items)} items")
    
    results = []
    
    # Process each item
    for index, item in enumerate(items):
        try:
            # Prepare context with standardized structure
            prepared_data, ksi_context = prepare_context_func(event, data, context)
            
            # Enhance context with foreach-specific data
            foreach_context = prepare_foreach_context(
                item, index, len(items), 
                prepared_data, ksi_context
            )
            
            # Apply mapping with foreach context as the data
            transformed_data = apply_mapping_func(
                transformer.get('mapping', {}),
                foreach_context  # Pass foreach context as data for template substitution
            )
            
            # Check if we should skip this item (optional filter)
            if transformer.get('filter'):
                # TODO: Implement filter evaluation
                pass
            
            # Emit to target
            logger.debug(f"Foreach[{index}/{len(items)}]: Emitting {target} for item {index}")
            result = await emit_func(target, transformed_data, context)
            results.append(result)
            
        except Exception as e:
            logger.error(f"Foreach transformer failed for item {index} in {event} -> {target}: {e}")
            # Continue processing other items
            continue
    
    logger.info(f"Foreach transformer completed: {event} -> {target}, processed {len(results)}/{len(items)} items")
    
    return results


# Helper function to check if any transformer in a list is a foreach transformer
def has_foreach_transformers(transformers: List[Dict[str, Any]]) -> bool:
    """Check if any transformer in the list is a foreach transformer."""
    return any(should_process_foreach_transformer(t) for t in transformers)


# Configuration for foreach transformers
FOREACH_CONFIG = {
    # Maximum items to process in a single foreach (safety limit)
    "max_items": 1000,
    
    # Whether to process foreach items in parallel (future enhancement)
    "parallel_processing": False,
    
    # Whether to stop on first error or continue
    "continue_on_error": True,
}


def validate_foreach_transformer(transformer: Dict[str, Any]) -> Optional[str]:
    """
    Validate a foreach transformer configuration.
    
    Returns:
        None if valid, error message if invalid
    """
    if not transformer.get('foreach'):
        return "Foreach transformer missing 'foreach' field"
    
    if not transformer.get('target'):
        return "Foreach transformer missing 'target' field"
    
    # Validate foreach path doesn't contain dangerous patterns
    foreach_path = transformer['foreach']
    if '..' in foreach_path or foreach_path.startswith('/'):
        return f"Invalid foreach path: {foreach_path}"
    
    return None