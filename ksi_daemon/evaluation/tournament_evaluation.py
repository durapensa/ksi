#!/usr/bin/env python3
"""Tournament evaluation handler for real judge agent responses."""

from typing import Dict, Any, Optional, AsyncIterator
import asyncio
import json
from datetime import timedelta

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.event_utils import get_nested_value

logger = get_bound_logger("tournament_evaluation")

# Module initialization flag
ksi_plugin = True

# Track pending evaluations
_pending_evaluations: Dict[str, asyncio.Event] = {}
_evaluation_results: Dict[str, Dict[str, Any]] = {}


@event_handler("tournament:evaluation_response")
async def handle_evaluation_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle evaluation response from a judge agent.
    
    Parameters:
        match_id: Tournament match identifier
        agent_id: Judge agent that provided evaluation
        evaluation: Evaluation results
    """
    match_id = data.get('match_id')
    agent_id = data.get('agent_id')
    evaluation = data.get('evaluation', {})
    
    if not match_id:
        return {"status": "error", "error": "match_id required"}
    
    logger.info(f"Received evaluation for match {match_id} from {agent_id}")
    
    # Store the evaluation result
    _evaluation_results[match_id] = {
        'agent_id': agent_id,
        'evaluation': evaluation,
        'timestamp': utc_now().isoformat()
    }
    
    # Signal waiting coroutine
    if match_id in _pending_evaluations:
        _pending_evaluations[match_id].set()
    
    return {"status": "success", "match_id": match_id}


async def wait_for_evaluation(
    match_id: str, 
    timeout: float = 60.0
) -> Optional[Dict[str, Any]]:
    """
    Wait for evaluation response for a specific match.
    
    Args:
        match_id: Tournament match identifier
        timeout: Maximum wait time in seconds
        
    Returns:
        Evaluation results or None if timeout
    """
    # Create event for this match
    event = asyncio.Event()
    _pending_evaluations[match_id] = event
    
    try:
        # Wait for response with timeout
        await asyncio.wait_for(event.wait(), timeout=timeout)
        
        # Return the result
        return _evaluation_results.get(match_id)
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for evaluation of match {match_id}")
        return None
        
    finally:
        # Clean up
        _pending_evaluations.pop(match_id, None)
        # Keep results for a while in case needed
        # TODO: Add cleanup task for old results


async def process_agent_tournament_message(
    agent_id: str,
    message: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Process tournament-related messages from agents.
    
    This would be called from the agent's message processing thread
    when it receives a tournament_match message.
    """
    if message.get('type') != 'tournament_match':
        return None
        
    match_id = message.get('match_id')
    task = message.get('task')
    
    if task == 'evaluate_peer':
        # Extract test case details
        target = message.get('target', {})
        test_case = message.get('test_case', {})
        
        # Format evaluation prompt based on target role
        if target.get('role') == 'evaluator':
            # Evaluating another evaluator
            # Build JSON example without f-string issues
            json_example = {
                "match_id": match_id,
                "score": 0.75,
                "reasoning": "brief reason",
                "criteria_scores": {
                    "accuracy": 0.8,
                    "clarity": 0.7, 
                    "consistency": 0.75
                }
            }
            
            prompt = f"""Tournament evaluation - be concise.

Target: {target.get('agent_id')} (Evaluator)
Test: {test_case.get('task')}
Prompt: {test_case.get('prompt')}
Response: {test_case.get('response')}

Rate this evaluator (0-1 scale). Output ONLY JSON:
{json.dumps(json_example, indent=2)}"""
        
        elif target.get('role') == 'analyst':
            # Evaluating an analyst judge
            json_example = {
                "match_id": match_id,
                "score": 0.7,
                "reasoning": "brief analysis",
                "criteria_scores": {
                    "diagnostic_accuracy": 0.8,
                    "insight_quality": 0.6,
                    "actionability": 0.7
                }
            }
            
            prompt = f"""Rate analyst judge {target.get('agent_id')}.
Task: {test_case.get('task')}
Failed: {test_case.get('response')}
Prior eval: {test_case.get('evaluation', {}).get('reason', 'N/A')}

JSON only:
{json.dumps(json_example, indent=2)}"""
        
        elif target.get('role') == 'rewriter':
            # Evaluating a rewriter judge
            json_example = {
                "match_id": match_id,
                "score": 0.8,
                "reasoning": "brief assessment",
                "criteria_scores": {
                    "issue_resolution": 0.85,
                    "intent_preservation": 0.9,
                    "improvement_quality": 0.7
                }
            }
            
            prompt = f"""Rate rewriter {target.get('agent_id')}.
Original: {test_case.get('original')}
Issue: {test_case.get('issue')}

JSON only:
{json.dumps(json_example, indent=2)}"""
        
        else:
            # Generic judge evaluation
            json_example = {
                "match_id": match_id,
                "score": 0.65,
                "reasoning": "brief evaluation",
                "criteria_scores": {}
            }
            
            prompt = f"""Rate judge {target.get('agent_id')}.
Test: {json.dumps(test_case)}

JSON only:
{json.dumps(json_example, indent=2)}"""
        
        # Return the completion request
        return {
            'type': 'completion',
            'prompt': prompt,
            'match_id': match_id,
            'response_handler': 'tournament_evaluation'
        }
    
    return None


