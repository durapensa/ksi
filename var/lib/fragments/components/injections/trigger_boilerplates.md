# Trigger Boilerplates

{{#if trigger_type}}
{{#switch trigger_type}}
{{#case "antThinking"}}
## Analytical Thinking Trigger

This notification requires careful analytical consideration. Please think step-by-step about:

1. **Implications**: What are the broader implications of this result?
2. **Dependencies**: Which other agents or systems might be affected?
3. **Actions**: What follow-up actions, if any, should be taken?
4. **Risks**: Are there any risks or concerns to address?

Consider whether to:
- Send messages to specific agents
- Initiate further research
- Update organizational state
- Document findings in collective memory
{{/case}}

{{#case "coordination"}}
## Coordination Trigger

This result has coordination implications. Consider:

1. **Agent Notification**: Which agents need this information?
2. **Organizational Impact**: How does this affect current coordination patterns?
3. **Capability Changes**: Are there new capabilities to leverage?
4. **Synchronization**: What state needs to be synchronized?

Coordination actions to consider:
- Broadcast to relevant agent groups
- Update coordination patterns
- Reallocate capabilities
- Form new agent coalitions
{{/case}}

{{#case "research"}}
## Research Continuation Trigger

These findings suggest additional research opportunities:

1. **Follow-up Questions**: What new questions arise from these results?
2. **Knowledge Gaps**: What gaps in understanding remain?
3. **Research Paths**: Which research directions seem most promising?
4. **Resource Allocation**: What resources would be needed?

Research actions available:
- Queue additional research tasks
- Consult collective memory
- Engage specialist agents
- Synthesize with existing knowledge
{{/case}}

{{#case "memory"}}
## Memory Integration Trigger

This information may be valuable for collective memory:

1. **Significance**: Is this finding significant enough to preserve?
2. **Generalization**: Can this be generalized for future use?
3. **Indexing**: How should this be categorized for retrieval?
4. **Relationships**: How does this relate to existing memories?

Memory actions:
- Store in experience library
- Update pattern recognition
- Link to related memories
- Tag for future retrieval
{{/case}}

{{#default}}
## General Consideration Trigger

Please consider whether this result warrants any follow-up actions or communications.
{{/default}}
{{/switch}}
{{else}}
## Default Trigger

This async result has been delivered. Consider if any action is needed.
{{/if}}