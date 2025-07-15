# KSI Discovery System Enhancements for CLI Integration

## Executive Summary

The KSI discovery system is sophisticated but needs specific enhancements to enable dynamic CLI generation. Based on testing ksi-cli-click, here are targeted improvements that would make CLI tools self-configuring and dramatically more usable.

## Current State Analysis

### What Works Well
- TypedDict parameter extraction
- AST-based example mining  
- Multiple output formats (verbose, compact, ultra_compact, mcp)
- Parameter type introspection

### Critical Gaps for CLI
1. **Parameter discovery failing** - Events show `"parameters": {}` despite having TypedDict definitions
2. **No CLI metadata** - Missing flags vs options vs arguments guidance
3. **No parameter relationships** - No mutual exclusion or dependency info
4. **No shell completion data** - Missing dynamic value completion hints
5. **Limited client-side validation** - Can't validate before network call

## Proposed Enhancements

### 1. Fix Parameter Discovery (Critical)

**Problem**: `monitor:get_status` has rich TypedDict but discovery returns empty parameters.

**Root Cause**: The `UnifiedHandlerAnalyzer` may not be finding the TypedDict class correctly.

**Solution**: Enhance TypedDict discovery in `discovery.py`:

```python
class EnhancedUnifiedHandlerAnalyzer(UnifiedHandlerAnalyzer):
    def _find_typed_dict_class(self):
        """Enhanced TypedDict discovery with better fallback strategies."""
        # Strategy 1: Type hints (current)
        result = super()._find_typed_dict_class()
        if result:
            return result
            
        # Strategy 2: Look for class name patterns
        handler_name = self.func.__name__
        if handler_name.startswith('handle_'):
            event_part = handler_name[7:]  # Remove 'handle_'
            possible_class_names = [
                f"{event_part.title()}Data",
                f"{event_part.title().replace('_', '')}Data",
                f"{''.join(word.title() for word in event_part.split('_'))}Data"
            ]
            
            func_globals = getattr(self.func, '__globals__', {})
            for class_name in possible_class_names:
                if class_name in func_globals:
                    candidate = func_globals[class_name]
                    if is_typeddict(candidate):
                        return candidate
        
        # Strategy 3: Search module for TypedDict classes
        import inspect
        module = inspect.getmodule(self.func)
        if module:
            for name, obj in inspect.getmembers(module):
                if is_typeddict(obj) and event_part.lower() in name.lower():
                    return obj
                    
        return None
```

### 2. Add CLI-Specific Metadata

**Enhancement**: Extend discovery to include CLI hints:

```python
class CLIMetadata(TypedDict):
    """CLI-specific metadata for parameters."""
    cli_type: Literal['flag', 'option', 'argument']  # How to present in CLI
    cli_name: NotRequired[str]  # Override parameter name for CLI
    cli_short: NotRequired[str]  # Short form (-v for --verbose)
    cli_hidden: NotRequired[bool]  # Hide from CLI (internal params)
    cli_group: NotRequired[str]  # Group related options together
    mutual_exclusive: NotRequired[List[str]]  # Mutually exclusive with these params
    requires: NotRequired[List[str]]  # Requires these other parameters
    completion_type: NotRequired[str]  # Shell completion hint ('file', 'choice', 'command')
    completion_values: NotRequired[List[str]]  # Static completion values

# Enhanced parameter info
class EnhancedParameterInfo(TypedDict):
    type: str
    required: bool
    description: str
    default: NotRequired[Any]
    allowed_values: NotRequired[List[Any]]
    cli: NotRequired[CLIMetadata]  # CLI-specific metadata
```

**Usage in TypedDict definitions**:

```python
class MonitorGetStatusData(TypedDict):
    """Get consolidated KSI daemon status including recent events and agent info."""
    event_patterns: NotRequired[List[str]]  # Event name patterns (supports wildcards) [CLI:option,completion:event]
    since: NotRequired[Union[str, float]]  # Start time for events [CLI:option,completion:datetime]  
    limit: NotRequired[int]  # Maximum number of events to return (default: 20) [CLI:option,range:1-1000]
    include_agents: NotRequired[bool]  # Include agent status (default: True) [CLI:flag]
    include_events: NotRequired[bool]  # Include recent events (default: True) [CLI:flag]
```

### 3. Dynamic CLI Command Generation

**Enhancement**: Add endpoint to generate CLI command definitions:

```python
@event_handler("system:cli_metadata")
async def handle_cli_metadata(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate CLI metadata for dynamic command generation."""
    from ksi_common.event_parser import event_format_linter
    
    class SystemCLIMetadataData(TypedDict):
        event: NotRequired[str]  # Specific event (optional)
        namespace: NotRequired[str]  # Filter by namespace (optional)
        format: NotRequired[Literal['click', 'argparse', 'typer']]  # CLI framework format
    
    data = event_format_linter(raw_data, SystemCLIMetadataData)
    format_type = data.get('format', 'click')
    
    # Generate CLI-specific metadata
    cli_commands = {}
    
    for event_name, handlers in router._handlers.items():
        if data.get('event') and event_name != data['event']:
            continue
        if data.get('namespace') and not event_name.startswith(f"{data['namespace']}:"):
            continue
            
        handler = handlers[0]
        analyzer = EnhancedUnifiedHandlerAnalyzer(handler.func, event_name=event_name)
        analysis = analyzer.analyze()
        
        # Convert to CLI framework format
        if format_type == 'click':
            cli_commands[event_name] = {
                'click_options': _generate_click_options(analysis['parameters']),
                'click_arguments': _generate_click_arguments(analysis['parameters']),
                'validation_rules': _generate_click_validation(analysis['parameters'])
            }
    
    return event_response_builder({
        'cli_commands': cli_commands,
        'format': format_type
    }, context=context)
```

