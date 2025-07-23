"""Optimization result evaluation service using LLM-as-Judge methodology."""

import json
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.config import config

logger = get_bound_logger("optimization_evaluation")


class OptimizationEvaluationService:
    """Service for evaluating optimization results using LLM-as-Judge."""
    
    def __init__(self):
        self.router = None
        
    async def initialize(self, system_context: Dict[str, Any]):
        """Initialize the evaluation service with system context."""
        self.router = get_router()
        logger.info("Optimization evaluation service initialized")
    
    async def process_optimization_completion(
        self, 
        optimization_id: str,
        optimization_result: Dict[str, Any],
        skip_git: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Process completed optimization and route through LLM-as-Judge pipeline."""
        
        try:
            logger.info(f"Processing optimization completion: {optimization_id}")
            
            # Extract optimization artifacts and metadata
            component_name = optimization_result.get("component_name")
            original_content = optimization_result.get("original_content")
            optimized_content = optimization_result.get("optimized_content")
            
            if not all([component_name, original_content, optimized_content]):
                return {
                    "status": "error",
                    "message": "Missing required optimization result fields",
                    "optimization_id": optimization_id
                }
            
            # Spawn LLM-as-Judge agent for evaluation
            judge_result = await self._spawn_optimization_judge(
                optimization_id=optimization_id,
                component_name=component_name,
                original_content=original_content,
                optimized_content=optimized_content,
                optimization_metadata=optimization_result.get("optimization_metadata", {})
            )
            
            if judge_result.get("status") == "error":
                return judge_result
            
            # Process judge's decision
            evaluation = judge_result.get("evaluation", {})
            recommendation = evaluation.get("recommendation", "reject")
            
            if recommendation == "accept":
                # Update component in composition system
                update_result = await self._update_component(
                    component_name=component_name,
                    optimized_content=optimized_content,
                    optimization_id=optimization_id,
                    evaluation=evaluation
                )
                
                if update_result.get("status") == "success":
                    # Commit to git unless explicitly skipped
                    if skip_git:
                        logger.info(f"Skipping git commit for optimization {optimization_id} as requested")
                        commit_result = {"status": "skipped", "message": "Git operations disabled"}
                    else:
                        commit_result = await self._commit_optimization(
                            component_name=component_name,
                            optimization_id=optimization_id,
                            evaluation=evaluation
                        )
                    
                    return {
                        "status": "completed",
                        "optimization_id": optimization_id,
                        "recommendation": "accepted",
                        "component_updated": True,
                        "git_committed": commit_result.get("status") == "success",
                        "git_skipped": skip_git,
                        "evaluation": evaluation
                    }
                else:
                    return {
                        "status": "error",
                        "optimization_id": optimization_id,
                        "message": "Failed to update component",
                        "details": update_result
                    }
            
            elif recommendation == "revise":
                # Queue for manual review or trigger re-optimization
                return {
                    "status": "pending_revision",
                    "optimization_id": optimization_id,
                    "recommendation": "revise", 
                    "evaluation": evaluation,
                    "message": "Optimization requires revision based on judge evaluation"
                }
            
            else:  # reject
                return {
                    "status": "rejected",
                    "optimization_id": optimization_id,
                    "recommendation": "rejected",
                    "evaluation": evaluation,
                    "message": "Optimization rejected by LLM-as-Judge"
                }
                
        except Exception as e:
            logger.error(f"Error processing optimization completion {optimization_id}: {e}")
            return {
                "status": "error",
                "optimization_id": optimization_id,
                "message": f"Evaluation service error: {str(e)}"
            }
    
    async def _spawn_optimization_judge(
        self,
        optimization_id: str,
        component_name: str,
        original_content: str,
        optimized_content: str,
        optimization_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Spawn LLM-as-Judge agent to evaluate optimization results."""
        
        try:
            # Spawn judge agent using the optimization_judge component
            spawn_result = await self.router.emit(
                "agent:spawn_from_component",
                {
                    "component": "components/evaluations/quality/optimization_judge",
                    "agent_name": f"optimization_judge_{optimization_id}",
                    "metadata": {
                        "optimization_id": optimization_id,
                        "component_name": component_name,
                        "purpose": "optimization_evaluation"
                    }
                }
            )
            
            if spawn_result.get("status") != "success":
                return {
                    "status": "error",
                    "message": "Failed to spawn optimization judge agent",
                    "details": spawn_result
                }
            
            judge_agent_id = spawn_result.get("agent_id")
            
            # Prepare evaluation prompt with both components
            evaluation_prompt = self._build_evaluation_prompt(
                component_name=component_name,
                original_content=original_content,
                optimized_content=optimized_content,
                optimization_metadata=optimization_metadata
            )
            
            # Send evaluation task to judge agent
            completion_result = await self.router.emit(
                "completion:async",
                {
                    "agent_id": judge_agent_id,
                    "prompt": evaluation_prompt,
                    "timeout": 180  # 3 minutes for evaluation
                }
            )
            
            if completion_result.get("status") != "success":
                return {
                    "status": "error", 
                    "message": "Judge agent completion failed",
                    "details": completion_result
                }
            
            # Extract evaluation from agent response
            evaluation_data = self._extract_evaluation_from_response(
                completion_result.get("response", "")
            )
            
            return {
                "status": "success",
                "judge_agent_id": judge_agent_id,
                "evaluation": evaluation_data
            }
            
        except Exception as e:
            logger.error(f"Error spawning optimization judge: {e}")
            return {
                "status": "error",
                "message": f"Judge spawn error: {str(e)}"
            }
    
    def _build_evaluation_prompt(
        self,
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

Provide your evaluation in the specified JSON format with detailed reasoning.
"""
    
    def _extract_evaluation_from_response(self, response: str) -> Dict[str, Any]:
        """Extract evaluation data from judge agent response."""
        
        # Look for agent:result event with evaluation data
        import re
        
        # Find JSON blocks in response
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        json_matches = re.findall(json_pattern, response, re.DOTALL)
        
        # Also look for direct JSON (without code blocks)
        direct_json_pattern = r'\{"event":\s*"agent:result".*?\}'
        direct_matches = re.findall(direct_json_pattern, response, re.DOTALL)
        
        all_matches = json_matches + direct_matches
        
        for match in all_matches:
            try:
                parsed = json.loads(match)
                if (parsed.get("event") == "agent:result" and 
                    parsed.get("data", {}).get("result_type") == "optimization_evaluation"):
                    return parsed.get("data", {}).get("evaluation", {})
            except json.JSONDecodeError:
                continue
        
        # Fallback: look for any evaluation-like structure
        try:
            # Try to find any JSON with evaluation fields
            eval_pattern = r'\{[^}]*"overall_winner"[^}]*\}'
            eval_matches = re.findall(eval_pattern, response, re.DOTALL)
            for match in eval_matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        except:
            pass
        
        # Default fallback
        logger.warning(f"Could not extract evaluation from response: {response[:200]}...")
        return {
            "overall_winner": "tie",
            "confidence": "low", 
            "recommendation": "reject",
            "reasoning": "Could not parse judge evaluation - defaulting to reject"
        }
    
    async def _update_component(
        self,
        component_name: str,
        optimized_content: str,
        optimization_id: str,
        evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update component in composition system with optimized content."""
        
        try:
            # Update component using composition:create_component
            # This will overwrite the existing component with optimized version
            update_result = await self.router.emit(
                "composition:create_component",
                {
                    "name": component_name,
                    "content": optimized_content,
                    "metadata": {
                        "optimization_id": optimization_id,
                        "optimization_accepted": True,
                        "judge_confidence": evaluation.get("confidence"),
                        "judge_reasoning": evaluation.get("reasoning", "")[:200]
                    }
                }
            )
            
            if update_result.get("status") == "success":
                logger.info(f"Component {component_name} updated with optimization {optimization_id}")
                return {"status": "success", "component_name": component_name}
            else:
                logger.error(f"Failed to update component {component_name}: {update_result}")
                return {"status": "error", "details": update_result}
                
        except Exception as e:
            logger.error(f"Error updating component {component_name}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _commit_optimization(
        self,
        component_name: str,
        optimization_id: str,
        evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Commit optimization to git with descriptive message."""
        
        try:
            import subprocess
            from pathlib import Path
            
            # Change to compositions directory for git operations
            compositions_dir = Path(config.compositions_base_path)
            
            # Check git status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=compositions_dir,
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                logger.info(f"No changes to commit for optimization {optimization_id}")
                return {"status": "success", "message": "No changes to commit"}
            
            # Stage the component file
            add_result = subprocess.run(
                ["git", "add", f"components/{component_name}.md"],
                cwd=compositions_dir,
                capture_output=True,
                text=True
            )
            
            if add_result.returncode != 0:
                return {"status": "error", "message": f"Git add failed: {add_result.stderr}"}
            
            # Create commit message
            confidence = evaluation.get("confidence", "unknown")
            winner = evaluation.get("overall_winner", "unknown")
            
            commit_message = f"""feat: Apply DSPy optimization to {component_name}

Optimization ID: {optimization_id}
Judge Decision: {winner} (confidence: {confidence})
Optimizer: DSPy MIPROv2 zero-shot

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
            
            # Commit the changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=compositions_dir,
                capture_output=True,
                text=True
            )
            
            if commit_result.returncode == 0:
                logger.info(f"Optimization {optimization_id} committed to git")
                return {
                    "status": "success",
                    "commit_message": commit_message,
                    "component_name": component_name
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Git commit failed: {commit_result.stderr}"
                }
                
        except Exception as e:
            logger.error(f"Error committing optimization {optimization_id}: {e}")
            return {"status": "error", "message": str(e)}


# Global service instance
evaluation_service = OptimizationEvaluationService()


@event_handler("optimization:evaluate_result")
async def handle_optimization_evaluate_result(data, context):
    """Handle optimization result evaluation requests."""
    
    if evaluation_service.router is None:
        await evaluation_service.initialize(context)
    
    optimization_id = data.get("optimization_id")
    if not optimization_id:
        return {"status": "error", "message": "optimization_id is required"}
    
    # Get optimization result (this should come from the completed optimization)
    optimization_result = data.get("optimization_result", {})
    
    if not optimization_result:
        return {"status": "error", "message": "optimization_result is required"}
    
    # Process through evaluation pipeline
    result = await evaluation_service.process_optimization_completion(
        optimization_id=optimization_id,
        optimization_result=optimization_result,
        **data
    )
    
    return result


@event_handler("optimization:process_completion")  
async def handle_optimization_process_completion(data, context):
    """Handle optimization completion events and automatically evaluate."""
    
    if evaluation_service.router is None:
        await evaluation_service.initialize(context)
    
    optimization_id = data.get("optimization_id")
    if not optimization_id:
        return {"status": "error", "message": "optimization_id is required"}
    
    # This handler would be called when an optimization completes successfully
    # It should retrieve the optimization result and route it through evaluation
    
    try:
        # Get optimization status/result 
        router = get_router()
        status_result = await router.emit("optimization:status", {"optimization_id": optimization_id})
        
        if status_result.get("status") != "completed":
            return {
                "status": "error",
                "message": f"Optimization {optimization_id} not completed",
                "current_status": status_result.get("status")
            }
        
        # Extract optimization result from status
        optimization_result = {
            "component_name": status_result.get("metadata", {}).get("component", "unknown"),
            "original_content": data.get("original_content", ""),
            "optimized_content": data.get("optimized_content", ""), 
            "optimization_metadata": status_result.get("metadata", {})
        }
        
        # Process through evaluation pipeline
        result = await evaluation_service.process_optimization_completion(
            optimization_id=optimization_id,
            optimization_result=optimization_result,
            skip_git=data.get("skip_git", False)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing optimization completion {optimization_id}: {e}")
        return {"status": "error", "message": str(e)}