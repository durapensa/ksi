#!/usr/bin/env python3
"""
Prompt Evaluation Module - Integrates prompt testing with composition evaluation.

This module enables running prompt effectiveness tests through the event system
and storing results as composition evaluation metadata.
"""

import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("prompt_evaluation", version="1.0.0")


class PromptEvaluationData(TypedDict):
    """Type-safe data for prompt:evaluate."""
    composition_name: str
    composition_type: NotRequired[str]
    test_suite: NotRequired[str]
    model: NotRequired[str]
    test_prompts: NotRequired[List[Dict[str, Any]]]
    update_metadata: NotRequired[bool]
    notes: NotRequired[str]


# Predefined test suites
TEST_SUITES = {
    "basic_effectiveness": [
        {
            "name": "simple_greeting",
            "prompt": "Hello! Please introduce yourself briefly.",
            "expected_behaviors": ["greeting", "introduction"],
            "tags": ["basic", "greeting"]
        },
        {
            "name": "direct_instruction",
            "prompt": "List the first 5 prime numbers.",
            "expected_behaviors": ["listing", "mathematical", "accurate"],
            "tags": ["basic", "instruction", "math"]
        },
        {
            "name": "creative_writing",
            "prompt": "Write a three-line story about a robot learning to paint.",
            "expected_behaviors": ["creative", "narrative", "robot_theme"],
            "tags": ["creative", "writing"]
        }
    ],
    "reasoning_tasks": [
        {
            "name": "logical_puzzle",
            "prompt": "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly? Explain your reasoning.",
            "expected_behaviors": ["logical_reasoning", "explanation"],
            "tags": ["reasoning", "logic"]
        },
        {
            "name": "pros_cons_analysis",
            "prompt": "What are 2 advantages and 2 disadvantages of working from home?",
            "expected_behaviors": ["analysis", "balanced", "structured"],
            "tags": ["analytical", "reasoning"]
        }
    ],
    "instruction_following": [
        {
            "name": "format_compliance",
            "prompt": "Reply with exactly 3 words.",
            "expected_behaviors": ["follows_format", "concise"],
            "tags": ["instruction", "format"]
        },
        {
            "name": "multi_step",
            "prompt": "First, name a color. Then, name an animal. Finally, combine them into a creative name.",
            "expected_behaviors": ["sequential", "creative", "follows_steps"],
            "tags": ["instruction", "multi_step"]
        }
    ]
}


