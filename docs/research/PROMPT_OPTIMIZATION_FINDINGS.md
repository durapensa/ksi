# Prompt Optimization Findings for KSI JSON Emission

## Executive Summary

After systematic testing of prompt patterns for consistent JSON emission from KSI agents, the "imperative_start" pattern successfully produced JSON events. However, the success appears to be influenced by multiple factors beyond just the prompt pattern.

## Test Results

### Successful Pattern: imperative_start
- **Agent**: agent_d49e82bd  
- **Duration**: 52 seconds, 32 turns
- **Events Emitted**: 
  - `state:entity:update` with progress tracking
  - `agent:status` with completion status
- **Key Characteristics**:
  - Used "MANDATORY:" prefix
  - Direct instruction: "Start your response with this exact JSON:"
  - Clear, imperative language

### Failed Patterns
1. **baseline_legitimate** (agent_d54079ec)
   - Error during execution, 0 turns
   - Used conditional "When starting work, emit:"
   
2. **no_preamble** (agent_b20cd2d6)  
   - Completed successfully but no JSON events
   - 19 turns, but didn't emit structured data
   
3. **persona_first_minimal** (agent_5b6d821c)
   - No completion recorded

## Key Findings

### 1. Imperative Language Works Better
The successful pattern used strong imperative language:
```
## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
```

### 2. JSON Extraction System Is Working
The enhanced JSON extraction system with balanced brace parsing successfully extracted deeply nested JSON objects from the agent's response.

### 3. Agent Behavior Varies
- Agents may take many turns (32 in the successful case) to complete analysis
- Some agents fail immediately (error_during_execution)
- Others complete but don't emit JSON

### 4. Factors Beyond Prompting
Success appears influenced by:
- Agent initialization timing
- System resource availability  
- Claude model behavior variations
- Complexity of the analysis task

## Recommended Pattern

Based on the successful test, the optimal pattern includes:

```markdown
# [Role/Persona]

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized", "task": "[task_name]"}}

[Instructions for the task]

During your work, emit progress updates:
{"event": "state:entity:update", "data": {"id": "{{agent_id}}_progress", "properties": {"percent": [number], "stage": "[description]"}}}

When complete, end with:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed", "task": "[task_name]", "result": "success"}}
```

## Implementation Recommendations

1. **Use Strong Imperatives**: "MANDATORY:", "MUST", "Start your response with"
2. **Provide Exact JSON**: Include the complete JSON structure
3. **Template Variables**: Use {{agent_id}} for agent-specific values
4. **Multiple Events**: Define initialization, progress, and completion events
5. **Clear Task Context**: Specify what analysis or work should be done

## Testing Considerations

1. **Allow Sufficient Time**: Agents may need 30-60 seconds to complete
2. **Monitor Turn Count**: High turn counts (20+) indicate complex processing
3. **Check Error States**: Some patterns cause immediate errors
4. **Verify JSON Extraction**: Ensure the extraction system captures events

## Next Steps

1. Create standardized component templates using the imperative pattern
2. Test with different task complexities
3. Monitor success rates across different Claude models
4. Develop automated testing for prompt effectiveness

---

*Generated: 2025-07-18*  
*Test Environment: KSI with enhanced JSON extraction system*