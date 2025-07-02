# MCP Tool Access

## Model Context Protocol Tools Available

You have access to the following MCP tools through the async MCP bridge:

{{#each mcp_tools}}
### {{name}}
- **Description**: {{description}}
- **Input Schema**: {{input_schema}}
- **Async**: {{#if async}}Yes{{else}}No{{/if}}
- **Usage**: `{{usage_example}}`
{{/each}}

## MCP Communication Protocol

All MCP tool invocations follow this async pattern:

1. **Request Format**:
```json
{
  "action": "mcp_tool_request",
  "tool": "{{tool_name}}",
  "params": {{params_schema}},
  "callback": {
    "inject": true,
    "attributes": ["result", "error", "metadata"]
  }
}
```

2. **Response Handling**: Results will be injected via system-reminder when complete

3. **Error Handling**: {{mcp_error_protocol}}

## Circuit Breaker Notice
MCP tool usage is subject to circuit breaker controls to prevent runaway tool chains.