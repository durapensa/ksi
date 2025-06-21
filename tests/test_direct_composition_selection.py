#!/usr/bin/env python3
"""Direct test of composition selection without spawning full agents"""

import asyncio
import sys
sys.path.insert(0, '.')
from prompts.composition_selector import CompositionSelector, SelectionContext


async def test_selections():
    """Test composition selection for different contexts"""
    selector = CompositionSelector()
    
    print("=== Direct Composition Selection Test ===\n")
    
    test_contexts = [
        {
            'name': 'Researcher Agent',
            'context': SelectionContext(
                agent_id='test_researcher',
                role='researcher',
                capabilities=['web_search', 'summarization', 'analysis'],
                task_description='Research AI ethics and summarize findings'
            )
        },
        {
            'name': 'Coder Agent',
            'context': SelectionContext(
                agent_id='test_coder',
                role='coder',
                capabilities=['code_generation', 'debugging', 'testing'],
                task_description='Implement a sorting algorithm'
            )
        },
        {
            'name': 'Debate Moderator',
            'context': SelectionContext(
                agent_id='test_moderator',
                role='moderator',
                capabilities=['conversation_management'],
                task_description='Moderate debate on climate change'
            )
        },
        {
            'name': 'Generic Assistant',
            'context': SelectionContext(
                agent_id='test_assistant',
                role='assistant',
                task_description='Help user with various tasks'
            )
        }
    ]
    
    for test in test_contexts:
        print(f"{test['name']}:")
        result = await selector.select_composition(test['context'])
        print(f"  Selected: {result.composition_name}")
        print(f"  Score: {result.score:.1f}")
        print(f"  Reasons: {', '.join(result.reasons[:3])}")
        print(f"  Fallback: {'Yes' if result.fallback_used else 'No'}")
        print()
    
    # Test caching
    print("Testing cache performance:")
    import time
    
    context = SelectionContext(agent_id='cache_test', role='assistant')
    
    start = time.time()
    result1 = await selector.select_composition(context)
    time1 = time.time() - start
    
    start = time.time()
    result2 = await selector.select_composition(context)
    time2 = time.time() - start
    
    print(f"  First call: {time1:.3f}s -> {result1.composition_name}")
    print(f"  Second call: {time2:.3f}s -> {result2.composition_name}")
    print(f"  Cache speedup: {time1/time2:.1f}x")


if __name__ == '__main__':
    asyncio.run(test_selections())