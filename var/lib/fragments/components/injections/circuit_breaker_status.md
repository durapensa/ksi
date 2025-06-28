# Circuit Breaker Status

{{#if circuit_breaker_status}}
## Safety Monitoring Status

**Ideation Chain Depth**: {{circuit_breaker_status.depth}}/{{circuit_breaker_status.max_depth}}
{{#if (gte circuit_breaker_status.depth 3)}}
⚠️ Approaching maximum ideation depth. Consider whether continued processing is necessary.
{{/if}}

**Token Usage**: {{circuit_breaker_status.tokens_used}}/{{circuit_breaker_status.token_budget}}
{{#if (gte circuit_breaker_status.tokens_used (multiply circuit_breaker_status.token_budget 0.8))}}
⚠️ Approaching token budget limit ({{percentage circuit_breaker_status.tokens_used circuit_breaker_status.token_budget}}% used).
{{/if}}

**Time Elapsed**: {{circuit_breaker_status.time_elapsed}}s/{{circuit_breaker_status.time_window}}s
{{#if (gte circuit_breaker_status.time_elapsed (multiply circuit_breaker_status.time_window 0.9))}}
⚠️ Approaching time window limit.
{{/if}}

{{#if (gt circuit_breaker_status.risk_score 0.5)}}
**Context Health**: Risk Score {{circuit_breaker_status.risk_score}}
⚠️ Elevated risk of context degradation detected. Consider:
- Summarizing findings so far
- Starting fresh with refined approach
- Consulting different sources
{{/if}}

{{#if circuit_breaker_status.blocked_count}}
**Blocked Requests**: {{circuit_breaker_status.blocked_count}} requests have been blocked by safety mechanisms.
{{/if}}
{{/if}}