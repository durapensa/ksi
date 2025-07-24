"""
Example migration: Update event_system.py to use unified template utility.

This shows how to replace the duplicate _apply_mapping implementation
with the enhanced template utility.
"""

from typing import Dict, Any, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# BEFORE: Duplicate implementation in event_system.py
def _apply_mapping_OLD(self, mapping: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """OLD: Apply field mapping from transformer definition."""
    
    def substitute_template(value: Any, data: Dict[str, Any]) -> Any:
        """Recursively substitute template variables in any structure."""
        if isinstance(value, str):
            # Check for embedded templates in strings
            import re
            template_pattern = r'\{\{([^}]+)\}\}'
            
            def replace_template(match):
                template = match.group(1).strip()
                # Simple dot notation support with array indexing
                parts = template.split('.')
                result = data
                for part in parts:
                    if isinstance(result, dict) and part in result:
                        result = result[part]
                    elif isinstance(result, list) and part.isdigit():
                        # Array index access
                        index = int(part)
                        if 0 <= index < len(result):
                            result = result[index]
                        else:
                            return match.group(0)  # Return template unchanged
                    else:
                        return match.group(0)  # Return template unchanged if not found
                return str(result) if result is not None else match.group(0)
            
            return re.sub(template_pattern, replace_template, value)
        elif isinstance(value, dict):
            # Recursively process dictionaries
            return {k: substitute_template(v, data) for k, v in value.items()}
        elif isinstance(value, list):
            # Recursively process lists
            return [substitute_template(item, data) for item in value]
        else:
            # Return non-string values as-is
            return value
    
    # Process the entire mapping
    if isinstance(mapping, dict):
        return substitute_template(mapping, data)
    else:
        # If mapping is not a dict (e.g., a string template), return as-is
        return substitute_template(mapping, data)


# AFTER: Use unified template utility
from ksi_common.enhanced_template_utils import substitute_template

def _apply_mapping_NEW(self, mapping: Any, data: Dict[str, Any], 
                       context: Optional[Dict[str, Any]] = None) -> Any:
    """NEW: Apply field mapping using unified template system."""
    # Just delegate to the unified implementation
    return substitute_template(mapping, data, context)


# Example showing the benefits:
if __name__ == "__main__":
    # Test data
    test_data = {
        "agent_id": "agent_123",
        "event_name": "task:completed",
        "event_data": {
            "task_id": "task_789",
            "status": "success",
            "metrics": {
                "duration": 150,
                "tokens": 2500
            }
        },
        "items": ["first", "second", "third"],
        "timestamp": 1234567890
    }
    
    test_context = {
        "_agent_id": "orchestrator_456",
        "user_id": "user_789"
    }
    
    # Transformer mapping examples
    mappings = [
        # Simple pass-through (NEW feature)
        "{{$}}",
        
        # Complex nested mapping
        {
            "agent_id": "{{agent_id}}",
            "event_notification": {
                "source_agent": "{{_ksi_context._agent_id}}",  # NEW: context access
                "event": "{{event_name}}",
                "data": "{{event_data}}",
                "routed_by": "hierarchical_router",
                "timestamp": "{{timestamp_utc()}}"  # NEW: function call
            }
        },
        
        # Conditional mapping with defaults
        {
            "task_id": "{{event_data.task_id}}",
            "status": "{{event_data.status|unknown}}",  # NEW: default values
            "duration": "{{event_data.metrics.duration}}",
            "high_token_alert": "{{event_data.metrics.tokens > 2000}}",  # Future: expressions
            "items_count": "{{len(items)}}",  # NEW: function calls
            "first_item": "{{items.0}}",  # Already supported
            "uppercase_status": "{{upper(event_data.status)}}"  # NEW: string functions
        }
    ]
    
    print("=== Event System Template Migration Example ===\n")
    
    # Create mock event router
    class MockRouter:
        pass
    
    router = MockRouter()
    
    # Test each mapping
    for i, mapping in enumerate(mappings, 1):
        print(f"Test {i}: {type(mapping).__name__} mapping")
        print(f"Mapping: {mapping}")
        
        # Old implementation (limited features)
        router._apply_mapping = lambda self, m, d: _apply_mapping_OLD(self, m, d)
        try:
            old_result = router._apply_mapping(router, mapping, test_data)
            print(f"OLD Result: {old_result}")
        except Exception as e:
            print(f"OLD Result: ERROR - {e}")
        
        # New implementation (full features)  
        router._apply_mapping = lambda self, m, d, c=None: _apply_mapping_NEW(self, m, d, c)
        new_result = router._apply_mapping(router, mapping, test_data, test_context)
        print(f"NEW Result: {new_result}")
        print()
    
    print("\nBenefits of migration:")
    print("1. ✓ Support for {{$}} pass-through")
    print("2. ✓ Context access with {{_ksi_context.x}}")
    print("3. ✓ Function calls like {{timestamp_utc()}}")
    print("4. ✓ Default values with {{var|default}}")
    print("5. ✓ Consistent behavior across all KSI modules")
    print("6. ✓ Single implementation to maintain and enhance")