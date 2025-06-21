#!/usr/bin/env python3
"""Test the composition selector"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.composition_selector import CompositionSelector, SelectionContext


async def test_selector():
    """Test composition selection with various contexts"""
    selector = CompositionSelector()
    
    print("=== Testing Composition Selector ===\n")
    
    # Test 1: Select for a researcher agent
    print("1. Testing selection for researcher agent...")
    context = SelectionContext(
        agent_id="test_researcher",
        role="researcher",
        capabilities=["web_search", "summarization", "analysis"],
        task_description="research AI ethics and summarize findings"
    )
    
    result = await selector.select_composition(context)
    print(f"   Selected: {result.composition_name} (score: {result.score:.1f})")
    print(f"   Reasons: {', '.join(result.reasons[:3])}")
    
    # Test 2: Select for a coder agent
    print("\n2. Testing selection for coder agent...")
    context = SelectionContext(
        agent_id="test_coder",
        role="coder",
        capabilities=["code_generation", "debugging", "testing"],
        task_description="implement a new feature with tests"
    )
    
    result = await selector.select_composition(context)
    print(f"   Selected: {result.composition_name} (score: {result.score:.1f})")
    print(f"   Reasons: {', '.join(result.reasons[:3])}")
    
    # Test 3: Get suggestions for debate moderator
    print("\n3. Testing suggestions for debate moderator...")
    context = SelectionContext(
        agent_id="test_moderator",
        role="moderator",
        capabilities=["conversation_management", "summarization"],
        task_description="moderate a debate about AI ethics",
        preferred_style="neutral"
    )
    
    suggestions = await selector.suggest_compositions(context, top_n=3)
    for i, suggestion in enumerate(suggestions, 1):
        print(f"   {i}. {suggestion.composition_name} (score: {suggestion.score:.1f})")
    
    # Test 4: Validate a selection
    print("\n4. Testing context validation...")
    context = SelectionContext(
        agent_id="test_agent",
        role="analyst",
        context_variables={
            "daemon_commands": {"TEST": "test command"},
            "enable_tools": True
        }
    )
    
    result = await selector.select_composition(context)
    validation = await selector.validate_selection(result.composition_name, context)
    
    if validation['valid']:
        print(f"   ✓ Context valid for {result.composition_name}")
    else:
        print(f"   ✗ Context invalid: missing {validation.get('missing_context', [])}")
    
    # Test 5: Cache behavior
    print("\n5. Testing cache behavior...")
    context = SelectionContext(
        agent_id="cache_test",
        role="assistant"
    )
    
    # First call
    import time
    start = time.time()
    result1 = await selector.select_composition(context)
    time1 = time.time() - start
    
    # Second call (should be cached)
    start = time.time()
    result2 = await selector.select_composition(context)
    time2 = time.time() - start
    
    print(f"   First call: {time1:.3f}s, Second call: {time2:.3f}s")
    print(f"   Cache working: {time2 < time1/2}")
    
    print("\n=== All tests completed ===")


if __name__ == '__main__':
    asyncio.run(test_selector())