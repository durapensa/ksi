"""Agent-based behavioral evaluation metric for DSPy optimization."""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import get_router

logger = get_bound_logger("agent_behavioral_metric")

# Suppress noise during metric evaluation
logging.getLogger("dspy").setLevel(logging.WARNING)


@dataclass
class BehavioralTestCase:
    """Test case for behavioral evaluation."""
    prompt: str
    expected_behaviors: List[str]
    weight: float = 1.0


class AgentBehavioralMetric:
    """
    Metric that evaluates actual agent behavior by spawning test agents
    and comparing their outputs.
    """
    
    def __init__(
        self,
        test_cases: Optional[List[BehavioralTestCase]] = None,
        test_suite: str = "behavioral_effectiveness",
        spawn_timeout: int = 30,
        completion_timeout: int = 60
    ):
        self.test_cases = test_cases or self._get_default_test_cases()
        self.test_suite = test_suite
        self.spawn_timeout = spawn_timeout
        self.completion_timeout = completion_timeout
        self.router = None
        self._loop = None
        
    def _get_default_test_cases(self) -> List[BehavioralTestCase]:
        """Default behavioral test cases."""
        return [
            BehavioralTestCase(
                prompt="Analyze this data: [1, 2, 3, 4, 5]. Emit your findings as JSON.",
                expected_behaviors=["json_emission", "data_analysis"],
                weight=1.5
            ),
            BehavioralTestCase(
                prompt="Process this request and report your status using KSI events.",
                expected_behaviors=["status_reporting", "event_emission"],
                weight=1.0
            ),
            BehavioralTestCase(
                prompt="Examine this pattern and provide structured insights: A->B->C->A",
                expected_behaviors=["pattern_recognition", "structured_output"],
                weight=1.0
            )
        ]
    
    async def _ensure_router(self):
        """Ensure router is initialized."""
        if self.router is None:
            self.router = get_router()
    
    async def evaluate_behavior_async(
        self,
        instruction: str,
        component_name: str = "test_component"
    ) -> float:
        """
        Evaluate agent behavior with given instructions.
        
        Returns score from 0.0 to 1.0 based on behavioral effectiveness.
        """
        await self._ensure_router()
        
        try:
            # Create temporary component with instructions
            temp_component_name = f"temp/optimization/{component_name}_test"
            
            # Build component content with the instruction
            component_content = f"""---
component_type: agent
name: {component_name}_behavioral_test
version: 1.0.0
description: Temporary component for behavioral testing
dependencies:
  - behaviors/communication/ksi_events_as_tool_calls
---

{instruction}
"""
            
            # Create temporary component
            create_result = await self.router.emit(
                "composition:create_component",
                {
                    "name": temp_component_name,
                    "content": component_content,
                    "metadata": {"temporary": True, "purpose": "optimization_testing"}
                }
            )
            
            if create_result.get("status") != "success":
                logger.error(f"Failed to create test component: {create_result}")
                return 0.0
            
            # Spawn test agent
            spawn_result = await self.router.emit(
                "agent:spawn_from_component",
                {
                    "component": f"components/{temp_component_name}",
                    "agent_name": f"behavioral_test_{component_name}",
                    "metadata": {"purpose": "behavioral_testing"}
                },
                timeout=self.spawn_timeout
            )
            
            if spawn_result.get("status") != "success":
                logger.error(f"Failed to spawn test agent: {spawn_result}")
                return 0.0
            
            agent_id = spawn_result.get("agent_id")
            
            # Run test cases
            total_score = 0.0
            total_weight = 0.0
            
            for test_case in self.test_cases:
                try:
                    # Send test prompt
                    completion_result = await self.router.emit(
                        "completion:async",
                        {
                            "agent_id": agent_id,
                            "prompt": test_case.prompt
                        },
                        timeout=self.completion_timeout
                    )
                    
                    if completion_result.get("status") == "success":
                        response = completion_result.get("response", "")
                        
                        # Evaluate response against expected behaviors
                        case_score = self._evaluate_response(
                            response,
                            test_case.expected_behaviors
                        )
                        
                        total_score += case_score * test_case.weight
                        total_weight += test_case.weight
                    else:
                        logger.warning(f"Test case completion failed: {completion_result}")
                        
                except Exception as e:
                    logger.error(f"Error running test case: {e}")
            
            # Clean up test agent
            try:
                await self.router.emit(
                    "agent:terminate",
                    {"agent_id": agent_id}
                )
            except:
                pass
            
            # Calculate final score
            if total_weight > 0:
                return total_score / total_weight
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error in behavioral evaluation: {e}")
            return 0.0
    
    def _evaluate_response(self, response: str, expected_behaviors: List[str]) -> float:
        """Evaluate response against expected behaviors."""
        score = 0.0
        behavior_count = len(expected_behaviors)
        
        for behavior in expected_behaviors:
            if behavior == "json_emission":
                # Check for valid JSON in response
                if self._contains_valid_json(response):
                    score += 1.0 / behavior_count
                    
            elif behavior == "data_analysis":
                # Check for analysis indicators
                analysis_keywords = ["analysis", "findings", "insights", "patterns", "trend"]
                if any(kw in response.lower() for kw in analysis_keywords):
                    score += 1.0 / behavior_count
                    
            elif behavior == "status_reporting":
                # Check for status-related content
                status_keywords = ["status", "complete", "ready", "initialized", "progress"]
                if any(kw in response.lower() for kw in status_keywords):
                    score += 1.0 / behavior_count
                    
            elif behavior == "event_emission":
                # Check for KSI event patterns
                if '"event"' in response or '"type": "ksi_tool_use"' in response:
                    score += 1.0 / behavior_count
                    
            elif behavior == "pattern_recognition":
                # Check for pattern analysis
                pattern_keywords = ["pattern", "cycle", "sequence", "relationship"]
                if any(kw in response.lower() for kw in pattern_keywords):
                    score += 1.0 / behavior_count
                    
            elif behavior == "structured_output":
                # Check for structured formatting
                structure_indicators = ["\n-", "\n*", "\n1.", "##", "**"]
                if any(ind in response for ind in structure_indicators):
                    score += 1.0 / behavior_count
        
        return score
    
    def _contains_valid_json(self, text: str) -> bool:
        """Check if text contains valid JSON."""
        import re
        
        # Look for JSON-like patterns
        json_patterns = [
            r'\{[^{}]*"event"[^{}]*\}',
            r'\{[^{}]*"type"[^{}]*"ksi_tool_use"[^{}]*\}',
            r'\{[^{}]*"data"[^{}]*\}'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match)
                    return True
                except:
                    continue
        
        return False
    
    def __call__(self, example, prediction, trace=None):
        """
        Synchronous wrapper for DSPy compatibility.
        
        Args:
            example: DSPy example with current_instruction field
            prediction: DSPy prediction with optimized_instruction field
            trace: Optional trace for bootstrapping mode
            
        Returns:
            float score (0.0-1.0) or bool for bootstrapping
        """
        # Extract instruction from prediction
        if hasattr(prediction, 'optimized_instruction'):
            instruction = str(prediction.optimized_instruction)
        elif hasattr(prediction, 'answer'):
            instruction = str(prediction.answer)
        else:
            instruction = str(prediction)
        
        # Basic validation
        if len(instruction) < 50:
            return False if trace is not None else 0.1
        
        # For bootstrapping, use simple heuristic
        if trace is not None:
            # In bootstrapping mode, accept any reasonable attempt
            return len(instruction) > 100 and instruction != str(example.current_instruction)
        
        # For optimization, run behavioral evaluation
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async evaluation
            score = loop.run_until_complete(
                self.evaluate_behavior_async(
                    instruction,
                    component_name=getattr(example, 'component_name', 'unknown')
                )
            )
            
            return score
            
        except Exception as e:
            logger.error(f"Error in synchronous metric wrapper: {e}")
            # Fallback to baseline score
            return 0.3


def create_behavioral_metric(
    test_suite: str = "behavioral_effectiveness",
    **kwargs
) -> AgentBehavioralMetric:
    """
    Factory function to create behavioral metric for DSPy optimization.
    
    Args:
        test_suite: Name of test suite to use
        **kwargs: Additional arguments for AgentBehavioralMetric
        
    Returns:
        Configured AgentBehavioralMetric instance
    """
    return AgentBehavioralMetric(test_suite=test_suite, **kwargs)