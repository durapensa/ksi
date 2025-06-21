#!/usr/bin/env python3
"""Test script to directly use PromptComposer and see the exact prompt."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompt_composer import PromptComposer
import json

def test_prompt_composition():
    """Test the prompt composition directly."""
    
    # Initialize composer
    composer = PromptComposer()
    
    # Test context that would be provided by hello_agent
    test_context = {
        "role": "helpful assistant",
        "task": "respond to greetings appropriately",
        "constraints": [
            "Be friendly and welcoming",
            "Keep responses brief"
        ]
    }
    
    # User message
    user_message = "Hi there!"
    
    print("=" * 80)
    print("TESTING PROMPT COMPOSITION")
    print("=" * 80)
    print()
    
    print("Template: simple_hello_goodbye")
    print("Context:", json.dumps(test_context, indent=2))
    print("User message:", user_message)
    print()
    
    # Compose the prompt
    try:
        composed_prompt = composer.compose("simple_hello_goodbye", test_context, user_message)
        
        print("=" * 80)
        print("COMPOSED PROMPT:")
        print("=" * 80)
        print(composed_prompt)
        print("=" * 80)
        
    except Exception as e:
        print(f"Error composing prompt: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Also test what happens with minimal context
    print("Testing with minimal context...")
    minimal_context = {}
    
    try:
        minimal_prompt = composer.compose("simple_hello_goodbye", minimal_context, user_message)
        
        print("=" * 80)
        print("MINIMAL CONTEXT PROMPT:")
        print("=" * 80)
        print(minimal_prompt)
        print("=" * 80)
        
    except Exception as e:
        print(f"Error with minimal context: {e}")

if __name__ == "__main__":
    test_prompt_composition()