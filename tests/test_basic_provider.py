#!/usr/bin/env python3
"""
Safe test of claude_cli_provider basic functionality with tools disabled
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import litellm
from claude_cli_provider import ClaudeCLIProvider

def test_basic_provider():
    """Test basic provider functionality with tools disabled"""
    try:
        # Simple, non-instructional prompt
        response = litellm.completion(
            model="claude-cli/sonnet",
            messages=[{"role": "user", "content": "What is 2+2?"}],
            disallowed_tools=["Bash", "Read", "Edit", "Write", "WebFetch", "WebSearch", "Task", "Glob", "Grep", "LS", "MultiEdit"]
        )
        
        print("✅ Basic provider test successful")
        print(f"Response ID: {response.id}")
        print(f"Model: {response.model}")
        print(f"Content: {response.choices[0].message.content[:100]}...")
        
        # Check for Claude metadata
        if hasattr(response, '_claude_metadata'):
            print("✅ Claude metadata preserved")
            if hasattr(response, 'sessionId'):
                print(f"✅ Session ID: {response.sessionId}")
        
        if hasattr(response, '_stderr') and response._stderr:
            print(f"⚠️  Stderr: {response._stderr}")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_provider()
    sys.exit(0 if success else 1)