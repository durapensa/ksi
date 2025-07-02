# Coordination Guidance

{{#if coordination_context}}
## Multi-Agent Coordination Context

{{#if coordination_context.participating_agents}}
### Participating Agents
{{#each coordination_context.participating_agents}}
- **{{name}}** ({{id}}): {{role}}
  - Status: {{status}}
  - Capabilities: {{#each capabilities}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}
{{/each}}
{{/if}}

{{#if coordination_context.coordination_pattern}}
### Active Coordination Pattern
- **Pattern**: {{coordination_context.coordination_pattern.name}}
- **Description**: {{coordination_context.coordination_pattern.description}}
- **Your Role**: {{coordination_context.coordination_pattern.your_role}}
{{/if}}

{{#if coordination_context.shared_state}}
### Shared Organizational State
{{#each coordination_context.shared_state}}
- **{{@key}}**: {{this}}
{{/each}}
{{/if}}

### Coordination Actions Available
{{#if coordination_actions}}
{{#each coordination_actions}}
- **{{action}}**: {{description}}
  - Command: `{{command}}`
{{/each}}
{{else}}
- **Broadcast**: Send message to all participating agents
- **Direct Message**: Send message to specific agent
- **Update State**: Update shared organizational state
- **Request Capability**: Request specific capability from another agent
- **Form Coalition**: Propose new agent coalition for task
{{/if}}

{{#if coordination_context.pending_decisions}}
### Pending Coordination Decisions
{{#each coordination_context.pending_decisions}}
- {{description}} (Priority: {{priority}})
{{/each}}
{{/if}}
{{/if}}