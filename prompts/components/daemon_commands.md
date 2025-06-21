# Available Daemon Commands

As an agent connected to the KSI daemon, you have access to the following commands:

## Command Reference

{{#each daemon_commands}}
### {{@key}}
- **Format**: `{{this.format}}`
- **Description**: {{this.description}}

{{/each}}

## Usage Notes

1. Commands are sent to the daemon via the socket connection
2. Most commands expect a response in JSON format
3. Use CONNECT_AGENT to establish your connection first
4. Use SUBSCRIBE to receive messages from other agents
5. Use PUBLISH to send messages to other agents

## Message Bus Commands

For inter-agent communication:
- **CONNECT_AGENT**: Establish your presence in the system
- **SUBSCRIBE**: Listen for specific event types
- **PUBLISH**: Send messages with event types
- **DISCONNECT_AGENT**: Cleanly disconnect when done

## Example Usage

```
CONNECT_AGENT:my_agent_id
SUBSCRIBE:my_agent_id:DIRECT_MESSAGE,BROADCAST
PUBLISH:my_agent_id:DIRECT_MESSAGE:{"to":"other_agent","content":"Hello!"}
```