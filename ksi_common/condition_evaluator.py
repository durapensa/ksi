"""
Safe condition evaluator for transformer conditions.

Supports complex boolean expressions without using eval/exec.
"""

import re
from typing import Any, Dict, Optional, Union
import operator


class ConditionEvaluator:
    """Safely evaluate complex boolean conditions for transformers."""
    
    # Supported operators
    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
        'in': lambda a, b: a in b,
        'not in': lambda a, b: a not in b,
    }
    
    def __init__(self):
        # Token patterns for lexical analysis
        self.token_patterns = [
            ('LPAREN', r'\('),
            ('RPAREN', r'\)'),
            ('LBRACKET', r'\['),
            ('RBRACKET', r'\]'),
            ('COMMA', r','),
            ('AND', r'\band\b'),
            ('OR', r'\bor\b'),
            ('NOT', r'\bnot\b'),
            ('TRUE', r'\btrue\b|\bTrue\b'),
            ('FALSE', r'\bfalse\b|\bFalse\b'),
            ('NONE', r'\bnone\b|\bNone\b'),
            ('NUMBER', r'-?\d+\.?\d*'),
            ('STRING', r"'[^']*'|\"[^\"]*\""),
            ('COMPARISON', r'==|!=|<=|>=|<|>|not in|in'),  # MOVED BEFORE IDENTIFIER
            ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),      # MOVED AFTER COMPARISON
            ('DOT', r'\.'),
            ('WHITESPACE', r'\s+'),
        ]
        
        # Compile patterns
        self.token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in self.token_patterns)
        self.compiled_regex = re.compile(self.token_regex)
        
    def evaluate(self, condition: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate a condition expression against data.
        
        Args:
            condition: Boolean expression to evaluate
            data: Event data dictionary
            context: Optional context with special variables like source_event
            
        Returns:
            Boolean result of evaluation
        """
        try:
            # Prepare evaluation context
            eval_context = {
                **data,
                'source_event': context.get('event', '') if context else '',
                '_ksi_context': context or {}
            }
            
            # Log evaluation details for debugging complex conditions
            import logging
            logger = logging.getLogger(__name__)
            if 'agent_id' in condition and 'result_type' in condition:
                # This looks like a routing condition, log details
                logger.debug(f"Evaluating routing condition: {condition}")
                logger.debug(f"  Available data keys: {list(eval_context.keys())}")
                if 'agent_id' in eval_context:
                    logger.debug(f"  agent_id value: {eval_context['agent_id']}")
                if 'result_type' in eval_context:
                    logger.debug(f"  result_type value: {eval_context['result_type']}")
            
            # Tokenize the condition
            tokens = self._tokenize(condition)
            
            # Parse and evaluate
            result = self._parse_or_expression(tokens, eval_context)
            
            # Ensure we consumed all tokens
            if tokens:
                raise ValueError(f"Unexpected tokens remaining: {tokens}")
                
            return bool(result)
            
        except Exception as e:
            # Log error and return True (allow by default to avoid blocking)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return True
    
    def _tokenize(self, expression: str) -> list:
        """Tokenize the expression into a list of (type, value) tuples."""
        tokens = []
        
        for match in self.compiled_regex.finditer(expression):
            token_type = match.lastgroup
            token_value = match.group()
            
            # Skip whitespace
            if token_type == 'WHITESPACE':
                continue
                
            # Convert values for certain types
            if token_type == 'NUMBER':
                token_value = float(token_value) if '.' in token_value else int(token_value)
            elif token_type == 'STRING':
                token_value = token_value[1:-1]  # Remove quotes
            elif token_type in ('TRUE', 'FALSE', 'NONE'):
                token_value = {'TRUE': True, 'FALSE': False, 'NONE': None}[token_type]
                
            tokens.append((token_type, token_value))
            
        return tokens
    
    def _parse_or_expression(self, tokens: list, context: Dict[str, Any]) -> Any:
        """Parse OR expressions (lowest precedence)."""
        left = self._parse_and_expression(tokens, context)
        
        while tokens and tokens[0] == ('OR', 'or'):
            tokens.pop(0)  # Consume 'or'
            right = self._parse_and_expression(tokens, context)
            left = left or right
            
        return left
    
    def _parse_and_expression(self, tokens: list, context: Dict[str, Any]) -> Any:
        """Parse AND expressions."""
        left = self._parse_not_expression(tokens, context)
        
        while tokens and tokens[0] == ('AND', 'and'):
            tokens.pop(0)  # Consume 'and'
            right = self._parse_not_expression(tokens, context)
            left = left and right
            
        return left
    
    def _parse_not_expression(self, tokens: list, context: Dict[str, Any]) -> Any:
        """Parse NOT expressions."""
        if tokens and tokens[0] == ('NOT', 'not'):
            tokens.pop(0)  # Consume 'not'
            return not self._parse_not_expression(tokens, context)
        
        return self._parse_comparison(tokens, context)
    
    def _parse_comparison(self, tokens: list, context: Dict[str, Any]) -> Any:
        """Parse comparison expressions."""
        left = self._parse_primary(tokens, context)
        
        if tokens and tokens[0][0] == 'COMPARISON':
            op_type, op_value = tokens.pop(0)
            right = self._parse_primary(tokens, context)
            
            # Special handling for string methods
            if op_value == 'in' and hasattr(left, 'startswith'):
                # Check if this is actually a method call pattern
                if isinstance(right, str) and right.startswith('(') and right.endswith(')'):
                    # This is a method call like source_event.startswith('transport:')
                    return self._handle_method_call(left, right[1:-1])
            
            # Normal comparison
            if op_value in self.OPERATORS:
                return self.OPERATORS[op_value](left, right)
            else:
                raise ValueError(f"Unknown operator: {op_value}")
                
        return left
    
    def _parse_primary(self, tokens: list, context: Dict[str, Any]) -> Any:
        """Parse primary expressions (values, identifiers, parentheses, lists)."""
        if not tokens:
            raise ValueError("Unexpected end of expression")
            
        token_type, token_value = tokens.pop(0)
        
        if token_type == 'LPAREN':
            # Parenthesized expression
            result = self._parse_or_expression(tokens, context)
            if not tokens or tokens.pop(0) != ('RPAREN', ')'):
                raise ValueError("Missing closing parenthesis")
            return result
            
        elif token_type == 'LBRACKET':
            # List expression
            list_items = []
            
            # Handle empty list
            if tokens and tokens[0] == ('RBRACKET', ']'):
                tokens.pop(0)  # Consume closing bracket
                return list_items
            
            # Parse list items
            while True:
                if not tokens:
                    raise ValueError("Unexpected end of list expression")
                    
                # Parse list item
                item = self._parse_primary(tokens, context)
                list_items.append(item)
                
                # Check for comma or closing bracket
                if not tokens:
                    raise ValueError("Missing closing bracket for list")
                    
                next_token = tokens[0]
                if next_token == ('RBRACKET', ']'):
                    tokens.pop(0)  # Consume closing bracket
                    break
                elif next_token == ('COMMA', ','):
                    tokens.pop(0)  # Consume comma
                    continue
                else:
                    raise ValueError(f"Expected comma or closing bracket in list, got {next_token}")
            
            return list_items
            
        elif token_type in ('NUMBER', 'STRING', 'TRUE', 'FALSE', 'NONE'):
            # Literal value
            return token_value
            
        elif token_type == 'IDENTIFIER':
            # Variable or method call
            return self._resolve_identifier(token_value, tokens, context)
            
        else:
            raise ValueError(f"Unexpected token: {token_type} = {token_value}")
    
    def _resolve_identifier(self, name: str, tokens: list, context: Dict[str, Any]) -> Any:
        """Resolve an identifier, handling dots and method calls."""
        # Start with the base identifier
        value = context.get(name, None)
        
        # Handle dot notation
        while tokens and tokens[0] == ('DOT', '.'):
            tokens.pop(0)  # Consume dot
            
            if not tokens or tokens[0][0] != 'IDENTIFIER':
                raise ValueError("Expected identifier after dot")
                
            attr_type, attr_name = tokens.pop(0)
            
            # Check if this is a method call
            if tokens and tokens[0] == ('LPAREN', '('):
                tokens.pop(0)  # Consume opening paren
                
                # Parse method arguments
                args = []
                while tokens and tokens[0] != ('RPAREN', ')'):
                    if args:  # Need comma between args
                        if tokens[0] == ('IDENTIFIER', ','):
                            tokens.pop(0)
                        else:
                            # For now, support single argument
                            pass
                    
                    arg = self._parse_primary(tokens, context)
                    args.append(arg)
                    
                if not tokens or tokens.pop(0) != ('RPAREN', ')'):
                    raise ValueError("Missing closing parenthesis for method call")
                    
                # Call the method
                if hasattr(value, attr_name):
                    method = getattr(value, attr_name)
                    return method(*args) if args else method()
                else:
                    return False
            else:
                # Attribute access
                if hasattr(value, attr_name):
                    value = getattr(value, attr_name)
                elif isinstance(value, dict):
                    value = value.get(attr_name)
                else:
                    value = None
                    
        return value
    
    def _handle_method_call(self, obj: Any, method_call: str) -> bool:
        """Handle method calls like startswith('prefix')."""
        # Parse method name and arguments
        if '(' in method_call:
            method_name, args_str = method_call.split('(', 1)
            args_str = args_str.rstrip(')')
            
            # Parse arguments (simple string parsing for now)
            args = []
            if args_str:
                # Remove quotes and split (simple implementation)
                arg = args_str.strip().strip("'\"")
                args.append(arg)
                
            # Call the method
            if hasattr(obj, method_name):
                method = getattr(obj, method_name)
                try:
                    return method(*args) if args else method()
                except:
                    return False
                    
        return False


# Create singleton instance
_evaluator = ConditionEvaluator()


def evaluate_condition(condition: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Evaluate a condition expression.
    
    Args:
        condition: Boolean expression to evaluate
        data: Event data dictionary  
        context: Optional context with special variables
        
    Returns:
        Boolean result of evaluation
    """
    return _evaluator.evaluate(condition, data, context)