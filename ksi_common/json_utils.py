#!/usr/bin/env python3

"""
Modern JSON utilities with enhanced error handling and validation
Provides robust JSON parsing, serialization, and extraction capabilities

## When to Use parse_json_parameter

The `parse_json_parameter` function is specifically designed for handling CLI parameters that can be 
passed as JSON strings. It should be used ONLY in event handlers that receive data from external 
sources (like the KSI CLI).

### When TO Use parse_json_parameter:

1. **In Event Handlers for CLI-facing Parameters**
   - Parameters that users pass via `ksi send` commands
   - Examples: --filter, --properties, --metadata, --vars
   - These come as JSON strings from the CLI: `--filter '{"type": "orchestration"}'`

2. **For Parameters That Accept Complex Structures**
   - When a parameter needs to accept nested data (objects/arrays)
   - When the CLI interface needs to support structured input
   - Examples: filter criteria, configuration objects, metadata

3. **At the Entry Point of External Data**
   - Only in the initial event handler that receives data from outside
   - Before passing data to internal functions/services
   - Ensures JSON strings are parsed into proper Python objects

### When NOT to Use parse_json_parameter:

1. **Internal Service-to-Service Communication**
   - Data passed between internal Python functions
   - Already-parsed Python dictionaries and objects
   - Would cause double-parsing errors

2. **Non-String Parameters**
   - Parameters that are already Python objects (dict, list, etc.)
   - Simple scalar values (int, bool, etc.)
   - The function safely ignores non-string parameters

3. **After Initial Parsing**
   - Once data enters the system and is parsed, keep it as Python objects
   - Don't re-stringify and re-parse internally

### Best Practices:

1. **Parse Once at the Boundary**
   ```python
   def handle_event(raw_data):
       data = event_format_linter(raw_data, MyDataType)
       # Parse JSON parameters at entry point
       parse_json_parameter(data, 'filter')
       parse_json_parameter(data, 'properties')
       # Now pass parsed data to internal functions
       return internal_service.process(data)
   ```

2. **Document JSON Parameters in TypedDict**
   ```python
   class MyEventData(TypedDict):
       filter: Union[str, Dict[str, Any]]  # JSON string from CLI or dict internally
       limit: int  # Simple scalar, no parsing needed
   ```

3. **Let the Function Handle Edge Cases**
   - It safely ignores missing parameters (returns None)
   - It safely ignores non-string parameters
   - It logs warnings for invalid JSON

### Examples from KSI:

**External-facing (USE parse_json_parameter):**
- `composition:list` handler parses `filter` parameter
- `state:entity:create` handler parses `properties` parameter
- `orchestration:start` handler parses `vars` parameter

**Internal functions (DON'T USE):**
- Database query builders receive already-parsed dicts
- Service layer functions work with Python objects
- Component renderers process structured data
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional, List, Callable, Tuple
import structlog
from .timestamps import sanitize_for_json

logger = structlog.get_logger("json_utils")


class JSONParseError(ValueError):
    """JSON parsing error with context and suggestions."""
    
    def __init__(self, message: str, suggestion: str = None, original_error: Exception = None):
        super().__init__(message)
        self.suggestion = suggestion
        self.original_error = original_error


class JSONProcessor:
    """Enhanced JSON processor with comprehensive error handling."""
    
    def __init__(self, ensure_ascii: bool = False, indent: int = 2, sort_keys: bool = False):
        """Initialize JSON processor with formatting options."""
        self.ensure_ascii = ensure_ascii
        self.indent = indent
        self.sort_keys = sort_keys
    
    def loads(self, content: str) -> Any:
        """Parse JSON string with enhanced error handling."""
        if not content or not content.strip():
            return {}
            
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            suggestion = self._suggest_fix(content, e)
            raise JSONParseError(
                f"JSON parsing failed: {e}",
                suggestion=suggestion,
                original_error=e
            ) from e
    
    def dumps(self, data: Any, sanitize_dates: bool = True) -> str:
        """Convert data to JSON string with consistent formatting."""
        if sanitize_dates:
            data = sanitize_for_json(data)
            
        try:
            return json.dumps(
                data,
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
                sort_keys=self.sort_keys,
                separators=(',', ': ')
            )
        except TypeError as e:
            raise JSONParseError(
                f"JSON serialization failed: {e}",
                suggestion="Check for non-serializable objects (datetime, custom classes, etc.)",
                original_error=e
            ) from e
    
    def load_file(self, file_path: Union[str, Path]) -> Any:
        """Load JSON from file with comprehensive error handling."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return self.loads(content)
        except UnicodeDecodeError as e:
            logger.error(f"UTF-8 decode error in {path}: {e}")
            raise JSONParseError(
                f"File encoding error in {path}: {e}",
                suggestion="Ensure file is saved as UTF-8",
                original_error=e
            ) from e
    
    def save_file(self, file_path: Union[str, Path], data: Any,
                  create_dirs: bool = True, atomic: bool = True) -> None:
        """Save data to JSON file with atomic writes."""
        path = Path(file_path)
        
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
            
        content = self.dumps(data)
        
        if atomic:
            # Atomic write using temporary file
            temp_path = path.with_suffix(path.suffix + '.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                temp_path.replace(path)  # Atomic on most filesystems
            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                raise JSONParseError(
                    f"Failed to write JSON file {path}: {e}",
                    original_error=e
                ) from e
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _suggest_fix(self, json_str: str, error: json.JSONDecodeError) -> str:
        """Provide helpful suggestions for common JSON errors."""
        error_msg = str(error).lower()
        
        # Common error patterns and suggestions
        if 'expecting property name' in error_msg:
            if "'" in json_str:
                return "Use double quotes for JSON strings, not single quotes"
            return "Property names must be quoted with double quotes"
        
        elif 'extra data' in error_msg:
            return "Multiple JSON objects found - ensure only one object per parse"
        
        elif 'expecting value' in error_msg:
            return "Check for trailing commas or missing values"
        
        elif 'unterminated string' in error_msg:
            return "Check for unclosed strings or unescaped quotes"
        
        elif 'expecting \',\' delimiter' in error_msg:
            return "Missing comma between object properties or array elements"
        
        elif 'control character' in error_msg:
            return "Remove control characters or escape them properly"
        
        return "Check JSON syntax - common issues: trailing commas, single quotes, unescaped characters"


class JSONExtractor:
    """Enhanced JSON extraction from text with comprehensive error handling."""
    
    def __init__(self, processor: JSONProcessor = None):
        """Initialize with optional custom processor."""
        self.processor = processor or JSONProcessor()
        
    def extract_json_objects(self, text: str, 
                           filter_func: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Extract all valid JSON objects from text using balanced brace parsing."""
        return self.extract_json_objects_balanced(text, filter_func=filter_func)
    
    def extract_json_objects_balanced(self, text: str, 
                                    filter_func: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Extract all valid JSON objects from text using balanced brace parsing.
        
        This method can handle deeply nested JSON objects by using proper brace balancing
        instead of regex patterns that fail on complex nesting.
        
        Args:
            text: Text to extract JSON from
            filter_func: Optional filter function to apply to extracted objects
            
        Returns:
            List of extracted JSON objects
        """
        objects = []
        
        # First, check for JSON in code blocks
        code_block_pattern = r'```(?:json)?\s*(\{[^`]+\})\s*```'
        for match in re.finditer(code_block_pattern, text, re.DOTALL):
            json_str = match.group(1)
            try:
                obj = self.processor.loads(json_str)
                if isinstance(obj, dict):
                    if filter_func is None or filter_func(obj):
                        objects.append(obj)
            except JSONParseError:
                # Try to fix common issues
                fixed_json = self._attempt_fix(json_str)
                if fixed_json:
                    try:
                        obj = self.processor.loads(fixed_json)
                        if isinstance(obj, dict):
                            if filter_func is None or filter_func(obj):
                                objects.append(obj)
                    except JSONParseError:
                        continue
        
        # Extract JSON objects using balanced brace parsing
        extracted_strings = self._extract_balanced_json_strings(text)
        
        for json_str in extracted_strings:
            # Skip if this was already found in a code block
            if any(json_str in str(obj) for obj in objects):
                continue
                
            try:
                obj = self.processor.loads(json_str)
                if isinstance(obj, dict):
                    if filter_func is None or filter_func(obj):
                        # Avoid duplicates
                        if obj not in objects:
                            objects.append(obj)
            except JSONParseError:
                # Try to fix common issues
                fixed_json = self._attempt_fix(json_str)
                if fixed_json:
                    try:
                        obj = self.processor.loads(fixed_json)
                        if isinstance(obj, dict):
                            if filter_func is None or filter_func(obj):
                                if obj not in objects:
                                    objects.append(obj)
                    except JSONParseError:
                        continue
        
        return objects
    
    def _extract_balanced_json_strings(self, text: str) -> List[str]:
        """Extract JSON strings using balanced brace parsing.
        
        This method can handle arbitrary levels of nesting by properly balancing
        braces, brackets, and quotes.
        
        Args:
            text: Text to extract JSON strings from
            
        Returns:
            List of potential JSON strings
        """
        json_strings = []
        i = 0
        
        while i < len(text):
            # Look for opening brace
            if text[i] == '{':
                json_str, end_pos = self._extract_balanced_object(text, i)
                if json_str:
                    json_strings.append(json_str)
                    i = end_pos
                else:
                    i += 1
            else:
                i += 1
        
        return json_strings
    
    def _extract_balanced_object(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
        """Extract a balanced JSON object starting at the given position.
        
        Args:
            text: Text containing the JSON object
            start_pos: Starting position (should be at an opening brace)
            
        Returns:
            Tuple of (json_string, end_position) or (None, start_pos+1) if invalid
        """
        if start_pos >= len(text) or text[start_pos] != '{':
            return None, start_pos + 1
        
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        i = start_pos
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                escape_next = False
                i += 1
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                i += 1
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                i += 1
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the end of the JSON object
                        json_str = text[start_pos:i+1]
                        return json_str, i + 1
                    elif brace_count < 0:
                        # Unbalanced braces
                        return None, start_pos + 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count < 0:
                        # Unbalanced brackets
                        return None, start_pos + 1
            
            i += 1
        
        # Reached end of text without closing the object
        return None, start_pos + 1
    
    def extract_json_objects_with_errors(self, text: str, 
                                       filter_func: Optional[Callable] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract JSON objects and collect parsing errors with suggestions using balanced brace parsing."""
        objects = []
        errors = []
        
        # First, check for JSON in code blocks
        code_block_pattern = r'```(?:json)?\s*(\{[^`]+\})\s*```'
        for match in re.finditer(code_block_pattern, text, re.DOTALL):
            json_str = match.group(1)
            try:
                obj = self.processor.loads(json_str)
                if isinstance(obj, dict):
                    if filter_func is None or filter_func(obj):
                        objects.append(obj)
            except JSONParseError as e:
                errors.append({
                    'json_str': json_str[:200] + ('...' if len(json_str) > 200 else ''),
                    'error': str(e),
                    'suggestion': e.suggestion,
                    'position': match.start(),
                    'location': 'code_block'
                })
                
                # Try to fix and extract anyway
                fixed_json = self._attempt_fix(json_str)
                if fixed_json:
                    try:
                        obj = self.processor.loads(fixed_json)
                        if isinstance(obj, dict):
                            if filter_func is None or filter_func(obj):
                                objects.append(obj)
                                # Mark as fixed
                                errors[-1]['fixed'] = True
                                errors[-1]['fixed_json'] = fixed_json
                    except JSONParseError:
                        pass
        
        # Extract JSON objects using balanced brace parsing
        extracted_strings = self._extract_balanced_json_strings(text)
        
        for json_str in extracted_strings:
            # Skip if this was already found in a code block
            if any(json_str in str(obj) for obj in objects):
                continue
                
            try:
                obj = self.processor.loads(json_str)
                if isinstance(obj, dict):
                    if filter_func is None or filter_func(obj):
                        # Avoid duplicates
                        if obj not in objects:
                            objects.append(obj)
            except JSONParseError as e:
                errors.append({
                    'json_str': json_str[:200] + ('...' if len(json_str) > 200 else ''),
                    'error': str(e),
                    'suggestion': e.suggestion,
                    'position': text.find(json_str),
                    'location': 'inline'
                })
                
                # Try to fix and extract anyway
                fixed_json = self._attempt_fix(json_str)
                if fixed_json:
                    try:
                        obj = self.processor.loads(fixed_json)
                        if isinstance(obj, dict):
                            if filter_func is None or filter_func(obj):
                                if obj not in objects:
                                    objects.append(obj)
                                    # Mark as fixed
                                    errors[-1]['fixed'] = True
                                    errors[-1]['fixed_json'] = fixed_json
                    except JSONParseError:
                        pass
        
        return objects, errors
    
    def extract_event_json(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON objects that look like event emissions."""
        def is_event(obj):
            return isinstance(obj, dict) and 'event' in obj
        
        return self.extract_json_objects(text, filter_func=is_event)
    
    def _attempt_fix(self, json_str: str) -> Optional[str]:
        """Attempt to fix common JSON issues."""
        # Remove trailing commas
        fixed = re.sub(r',\s*}', '}', json_str)
        fixed = re.sub(r',\s*]', ']', fixed)
        
        # Fix single quotes to double quotes (simple cases)
        fixed = re.sub(r"'([^']*)':", r'"\1":', fixed)
        fixed = re.sub(r":\s*'([^']*)'", r': "\1"', fixed)
        
        # Remove control characters
        fixed = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', fixed)
        
        return fixed if fixed != json_str else None


# Global instances for convenience
_default_processor = JSONProcessor()
_default_extractor = JSONExtractor(_default_processor)

# Convenience functions
def loads(content: str) -> Any:
    """Parse JSON string - enhanced version of json.loads()."""
    return _default_processor.loads(content)

def dumps(data: Any, sanitize_dates: bool = True) -> str:
    """Convert data to JSON string - enhanced version of json.dumps()."""
    return _default_processor.dumps(data, sanitize_dates=sanitize_dates)

def load_json_file(file_path: Union[str, Path]) -> Any:
    """Load JSON from file - enhanced version of file_utils function."""
    return _default_processor.load_file(file_path)

def save_json_file(file_path: Union[str, Path], data: Any,
                   create_dirs: bool = True, atomic: bool = True) -> None:
    """Save data to JSON file - enhanced version of file_utils function."""
    _default_processor.save_file(file_path, data, create_dirs=create_dirs, atomic=atomic)

def extract_json_objects(text: str, filter_func: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Extract all valid JSON objects from text."""
    return _default_extractor.extract_json_objects(text, filter_func=filter_func)

def extract_json_objects_with_errors(text: str, 
                                   filter_func: Optional[Callable] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract JSON objects and collect parsing errors with suggestions."""
    return _default_extractor.extract_json_objects_with_errors(text, filter_func=filter_func)

def extract_event_json(text: str) -> List[Dict[str, Any]]:
    """Extract JSON objects that look like event emissions."""
    return _default_extractor.extract_event_json(text)

def validate_json_structure(data: Any, required_keys: List[str], 
                          optional_keys: List[str] = None) -> bool:
    """Validate JSON structure has required keys."""
    if not isinstance(data, dict):
        return False
        
    optional_keys = optional_keys or []
    all_allowed_keys = set(required_keys + optional_keys)
    data_keys = set(data.keys())
    
    # Check required keys exist
    if not all(key in data_keys for key in required_keys):
        return False
        
    # Check no unexpected keys
    if not data_keys.issubset(all_allowed_keys):
        return False
        
    return True

def format_json_for_logging(data: Any, max_length: int = 1000) -> str:
    """Format JSON for logging with length limits."""
    try:
        json_str = dumps(data, sanitize_dates=True)
        if len(json_str) > max_length:
            return json_str[:max_length] + "... (truncated)"
        return json_str
    except Exception:
        return str(data)[:max_length]

def merge_json_objects(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge JSON objects."""
    def _deep_merge(base_obj: Dict[str, Any], override_obj: Dict[str, Any]) -> Dict[str, Any]:
        result = base_obj.copy()
        for key, value in override_obj.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    return _deep_merge(base, override)


def parse_json_parameter(data: Dict[str, Any], param_name: str, 
                        merge_into_data: bool = True, 
                        remove_original: bool = True) -> Optional[Dict[str, Any]]:
    """Parse a parameter that might be a JSON string and optionally merge it into data.
    
    This handles parameters from external sources that might be JSON strings:
    - CLI: --filter '{"type": "orchestration"}'
    - Agents: When they emit events with JSON in their responses
    - MCP servers: Following system parameter guidelines
    - External APIs: WebSocket/HTTP clients sending structured data
    
    Args:
        data: Dictionary containing the parameter
        param_name: Name of the parameter to parse
        merge_into_data: If True, merge parsed JSON into data dict
        remove_original: If True, remove the original string parameter after parsing
        
    Returns:
        Parsed JSON object or None if parameter not found or not a string
        
    Example:
        data = {"filter": '{"type": "orchestration"}', "limit": 10}
        parse_json_parameter(data, "filter")
        # data is now: {"type": "orchestration", "limit": 10}
    """
    if param_name not in data:
        return None
        
    param_value = data[param_name]
    
    # Only process if it's a string
    if not isinstance(param_value, str):
        return None
        
    try:
        parsed_obj = loads(param_value)
        
        # If it's a dict and merge_into_data is True, merge it
        if isinstance(parsed_obj, dict) and merge_into_data:
            # Remove the original parameter first to avoid conflicts
            if remove_original:
                data.pop(param_name, None)
            # Merge the parsed object into data
            data.update(parsed_obj)
            
        return parsed_obj
        
    except JSONParseError as e:
        logger.warning(f"Invalid JSON in {param_name} parameter: {param_value[:100]}")
        logger.debug(f"JSON parse error: {e}")
        return None


# Specialized processors for different use cases
class EventJSONProcessor(JSONProcessor):
    """JSON processor optimized for event data."""
    
    def __init__(self):
        super().__init__(ensure_ascii=False, indent=None, sort_keys=False)
        
    def validate_event_structure(self, event: Dict[str, Any]) -> bool:
        """Validate event JSON structure."""
        required_keys = ['event']
        optional_keys = ['data', 'timestamp', 'context', 'metadata']
        return validate_json_structure(event, required_keys, optional_keys)


class ConfigJSONProcessor(JSONProcessor):
    """JSON processor optimized for configuration data."""
    
    def __init__(self):
        super().__init__(ensure_ascii=False, indent=2, sort_keys=True)


# Export specialized processors
event_json = EventJSONProcessor()
config_json = ConfigJSONProcessor()