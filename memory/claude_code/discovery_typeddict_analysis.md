# Discovery System TypedDict Analysis

## Current State of Discovery System

### What TypedDict Provides

1. **Type Information**: The discovery system successfully extracts:
   - Parameter types (including complex types like `Literal`, `Optional`, `Union`)
   - Required vs optional fields (using `Required`/`NotRequired` or TypedDict's `__required_keys__`)
   - Allowed values for `Literal` types (e.g., `agent_type: Literal['construct', 'system', 'user']`)

2. **Inline Comments**: TypedDict fields have inline comments that describe parameters:
   ```python
   class AgentSpawnData(TypedDict):
       profile: Required[str]  # Profile name
       agent_id: NotRequired[str]  # Agent ID (auto-generated if not provided)
       session_id: NotRequired[str]  # Session ID for conversation continuity
   ```

### What We're Missing

1. **Inline Comment Extraction**: The current `type_discovery.py` has a method `_extract_field_description` but it only looks in the TypedDict class docstring, NOT inline comments. The `discovery_utils.py` HAS working AST-based inline comment extraction, but it's NOT USED when TypedDict analysis succeeds.

2. **Discovery Flow Problem**: 
   - When `type_analyze_handler` (from type_discovery.py) finds parameters, it's used exclusively
   - AST analysis (which extracts inline comments) is only used as a fallback
   - This means TypedDict handlers lose their inline comment descriptions

3. **Rich Parameter Documentation**: Pre-migration handlers had structured docstrings like:
   ```python
   """
   Evaluate a prompt's response using LLM-as-Judge.
   
   Parameters:
       prompt: The prompt that was sent
       response: The response to evaluate
       criteria: List of evaluation criteria
       judge_model: Model to use as judge (default: claude-cli/sonnet)
   """
   ```
   
   This provided more detailed descriptions than inline comments allow.

3. **Usage Examples**: The old docstring format could include examples and detailed usage guidance that doesn't fit in inline comments.

## Discovery System Components

1. **type_discovery.py** (`ksi_daemon/core/type_discovery.py`):
   - Analyzes TypedDict definitions using runtime type introspection
   - Extracts types, required fields, literal values
   - Does NOT currently extract inline comments (has placeholder for enhancement)

2. **discovery_utils.py** (`ksi_daemon/core/discovery_utils.py`): 
   - Has AST-based analysis including `_extract_inline_comment` method
   - Can parse source files to extract inline comments
   - Supports multiple output formats (verbose, compact, MCP, JSON Schema)

## Current Discovery Output

The discovery system IS showing parameter descriptions for some events, suggesting that either:
1. The AST-based extraction is being used in some cases
2. Some handlers still have the old docstring format
3. Descriptions are being provided another way

Example output shows descriptions are present:
```
Parameters:
  --profile: str (required)
  --agent_id: str (optional)
  --session_id: str (optional)
  ...
```

## Recommendations

1. **Enhance type_discovery.py**: Integrate AST-based inline comment extraction from discovery_utils.py into the TypedDict analyzer

2. **Support Extended Descriptions**: For parameters needing more documentation than fits in inline comments, consider:
   - TypedDict class docstrings with structured format
   - Separate documentation metadata
   - Enhanced comment syntax (e.g., multiline comments)

3. **Preserve Important Documentation**: For handlers losing critical usage guidance, either:
   - Keep some docstring content for complex handlers
   - Move detailed docs to TypedDict class docstrings
   - Create a documentation companion system

## Key Findings

After investigation, we found:

1. **TypedDict analysis works** - extracts types, required fields, literal values correctly
2. **Inline comments exist** in TypedDict definitions but are NOT extracted
3. **AST analysis CAN extract inline comments** but is bypassed when TypedDict succeeds
4. **Old handlers with docstring Parameters:** sections still show descriptions
5. **New TypedDict handlers** show no parameter descriptions

## Solution Options

1. **Quick Fix**: Modify discovery.py to merge TypedDict and AST analysis:
   ```python
   # Instead of using TypedDict OR AST, use TypedDict AND enhance with AST comments
   type_metadata = type_analyze_handler(handler.func)
   ast_analysis = analyze_handler(handler.func, event_name)
   # Merge AST comments into TypedDict parameters
   ```

2. **Better Fix**: Enhance type_discovery.py to extract inline comments using AST
   - Add source code analysis to TypedDict analyzer
   - Extract comments from the TypedDict class definition
   - Preserve the single source of truth

3. **Alternative**: Use TypedDict docstrings for parameter documentation:
   ```python
   class AgentSpawnData(TypedDict):
       """
       Spawn agent parameters.
       
       profile: Profile name to use for the agent
       agent_id: Agent ID (auto-generated if not provided)
       session_id: Session ID for conversation continuity
       """
   ```

## Immediate Action Needed

The discovery system is currently missing parameter descriptions for all TypedDict-migrated handlers. This impacts:
- CLI help output
- API documentation
- Developer experience

We should implement the quick fix first to restore descriptions, then work on the better solution.