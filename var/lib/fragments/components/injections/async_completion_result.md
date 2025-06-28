# Async Completion Result Injection

## Result Notification

An asynchronous completion has returned with the following result:

{{completion_result}}

{{#if attributes}}
## Additional Attributes
{{#each attributes}}
- {{@key}}: {{this}}
{{/each}}
{{/if}}

## Consideration Trigger

{{trigger_boilerplate}}

{{#if follow_up_guidance}}
## Follow-up Guidance
{{follow_up_guidance}}
{{/if}}

{{#if circuit_breaker_status}}
## Circuit Breaker Status
- Ideation Depth: {{circuit_breaker_status.depth}}/{{circuit_breaker_status.max_depth}}
- Token Budget: {{circuit_breaker_status.tokens_used}}/{{circuit_breaker_status.token_budget}}
- Time Window: {{circuit_breaker_status.time_elapsed}}/{{circuit_breaker_status.time_window}}
{{/if}}