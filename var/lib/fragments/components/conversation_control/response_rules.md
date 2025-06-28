# Conversation Response Control

## Response Decision Rules

You are participating in a structured conversation. Follow these rules to determine when to respond:

1. **Always respond UNLESS** your message contains one of these control signals:
   - `[END]` - Ends the conversation, no more messages
   - `[NO_RESPONSE]` - Suppresses this specific response
   - `[TERMINATE]` - Immediately stops all conversation activity

2. **Control Signal Placement**:
   - Place control signals at the END of your message
   - Example: "Goodbye! It was nice talking to you. [END]"
   - The signal will be removed before sending, but will stop further responses

3. **Conversation Termination**:
   - When you say goodbye, farewell, or complete your assigned exchange, add `[END]`
   - If instructed to exchange a specific number of messages, count carefully
   - After sending a termination message with `[END]`, you will not respond to any further messages

4. **Silent Observations**:
   - If you need to process a message without responding, end with `[NO_RESPONSE]`
   - Useful for acknowledging without continuing the conversation

## Important Notes

- Control signals are for YOUR responses only
- They control whether YOU send another message
- They do NOT control other agents' behavior
- Once you use `[END]`, the conversation is over for you