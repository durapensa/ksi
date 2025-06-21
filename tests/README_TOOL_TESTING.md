# Tool Usage Testing for KSI Agents

## Overview
This directory contains tests for verifying that agents properly signal and log their tool usage.

## Implementation Details

### Tool Signaling Protocol
Agents with tool access are instructed to:
1. Include `[TOOL_USE]` before invoking any tool
2. Explain what they're doing and why
3. Report results after tool execution

### Tool Control
- Agent profiles can set `enable_tools: true/false`
- When false, `--allowedTools` is omitted from the Claude command
- The prompt composer includes tool signaling instructions based on this setting

### Components Added
1. **prompts/components/tool_signaling.md** - Instructions for tool usage signaling
2. **Updated claude_agent_default.yaml** - Includes tool signaling component
3. **Enhanced command_handler.py** - Checks agent profiles for enable_tools setting
4. **Updated agent_process.py** - Passes enable_tools to prompt context

### Test Scripts
- **test_agent_tools.py** - Comprehensive test suite for tool-enabled vs disabled agents
- **test_tool_signaling.py** - Simple direct test of tool signaling

## Running Tests

```bash
# Start the daemon
./daemon_control.sh start

# Run comprehensive tests
python3 tests/test_agent_tools.py

# Run simple signaling test
python3 tests/test_tool_signaling.py

# Verify tool execution
python3 tests/verify_tool_execution.py
```

## Verification
After running tests, check:
1. Agent responses for `[TOOL_USE]` signals
2. `claude_logs/*.jsonl` for tool_calls arrays
3. `logs/daemon.log` for enable_tools settings

## Example Agent Profiles

### Tool-Enabled Agent (researcher.json)
```json
{
  "name": "researcher",
  "enable_tools": true,
  ...
}
```

### Tool-Disabled Agent (conversationalist.json)
```json
{
  "name": "conversationalist", 
  "enable_tools": false,
  ...
}
```

## Log Format
Claude's output includes tool usage information:
- `tool_calls` array with individual tool invocations
- `usage.server_tool_use` with tool usage statistics

## Next Steps
- Monitor agent conversations for proper tool signaling
- Analyze tool usage patterns in logs
- Create specialized tool-aware compositions
- Implement tool usage analytics