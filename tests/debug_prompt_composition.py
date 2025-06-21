#!/usr/bin/env python3
"""Debug prompt composition to see what Claude receives"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from prompts.composer import PromptComposer

# Test context that would be provided by hello_agent
context = {
    'agent_id': 'hello_agent',
    'agent_role': 'responder',
    'conversation_id': 'conv_test_123',
    'daemon_commands': {},
    'user_prompt': 'Hello!',
    'conversation_history': 'Previous conversation:\ngoodbye_agent: Hello!\n'
}

composer = PromptComposer()
prompt = composer.compose('simple_hello_goodbye', context)

print("="*80)
print("COMPOSED PROMPT FOR HELLO_AGENT (RESPONDER):")
print("="*80)
print(prompt)
print("="*80)

# Now test initiator
context['agent_role'] = 'initiator'
context['agent_id'] = 'goodbye_agent'
context['conversation_history'] = 'Previous conversation:\nhello_agent: Hello! Nice to meet you!\n'
context['user_prompt'] = 'Hello! Nice to meet you!'

prompt = composer.compose('simple_hello_goodbye', context)

print("\nCOMPOSED PROMPT FOR GOODBYE_AGENT (INITIATOR):")
print("="*80)
print(prompt)
print("="*80)