# Discovery System Enhancement Progress

## Current Status

### ✅ Completed
1. **TypedDict type extraction** - Successfully extracting types like `str`, `bool`, `List[Dict[str, Any]]`
2. **Basic implementation** - AST analysis enhanced with TypedDict support
3. **Type resolution** - Converting AST annotations to readable type strings

### 🔧 Issues Found
1. **Inline comments not extracted** - Comments like `# List of composition names to compare` not showing up
2. **TypedDict parameter mixing** - Parameters from one handler's TypedDict appearing in other handlers
3. **Generic descriptions** - Still showing "parameter_name parameter" instead of inline comments

### 📊 Test Results

**evaluation:prompt with TypedDict:**
- ✅ Shows `composition_name` as type `str`, required=true
- ✅ Shows `test_prompts` as type `List[Dict[str, Any]]`
- ❌ Not showing inline comment descriptions
- ❌ Mixing in parameters from other handlers

**evaluation:compare without TypedDict:**
- ❌ All types still show as "Any"
- ❌ Not extracting inline comments
- ❌ Showing TypedDict fields from other handlers

## Root Causes

1. **Inline comment issue**: The HandlerAnalyzer is initialized with source lines from the handler function, but when extracting comments, it needs the exact line numbers to match up
2. **TypedDict mixing**: The `get_typed_dict_params` method is looking at all TypedDicts in the module, not just the one used by the specific handler
3. **Source line mismatch**: Function source starts at different line than in file, causing comment extraction to fail

## Next Steps

1. Fix source line offset calculation for inline comments
2. Properly associate TypedDict with specific handler based on parameter annotation
3. Test with handlers that have inline comments and proper TypedDict usage
4. Add validation pattern parsing once comments are working