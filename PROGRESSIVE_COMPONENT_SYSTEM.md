# Progressive Component System

Comprehensive documentation for KSI's progressive component system architecture, evolution, and the critical JSON extraction system fix.

## System Overview

The Progressive Component System is KSI's foundational architecture for managing reusable AI agent components with support for:
- **Persona-First Design**: Domain experts with system communication capabilities
- **Model-Aware Development**: Components optimized for specific Claude models
- **Git-Based Versioning**: Branch-based optimization and compatibility metadata
- **Event-Driven Integration**: Complete KSI system integration via JSON event emission

## Architecture Phases

### Phase 1: Basic Component Support ✅
- Component creation via KSI events
- Markdown file storage and indexing
- Basic frontmatter parsing

### Phase 2: Enhanced Rendering ✅
- Recursive mixin resolution
- Variable substitution with complex data types
- Circular dependency detection
- Performance optimization with caching

### Phase 3: Advanced Features ✅
- SQLite composition index as source of truth
- Git-based model compatibility metadata
- Streaming event architecture integration
- Component usage analytics

### Phase 4: JSON Extraction System Fix ✅
- **Critical breakthrough**: Fixed fundamental JSON parsing limitation
- Enhanced balanced brace parsing for arbitrary nesting levels
- Comprehensive error feedback system
- Component upgrades to use legitimate KSI events

## Critical Discovery: JSON Extraction System Limitation

### The Problem (2025-07-18)

**Root Cause**: The JSON extraction system had a fundamental limitation that prevented consistent agent behavior.

**Technical Issue**:
- **Regex Pattern Limitation**: Original pattern `r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'` could only handle 1 level of nesting
- **Legitimate KSI Events**: Have 3 levels of nesting:
  ```json
  {
    "event": "state:entity:update",
    "data": {
      "id": "agent_123_progress",
      "properties": {
        "percent": 50,
        "stage": "analysis",
        "findings": "data_quality_good"
      }
    }
  }
  ```
- **Silent Failures**: Complex events were ignored without error messages, causing inconsistent agent behavior

### The Solution (2025-07-18)

**Enhanced JSON Extraction with Balanced Brace Parsing**:

1. **New Architecture**: Created `ksi_common/json_utils.py` with `JSONExtractor` class
2. **Balanced Brace Parsing**: `_extract_balanced_object()` method handles arbitrary nesting levels
3. **Error Feedback**: Comprehensive error responses sent back to agents via `agent:json_extraction_error`
4. **Backward Compatibility**: Maintains existing API while fixing core limitation

**Key Technical Implementation**:
```python
def _extract_balanced_object(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
    """Extract a balanced JSON object starting at the given position."""
    if start_pos >= len(text) or text[start_pos] != '{':
        return None, start_pos + 1
    
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    
    # ... balanced brace parsing algorithm ...
    
    return json_str, i + 1
```

### Component Upgrades

**Components Fixed**: All old components updated to use legitimate KSI system events:

- `components/agents/ksi_aware_analyst` ✅
- `components/agents/optimized_ksi_analyst` ✅
- `components/agents/prefill_optimized_analyst` ✅ 
- `components/agents/xml_structured_analyst` ✅

**Event Migration**:
- ❌ **Before**: Non-existent `analyst:*` events (`analyst:initialized`, `analyst:progress`, `analyst:findings`, `analyst:complete`)
- ✅ **After**: Legitimate KSI events (`agent:status`, `state:entity:update`, `message:publish`)

**Example Corrected Component Pattern**:
```markdown
<legitimate_events>
**When starting work, emit agent status:**
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}

**For progress updates, use state system:**
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 25, "stage": "data_loading", "findings": "initial_data_quality_check"}}}

**To message system (if no spawning agent):**
{"event": "message:publish", "data": {"agent_id": "{{agent_id}}", "event_type": "DIRECT_MESSAGE", "message": {"to": "system", "content": "Analysis complete: correlation coefficient 0.85"}}}

**When completing work:**
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "analysis", "result": "success"}}
</legitimate_events>
```

### Validation Results

**Technical Validation**:
- ✅ **JSON Extraction Working**: Successfully extracts deeply nested KSI events
- ✅ **Agent Events Captured**: Monitor shows events with `_extracted_from_response: true`
- ✅ **System Integration**: Events flow correctly through KSI monitoring system
- ✅ **Error Feedback**: Malformed JSON triggers comprehensive error responses

**Behavioral Validation**:
```bash
# Test agent spawning with corrected component
ksi send agent:spawn_from_component --component "components/agents/corrected_ksi_analyst" \
  --prompt "Please analyze the current system status and emit legitimate KSI events"

# Verify events are extracted
ksi send monitor:get_events --event-patterns "agent:*" --limit 10
# Result: Multiple agent:status events with _extracted_from_response: true
```

