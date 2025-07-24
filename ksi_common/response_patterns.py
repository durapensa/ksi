#!/usr/bin/env python3
"""
Response Patterns - Shared utilities for standardized response building.

Eliminates repetitive response patterns across KSI services:
- Validation error responses
- Service ready responses  
- Entity not found responses
- List responses with counts
- Success/error patterns
"""

from typing import Dict, Any, List, Optional, Union
from ksi_common.event_response_builder import (
    event_response_builder, 
    error_response, 
    success_response,
    list_response
)

def validate_required_fields(
    data: Dict[str, Any], 
    required: List[str], 
    context: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Validate required fields are present, return error response if not.
    
    Args:
        data: Data dictionary to validate
        required: List of required field names
        context: Optional context for error response
        
    Returns:
        Error response if fields missing, None if all present
        
    Example:
        error = validate_required_fields(data, ["agent_id", "prompt"])
        if error:
            return error
    """
    missing = [field for field in required if not data.get(field)]
    if missing:
        return error_response(f"{', '.join(missing)} required", context)
    return None

def validate_one_of_fields(
    data: Dict[str, Any],
    field_groups: List[List[str]],
    context: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Validate that at least one field from each group is present.
    
    Args:
        data: Data dictionary to validate
        field_groups: List of field groups (at least one from each group required)
        context: Optional context for error response
        
    Returns:
        Error response if validation fails, None if valid
        
    Example:
        error = validate_one_of_fields(data, [["id", "name"], ["profile", "component"]])
        if error:
            return error
    """
    for group in field_groups:
        if not any(data.get(field) for field in group):
            return error_response(f"One of {', '.join(group)} required", context)
    return None

def service_ready_response(
    service_name: str, 
    context: Optional[Dict[str, Any]] = None, 
    **extra_fields
) -> Dict[str, Any]:
    """
    Build a standardized service ready response.
    
    Args:
        service_name: Name of the service (e.g., "agent_service")
        context: Optional KSI context
        **extra_fields: Additional fields to include in response
        
    Returns:
        Standardized ready response
        
    Example:
        return service_ready_response("agent_service", context, agents_loaded=5)
    """
    response_data = {"status": f"{service_name}_ready"}
    response_data.update(extra_fields)
    return event_response_builder(response_data, context)

def entity_not_found_response(
    entity_type: str, 
    entity_id: str, 
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a standardized entity not found response.
    
    Args:
        entity_type: Type of entity (e.g., "agent", "composition")
        entity_id: ID of the missing entity
        context: Optional KSI context
        
    Returns:
        Standardized not found error response
        
    Example:
        return entity_not_found_response("agent", agent_id, context)
    """
    return error_response(f"{entity_type.capitalize()} {entity_id} not found", context)

def validation_error_response(
    errors: Union[str, List[str]], 
    warnings: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    field_errors: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Build a standardized validation error response.
    
    Args:
        errors: Single error or list of errors
        warnings: Optional list of warnings
        context: Optional KSI context
        field_errors: Optional dict of field-specific errors
        
    Returns:
        Standardized validation error response
        
    Example:
        return validation_error_response(
            ["Invalid format", "Missing required field"],
            warnings=["Deprecated field used"],
            field_errors={"email": "Invalid email format"}
        )
    """
    if isinstance(errors, str):
        errors = [errors]
    
    response_data = {
        "status": "validation_failed",
        "errors": errors,
        "error_count": len(errors)
    }
    
    if warnings:
        response_data["warnings"] = warnings
        response_data["warning_count"] = len(warnings)
        
    if field_errors:
        response_data["field_errors"] = field_errors
        
    return event_response_builder(response_data, context)

def operation_result_response(
    operation: str,
    status: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    Build a standardized operation result response.
    
    Args:
        operation: Operation performed (e.g., "create", "update", "delete")
        status: Status of operation (e.g., "success", "failed", "partial")
        entity_type: Optional entity type operated on
        entity_id: Optional entity ID
        context: Optional KSI context
        **extra_fields: Additional result fields
        
    Returns:
        Standardized operation response
        
    Example:
        return operation_result_response(
            "update", "success", "agent", agent_id,
            context, fields_updated=["profile", "capabilities"]
        )
    """
    response_data = {
        "operation": operation,
        "status": status
    }
    
    if entity_type:
        response_data["entity_type"] = entity_type
    if entity_id:
        response_data["entity_id"] = entity_id
        
    response_data.update(extra_fields)
    return event_response_builder(response_data, context)

def list_with_metadata_response(
    items: List[Any],
    total_count: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    items_field: str = "items",
    **extra_fields
) -> Dict[str, Any]:
    """
    Build a list response with pagination metadata.
    
    Args:
        items: List of items to return
        total_count: Total count (if different from items length)
        page: Current page number (1-based)
        page_size: Items per page
        context: Optional KSI context
        items_field: Field name for items (default: "items")
        **extra_fields: Additional metadata fields
        
    Returns:
        List response with metadata
        
    Example:
        return list_with_metadata_response(
            agents[:10], total_count=50, page=1, page_size=10,
            context, items_field="agents", filtered_by="active"
        )
    """
    response_data = {
        items_field: items,
        "count": len(items)
    }
    
    if total_count is not None:
        response_data["total_count"] = total_count
        
    if page is not None and page_size is not None:
        response_data["page"] = page
        response_data["page_size"] = page_size
        response_data["total_pages"] = (
            (total_count or len(items) + page_size - 1) // page_size
        )
        
    response_data.update(extra_fields)
    return list_response(items, context, count_field="count", items_field=items_field)

def batch_operation_response(
    succeeded: List[str],
    failed: List[str],
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    errors: Optional[Dict[str, str]] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    Build a response for batch operations with success/failure counts.
    
    Args:
        succeeded: List of successful entity IDs
        failed: List of failed entity IDs
        operation: Operation performed (e.g., "delete", "update")
        context: Optional KSI context
        errors: Optional dict mapping failed IDs to error messages
        **extra_fields: Additional result fields
        
    Returns:
        Batch operation response
        
    Example:
        return batch_operation_response(
            ["agent1", "agent2"], ["agent3"],
            "terminate", context,
            errors={"agent3": "Permission denied"}
        )
    """
    response_data = {
        "operation": operation,
        "succeeded": succeeded,
        "failed": failed,
        "success_count": len(succeeded),
        "failure_count": len(failed),
        "total_count": len(succeeded) + len(failed),
        "status": "partial" if failed else "success"
    }
    
    if errors:
        response_data["errors"] = errors
        
    response_data.update(extra_fields)
    return event_response_builder(response_data, context)

class ServiceResponseBuilder:
    """
    Service-specific response builder for consistent responses.
    
    Example:
        responses = ServiceResponseBuilder("agent_service")
        return responses.ready(context, agents_loaded=5)
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        
    def ready(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Build service ready response."""
        return service_ready_response(self.service_name, context, **kwargs)
    
    def not_found(self, entity_type: str, entity_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build entity not found response."""
        return entity_not_found_response(entity_type, entity_id, context)
    
    def validation_error(self, errors: Union[str, List[str]], context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Build validation error response."""
        return validation_error_response(errors, context=context, **kwargs)
    
    def operation_result(self, operation: str, status: str, entity_id: Optional[str] = None, 
                        context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Build operation result response."""
        return operation_result_response(operation, status, self.service_name.replace("_service", ""), 
                                       entity_id, context, **kwargs)

# Export convenience instances for common services
agent_responses = ServiceResponseBuilder("agent_service")
composition_responses = ServiceResponseBuilder("composition_service")
orchestration_responses = ServiceResponseBuilder("orchestration_service")
state_responses = ServiceResponseBuilder("state_service")