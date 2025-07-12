#!/usr/bin/env python3
"""
Discovery System Utilities

AST analysis utilities for extracting runtime behavior from event handlers.
Used by the unified discovery system in discovery.py.
"""

import ast
import inspect
from typing import Any, Callable, Dict, Optional, Set

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("discovery.utils")


class ValidationAnalyzer(ast.NodeVisitor):
    """Analyzes code to extract validation patterns for parameters."""
    
    def __init__(self):
        self.validations = {}  # param_name -> list of validation constraints
        self.current_param = None
        
    def visit_If(self, node):
        """Detect validation patterns in if statements."""
        # Try to extract parameter being validated
        param = self._extract_validated_param(node.test)
        if param:
            constraint = self._extract_constraint(node.test, param)
            if constraint:
                if param not in self.validations:
                    self.validations[param] = []
                # Don't add duplicate constraint types
                existing_keys = set()
                for existing in self.validations[param]:
                    existing_keys.update(existing.keys())
                # Only add if we don't have conflicting constraints
                new_keys = set(constraint.keys())
                if not any(k in existing_keys for k in new_keys):
                    self.validations[param].append(constraint)
                
        self.generic_visit(node)
        
    def visit_Assert(self, node):
        """Detect validation patterns in assert statements."""
        param = self._extract_validated_param(node.test)
        if param:
            constraint = self._extract_constraint(node.test, param)
            if constraint:
                if param not in self.validations:
                    self.validations[param] = []
                self.validations[param].append(constraint)
                
        self.generic_visit(node)
        
    def _extract_validated_param(self, node):
        """Extract parameter name being validated."""
        if isinstance(node, ast.Compare):
            # e.g., value < 0, len(value) > 100
            left = node.left
            if isinstance(left, ast.Name):
                return left.id
            elif isinstance(left, ast.Call) and isinstance(left.func, ast.Name):
                # e.g., len(param), int(param)
                if left.args and isinstance(left.args[0], ast.Name):
                    return left.args[0].id
                elif left.args and isinstance(left.args[0], ast.Subscript):
                    # e.g., len(data["param"])
                    if (isinstance(left.args[0].value, ast.Name) and 
                        left.args[0].value.id == "data" and
                        isinstance(left.args[0].slice, ast.Constant)):
                        return left.args[0].slice.value
            elif isinstance(left, ast.Subscript):
                # e.g., data["param"]
                if (isinstance(left.value, ast.Name) and left.value.id == "data" and
                    isinstance(left.slice, ast.Constant)):
                    return left.slice.value
            elif isinstance(left, ast.Attribute):
                # e.g., data.get("param")
                if (isinstance(left.value, ast.Call) and 
                    isinstance(left.value.func, ast.Attribute) and
                    left.value.func.attr == "get" and
                    left.value.args and isinstance(left.value.args[0], ast.Constant)):
                    return left.value.args[0].value
                    
        elif isinstance(node, ast.Call):
            # e.g., isinstance(value, str)
            if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                if node.args and isinstance(node.args[0], ast.Name):
                    return node.args[0].id
                    
        return None
        
    def _extract_constraint(self, node, param_name):
        """Extract validation constraint from AST node."""
        if isinstance(node, ast.Compare):
            left = node.left
            op = node.ops[0]
            comparator = node.comparators[0]
            
            # Numeric comparisons
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, (int, float)):
                value = comparator.value
                # For validation checks that raise errors, the logic is inverted
                # if x < 0: raise => minimum value is 0
                # if x > 100: raise => maximum value is 100
                if isinstance(op, ast.Lt):
                    # x < N typically means minimum is N
                    return {'min_value': value}
                elif isinstance(op, ast.LtE):
                    return {'min_value': value + 1}
                elif isinstance(op, ast.Gt):
                    # x > N typically means maximum is N
                    return {'max_value': value}
                elif isinstance(op, ast.GtE):
                    return {'max_value': value - 1}
                elif isinstance(op, ast.Eq):
                    return {'exact_value': value}
                    
            # Length comparisons
            elif (isinstance(left, ast.Call) and 
                  isinstance(left.func, ast.Name) and 
                  left.func.id == "len"):
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, int):
                    value = comparator.value
                    # For validation checks that raise errors, the logic is inverted
                    # if len(x) < 2: raise => minimum length is 2
                    # if len(x) > 10: raise => maximum length is 10
                    # Check if this is inside an if statement that leads to error
                    if isinstance(op, ast.Lt):
                        # len(x) < N typically means minimum is N
                        return {'min_length': value}
                    elif isinstance(op, ast.LtE):
                        return {'min_length': value + 1}
                    elif isinstance(op, ast.Gt):
                        # len(x) > N typically means maximum is N  
                        return {'max_length': value}
                    elif isinstance(op, ast.GtE):
                        return {'max_length': value - 1}
                    elif isinstance(op, ast.Eq):
                        return {'exact_length': value}
                        
            # In/NotIn comparisons for allowed values
            elif isinstance(op, ast.In) and isinstance(comparator, (ast.List, ast.Tuple, ast.Set)):
                values = []
                for elt in comparator.elts:
                    if isinstance(elt, ast.Constant):
                        values.append(elt.value)
                if values:
                    return {'allowed_values': values}
                    
        elif isinstance(node, ast.Call):
            # Type checking
            if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                if len(node.args) >= 2:
                    type_arg = node.args[1]
                    if isinstance(type_arg, ast.Name):
                        return {'expected_type': type_arg.id}
                    elif isinstance(type_arg, ast.Tuple):
                        types = []
                        for elt in type_arg.elts:
                            if isinstance(elt, ast.Name):
                                types.append(elt.id)
                        if types:
                            return {'expected_types': types}
                            
        return None


