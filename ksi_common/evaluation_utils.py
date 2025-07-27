#!/usr/bin/env python3
"""
Shared utilities for evaluation orchestration.

Provides common patterns for:
- Loading evaluation components
- Orchestrating judge evaluations
- Managing evaluation workflows
- Integrating with optimization system
"""

from typing import Dict, Any, List, Optional, Tuple
import asyncio
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("evaluation_utils")


class EvaluationOrchestrator:
    """Orchestrates evaluation workflows using composition components."""
    
    def __init__(self, event_emitter):
        """Initialize with event emitter for composition system access."""
        self.event_emitter = event_emitter
        self._judge_cache = {}
        self._technique_cache = {}
    
    async def get_available_techniques(self, judge_role: str) -> List[Dict[str, Any]]:
        """Get available techniques for a judge role from composition system."""
        cache_key = f"{judge_role}_techniques"
        
        if cache_key in self._technique_cache:
            return self._technique_cache[cache_key]
        
        # Query composition system for technique catalog
        result = await self.event_emitter("composition:get_component", {
            "name": f"evaluations/techniques/{judge_role}_techniques"
        })
        
        if result and result.get("status") == "success":
            component = result.get("component", {})
            # Parse techniques from component content
            techniques = self._parse_techniques_from_component(component)
            self._technique_cache[cache_key] = techniques
            return techniques
        
        logger.warning(f"No techniques found for {judge_role}")
        return []
    
    def _parse_techniques_from_component(self, component: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse technique definitions from a technique catalog component."""
        techniques = []
        content = component.get("content", "")
        
        # Simple parsing - in production, use proper markdown parser
        # For now, extract technique info from markdown structure
        current_technique = None
        
        for line in content.split('\n'):
            if line.startswith('### ') and not line.startswith('### '):
                if current_technique:
                    techniques.append(current_technique)
                current_technique = {"name": line[4:].strip()}
            elif current_technique and line.startswith('- **Name**: '):
                current_technique["id"] = line.split('`')[1]
            elif current_technique and line.startswith('- **Description**: '):
                current_technique["description"] = line[19:].strip()
            elif current_technique and line.startswith('- **Component**: '):
                current_technique["component"] = line.split('`')[1]
        
        if current_technique:
            techniques.append(current_technique)
        
        return techniques
    
    async def spawn_judge(self, judge_type: str, technique: str, config: Optional[Dict[str, Any]] = None) -> str:
        """Spawn a judge agent with specified technique."""
        # Get technique details
        techniques = await self.get_available_techniques(judge_type)
        technique_info = next((t for t in techniques if t["id"] == technique), None)
        
        if not technique_info:
            raise ValueError(f"Unknown technique {technique} for {judge_type}")
        
        # Spawn agent using the component
        spawn_result = await self.event_emitter("agent:spawn", {
            "component": technique_info["component"],
            "agent_id": f"{judge_type}_{technique}_{timestamp_utc()}",
            "variables": config or {}
        })
        
        if spawn_result and spawn_result.get("status") == "created":
            agent_id = spawn_result["agent_id"]
            logger.info(f"Spawned {judge_type} judge with {technique} technique: {agent_id}")
            return agent_id
        
        raise RuntimeError(f"Failed to spawn judge: {spawn_result}")
    
    async def evaluate_with_judge(self, judge_agent_id: str, evaluation_request: Dict[str, Any]) -> Dict[str, Any]:
        """Send evaluation request to judge and get response."""
        result = await self.event_emitter("agent:send_message", {
            "agent_id": judge_agent_id,
            "message": evaluation_request
        })
        
        if result and result.get("status") == "sent_to_completion":
            # Wait for completion result
            # In production, use proper async waiting with completion:result events
            await asyncio.sleep(2)  # Simple wait for demo
            
            # Get agent response
            response = await self.event_emitter("agent:get_last_response", {
                "agent_id": judge_agent_id
            })
            
            return response
        
        return {"error": "Failed to get judge response"}


class EvaluationWorkflow:
    """Manages evaluation workflows and patterns."""
    
    def __init__(self, orchestrator: EvaluationOrchestrator):
        self.orchestrator = orchestrator
    
    async def run_pairwise_evaluation(self, 
                                     judge_type: str,
                                     technique: str,
                                     option_a: Dict[str, Any],
                                     option_b: Dict[str, Any],
                                     criteria: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run pairwise comparison evaluation."""
        # Spawn judge
        judge_id = await self.orchestrator.spawn_judge(judge_type, technique)
        
        # Prepare evaluation request
        evaluation_request = {
            "evaluation_type": "pairwise_comparison",
            "option_a": option_a,
            "option_b": option_b,
            "criteria": criteria or ["quality", "clarity", "effectiveness"],
            "output_format": "structured_json"
        }
        
        # Get evaluation
        result = await self.orchestrator.evaluate_with_judge(judge_id, evaluation_request)
        
        # Terminate judge
        await self.orchestrator.event_emitter("agent:terminate", {"agent_id": judge_id})
        
        return result
    
    async def run_ground_truth_evaluation(self,
                                        judge_type: str,
                                        technique: str,
                                        test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate judge against ground truth cases."""
        # Load evaluation rubric
        rubric_result = await self.orchestrator.event_emitter("composition:get_component", {
            "name": "evaluations/ground_truth/judge_evaluation_rubric"
        })
        
        if not rubric_result or rubric_result.get("status") != "success":
            raise ValueError("Could not load evaluation rubric")
        
        # Spawn judge
        judge_id = await self.orchestrator.spawn_judge(judge_type, technique)
        
        results = []
        for test_case in test_cases:
            # Evaluate test case
            response = await self.orchestrator.evaluate_with_judge(judge_id, test_case["input"])
            
            # Score against expected output
            score = self._score_response(response, test_case["expected_output"], test_case.get("rubric", {}))
            
            results.append({
                "case_id": test_case["id"],
                "score": score,
                "response": response
            })
        
        # Calculate aggregate scores
        total_score = sum(r["score"] for r in results) / len(results) if results else 0.0
        
        # Terminate judge
        await self.orchestrator.event_emitter("agent:terminate", {"agent_id": judge_id})
        
        return {
            "judge_type": judge_type,
            "technique": technique,
            "total_score": total_score,
            "results": results
        }
    
    def _score_response(self, response: Dict[str, Any], expected: Dict[str, Any], rubric: Dict[str, float]) -> float:
        """Score response against expected output using rubric."""
        # Simple scoring implementation - in production, use more sophisticated comparison
        if not rubric:
            rubric = {
                "format_compliance": 0.2,
                "accuracy": 0.4,
                "completeness": 0.3,
                "reasoning_quality": 0.1
            }
        
        total_score = 0.0
        
        # Check format compliance
        if isinstance(response, dict) and isinstance(expected, dict):
            if set(response.keys()) == set(expected.keys()):
                total_score += rubric.get("format_compliance", 0.2)
        
        # Simple accuracy check (in production, use semantic similarity)
        if response == expected:
            total_score += rubric.get("accuracy", 0.4)
        
        # Add partial scores for completeness and reasoning
        # In production, implement proper evaluation logic
        total_score += rubric.get("completeness", 0.3) * 0.5
        total_score += rubric.get("reasoning_quality", 0.1) * 0.5
        
        return min(total_score, 1.0)


class OptimizationEvaluationBridge:
    """Bridges optimization and evaluation systems."""
    
    def __init__(self, event_emitter):
        self.event_emitter = event_emitter
        self.orchestrator = EvaluationOrchestrator(event_emitter)
        self.workflow = EvaluationWorkflow(self.orchestrator)
    
    async def evaluate_optimization_result(self, 
                                         optimization_result: Dict[str, Any],
                                         evaluation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an optimization result using appropriate judges."""
        # Determine judge type based on optimization type
        optimization_type = optimization_result.get("optimization_type", "general")
        
        judge_mapping = {
            "instruction_optimization": "instruction_optimization_judge",
            "component_optimization": "improvement_judge",
            "mipro_optimization": "optimization_judge",
            "general": "response_quality_judge"
        }
        
        judge_component = judge_mapping.get(optimization_type, "response_quality_judge")
        
        # For pairwise comparison (before vs after)
        if optimization_result.get("original") and optimization_result.get("optimized"):
            result = await self.workflow.run_pairwise_evaluation(
                judge_type="evaluator",
                technique="holistic_quality",
                option_a=optimization_result["original"],
                option_b=optimization_result["optimized"],
                criteria=evaluation_config.get("criteria", ["effectiveness", "clarity", "efficiency"])
            )
            
            return {
                "evaluation_type": "pairwise_comparison",
                "result": result,
                "optimization_id": optimization_result.get("id"),
                "timestamp": timestamp_utc()
            }
        
        # For single result evaluation
        else:
            # Spawn appropriate judge
            judge_result = await self.event_emitter("agent:spawn", {
                "component": f"evaluations/judges/{judge_component}"
            })
            
            if judge_result and judge_result.get("status") == "created":
                judge_id = judge_result["agent_id"]
                
                # Evaluate
                evaluation = await self.orchestrator.evaluate_with_judge(
                    judge_id,
                    {
                        "content": optimization_result.get("result", optimization_result),
                        "evaluation_criteria": evaluation_config.get("criteria", [])
                    }
                )
                
                # Cleanup
                await self.event_emitter("agent:terminate", {"agent_id": judge_id})
                
                return {
                    "evaluation_type": "single_evaluation",
                    "result": evaluation,
                    "optimization_id": optimization_result.get("id"),
                    "timestamp": timestamp_utc()
                }
            
            return {"error": "Failed to spawn evaluation judge"}
    
    async def run_optimization_tournament(self,
                                        candidates: List[Dict[str, Any]],
                                        tournament_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run tournament evaluation for multiple optimization candidates."""
        # Use existing tournament infrastructure
        tournament_result = await self.event_emitter("evaluation:tournament", {
            "candidates": candidates,
            "judge_config": {
                "judge_type": tournament_config.get("judge_type", "optimization_judge"),
                "technique": tournament_config.get("technique", "pairwise_comparison")
            },
            "rounds": tournament_config.get("rounds", 1),
            "criteria": tournament_config.get("criteria", ["effectiveness", "efficiency", "clarity"])
        })
        
        return tournament_result


# Factory function for easy import
def create_evaluation_orchestrator(event_emitter) -> EvaluationOrchestrator:
    """Create an evaluation orchestrator instance."""
    return EvaluationOrchestrator(event_emitter)


def create_optimization_bridge(event_emitter) -> OptimizationEvaluationBridge:
    """Create an optimization-evaluation bridge instance."""
    return OptimizationEvaluationBridge(event_emitter)