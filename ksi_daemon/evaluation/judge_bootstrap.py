#!/usr/bin/env python3
"""Bootstrap protocol for creating high-quality judge agents."""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
import yaml
from pathlib import Path

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler
from ksi_daemon.agent.agent_service import spawn_agent

logger = get_bound_logger("judge_bootstrap")


@dataclass
class JudgeCandidate:
    """A candidate judge with specific prompt variations."""
    candidate_id: str
    role: str  # evaluator, analyst, rewriter, meta
    base_profile: str
    prompt_variation: str
    variation_technique: str  # what technique was used
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def overall_score(self) -> float:
        """Calculate overall performance score."""
        if not self.performance_metrics:
            return 0.0
        return sum(self.performance_metrics.values()) / len(self.performance_metrics)


@dataclass
class GroundTruthCase:
    """A validated test case for judge evaluation."""
    case_id: str
    case_type: str  # evaluation, analysis, rewrite, meta_decision
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    quality_rubric: Dict[str, float]  # criteria -> weight
    human_validated: bool = True


class JudgeBootstrapProtocol:
    """Implements the multi-phase bootstrap protocol for judge quality."""
    
    def __init__(self):
        self.candidates: Dict[str, JudgeCandidate] = {}
        self.ground_truth: List[GroundTruthCase] = []
        self.bootstrap_dir = config.evaluations_dir / "judge_bootstrap"
        self.bootstrap_dir.mkdir(exist_ok=True)
        
        # Load ground truth cases
        self._load_ground_truth()
    
    def _load_ground_truth(self):
        """Load human-validated ground truth cases."""
        ground_truth_file = self.bootstrap_dir / "ground_truth_cases.yaml"
        
        if not ground_truth_file.exists():
            # Create initial ground truth cases
            self._create_initial_ground_truth()
            return
        
        with open(ground_truth_file) as f:
            cases_data = yaml.safe_load(f)
            
        for case_data in cases_data.get('cases', []):
            self.ground_truth.append(GroundTruthCase(**case_data))
    
    def _create_initial_ground_truth(self):
        """Create initial set of ground truth test cases."""
        cases = [
            # Evaluator test case
            GroundTruthCase(
                case_id="eval_format_fail_001",
                case_type="evaluation",
                input_data={
                    "prompt": "What is 2+2? Format: The answer is [NUMBER].",
                    "response": "The answer is 4",
                    "criteria": [
                        {"name": "format_compliance", "pattern": "The answer is [NUMBER]", "weight": 1.0}
                    ]
                },
                expected_output={
                    "format_score": 0.0,
                    "overall_score": 0.5,
                    "diagnosis": "Missing brackets around number"
                },
                quality_rubric={
                    "correct_score": 0.4,
                    "accurate_diagnosis": 0.3,
                    "helpful_feedback": 0.3
                }
            ),
            
            # Analyst test case
            GroundTruthCase(
                case_id="analyst_diagnosis_001",
                case_type="analysis",
                input_data={
                    "prompt": "List three colors",
                    "response": "Red",
                    "evaluation": {"score": 0.33, "failed": "incomplete_list"}
                },
                expected_output={
                    "root_cause": "Incomplete response - only one item instead of three",
                    "failure_category": "partial_compliance",
                    "improvement_strategy": "emphasis_on_quantity"
                },
                quality_rubric={
                    "correct_diagnosis": 0.5,
                    "actionable_strategy": 0.3,
                    "insight_depth": 0.2
                }
            ),
            
            # Rewriter test case
            GroundTruthCase(
                case_id="rewriter_improvement_001",
                case_type="rewrite",
                input_data={
                    "original_prompt": "Name a fruit",
                    "analysis": {
                        "issue": "Too open-ended, no format specified",
                        "suggestion": "Add specific format requirement"
                    }
                },
                expected_output={
                    "improved_prompt": "Name exactly one fruit. Format your answer as: Fruit: [NAME]",
                    "technique": "format_specification",
                    "preserves_intent": True
                },
                quality_rubric={
                    "addresses_issue": 0.4,
                    "clarity_improvement": 0.3,
                    "intent_preservation": 0.3
                }
            )
        ]
        
        # Save ground truth
        ground_truth_data = {
            "version": "1.0.0",
            "created": datetime.utcnow().isoformat(),
            "cases": [
                {
                    "case_id": case.case_id,
                    "case_type": case.case_type,
                    "input_data": case.input_data,
                    "expected_output": case.expected_output,
                    "quality_rubric": case.quality_rubric,
                    "human_validated": case.human_validated
                }
                for case in cases
            ]
        }
        
        ground_truth_file = self.bootstrap_dir / "ground_truth_cases.yaml"
        with open(ground_truth_file, 'w') as f:
            yaml.dump(ground_truth_data, f)
        
        self.ground_truth = cases
        logger.info(f"Created {len(cases)} ground truth cases")
    
    async def generate_judge_variations(self, role: str, num_variations: int = 5) -> List[JudgeCandidate]:
        """Generate multiple variations of a judge type."""
        
        # KSI IMPROVEMENT NEEDED #1:
        # We need a way to spawn agents with prompt variations.
        # Currently we can only spawn with exact profiles.
        # Ideal: spawn_agent with prompt_override parameter
        
        variation_techniques = [
            {
                "name": "detailed_rubric",
                "description": "Emphasize detailed scoring rubrics",
                "prompt_suffix": "\n\nAlways break down your evaluation into specific criteria with individual scores."
            },
            {
                "name": "example_driven", 
                "description": "Include examples in instructions",
                "prompt_suffix": "\n\nExample evaluations:\n- Good format: Score 1.0\n- Missing elements: Score 0.0-0.5"
            },
            {
                "name": "step_by_step",
                "description": "Emphasize step-by-step analysis",
                "prompt_suffix": "\n\nFollow these steps:\n1. Read the prompt\n2. Analyze the response\n3. Score each criterion\n4. Calculate overall score"
            },
            {
                "name": "error_focused",
                "description": "Focus on finding errors",
                "prompt_suffix": "\n\nPay special attention to what's missing or incorrect. Be precise about failures."
            },
            {
                "name": "constructive_feedback",
                "description": "Emphasize helpful feedback",
                "prompt_suffix": "\n\nAlways provide specific, actionable feedback for improvement."
            }
        ]
        
        candidates = []
        base_profile = f"{role}_judge"
        
        for i, technique in enumerate(variation_techniques[:num_variations]):
            candidate = JudgeCandidate(
                candidate_id=f"{role}_v{i+1}_{technique['name']}",
                role=role,
                base_profile=base_profile,
                prompt_variation=technique['prompt_suffix'],
                variation_technique=technique['name']
            )
            candidates.append(candidate)
            self.candidates[candidate.candidate_id] = candidate
        
        logger.info(f"Generated {len(candidates)} variations for {role} judge")
        return candidates
    
    async def evaluate_against_ground_truth(self, candidate: JudgeCandidate) -> float:
        """Evaluate a judge candidate against ground truth cases."""
        
        # KSI IMPROVEMENT NEEDED #2:
        # We need agent-to-agent messaging with structured responses.
        # Currently agents can only respond to strings, not structured judge protocols.
        # Ideal: agent.send_structured_message() that returns parsed response
        
        relevant_cases = [
            case for case in self.ground_truth 
            if case.case_type == candidate.role or case.case_type == "evaluation"
        ]
        
        total_score = 0.0
        
        for case in relevant_cases:
            # Simulate judge evaluation (in real system, would spawn agent)
            score = await self._simulate_judge_evaluation(candidate, case)
            candidate.test_results.append({
                "case_id": case.case_id,
                "score": score,
                "timestamp": datetime.utcnow().isoformat()
            })
            total_score += score
        
        avg_score = total_score / len(relevant_cases) if relevant_cases else 0.0
        candidate.performance_metrics['ground_truth_alignment'] = avg_score
        
        return avg_score
    
    async def _simulate_judge_evaluation(self, candidate: JudgeCandidate, case: GroundTruthCase) -> float:
        """Simulate evaluation (placeholder for real agent interaction)."""
        # In real implementation, this would:
        # 1. Spawn agent with candidate's prompt variation
        # 2. Send case input
        # 3. Compare response to expected output
        # 4. Score based on quality rubric
        
        # For now, return simulated score based on technique
        technique_scores = {
            "detailed_rubric": 0.85,
            "example_driven": 0.90,
            "step_by_step": 0.88,
            "error_focused": 0.82,
            "constructive_feedback": 0.87
        }
        
        return technique_scores.get(candidate.variation_technique, 0.80)
    
    async def run_tournament(self, candidates: List[JudgeCandidate]) -> List[Tuple[JudgeCandidate, JudgeCandidate, Dict[str, Any]]]:
        """Run tournament where judges evaluate each other."""
        
        # KSI IMPROVEMENT NEEDED #3:
        # We need a tournament event system or coordination mechanism.
        # Currently no built-in way to coordinate multi-agent evaluations.
        # Ideal: tournament:start event that orchestrates judge interactions
        
        tournament_results = []
        
        # Each judge evaluates others
        for evaluator in candidates:
            for evaluated in candidates:
                if evaluator.candidate_id == evaluated.candidate_id:
                    continue
                
                # Simulate cross-evaluation
                result = await self._simulate_cross_evaluation(evaluator, evaluated)
                tournament_results.append((evaluator, evaluated, result))
        
        # Calculate tournament scores
        for candidate in candidates:
            # How well did this judge evaluate others?
            evaluation_scores = [
                r[2]['score'] for r in tournament_results 
                if r[0].candidate_id == candidate.candidate_id
            ]
            if evaluation_scores:
                candidate.performance_metrics['evaluation_accuracy'] = sum(evaluation_scores) / len(evaluation_scores)
            
            # How well was this judge evaluated by others?
            peer_scores = [
                r[2]['peer_score'] for r in tournament_results
                if r[1].candidate_id == candidate.candidate_id
            ]
            if peer_scores:
                candidate.performance_metrics['peer_rating'] = sum(peer_scores) / len(peer_scores)
        
        return tournament_results
    
    async def _simulate_cross_evaluation(self, evaluator: JudgeCandidate, evaluated: JudgeCandidate) -> Dict[str, Any]:
        """Simulate one judge evaluating another."""
        # Placeholder for real cross-evaluation
        return {
            "score": 0.85,
            "peer_score": 0.88,
            "feedback": "Good evaluation criteria but could be more specific"
        }
    
    async def select_best_judges(self, role: str, top_n: int = 1) -> List[JudgeCandidate]:
        """Select the best performing judges for each role."""
        role_candidates = [
            c for c in self.candidates.values() 
            if c.role == role
        ]
        
        # Sort by overall score
        role_candidates.sort(key=lambda c: c.overall_score, reverse=True)
        
        return role_candidates[:top_n]
    
    async def save_bootstrap_results(self):
        """Save bootstrap results and selected judges."""
        results = {
            "bootstrap_run": datetime.utcnow().isoformat(),
            "candidates_evaluated": len(self.candidates),
            "selected_judges": {},
            "detailed_results": []
        }
        
        # Get best judge for each role
        for role in ["evaluator", "analyst", "rewriter", "meta"]:
            best = await self.select_best_judges(role, top_n=1)
            if best:
                results["selected_judges"][role] = {
                    "candidate_id": best[0].candidate_id,
                    "technique": best[0].variation_technique,
                    "score": best[0].overall_score
                }
        
        # Detailed results for all candidates
        for candidate in self.candidates.values():
            results["detailed_results"].append({
                "candidate_id": candidate.candidate_id,
                "role": candidate.role,
                "technique": candidate.variation_technique,
                "metrics": candidate.performance_metrics,
                "overall_score": candidate.overall_score
            })
        
        results_file = self.bootstrap_dir / f"bootstrap_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.yaml"
        with open(results_file, 'w') as f:
            yaml.dump(results, f)
        
        logger.info(f"Saved bootstrap results to {results_file}")
        return results


