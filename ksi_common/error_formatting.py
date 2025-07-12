#!/usr/bin/env python3
"""
Error Formatting Utilities

Simple utilities for formatting enhanced error messages in different contexts.
"""

from typing import Dict, Any, List, Optional


def format_error_for_cli(error_data: Dict[str, Any]) -> str:
    """
    Format enhanced error data for CLI display.
    
    Args:
        error_data: Enhanced error dict from error_handler functions
        
    Returns:
        Formatted error string for CLI output
    """
    lines = [error_data["error"]]
    
    # Handle unknown events with special formatting
    if "namespaces" in error_data or ("similar" in error_data and error_data["error"].startswith("Unknown event:")):
        lines.append("")  # Empty line for readability
        
        # Add similar events with friendly formatting
        if "similar" in error_data:
            similar = error_data["similar"]
            if similar:
                if len(similar) == 1:
                    lines.append(f"Did you mean: {similar[0]}?")
                else:
                    lines.append(f"Did you mean: {', '.join(similar)}?")
                lines.append("")  # Empty line
        
        # Add namespaces with guidance
        if "namespaces" in error_data:
            namespaces = error_data["namespaces"]
            if namespaces:
                lines.append(f"Available namespaces: {', '.join(namespaces)}")
                
                # Extract namespace from original event for targeted help
                original_event = error_data["error"].split(": ")[-1] if ": " in error_data["error"] else ""
                if ":" in original_event:
                    namespace = original_event.split(":")[0]
                    if namespace in namespaces:
                        lines.append(f"Use 'ksi discover --namespace {namespace}' for {namespace} events")
    else:
        # Handle other error types (missing parameters, etc.)
        
        # Add available parameters if present
        if "available" in error_data:
            available = error_data["available"]
            if available:
                lines.append(f"Available parameters: {', '.join(available)}")
        
        # Add similar events if present  
        if "similar" in error_data:
            similar = error_data["similar"]
            if similar:
                lines.append(f"Similar events: {', '.join(similar)}")
    
    # Add help suggestion if present
    if "help" in error_data:
        lines.append(error_data["help"])
        
    return "\n".join(lines)


def format_error_for_json(error_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format enhanced error data for JSON API responses.
    
    Args:
        error_data: Enhanced error dict from error_handler functions
        
    Returns:
        Clean JSON-serializable error response
    """
    # Just return the error_data as-is since it's already structured
    return error_data


def format_parameter_suggestion(param_name: str, param_info: Dict[str, Any]) -> str:
    """
    Format a parameter suggestion with type and description.
    
    Args:
        param_name: Parameter name
        param_info: Parameter information from discovery
        
    Returns:
        Formatted parameter suggestion
    """
    param_type = param_info.get("type", "unknown")
    required = param_info.get("required", False)
    description = param_info.get("description", "")
    
    parts = [f"--{param_name}: {param_type}"]
    
    if required:
        parts.append("(required)")
    else:
        parts.append("(optional)")
        
    if description:
        parts.append(f"- {description}")
        
    return " ".join(parts)


def extract_parameter_from_error(error_str: str) -> Optional[str]:
    """
    Extract parameter name from common error patterns.
    
    Args:
        error_str: Error message string
        
    Returns:
        Parameter name if found, None otherwise
    """
    import re
    
    # Missing parameter pattern
    match = re.search(r"Missing required parameter: (\w+)", error_str)
    if match:
        return match.group(1)
        
    # Type mismatch pattern
    match = re.search(r"Parameter '(\w+)' expected", error_str)
    if match:
        return match.group(1)
        
    return None


def suggest_parameter_fixes(
    provided_params: Dict[str, Any], 
    available_params: List[str]
) -> List[str]:
    """
    Suggest parameter fixes based on what was provided vs what's available.
    
    Args:
        provided_params: Parameters that were provided
        available_params: Available parameters from discovery
        
    Returns:
        List of suggestion strings
    """
    suggestions = []
    
    # Find typos in provided parameters
    from difflib import get_close_matches
    
    for provided_param in provided_params.keys():
        if provided_param not in available_params:
            matches = get_close_matches(provided_param, available_params, n=1, cutoff=0.6)
            if matches:
                suggestions.append(f"Did you mean '--{matches[0]}' instead of '--{provided_param}'?")
    
    # Suggest missing required parameters
    # (This would need access to which parameters are required)
    
    return suggestions


def format_constraint_violation(
    param_name: str, 
    constraint_type: str, 
    constraint_value: Any,
    provided_value: Any
) -> str:
    """
    Format constraint violation messages.
    
    Args:
        param_name: Parameter that violated constraint
        constraint_type: Type of constraint (allowed_values, min_length, etc.)
        constraint_value: The constraint specification
        provided_value: What was actually provided
        
    Returns:
        Formatted constraint violation message
    """
    if constraint_type == "allowed_values":
        return f"Parameter '{param_name}' must be one of: {', '.join(constraint_value)}"
    elif constraint_type == "min_length":
        return f"Parameter '{param_name}' must be at least {constraint_value} characters"
    elif constraint_type == "max_length":
        return f"Parameter '{param_name}' must be no more than {constraint_value} characters"
    elif constraint_type == "range":
        min_val, max_val = constraint_value
        return f"Parameter '{param_name}' must be between {min_val} and {max_val}"
    else:
        return f"Parameter '{param_name}' violates constraint: {constraint_type}"