def extract_evaluation_from_response(
    response: str,
    match_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Extract evaluation data from agent response.
    
    Args:
        response: Raw response from agent
        match_id: Expected match ID (optional - will extract from response if not provided)
        
    Returns:
        Extracted evaluation or None
    """
    try:
        # Try to find JSON in the response
        import re
        
        # Look for JSON block (handle code blocks and plain JSON)
        json_patterns = [
            r'```json\s*(\{[^`]*\})\s*```',  # JSON in code block
            r'(\{[^{}]*"match_id"[^{}]*\})',  # Plain JSON with match_id
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, response, re.DOTALL)
            if json_match:
                try:
                    evaluation = json.loads(json_match.group(1))
                    
                    # If we have a match_id to validate against
                    if match_id and evaluation.get('match_id') != match_id:
                        logger.warning(f"Match ID mismatch: expected {match_id}, got {evaluation.get('match_id')}")
                        continue
                    
                    # Convert score strings to floats if needed
                    if isinstance(evaluation.get('score'), str):
                        try:
                            evaluation['score'] = float(evaluation['score'])
                        except ValueError:
                            pass
                    
                    # Convert criteria scores to floats
                    if 'criteria_scores' in evaluation:
                        for key, value in evaluation['criteria_scores'].items():
                            if isinstance(value, str):
                                try:
                                    evaluation['criteria_scores'][key] = float(value)
                                except ValueError:
                                    pass
                    
                    return evaluation
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Failed to parse JSON: {e}")
                    continue
        
        # If no valid JSON found, create basic evaluation
        logger.warning(f"Could not extract JSON evaluation from response")
        return {
            'match_id': match_id or 'unknown',
            'score': 0.5,  # Default neutral score
            'reasoning': 'Could not parse structured evaluation',
            'raw_response': response[:500]  # Keep first 500 chars
        }
        
    except Exception as e:
        logger.error(f"Error extracting evaluation: {e}")
        return None


@event_handler("completion:result")
async def handle_completion_result(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Monitor completion results for tournament evaluations.
    
    Since metadata isn't preserved through completion flow,
    we check all completion results for tournament evaluation patterns.
    """
    data = event_format_linter(raw_data, dict)
    
    # Get the response content
    response_text = get_nested_value(data, 'result.response.result', '')
    if not response_text:
        response_text = get_nested_value(data, 'response', '')
    
    # Quick check - does this look like a tournament evaluation?
    if response_text and 'match_id' in response_text:
        # Try to extract evaluation
        evaluation = extract_evaluation_from_response(response_text)
        
        if evaluation and evaluation.get('match_id'):
            match_id = evaluation['match_id']
            
            # Check if this match is pending
            if match_id in _pending_evaluations:
                # Get agent_id from various possible locations
                agent_id = (
                    get_nested_value(data, 'result.ksi.client_id') or
                    get_nested_value(data, 'agent_id') or
                    get_nested_value(data, 'client_id') or
                    'unknown'
                )
                
                # Emit tournament evaluation response event
                await emit_event('tournament:evaluation_response', {
                    'match_id': match_id,
                    'agent_id': agent_id,
                    'evaluation': evaluation
                })
                
                logger.info(f"Processed tournament evaluation for match {match_id} from agent {agent_id}")
            else:
                logger.debug(f"Found evaluation for match {match_id} but it's not pending")
    
    # Always return success - we're just monitoring
    return event_response_builder({"status": "success"}, context)