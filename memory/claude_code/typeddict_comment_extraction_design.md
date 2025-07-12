# TypedDict Comment Extraction Enhancement Design

## Goal
Extract inline comments from TypedDict field definitions to provide rich parameter descriptions in discovery output.

## Implementation Plan

### 1. Enhance TypeAnalyzer._extract_field_description()

Current implementation only looks in docstrings. We need to:
1. Get the source code of the TypedDict class
2. Parse it with AST
3. Match field definitions with their inline comments

```python
def _extract_field_description(self, td_class: Type[TypedDict], field_name: str) -> Optional[str]:
    """Extract field description from inline comments or docstring."""
    # First try existing docstring approach
    if td_class.__doc__:
        # ... existing code ...
    
    # New: Extract from inline comments
    try:
        source = inspect.getsource(td_class)
        tree = ast.parse(source)
        
        # Find the ClassDef node
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == td_class.__name__:
                # Look for AnnAssign nodes (field: Type annotations)
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        if stmt.target.id == field_name:
                            # Found our field, extract comment
                            return self._extract_inline_comment_from_line(
                                source.splitlines(), 
                                stmt.lineno
                            )
    except Exception as e:
        logger.debug(f"Failed to extract inline comment for {field_name}: {e}")
    
    return None
```

### 2. Merge TypedDict and AST Analysis in discovery.py

Instead of either/or, we should merge:

```python
# In handle_discover():
if include_detail:
    # Always try type-based discovery first
    type_metadata = type_analyze_handler(handler.func)
    
    # Always run AST analysis for additional info
    ast_analysis = analyze_handler(handler.func, event_name)
    
    if type_metadata and type_metadata.get('parameters'):
        # Start with type-based parameters (accurate types)
        handler_info['parameters'] = type_metadata['parameters']
        
        # Enhance with AST-discovered info
        ast_params = ast_analysis.get('parameters', {})
        for param_name, ast_info in ast_params.items():
            if param_name in handler_info['parameters']:
                # Merge descriptions if AST has one and TypedDict doesn't
                if ast_info.get('comment') and not handler_info['parameters'][param_name].get('description'):
                    handler_info['parameters'][param_name]['description'] = ast_info['comment']
            else:
                # Parameter found by AST but not TypedDict (shouldn't happen, but handle it)
                handler_info['parameters'][param_name] = {
                    'type': 'Any',
                    'required': ast_info.get('required', False),
                    'description': ast_info.get('comment')
                }
        
        # Always get triggers from AST
        handler_info['triggers'] = ast_analysis.get('triggers', [])
    else:
        # Fallback to pure AST analysis
        handler_info.update(ast_analysis)
```

### 3. Handle Edge Cases

1. **TypedDict fields with complex annotations:**
   ```python
   session_id: NotRequired[str]  # Session ID for conversation continuity
   ```

2. **Multi-line field definitions:**
   ```python
   messages: NotRequired[
       List[Dict[str, Any]]
   ]  # Conversation messages
   ```

3. **Comments on subsequent lines:**
   ```python
   prompt: NotRequired[str]
   # Initial prompt to send to the agent
   ```

## Benefits of Merging

1. **Complete Information**: Types from TypedDict + descriptions from both sources + triggers from AST
2. **Redundancy**: If one system misses something, the other might catch it
3. **Evolution Path**: We can enhance either system independently
4. **Backwards Compatible**: Works with handlers that haven't migrated to TypedDict yet

## Example Output After Enhancement

```bash
ksi help agent:spawn

agent:spawn
Spawn a new agent.

Parameters:
  --profile: str (required)
      Profile name
  --agent_id: str (optional)
      Agent ID (auto-generated if not provided)
  --session_id: str (optional)
      Session ID for conversation continuity
  --context: dict[str, Any] (optional)
      Additional context

Triggers:
  - agent:created
  - observation:subscribe
  - completion:async
```

## Implementation Priority

1. **Phase 1**: Enhance type_discovery.py to extract inline comments (High Priority)
2. **Phase 2**: Modify discovery.py to merge both analyses (High Priority)
3. **Phase 3**: Add tests to ensure both systems work together (Medium Priority)
4. **Phase 4**: Optimize performance if needed (Low Priority)