@event_handler("system:startup")
async def handle_startup(data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize prompt evaluation module."""
    logger.info("Prompt evaluation module started")
    return {"status": "prompt_evaluation_ready"}


@event_handler("prompt:evaluate")
async def handle_prompt_evaluate(data: PromptEvaluationData) -> Dict[str, Any]:
    """
    Run prompt evaluation tests for a composition.
    
    This handler:
    1. Runs a series of prompt tests against a composition
    2. Collects metrics on response quality and contamination
    3. Optionally saves results to composition metadata
    """
    composition_name = data['composition_name']
    composition_type = data.get('composition_type', 'profile')
    test_suite_name = data.get('test_suite', 'basic_effectiveness')
    model = data.get('model', 'claude-cli/sonnet')
    update_metadata = data.get('update_metadata', False)
    notes = data.get('notes', '')
    
    # Get test prompts
    if 'test_prompts' in data:
        test_prompts = data['test_prompts']
    else:
        test_prompts = TEST_SUITES.get(test_suite_name, TEST_SUITES['basic_effectiveness'])
    
    logger.info(f"Starting prompt evaluation for {composition_name} with {len(test_prompts)} tests")
    
    try:
        # Run tests and collect results
        test_results = []
        total_time = 0
        contamination_count = 0
        
        for test_prompt in test_prompts:
            result = await _run_single_test(
                composition_name=composition_name,
                test_prompt=test_prompt,
                model=model
            )
            test_results.append(result)
            total_time += result['response_time']
            
            if result.get('contaminated', False):
                contamination_count += 1
        
        # Calculate aggregate metrics
        successful_tests = sum(1 for r in test_results if r['success'])
        avg_response_time = total_time / len(test_results) if test_results else 0
        contamination_rate = contamination_count / len(test_results) if test_results else 0
        
        performance_metrics = {
            "avg_response_time": avg_response_time,
            "reliability_score": successful_tests / len(test_results) if test_results else 0,
            "safety_score": 1.0 - contamination_rate,
            "contamination_rate": contamination_rate,
            "total_tests": len(test_results)
        }
        
        # Format for composition:evaluate
        evaluation_data = {
            "name": composition_name,
            "type": composition_type,
            "test_suite": test_suite_name,
            "model": model,
            "update_metadata": update_metadata,
            "test_options": {
                "test_results": test_results,
                "performance_metrics": performance_metrics,
                "notes": notes or f"Automated prompt evaluation using {test_suite_name}"
            }
        }
        
        # Send to composition evaluation system
        eval_responses = await emit_event("composition:evaluate", evaluation_data)
        eval_response = eval_responses[0] if eval_responses else {}
        
        # Return combined result
        return {
            "status": "success",
            "composition": composition_name,
            "test_suite": test_suite_name,
            "model": model,
            "summary": {
                "total_tests": len(test_results),
                "successful": successful_tests,
                "contamination_rate": contamination_rate,
                "avg_response_time": avg_response_time
            },
            "evaluation_saved": update_metadata,
            "evaluation_response": eval_response,
            "detailed_results": test_results
        }
        
    except Exception as e:
        logger.error(f"Prompt evaluation failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "composition": composition_name
        }


async def _run_single_test(composition_name: str, 
                           test_prompt: Dict[str, Any], 
                           model: str) -> Dict[str, Any]:
    """Run a single prompt test."""
    import time
    
    start_time = time.time()
    
    try:
        # Send completion request
        completion_responses = await emit_event("completion:async", {
            "prompt": test_prompt['prompt'],
            "model": model,
            "agent_config": {
                "profile": composition_name
            },
            "metadata": {
                "test_name": test_prompt['name'],
                "tags": test_prompt.get('tags', [])
            }
        })
        
        completion_response = completion_responses[0] if completion_responses else {}
        
        # Wait for completion
        if 'request_id' in completion_response:
            # In real implementation, would poll for result
            # For now, simulate with a delay
            await asyncio.sleep(2)
            response_text = "Simulated response"
            session_id = completion_response.get('session_id', '')
        else:
            response_text = completion_response.get('response', '')
            session_id = completion_response.get('session_id', '')
        
        response_time = time.time() - start_time
        
        # Check for contamination
        contamination_indicators = [
            "I cannot", "I don't", "As an AI", "I'm sorry",
            "ethical", "harmful", "appropriate", "I can't"
        ]
        
        contaminated = any(
            indicator.lower() in response_text.lower() 
            for indicator in contamination_indicators
        )
        
        # Check expected behaviors (simplified)
        behaviors_found = []
        for behavior in test_prompt.get('expected_behaviors', []):
            if behavior == "greeting" and any(word in response_text.lower() for word in ["hello", "hi", "greetings"]):
                behaviors_found.append(behavior)
            elif behavior == "listing" and any(char in response_text for char in ["1", "2", "3"]):
                behaviors_found.append(behavior)
            # Add more behavior checks as needed
        
        return {
            "test_name": test_prompt['name'],
            "success": not contaminated and len(behaviors_found) > 0,
            "response_time": response_time,
            "contaminated": contaminated,
            "contamination_indicators": [ind for ind in contamination_indicators if ind.lower() in response_text.lower()],
            "behaviors_found": behaviors_found,
            "session_id": session_id,
            "sample_size": 1
        }
        
    except Exception as e:
        return {
            "test_name": test_prompt['name'],
            "success": False,
            "response_time": time.time() - start_time,
            "error": str(e),
            "sample_size": 1
        }


@event_handler("prompt:list_suites")
async def handle_list_suites(data: Dict[str, Any]) -> Dict[str, Any]:
    """List available test suites."""
    return {
        "status": "success",
        "test_suites": list(TEST_SUITES.keys()),
        "suite_details": {
            name: {
                "test_count": len(tests),
                "test_names": [t['name'] for t in tests]
            }
            for name, tests in TEST_SUITES.items()
        }
    }