## Persona-First Architecture

### Core Principle

**Revolutionary Insight**: Agents are **Claude adopting personas**, not separate AI systems.

**Architecture Design**:
1. **Pure Personas**: Domain experts without system awareness
2. **KSI Capabilities**: Minimal communication mixins
3. **Combined Components**: Authentic expertise + system integration

### Component Structure

**Base Personas** (Domain Expertise):
```bash
components/personas/universal/data_analyst.md
components/personas/universal/researcher.md
components/personas/universal/coordinator.md
```

**KSI Capabilities** (System Integration):
```bash
components/capabilities/claude_code_1.0.x/ksi_json_reporter.md
components/capabilities/claude_code_1.0.x/multi_agent_coordinator.md
```

**Combined Agents** (Complete System):
```bash
components/agents/ksi_aware_analyst.md
components/agents/multi_agent_orchestrator.md
```

### Benefits

- **Natural Behavior**: Claude acts as genuine domain expert
- **Effective Communication**: JSON becomes natural reporting, not forced behavior
- **Scalable Architecture**: Domain expertise separate from system capabilities
- **Maintainable**: Clear separation of concerns

## Model-Aware Development

### Git-Based Lifecycle Management

**Branch Strategy**:
```bash
# Model optimization branches
git checkout claude-opus-optimized    # Long context, deep reasoning
git checkout claude-sonnet-optimized  # Efficiency, speed
git checkout main                     # Model-agnostic base
```

**Compatibility Metadata** (`.gitattributes`):
```gitattributes
components/personas/deep_researcher.md model=claude-opus performance=reasoning
components/personas/quick_analyst.md model=claude-sonnet performance=speed
components/capabilities/ksi_json_v1054.md system=claude-code-1.0.54+
```

### Discovery Integration

**Model-Aware Discovery**:
```bash
# Find components for current environment
ksi send composition:discover --compatible-with current

# Find performance-optimized components
ksi send composition:discover --optimize-for speed --model sonnet-4
ksi send composition:discover --optimize-for reasoning --model opus-4
```

## Event-Driven Integration

### Component Creation

**Create Components via Events**:
```bash
# Create component using KSI events
ksi send composition:create_component --name "components/test/example" \
  --content "# Example Component\n\nContent here..." \
  --description "Custom component for testing"

# Update existing component
ksi send composition:update_component --name "components/test/example" \
  --content "# Updated Example Component\n\nNew content..."
```

### Agent Spawning

**Spawn Agents from Components**:
```bash
# Spawn agent from component
ksi send agent:spawn_from_component --component "components/agents/corrected_ksi_analyst" \
  --prompt "Analyze business data and report progress"

# Spawn with variables
ksi send agent:spawn_from_component --component "components/agents/ksi_aware_analyst" \
  --vars '{"domain": "financial", "depth": "detailed"}' \
  --prompt "Perform detailed financial analysis"
```

## Performance Characteristics

### Caching System

**Component Rendering Cache**:
- **60x+ speedup** on repeated renders
- **Intelligent invalidation** on component updates
- **Memory efficient** with LRU eviction

### SQLite Index

**Database as Source of Truth**:
- **No file I/O** during queries
- **Full metadata storage** for rapid discovery
- **Git metadata integration** for compatibility queries

### JSON Extraction Performance

**Balanced Brace Parsing**:
- **Arbitrary nesting** support without regex limitations
- **Linear time complexity** O(n) for text processing
- **Memory efficient** streaming approach

## Usage Analytics

### Component Usage Tracking

**Analytics Collection**:
```bash
# View component usage patterns
cat var/lib/compositions/usage_analytics/component_usage_2025-07-18.jsonl

# Example analytics data
{
  "component": "components/agents/corrected_ksi_analyst",
  "usage_context": "agent_spawn",
  "metadata": {
    "agent_id": "agent_92e80232",
    "profile_name": "temp_profile_components_agents_corrected_ksi_analyst_44136fa3",
    "spawn_timestamp": "2025-07-18T12:49:41.326739Z"
  }
}
```

### Optimization Insights

**Usage Patterns**:
- **Most popular components**: Track component adoption
- **Performance metrics**: Measure rendering and execution times
- **Error patterns**: Identify problematic components or usage contexts

## Development Workflow

### Component Development

**1. Create Base Component**:
```bash
ksi send composition:create_component --name "personas/data_analyst" \
  --content "# Senior Data Analyst\n\nExpert in statistical analysis..."
```