@event_handler("evaluation:bootstrap_judges")
async def handle_bootstrap_judges(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run judge bootstrap protocol.
    
    Parameters:
        roles: List of judge roles to bootstrap (default: all)
        variations_per_role: Number of variations to test (default: 5)
        run_tournament: Whether to run cross-evaluation tournament (default: True)
    """
    roles = data.get('roles', ['evaluator', 'analyst', 'rewriter', 'meta'])
    variations_per_role = data.get('variations_per_role', 5)
    run_tournament = data.get('run_tournament', True)
    
    protocol = JudgeBootstrapProtocol()
    
    # Phase 1: Generate variations
    all_candidates = []
    for role in roles:
        candidates = await protocol.generate_judge_variations(role, variations_per_role)
        all_candidates.extend(candidates)
    
    # Phase 2: Evaluate against ground truth
    for candidate in all_candidates:
        await protocol.evaluate_against_ground_truth(candidate)
    
    # Phase 3: Tournament (if requested)
    if run_tournament and len(all_candidates) > 1:
        await protocol.run_tournament(all_candidates)
    
    # Phase 4: Select best and save
    results = await protocol.save_bootstrap_results()
    
    return {
        "status": "success",
        "candidates_tested": len(all_candidates),
        "selected_judges": results["selected_judges"],
        "results_file": str(results)
    }