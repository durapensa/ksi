"""Async Evaluation Service - Agent-Ready Patterns."""

import uuid
import json
from typing import Dict, Any, Optional
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config
from ksi_common.event_utils import extract_single_response, is_success_response, get_response_error
from ksi_common.event_response_builder import event_response_builder, error_response, success_response
from ksi_common.response_patterns import validate_required_fields
from ksi_common.json_extraction import extract_json_objects

logger = get_bound_logger("evaluation.async")




@event_handler("evaluation:async")
async def handle_evaluation_async(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Start async evaluation - returns immediately."""
    router = get_router()
    
    # Extract parameters - optimization_id now optional
    optimization_id = data.get("optimization_id")
    optimization_result = data.get("optimization_result", {})
    skip_git = data.get("skip_git", False)
    
    if not optimization_result:
        return error_response("optimization_result is required", context)
    
    # Parse optimization_result if it's a JSON string
    if isinstance(optimization_result, str):
        try:
            optimization_result = json.loads(optimization_result)
        except json.JSONDecodeError as e:
            return error_response(f"Invalid JSON in optimization_result: {e}", context)
    
    # Generate tracking IDs - works with or without optimization_id
    id_base = optimization_id if optimization_id else f"standalone_{uuid.uuid4().hex[:8]}"
    evaluation_id = f"assessment_{id_base}_{uuid.uuid4().hex[:8]}"
    judge_agent_id = f"judge_{evaluation_id}"
    
    source = f"optimization {optimization_id}" if optimization_id else "standalone comparison"
    logger.info(f"Starting async evaluation {evaluation_id} for {source}")
    
    # Pattern 1: Create routing rule to capture judge results
    rule_id = f"judge_complete_{evaluation_id}"
    # Changed from 'optimization_evaluation' to 'optimization_assessment' to avoid 'eval' validation issue
    # FIX: In condition evaluation context, the data parameter IS the event data, not a parent
    condition = f"agent_id == '{judge_agent_id}' and result_type == 'optimization_assessment'"
    
    logger.info(f"Creating routing rule {rule_id}")
    logger.info(f"  Source: agent:result")
    logger.info(f"  Condition: {condition}")
    logger.info(f"  Target: evaluation:judge_completed")
    logger.info(f"  Judge agent ID: {judge_agent_id}")
    
    routing_result = await router.emit("routing:add_rule", {
        "rule_id": rule_id,
        "source_pattern": "agent:result",
        "condition": condition,
        "target": "evaluation:judge_completed",
        "mapping": {
            "evaluation_id": evaluation_id,
            "optimization_id": optimization_id,
            "evaluation": "{{evaluation}}",
            "judge_agent_id": judge_agent_id,
            "optimization_result": optimization_result,
            "skip_git": skip_git
        },
        "ttl": 600,  # 10 minute timeout
        "persistence_class": "ephemeral",
        "parent_scope": {"type": "agent", "id": judge_agent_id}
    })
    
    # Check if routing rule was created successfully
    routing_result = extract_single_response(routing_result)
    if not is_success_response(routing_result):
        error_msg = get_response_error(routing_result)
        logger.error(f"Failed to create routing rule: {error_msg}")
        return error_response(
            f"Failed to create routing rule for evaluation: {error_msg}",
            context
        )
    
    # Pattern 2: Spawn judge agent
    spawn_result = await router.emit("agent:spawn", {
        "agent_id": judge_agent_id,
        "component": "evaluations/quality/optimization_judge",
        "metadata": {
            "evaluation_id": evaluation_id,
            "optimization_id": optimization_id
        },
        "permission_profile": "standard"
    })
    
    # Pattern 3: Send evaluation task
    evaluation_prompt = _build_evaluation_prompt(
        component_name=optimization_result.get("component_name"),
        original_content=optimization_result.get("original_content"),
        optimized_content=optimization_result.get("optimized_content"),
        optimization_metadata=optimization_result.get("optimization_metadata", {})
    )
    
    completion_result = await router.emit("completion:async", {
        "agent_id": judge_agent_id,
        "prompt": evaluation_prompt,
        "timeout": 180
    })
    
    # Return immediately
    return success_response(
        data={
            "evaluation_id": evaluation_id,
            "judge_agent_id": judge_agent_id
        },
        context=context,
        message="Evaluation started. Listen for evaluation:result event"
    )


@event_handler("evaluation:judge_completed")
async def handle_judge_completed(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Process judge results routed from agent:result."""
    router = get_router()
    
    evaluation_id = data.get("evaluation_id")
    optimization_id = data.get("optimization_id")  # Optional
    evaluation = data.get("evaluation", {})
    optimization_result = data.get("optimization_result", {})
    skip_git = data.get("skip_git", False)
    
    logger.info(f"=== EVALUATION:JUDGE_COMPLETED HANDLER TRIGGERED ===")
    logger.info(f"Processing judge results for evaluation {evaluation_id}")
    logger.info(f"Optimization ID: {optimization_id}")
    logger.info(f"Skip git: {skip_git}")
    
    # Handle case where evaluation comes as JSON string from agent:result or CLI
    if isinstance(evaluation, str):
        try:
            evaluation = json.loads(evaluation)
            logger.info(f"Parsed evaluation JSON: {evaluation}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse evaluation JSON: {e}")
            evaluation = {
                "recommendation": "reject",
                "confidence": "low", 
                "reasoning": f"Could not parse judge evaluation: {e}"
            }
    
    # Handle case where optimization_result comes as JSON string from CLI
    if isinstance(optimization_result, str):
        try:
            optimization_result = json.loads(optimization_result)
            logger.info(f"Parsed optimization_result JSON: {optimization_result}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse optimization_result JSON: {e}")
            optimization_result = {}
    
    # Emit result event for listeners
    await router.emit("evaluation:result", {
        "evaluation_id": evaluation_id,
        "optimization_id": optimization_id,
        "recommendation": evaluation.get("recommendation", "reject"),
        "evaluation": evaluation
    })
    
    # Handle acceptance
    if evaluation.get("recommendation") == "accept":
        component_name = optimization_result.get("component_name")
        optimized_content = optimization_result.get("optimized_content")
        
        if component_name and optimized_content:
            # Update component
            update_result = await router.emit("composition:create_component", {
                "name": component_name,
                "content": optimized_content,
                "metadata": {
                    "optimization_id": optimization_id,
                    "evaluation_id": evaluation_id,
                    "judge_confidence": evaluation.get("confidence")
                }
            })
            
            logger.info(f"Component {component_name} updated with optimization {optimization_id}")
            
            # Optionally commit to git
            if not skip_git:
                commit_result = await _commit_optimization(
                    router=router,
                    component_name=component_name,
                    optimization_id=optimization_id,
                    evaluation=evaluation
                )
                logger.info(f"Git commit result: {commit_result}")
    
    return success_response(
        data={
            "evaluation_id": evaluation_id,
            "recommendation": evaluation.get("recommendation", "reject"),
            "confidence": evaluation.get("confidence", "unknown")
        },
        context=context,
        message="Evaluation completed"
    )


@event_handler("optimization:evaluate_result")
async def handle_optimization_evaluate_result(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle optimization result evaluation requests."""
    # Validate required fields
    error = validate_required_fields(data, ["optimization_id", "optimization_result"], context)
    if error:
        return error
    
    optimization_id = data.get("optimization_id")
    optimization_result = data.get("optimization_result", {})
    if not optimization_result:
        return error_response("optimization_result is required", context)
    
    # Route through async evaluation
    return await handle_evaluation_async({
        "optimization_id": optimization_id,
        "optimization_result": optimization_result,
        "skip_git": data.get("skip_git", False)
    }, context)


@event_handler("optimization:process_completion")
async def handle_optimization_process_completion(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle optimization completion events and automatically evaluate."""
    router = get_router()
    
    # Validate required fields
    error = validate_required_fields(data, ["optimization_id"], context)
    if error:
        return error
    
    optimization_id = data.get("optimization_id")
    
    try:
        # Get optimization status
        status_result = await router.emit("optimization:status", {
            "optimization_id": optimization_id
        })
        
        status_result = extract_single_response(status_result)
        
        if status_result.get("status") != "completed":
            return error_response(
                f"Optimization {optimization_id} not completed",
                context,
                details={"current_status": status_result.get("status")}
            )
        
        # Build optimization result from status
        metadata = status_result.get("metadata", {})
        optimization_result = {
            "component_name": metadata.get("component", ""),
            "original_content": data.get("original_content", ""),
            "optimized_content": data.get("optimized_content", ""),
            "optimization_metadata": metadata
        }
        
        # Route through async evaluation
        return await handle_evaluation_async({
            "optimization_id": optimization_id,
            "optimization_result": optimization_result,
            "skip_git": data.get("skip_git", False)
        }, context)
        
    except Exception as e:
        logger.error(f"Error processing optimization completion {optimization_id}: {e}")
        return error_response(e, context)


# Helper functions (pure, no class needed)

def _build_evaluation_prompt(
    component_name: str,
    original_content: str,
    optimized_content: str,
    optimization_metadata: Dict[str, Any]
) -> str:
    """Build evaluation prompt for LLM-as-Judge."""
    
    optimizer_name = optimization_metadata.get("optimizer", "Unknown")
    
    return f"""Evaluate this DSPy optimization result using pairwise comparison methodology.

**Component**: {component_name}
**Optimizer**: {optimizer_name}
**Optimization Metadata**: {json.dumps(optimization_metadata, indent=2)}

## Original Component
```markdown
{original_content}
```

## Optimized Component  
```markdown
{optimized_content}
```

## Your Task
Compare the original vs optimized component using the evaluation criteria in your instructions. Provide a clear recommendation: accept, reject, or revise.

Focus on:
1. **Clarity and Specificity** - Are instructions clearer and more precise?
2. **Completeness and Actionability** - Is all necessary information provided?
3. **KSI Integration Quality** - Are event patterns and system communication improved?
4. **Behavioral Effectiveness** - Is the component more likely to produce desired behavior?

Provide your evaluation in the specified JSON format with detailed reasoning."""


def _extract_evaluation_from_response(response: str) -> Dict[str, Any]:
    """Extract evaluation data from judge agent response.
    
    Note: This function is not currently used since we listen for agent:result events
    which already contain structured evaluation data. Kept for potential future use."""
    
    # Use ksi_common's json extraction utilities
    def is_evaluation_event(obj: Dict[str, Any]) -> bool:
        """Check if JSON object is an evaluation event."""
        # Check for agent:result event with evaluation data
        if (obj.get("event") == "agent:result" and 
            obj.get("data", {}).get("result_type") == "optimization_assessment"):
            return True
        # Check for direct evaluation structure
        if "recommendation" in obj:
            return True
        return False
    
    # Extract all JSON objects and filter for evaluation events
    extracted_objects = extract_json_objects(response, filter_func=is_evaluation_event)
    
    # Process extracted objects
    for obj in extracted_objects:
        # If it's an agent:result event, extract the evaluation data
        if obj.get("event") == "agent:result":
            evaluation = obj.get("data", {}).get("evaluation", {})
            if evaluation:
                return evaluation
        # If it's a direct evaluation object
        elif "recommendation" in obj:
            return obj
    
    # Default fallback if no evaluation found
    logger.warning(f"Could not extract evaluation from response: {response[:200]}...")
    return {
        "recommendation": "reject",
        "confidence": "low",
        "reasoning": "Could not parse judge evaluation - defaulting to reject"
    }


@event_handler("comparison:evaluate")
async def handle_comparison_evaluate(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """General component comparison - not tied to optimization."""
    router = get_router()
    
    # Validate required fields
    error = validate_required_fields(data, ["component_name", "original_content", "improved_content"], context)
    if error:
        return error
    
    # Extract component comparison data
    component_name = data.get("component_name")
    original_content = data.get("original_content")
    improved_content = data.get("improved_content")
    metadata = data.get("metadata", {})
    
    # Handle case where metadata might be a JSON string from CLI
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    
    skip_git = data.get("skip_git", True)  # Default to no git for comparisons
    
    # Convert to optimization_result format for internal processing
    optimization_result = {
        "component_name": component_name,
        "original_content": original_content,
        "optimized_content": improved_content,
        "optimization_metadata": metadata
    }
    
    # Use the async evaluation flow
    return await handle_evaluation_async({
        "optimization_result": optimization_result,
        "skip_git": skip_git
    }, context)


async def _commit_optimization(
    router,
    component_name: str,
    optimization_id: str,
    evaluation: Dict[str, Any]
) -> Dict[str, Any]:
    """Commit optimization to git with descriptive message."""
    
    try:
        # Use KSI's git integration
        confidence = evaluation.get("confidence", "unknown")
        recommendation = evaluation.get("recommendation", "unknown")
        
        commit_message = f"""feat: Apply improvements to {component_name}

{f'Optimization ID: {optimization_id}' if optimization_id else 'Source: Manual improvement'}
Judge Decision: {recommendation} (confidence: {confidence})
{f'Optimizer: {evaluation.get("optimizer", "Unknown")}' if optimization_id else 'Method: Component comparison'}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
        
        # Emit git commit event (assuming such a handler exists)
        # This would be better than direct subprocess calls
        commit_result = await router.emit("git:commit", {
            "path": config.compositions_base_path,
            "files": [f"components/{component_name}.md"],
            "message": commit_message
        })
        
        commit_result = extract_single_response(commit_result)
        
        return commit_result
        
    except Exception as e:
        logger.error(f"Error committing optimization {optimization_id}: {e}")
        # Fallback to subprocess if git event doesn't exist
        import subprocess
        
        compositions_dir = Path(config.compositions_base_path)
        
        try:
            # Stage the file
            subprocess.run(
                ["git", "add", f"components/{component_name}.md"],
                cwd=compositions_dir,
                check=True
            )
            
            # Commit
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=compositions_dir,
                check=True
            )
            
            return success_response({"method": "subprocess"}, message="Component committed to git")
        except subprocess.CalledProcessError as sp_error:
            return error_response(f"Git operation failed: {str(sp_error)}")