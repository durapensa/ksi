#!/usr/bin/env python3
"""
Bridge between prompt testing framework and composition evaluation system.

Integrates prompt test results with composition:evaluate to track which
compositions work well with specific models.
"""

import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

from ksi_socket_utils import KSISocketClient
from prompt_testing_framework import PromptTestRunner, PromptTest


class CompositionEvaluationBridge:
    """
    Connects prompt testing framework to composition evaluation system.
    
    Enables:
    - Running prompt tests against specific compositions
    - Saving test results as composition evaluation metadata
    - Tracking which models work best with which compositions
    """
    
    def __init__(self, socket_path: str = "var/run/daemon.sock"):
        self.client = KSISocketClient(socket_path)
        self.test_runner = PromptTestRunner(socket_path=socket_path)
        
    async def evaluate_composition(self,
                                   composition_name: str,
                                   composition_type: str = "profile",
                                   test_suite: List[PromptTest] = None,
                                   test_suite_name: str = "prompt_effectiveness",
                                   model: str = "claude-cli/sonnet",
                                   update_metadata: bool = False,
                                   notes: str = "") -> Dict[str, Any]:
        """
        Evaluate a composition with prompt tests and optionally save results.
        
        Args:
            composition_name: Name of composition to evaluate
            composition_type: Type of composition (profile, prompt, etc)
            test_suite: List of PromptTest objects to run
            test_suite_name: Name for this test suite
            model: Model to test with
            update_metadata: Whether to save evaluation to composition metadata
            notes: Additional notes about the evaluation
            
        Returns:
            Dict containing evaluation results and status
        """
        if test_suite is None:
            test_suite = self._get_default_test_suite(composition_name)
            
        # Ensure all tests use the specified model
        for test in test_suite:
            test.model = model
            test.profile = composition_name
        
        # Run the test suite
        print(f"\n=== Evaluating Composition: {composition_name} ===")
        print(f"Model: {model}")
        print(f"Test Suite: {test_suite_name}")
        
        test_report = await self.test_runner.run_suite(test_suite)
        
        # Convert test results to composition evaluation format
        test_results = []
        for detailed_result in test_report.get("detailed_results", []):
            test_results.append({
                "test_name": detailed_result["test"],
                "success_rate": 1.0 if detailed_result["success"] else 0.0,
                "avg_response_time": detailed_result["response_time"],
                "contamination_rate": self._calculate_contamination_rate(detailed_result),
                "sample_size": 1,  # Single run per test for now
                "behaviors_found": detailed_result.get("behaviors_found", []),
                "error": detailed_result.get("error")
            })
        
        # Calculate overall metrics
        summary = test_report.get("summary", {})
        contamination = test_report.get("contamination", {})
        
        performance_metrics = {
            "avg_response_time": summary.get("avg_response_time", 0),
            "reliability_score": 1.0 - (summary.get("errors", 0) / summary.get("total_tests", 1)),
            "safety_score": 1.0 - contamination.get("rate", 0),
            "contamination_rate": contamination.get("rate", 0),
            "success_rate": summary.get("success_rate", 0)
        }
        
        # Build test options for composition:evaluate
        test_options = {
            "test_results": test_results,
            "performance_metrics": performance_metrics,
            "notes": notes or f"Automated evaluation using {test_suite_name}"
        }
        
        # Send evaluation to composition system
        evaluation_result = await self.client.send_command_async({
            "event": "composition:evaluate",
            "data": {
                "name": composition_name,
                "type": composition_type,
                "test_suite": test_suite_name,
                "model": model,
                "update_metadata": update_metadata,
                "test_options": test_options
            }
        })
        
        # Add test report to evaluation result
        if evaluation_result.get("status") == "success":
            evaluation_result["test_report"] = test_report
        
        return evaluation_result
    
    def _calculate_contamination_rate(self, result: Dict[str, Any]) -> float:
        """Calculate contamination rate for a single test result."""
        # This is handled by the test runner analysis, but we could
        # do more sophisticated analysis here if needed
        return 0.0  # Placeholder - actual calculation in test runner
    
    def _get_default_test_suite(self, composition_name: str) -> List[PromptTest]:
        """Get default test suite for a composition."""
        # Basic test suite that works for most compositions
        return [
            PromptTest(
                name="simple_greeting",
                profile=composition_name,
                prompt="Hello! Please introduce yourself briefly.",
                expected_behaviors=["greeting", "introduction"],
                tags=["basic", "greeting"]
            ),
            PromptTest(
                name="direct_task",
                profile=composition_name,
                prompt="Count from 1 to 5.",
                expected_behaviors=["counting", "follows_instruction"],
                tags=["basic", "instruction"]
            ),
            PromptTest(
                name="creative_task",
                profile=composition_name,
                prompt="Write a haiku about the ocean.",
                expected_behaviors=["creative", "poetry", "ocean_theme"],
                tags=["creative", "writing"]
            ),
            PromptTest(
                name="analytical_task",
                profile=composition_name,
                prompt="What are the pros and cons of remote work? List 3 of each.",
                expected_behaviors=["analysis", "structured_response", "balanced"],
                tags=["analytical", "reasoning"]
            )
        ]
    
    async def evaluate_multiple_compositions(self,
                                             compositions: List[str],
                                             test_suite: List[PromptTest] = None,
                                             models: List[str] = None,
                                             update_metadata: bool = False) -> Dict[str, Any]:
        """
        Evaluate multiple compositions with multiple models.
        
        Useful for comparative analysis.
        """
        if models is None:
            models = ["claude-cli/sonnet"]
            
        results = {}
        
        for composition in compositions:
            results[composition] = {}
            
            for model in models:
                print(f"\n--- Evaluating {composition} with {model} ---")
                
                eval_result = await self.evaluate_composition(
                    composition_name=composition,
                    test_suite=test_suite,
                    model=model,
                    update_metadata=update_metadata,
                    test_suite_name=f"comparative_{len(models)}_models"
                )
                
                results[composition][model] = eval_result
                
                # Brief pause between evaluations
                await asyncio.sleep(2)
        
        return {
            "compositions_tested": compositions,
            "models_tested": models,
            "results": results,
            "summary": self._summarize_comparative_results(results)
        }
    
    def _summarize_comparative_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize results across compositions and models."""
        summary = {
            "best_overall": None,
            "best_by_model": {},
            "best_by_metric": {}
        }
        
        best_score = 0
        
        for comp_name, model_results in results.items():
            for model, eval_result in model_results.items():
                if eval_result.get("status") != "success":
                    continue
                    
                evaluation = eval_result.get("evaluation", {})
                score = evaluation.get("overall_score", 0)
                
                # Track best overall
                if score > best_score:
                    best_score = score
                    summary["best_overall"] = {
                        "composition": comp_name,
                        "model": model,
                        "score": score
                    }
                
                # Track best by model
                if model not in summary["best_by_model"] or score > summary["best_by_model"][model]["score"]:
                    summary["best_by_model"][model] = {
                        "composition": comp_name,
                        "score": score
                    }
        
        return summary


# Example usage
async def main():
    """Example evaluation run."""
    bridge = CompositionEvaluationBridge()
    
    # Example 1: Evaluate a single composition
    result = await bridge.evaluate_composition(
        composition_name="base_single_agent",
        model="claude-cli/sonnet",
        update_metadata=False,  # Don't save to metadata during testing
        notes="Initial evaluation test"
    )
    
    print("\n=== Evaluation Result ===")
    print(f"Status: {result.get('status')}")
    if result.get('evaluation'):
        print(f"Overall Score: {result['evaluation']['overall_score']:.2f}")
        print(f"Model: {result['evaluation']['model']}")
    
    # Example 2: Compare multiple compositions
    # comparative_results = await bridge.evaluate_multiple_compositions(
    #     compositions=["base_single_agent", "conversationalist"],
    #     models=["claude-cli/sonnet", "claude-cli/opus"]
    # )


if __name__ == "__main__":
    asyncio.run(main())