def extract_summary(func: Callable) -> str:
    """Extract summary from function docstring."""
    doc = inspect.getdoc(func)
    if doc:
        # First line is summary
        return doc.split("\n")[0].strip()
    return f"Handle {func.__name__}"


class HandlerAnalyzer(ast.NodeVisitor):
    """AST visitor to extract parameters and event triggers from handler implementation."""

    def __init__(self, source_lines=None, module_tree=None, source_line_offset=0):
        self.data_gets = {}  # data.get() calls
        self.data_subscripts = set()  # data["key"] access
        self.triggers = []  # Events emitted
        self.source_lines = source_lines or []
        self.source_line_offset = source_line_offset  # Offset to real file line numbers

    def visit_Call(self, node):
        # Check for data.get() calls
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "data"
        ):
            if node.args and isinstance(node.args[0], ast.Constant):
                key = node.args[0].value
                default = None
                required = True

                if len(node.args) > 1:
                    required = False
                    # Enhanced default value extraction
                    default = self._extract_default_value(node.args[1])

                # Extract inline comment if present
                comment = self._extract_inline_comment(node.lineno)
                
                # Only update if we don't already have this parameter
                # This preserves the first (correct) extraction
                if key not in self.data_gets:
                    self.data_gets[key] = {
                        "required": required, 
                        "default": default,
                        "comment": comment
                    }

        # Check for event emissions
        elif self._is_emit_call(node):
            event_name = self._extract_event_name(node)
            if event_name:
                self.triggers.append(event_name)

        self.generic_visit(node)

    def visit_Subscript(self, node):
        # Check for data["key"] access
        if isinstance(node.value, ast.Name) and node.value.id == "data" and isinstance(node.slice, ast.Constant):
            key = node.slice.value
            self.data_subscripts.add(key)

        self.generic_visit(node)

    def _is_emit_call(self, node):
        """Check if this is an event emission."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in ["emit", "emit_event", "emit_first"]
        elif isinstance(node.func, ast.Name):
            return node.func.id in ["emit_event", "emit"]
        return False

    def _extract_event_name(self, node):
        """Extract event name from emit call."""
        if node.args and isinstance(node.args[0], ast.Constant):
            return node.args[0].value
        return None
    
    def _extract_inline_comment(self, lineno):
        """Extract inline comment from source line."""
        if not self.source_lines:
            return None
            
        # AST line numbers are relative to the parsed source (1-based)
        # We need to add the function's starting line offset if we have file lines
        actual_line_idx = self.source_line_offset + lineno - 1
        
        if actual_line_idx >= len(self.source_lines):
            return None
            
        line = self.source_lines[actual_line_idx]
        
        # Look for inline comment
        comment_idx = line.find('#')
        if comment_idx > 0:  # Must not be at start of line
            comment = line[comment_idx + 1:].strip()
            # Filter out obvious non-documentation comments
            if comment and not comment.startswith(('TODO', 'FIXME', 'NOTE:', 'noqa')):
                return comment
        
        return None
    
    def _extract_default_value(self, node):
        """Extract default value from AST node, handling various patterns."""
        if isinstance(node, ast.Constant):
            # Simple constant values
            return node.value
        elif isinstance(node, ast.Name):
            # Named constants like True, False, None
            if node.id in ('True', 'False', 'None'):
                return eval(node.id)
            # Variables (we'll represent as placeholder)
            return f"<{node.id}>"
        elif isinstance(node, ast.List):
            # List literals
            return [self._extract_default_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            # Dict literals
            result = {}
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant):
                    result[k.value] = self._extract_default_value(v)
            return result
        elif isinstance(node, ast.Call):
            # Function calls - represent as string
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}(...)"
            elif isinstance(node.func, ast.Attribute):
                return f"...{node.func.attr}(...)"
        elif isinstance(node, ast.Attribute):
            # Attribute access like config.value
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            return f"<{node.attr}>"
        elif isinstance(node, ast.BinOp):
            # Binary operations like "prefix_" + name
            left = self._extract_default_value(node.left)
            right = self._extract_default_value(node.right)
            if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str):
                # Handle string concatenation specially
                if left.startswith('<') and left.endswith('>'):
                    return f"'{left[1:-1]}' + {right}"
                elif right.startswith('<') and right.endswith('>'):
                    return f"{left} + '{right[1:-1]}'"
                return left + right
            return f"<expression>"
        elif isinstance(node, ast.UnaryOp):
            # Unary operations like -1
            if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
                return -node.operand.value
            return f"<expression>"
        elif isinstance(node, ast.IfExp):
            # Ternary expressions
            return f"<conditional>"
        else:
            # Unknown pattern
            return None