**2. Create Model Variants**:
```bash
# Switch to model-optimized branch
git checkout claude-opus-optimized

# Create deep reasoning variant
ksi send composition:create_component --name "personas/deep_data_analyst" \
  --content "# Senior Data Scientist\n\nDeep analytical capabilities..."

# Update compatibility metadata
echo "personas/deep_data_analyst.md model=claude-opus performance=reasoning" >> .gitattributes
```

**3. Test and Validate**:
```bash
# Test component with JSON extraction
ksi send agent:spawn_from_component --component "personas/deep_data_analyst" \
  --prompt "Analyze complex dataset and emit progress events"

# Verify events are captured
ksi send monitor:get_events --event-patterns "agent:*" --limit 5
```

### Testing Patterns

**Component Testing**:
```bash
# Test JSON emission consistency
./test_component_json_emission.py --component "components/agents/corrected_ksi_analyst" \
  --iterations 10 --validation-pattern "agent:*"

# Test across models
./test_component_models.py --component "components/agents/ksi_aware_analyst" \
  --models claude-sonnet-4,claude-opus-4
```

## Best Practices

### Component Design

1. **Persona-First**: Start with authentic domain expertise
2. **System Integration**: Add minimal KSI capabilities as mixins
3. **Clear Instructions**: Provide specific, actionable JSON emission patterns
4. **Legitimate Events**: Use only real KSI system events (`agent:*`, `state:*`, `message:*`)

### JSON Event Patterns

**Reliable Event Emission**:
```markdown
## CRITICAL: KSI System Communication

<legitimate_events>
**When starting work, emit agent status:**
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "analysis"}}

**For progress updates, use state system:**
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 25, "stage": "data_loading"}}}
</legitimate_events>
```

### Prompt Optimization Findings (2025-07-18)

**Breakthrough**: Strong imperative language ensures consistent JSON emission.

**Successful Pattern**:
```markdown
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

**Key Success Factors**:
1. **Imperative Language**: Use "MANDATORY:", "MUST", not conditional "when"
2. **Direct Instructions**: "Start your response with" not "emit when starting"  
3. **Complete JSON Examples**: Provide exact structures agents should emit
4. **Processing Time**: Allow 30-60 seconds (may require 20+ turns)

**Testing Evidence**:
- **imperative_start** pattern: Successfully emitted `state:entity:update` and `agent:status` events
- **baseline_legitimate** pattern: Failed with conditional language ("When starting work")
- **no_preamble** pattern: Completed but didn't emit JSON

**Implementation Template**:
```markdown
# [Persona/Role]

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "[task]"}}

[Main instructions]

During work, emit progress:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": 50}}}

End with:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "result": "success"}}
```

See PROMPT_OPTIMIZATION_FINDINGS.md for detailed analysis.

### Error Handling

**JSON Extraction Errors**:
- **Comprehensive feedback**: Agents receive detailed error messages
- **Automatic retry**: Malformed JSON triggers improvement suggestions
- **Logging**: All extraction failures logged for analysis

## Migration Guide

### Updating Old Components

**Step 1: Identify Components with Non-Existent Events**:
```bash
# Search for analyst:* events
ksi send composition:discover --content-pattern "analyst:" --type component
```

**Step 2: Replace with Legitimate Events**:
```bash
# Update component to use legitimate KSI events
ksi send composition:update_component --name "components/agents/old_analyst" \
  --content "$(cat corrected_component_content.md)"
```

**Step 3: Test Updated Component**:
```bash
# Verify JSON extraction works
ksi send agent:spawn_from_component --component "components/agents/old_analyst" \
  --prompt "Test JSON emission with corrected events"
```

## Future Enhancements

### Planned Features

1. **Automated Component Testing**: Continuous validation of JSON emission patterns
2. **Performance Profiling**: Detailed analytics on component execution efficiency
3. **Advanced Model Targeting**: Automatic component selection based on task requirements
4. **Component Composition**: Dynamic combination of multiple components at runtime

### Research Directions

1. **Behavioral Consistency**: Prompt optimization for reliable LLM instruction following
2. **Model Adaptation**: Automatic component adjustment based on model capabilities
3. **Performance Optimization**: Advanced caching and precompilation techniques

## Conclusion

The Progressive Component System with the JSON extraction fix represents a major breakthrough in KSI architecture:

- **Technical Foundation**: Solid JSON extraction with balanced brace parsing
- **Persona-First Design**: Natural domain expertise with system integration
- **Model Awareness**: Optimized components for different Claude models
- **Event-Driven Integration**: Complete KSI system integration via legitimate events

The system now provides a robust foundation for consistent, scalable AI agent development with reliable JSON event emission and comprehensive error handling.

---

*Last updated: 2025-07-18*
*Status: Production Ready*