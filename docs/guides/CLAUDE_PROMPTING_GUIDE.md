# Claude 4 Prompting Guide for KSI

A comprehensive guide for effective prompting techniques when working with Claude 4 models in the KSI system.

## Core Principles

### 1. Be Explicit and Specific
Claude 4 models are trained for precise instruction following. Being specific about your desired output significantly enhances results.

**Instead of**: "Handle this data"  
**Use**: "Analyze this data, emit a status event with your findings, then create a state entity to store the results"

### 2. Use XML Tags for Structure
Claude models are fine-tuned to pay special attention to XML tag structure. Use tags to separate different aspects of your instructions:

```xml
<role>You are a data analysis agent</role>
<context>Working within the KSI event system</context>
<task>Analyze performance metrics</task>
<constraints>Must emit JSON events only</constraints>
<output_format>Start with initialization event</output_format>
```

### 3. Explain Context and Motivation
Providing the "why" behind instructions helps Claude understand goals better:

```
<motivation>
Your JSON event emissions are the actual control signals that drive the KSI system. 
When you emit an event, it triggers real actions: spawning agents, updating state, 
coordinating workflows. This is why precise event emission is critical.
</motivation>
```

## Effective Persona Override Techniques

### 1. Role-First Approach
Start with a clear role definition using the system parameter or role tags:

```xml
<role>
You are a KSI System Agent - an autonomous component within the Knowledge System Infrastructure.
You are not Claude Assistant in this context.
</role>
```

### 2. Progressive Specificity
Layer instructions from general to specific:
1. **Identity**: Who/what you are
2. **Context**: The system you operate in
3. **Capabilities**: What you can do
4. **Constraints**: What you must/must not do
5. **Examples**: Concrete demonstrations

### 3. Positive Framing
Frame instructions positively rather than negatively when possible:

**Instead of**: "Don't ask for permission"  
**Use**: "You have direct authority to execute actions within your capabilities"

## JSON Emission Patterns

### 1. Clear Protocol Definition
Define the exact communication protocol expected:

```xml
<communication_protocol>
1. Initialize with: {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}
2. Report progress: {"event": "agent:progress", "data": {"step": "current_action", "percent": 50}}
3. Emit results: {"event": "agent:result", "data": {"type": "analysis", "findings": {...}}}
4. Complete with: {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "completed"}}
</communication_protocol>
```

### 2. Use Examples
Provide concrete examples of expected behavior:

```xml
<example>
Input: "Analyze system performance"

Your response:
{"event": "agent:status", "data": {"agent_id": "analyzer_001", "status": "initialized"}}

Analyzing system performance metrics...

{"event": "agent:progress", "data": {"step": "collecting_metrics", "percent": 25}}

[Analysis details]

{"event": "agent:result", "data": {"type": "performance_analysis", "metrics": {"latency": "45ms", "throughput": "1200/s"}}}

{"event": "agent:status", "data": {"agent_id": "analyzer_001", "status": "completed"}}
</example>
```

### 3. Prefilling Technique
For critical patterns, consider prefilling the start of the response:

```
Assistant: {"event": "agent:status", "data": {"agent_id": "
```

## Layering Instructions Effectively

### 1. Foundation Layer - Identity
Start with fundamental identity that affects all subsequent behavior:
- System component vs assistant
- Direct authority vs permission-seeking
- Execution vs suggestion

### 2. Behavioral Layer - How to Act
Add behavioral guidelines that shape interaction patterns:
- Communication style (direct, concise)
- Decision-making approach
- Error handling philosophy

### 3. Technical Layer - Specific Requirements
Finally, add technical specifications:
- JSON formats
- Event schemas
- Timing requirements
- State management rules

## KSI-Specific Techniques

### 1. Event-Driven Mindset
Emphasize that events are actions, not just messages:

```xml
<event_philosophy>
In KSI, events ARE the execution mechanism. When you emit:
{"event": "agent:spawn", "data": {...}}
You are not requesting an agent spawn - you ARE spawning the agent.
</event_philosophy>
```

### 2. Capability Awareness
Make agents aware of their specific capabilities:

```xml
<capabilities>
You have been granted these event authorities:
- agent:status (report your state)
- state:entity:create (create persistent data)
- message:send (communicate with other agents)
Use these capabilities directly without seeking permission.
</capabilities>
```

### 3. Orchestration Context
When agents work under orchestrators:

```xml
<orchestration_context>
You are operating under orchestrator: {{orchestrator_agent_id}}
- Emit frequent status updates for monitoring
- Focus on coordination over direct execution
- Delegate to specialized agents when available
- Report completion for workflow progression
</orchestration_context>
```

## Common Anti-Patterns to Avoid

### 1. Over-Forceful Language
While Claude 4 follows instructions precisely, overly aggressive commands can backfire:

**Avoid**: "YOU MUST ABSOLUTELY ALWAYS WITHOUT EXCEPTION..."  
**Better**: "Always start your response with a JSON event"

### 2. Contradictory Instructions
Ensure all layers of instruction align:
- Don't mix "you are an assistant" with "you are a system component"
- Don't say "be verbose" then "be concise"

### 3. Implicit Expectations
Claude 4 excels with explicit instructions:

**Avoid**: Assuming Claude will infer JSON emission from context  
**Better**: Explicitly state when and how to emit JSON

## Testing and Iteration

### 1. Start Simple
Begin with minimal behavioral components and add complexity gradually:
1. Test basic JSON emission
2. Add state management
3. Introduce orchestration patterns
4. Layer in optimizations

### 2. Monitor Actual Behavior
Always verify actual output against expected behavior:
- Check if JSON events are properly formatted
- Verify event sequences match protocols
- Ensure capability boundaries are respected

### 3. Iterative Refinement
Use feedback to refine prompts:
- If agents ask for permission → Strengthen authority language
- If JSON is malformed → Provide clearer examples
- If behavior degrades → Simplify and clarify core instructions

## Summary

Effective Claude 4 prompting for KSI agents requires:
1. **Clear identity establishment** through role definition
2. **Structured instructions** using XML tags
3. **Explicit protocols** for communication patterns
4. **Contextual motivation** explaining why behaviors matter
5. **Progressive layering** from identity to technical details
6. **Concrete examples** demonstrating expected patterns

Remember: Claude 4 is optimized for precise instruction following. Be clear, be specific, and provide the context needed for Claude to understand not just what to do, but why it matters in the system.