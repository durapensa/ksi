#!/usr/bin/env python3
"""
Discovery-Powered Error Handler

Enhances event system error messages using discovery data to provide
actionable guidance when events fail.
"""

import re
from typing import Dict, Any, List, Optional
from difflib import get_close_matches

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("error_handler")


class DiscoveryErrorHandler:
    """
    Enhances error messages using discovery system data.
    
    Provides configurable verbosity levels:
    - minimal: Enhanced error message only
    - medium: Add available parameters or suggestions  
    - verbose: Include full event help and examples
    """
    
    def __init__(self, router=None):
        """Initialize with event router for discovery access."""
        self.router = router
        
    async def enhance_error(
        self, 
        event_name: str, 
        provided_params: Dict[str, Any], 
        original_error: Exception,
        verbosity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Enhance an error with discovery-powered guidance.
        
        Args:
            event_name: The event that failed
            provided_params: Parameters that were provided
            original_error: The original exception
            verbosity: Error detail level (minimal, medium, verbose)
            
        Returns:
            Enhanced error dict with suggestions and guidance
        """
        error_str = str(original_error)
        
        # Classify the error type
        error_type = self._classify_error(error_str)
        
        # Get event information from discovery if available
        event_info = await self._get_event_info(event_name)
        
        # Generate enhanced error based on type and verbosity
        if error_type == "missing_parameter":
            return await self._handle_missing_parameter(
                event_name, provided_params, error_str, event_info, verbosity
            )
        elif error_type == "type_mismatch":
            return await self._handle_type_mismatch(
                event_name, provided_params, error_str, event_info, verbosity
            )
        elif error_type == "unknown_event":
            return await self._handle_unknown_event(
                event_name, provided_params, error_str, verbosity
            )
        else:
            # Generic enhancement
            return await self._handle_generic_error(
                event_name, provided_params, error_str, event_info, verbosity
            )
    
    def _classify_error(self, error_str: str) -> str:
        """Classify the error type based on error message patterns."""
        if "Missing required parameter" in error_str:
            return "missing_parameter"
        elif error_str.startswith("'") and error_str.endswith("'"):
            # KeyError pattern: 'parameter_name'
            return "missing_parameter"
        elif "expected" in error_str and "got" in error_str:
            return "type_mismatch"
        elif "Event not found" in error_str or "Unknown event" in error_str:
            return "unknown_event"
        elif "must be one of" in error_str:
            return "invalid_value"
        else:
            return "generic"
    
    async def _get_event_info(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Get event information from discovery system."""
        if not self.router or event_name not in self.router._handlers:
            return None
            
        try:
            from ksi_daemon.core.discovery import UnifiedHandlerAnalyzer, extract_summary
            
            handler = self.router._handlers[event_name][0]
            
            # Use the same analysis as system:help
            handler_info = {
                "module": handler.module,
                "handler": handler.name,
                "async": handler.is_async,
                "summary": extract_summary(handler.func),
            }
            
            analyzer = UnifiedHandlerAnalyzer(handler.func, event_name=event_name)
            analysis_result = analyzer.analyze()
            handler_info.update(analysis_result)
            
            return handler_info
            
        except Exception as e:
            logger.warning(f"Could not get event info for {event_name}: {e}")
            return None
    
    async def _handle_missing_parameter(
        self, event_name: str, provided_params: Dict[str, Any], 
        error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
    ) -> Dict[str, Any]:
        """Handle missing parameter errors."""
        
        # Extract parameter name from error
        param_match = re.search(r"Missing required parameter: (\w+)", error_str)
        if param_match:
            missing_param = param_match.group(1)
        elif error_str.startswith("'") and error_str.endswith("'"):
            # KeyError pattern: 'parameter_name'
            missing_param = error_str.strip("'")
        else:
            return {"error": error_str}
            
        if not missing_param:
            return {"error": error_str}
        
        # Create proper error message
        enhanced_error = {"error": f"Missing required parameter: {missing_param}"}
        
        if event_info and verbosity in ["medium", "verbose"]:
            # Get available parameters
            parameters = event_info.get("parameters", {})
            if parameters:
                param_names = list(parameters.keys())
                enhanced_error["available"] = param_names
                
                # Add type info if we have it for the missing parameter
                if missing_param in parameters:
                    param_info = parameters[missing_param]
                    param_type = param_info.get("type", "unknown")
                    enhanced_error["error"] = f"Missing required parameter: {missing_param} ({param_type})"
        
        if verbosity == "verbose" and event_info:
            # Add full parameter help
            enhanced_error["help"] = f"Use: help {event_name}"
            
        return enhanced_error
    
    async def _handle_type_mismatch(
        self, event_name: str, provided_params: Dict[str, Any],
        error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
    ) -> Dict[str, Any]:
        """Handle type mismatch errors."""
        
        enhanced_error = {"error": error_str}
        
        if verbosity in ["medium", "verbose"] and event_info:
            # Could add type examples here
            parameters = event_info.get("parameters", {})
            if parameters:
                enhanced_error["help"] = f"Use: help {event_name}"
        
        return enhanced_error
    
    async def _handle_unknown_event(
        self, event_name: str, provided_params: Dict[str, Any],
        error_str: str, verbosity: str
    ) -> Dict[str, Any]:
        """Handle unknown event errors."""
        
        enhanced_error = {"error": error_str}
        
        if verbosity in ["medium", "verbose"] and self.router:
            # Find similar event names
            all_events = list(self.router._handlers.keys())
            similar = get_close_matches(event_name, all_events, n=3, cutoff=0.6)
            
            if similar:
                enhanced_error["similar"] = similar
        
        return enhanced_error
    
    async def handle_unknown_event(
        self, event_name: str, provided_params: Dict[str, Any], verbosity: str
    ) -> Dict[str, Any]:
        """Handle unknown event with discovery guidance."""
        
        # Get all available events
        all_events = list(self.router._handlers.keys()) if self.router else []
        
        # Find similar events using fuzzy matching
        similar = get_close_matches(event_name, all_events, n=3, cutoff=0.6)
        
        # Extract unique namespaces
        namespaces = sorted(set(event.split(':')[0] for event in all_events if ':' in event))
        
        # Concise internal format for AI agents
        result = {"error": f"Unknown event: {event_name}"}
        
        if similar:
            result["similar"] = similar
            
        if verbosity in ["medium", "verbose"] and namespaces:
            result["namespaces"] = namespaces
        
        return result
    
    async def _handle_generic_error(
        self, event_name: str, provided_params: Dict[str, Any],
        error_str: str, event_info: Optional[Dict[str, Any]], verbosity: str
    ) -> Dict[str, Any]:
        """Handle generic errors."""
        
        enhanced_error = {"error": error_str}
        
        if verbosity == "verbose" and event_info:
            enhanced_error["help"] = f"Use: help {event_name}"
            
        return enhanced_error