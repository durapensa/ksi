#!/usr/bin/env python3
"""
Experiment: Using AST to discover event parameters from function body
"""

import ast
import inspect
from typing import Dict, Any, List, Tuple

def extract_data_access_from_function(func) -> Dict[str, Any]:
    """Extract parameter info by analyzing data.get() calls in function body."""
    source = inspect.getsource(func)
    tree = ast.parse(source)
    
    parameters = {}
    
    class DataGetVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for data.get() calls
            if (isinstance(node.func, ast.Attribute) and 
                node.func.attr == 'get' and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'data'):
                
                # Extract the key name
                if node.args and isinstance(node.args[0], ast.Constant):
                    key = node.args[0].value
                    
                    # Extract default value if present
                    default = None
                    required = True
                    if len(node.args) > 1:
                        required = False
                        if isinstance(node.args[1], ast.Constant):
                            default = node.args[1].value
                    
                    parameters[key] = {
                        'required': required,
                        'default': default,
                        'type': 'Any'  # Could be enhanced with type inference
                    }
            
            self.generic_visit(node)
    
    visitor = DataGetVisitor()
    visitor.visit(tree)
    
    return parameters

# Test with the state:set handler
def handle_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set a value in shared state."""
    namespace = data.get("namespace", "global") 
    key = data.get("key", "")
    value = data.get("value")
    metadata = data.get("metadata", {})
    
    if not key:
        return {"error": "Key is required"}
    
    return {"status": "set"}

# Extract parameters
params = extract_data_access_from_function(handle_set)
print("Discovered parameters:")
for name, info in params.items():
    print(f"  {name}: {info}")