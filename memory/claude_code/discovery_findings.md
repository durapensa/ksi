# KSI Discovery System Analysis

## Overview
The KSI discovery system is implemented in `ksi_daemon/core/discovery.py` and `discovery_utils.py`. It provides automatic parameter extraction and documentation for event handlers using AST analysis.

## Core Implementation

### Parameter Extraction
The discovery system uses AST analysis in `HandlerAnalyzer` class to extract parameters from event handlers by looking for:
1. `data.get('param_name', default)` calls - extracts parameter name, default value, and required status
2. `data['param_name']` subscript access - marks as required parameter
3. Inline comments after data.get() calls - used as parameter descriptions
4. Docstring parsing for additional parameter documentation

### Current Capabilities
- Automatic parameter discovery from code
- Multiple output formats (verbose, compact, ultra_compact, mcp, json_schema)
- Inline comment extraction for parameter descriptions
- Docstring parsing for parameter documentation
- Event trigger detection
- Usage example generation

## Module Documentation Quality Analysis

### Well-Documented Modules

#### 1. Evaluation Module (`ksi_daemon/evaluation/prompt_evaluation.py`)
**Good Practices:**
- Uses TypedDict for type-safe parameter definitions
- Extensive inline comments on data.get() calls
- Clear parameter descriptions in comments
- Example: `model = data.get('model', 'claude-cli/sonnet')  # Model for testing`

**Discovery Output Quality:**
```json
"parameters": {
  "model": {
    "type": "Any",
    "required": false,
    "default": "claude-cli/sonnet",
    "description": "Model for testing"
  }
}
```

#### 2. Composition Module (`ksi_daemon/composition/composition_service.py`)
**Good Practices:**
- TypedDict definitions for each event handler
- Inline comments for complex parameters
- Clear docstrings for handlers
- Example: `test_options = data.get('test_options', {})  # Test results and metrics`

### Poorly-Documented Modules

#### 1. Agent Service (`ksi_daemon/agent/agent_service.py`)
**Issues:**
- Has TypedDict definitions but handler doesn't use them as type hints
- No inline comments on data.get() calls
- Generic parameter descriptions in discovery output
- Example: `agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"`

**Discovery Output Quality:**
```json
"parameters": {
  "agent_id": {
    "type": "Any",
    "required": true,
    "description": "agent_id parameter"  // Generic description
  }
}
```

## Key Differences Between Well vs Poorly Documented Modules

### 1. Type Annotations
- **Good**: `async def handle_prompt_evaluate(data: PromptEvaluationData) -> Dict[str, Any]:`
- **Poor**: `async def handle_spawn_agent(data: Dict[str, Any]) -> Dict[str, Any]:`

### 2. Inline Comments
- **Good**: `model = data.get('model', 'claude-cli/sonnet')  # Model for testing`
- **Poor**: `agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"`

### 3. Parameter Documentation in Docstrings
- **Good**: Docstrings with Parameters sections
- **Poor**: Brief docstrings without parameter details

## Discovery Enhancement Opportunities

### 1. TypedDict Integration
The discovery system could be enhanced to:
- Extract parameter information from TypedDict definitions when handlers use them as type hints
- Get parameter types, descriptions from TypedDict docstrings
- Mark required vs NotRequired fields correctly

### 2. Enhanced Comment Parsing
- Look for comments on lines above data.get() calls
- Parse parameter descriptions from block comments
- Extract validation rules from comments

### 3. Type Information
Currently all parameters show as "type": "Any". The system could:
- Extract types from TypedDict definitions
- Infer types from default values
- Parse type hints from docstrings

### 4. Validation Information
Discovery could extract:
- Allowed values from inline comments or docstrings
- Value constraints (min/max, regex patterns)
- Mutually exclusive parameters

### 5. Examples Enhancement
- Generate better examples based on parameter types
- Include multiple examples for complex events
- Show examples with different parameter combinations

## Specific Module Patterns

### Conversation Service
- Uses TypedDict but not as handler type hints
- Good inline comments: `sort_by = data.get('sort_by', 'last_timestamp')  # or 'first_timestamp', 'message_count'`
- Shows allowed values in comments

### Config Service
- Comprehensive TypedDict definitions
- Less inline documentation
- Could benefit from type hint usage

### MCP Service
- Minimal parameter usage
- Simple event handlers
- Good example of focused functionality

## Recommendations for Module Authors

1. **Always use TypedDict as type hints** for event handlers
2. **Add inline comments** after every data.get() call
3. **Include Parameters section** in handler docstrings
4. **Document allowed values** in comments or docstrings
5. **Provide validation rules** where applicable

## Technical Debt

1. Discovery system doesn't use TypedDict information even when available
2. Type extraction is limited to "Any" for all parameters
3. No validation rule extraction
4. Limited example generation logic

## Next Steps

1. Enhance discovery to read TypedDict definitions
2. Improve type inference from defaults and context
3. Add validation rule extraction
4. Generate richer examples based on parameter metadata