### 4. Client-Side Parameter Validation

**Enhancement**: Add validation utilities for CLI:

```python
class ParameterValidator:
    """Client-side parameter validation using discovery metadata."""
    
    def __init__(self, event_name: str, discovery_client):
        self.event_name = event_name
        self.client = discovery_client
        self._parameters = None
    
    async def get_parameters(self):
        """Lazy load parameter metadata."""
        if self._parameters is None:
            result = await self.client.send_single("system:help", {"event": self.event_name})
            self._parameters = result.get('parameters', {})
        return self._parameters
    
    async def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate parameters before sending to daemon."""
        params = await self.get_parameters()
        errors = []
        
        # Check required parameters
        for name, info in params.items():
            if info.get('required', False) and name not in data:
                errors.append(f"Required parameter missing: {name}")
        
        # Check allowed values
        for name, value in data.items():
            if name in params:
                param_info = params[name]
                if 'allowed_values' in param_info:
                    if value not in param_info['allowed_values']:
                        errors.append(f"Invalid value for {name}: {value}. Allowed: {param_info['allowed_values']}")
                
                # Check type constraints
                if 'min_value' in param_info and isinstance(value, (int, float)):
                    if value < param_info['min_value']:
                        errors.append(f"Value for {name} too small: {value} < {param_info['min_value']}")
        
        return len(errors) == 0, errors
```

### 5. Enhanced ksi-cli-click with Dynamic Parameter Registration

**Enhancement**: Update ksi-cli-click to use discovery for dynamic command generation:

```python
async def create_dynamic_click_command(event_name: str, client: KSIClickClient):
    """Create a Click command dynamically based on discovery."""
    # Get parameter metadata
    help_result = await client.send_event("system:help", {"event": event_name})
    parameters = help_result.get('parameters', {})
    
    # Create Click options dynamically
    options = []
    for param_name, param_info in parameters.items():
        param_type = param_info.get('type', 'str')
        required = param_info.get('required', False)
        default = param_info.get('default')
        help_text = param_info.get('description', f'{param_name} parameter')
        
        # Convert to Click option
        if param_info.get('cli', {}).get('cli_type') == 'flag':
            option = click.option(f'--{param_name}', is_flag=True, help=help_text)
        elif 'allowed_values' in param_info:
            option = click.option(f'--{param_name}', 
                                type=click.Choice(param_info['allowed_values']),
                                required=required, default=default, help=help_text)
        else:
            # Determine Click type from parameter type
            click_type = {
                'int': int, 'float': float, 'bool': bool, 'str': str,
                'Path': click.Path(), 'File': click.File()
            }.get(param_type, str)
            
            option = click.option(f'--{param_name}', type=click_type,
                                required=required, default=default, help=help_text)
        
        options.append(option)
    
    return options
```

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. Fix parameter discovery for existing TypedDict classes
2. Add basic CLI metadata parsing from comments

### Phase 2: CLI Framework Integration (Short-term)  
3. Implement `system:cli_metadata` endpoint
4. Add client-side validation utilities
5. Create dynamic Click command generation

### Phase 3: Advanced Features (Medium-term)
6. Shell completion integration
7. Parameter relationship validation
8. Advanced CLI metadata support

## Benefits

### For Users
- **Self-documenting CLI** - Help text automatically reflects KSI capabilities
- **Better error messages** - Client-side validation with helpful hints
- **Shell completion** - Dynamic completion for parameters and values
- **Consistent interface** - All KSI events follow same CLI patterns

### For Developers  
- **No CLI maintenance** - CLI automatically updates when events change
- **Reduced duplication** - Single source of truth for parameter definitions
- **Better testing** - CLI can validate parameters match actual event handlers
- **Easier experimentation** - New events immediately available in CLI

## Example Usage After Enhancements

```bash
# Dynamic parameter discovery works
ksi-cli-click help monitor:get_status
# Shows: --limit (int), --namespace (str), --include-agents (flag), etc.

# Client-side validation  
ksi-cli-click send monitor:get_status --limit abc
# Error: Invalid value for limit: abc. Expected integer.

# Shell completion
ksi-cli-click send completion:async --model <TAB>
# Shows: sonnet, haiku, opus, gpt-4, etc.

# Auto-generated commands
ksi-cli-click monitor get-status --limit 5 --include-agents
# Equivalent to: ksi send monitor:get_status --limit 5 --include_agents true
```

This enhancement would make KSI CLI tools self-configuring, dramatically more usable, and require virtually no maintenance as the system evolves.