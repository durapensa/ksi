"""Hybrid Framework Adapter combining MIPRO and Judge evaluation for KSI Optimization."""

import logging
from typing import Dict, Any, Optional, List, Callable
import asyncio

from ksi_daemon.event_system import get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

from .dspy_events import DSPyFramework
from .judge_events import JudgeFramework

logger = get_bound_logger("hybrid_framework")


class HybridFramework:
    """Hybrid framework combining DSPy MIPRO optimization with LLM-as-Judge evaluation."""
    
    def __init__(self):
        self.dspy_framework = DSPyFramework()
        self.judge_framework = JudgeFramework()
        self.optimization_history = []
    
    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get framework information."""
        return {
            "available": True,
            "description": "Hybrid optimization combining MIPRO programmatic optimization with LLM-as-Judge evaluation",
            "version": "1.0.0",
            "capabilities": {
                "optimization": ["MIPRO", "gradient-free", "multi-objective"],
                "evaluation": ["quantitative metrics", "qualitative assessment", "human-like judgment"],
                "combination": ["weighted scoring", "iterative refinement", "multi-stage optimization"],
                "output": ["best of both approaches", "comprehensive feedback", "optimization history"]
            },
            "components": {
                "dspy": "MIPROv2 optimizer for programmatic parameter tuning",
                "judge": "LLM-as-Judge for qualitative evaluation",
                "hybrid": "Intelligent combination of both approaches"
            }
        }
    
    async def optimize(self, signature, training_data: List[Dict], evaluation_criteria: Dict, config: Dict = None) -> Dict[str, Any]:
        """Run hybrid optimization combining MIPRO and judge evaluation."""
        config = config or {}
        
        # Stage 1: MIPRO Optimization
        logger.info("Starting Stage 1: MIPRO optimization")
        mipro_result = await self._run_mipro_optimization(signature, training_data, config)
        
        # Stage 2: Judge Evaluation of MIPRO results
        logger.info("Starting Stage 2: Judge evaluation of MIPRO candidates")
        judge_results = await self._evaluate_with_judge(mipro_result.get("candidates", []), training_data, evaluation_criteria)
        
        # Stage 3: Hybrid Selection
        logger.info("Starting Stage 3: Hybrid candidate selection")
        final_result = await self._select_best_candidate(mipro_result, judge_results, config)
        
        # Store optimization history
        optimization_record = {
            "mipro_result": mipro_result,
            "judge_results": judge_results,
            "final_result": final_result,
            "config": config
        }
        self.optimization_history.append(optimization_record)
        
        return final_result
    
    async def _run_mipro_optimization(self, signature, training_data: List[Dict], config: Dict) -> Dict[str, Any]:
        """Run MIPRO optimization using DSPy framework."""
        try:
            # Configure MIPRO parameters
            mipro_config = {
                "num_candidates": config.get("mipro_candidates", 8),
                "max_bootstrapped_demos": config.get("max_demos", 4),
                "init_temperature": config.get("temperature", 0.7),
                "auto": config.get("auto_level", "medium")
            }
            
            # Create programmatic metric (simplified for demo)
            def programmatic_metric(prediction, ground_truth, trace=None):
                """Simple programmatic metric combining multiple factors."""
                if not hasattr(prediction, 'confidence'):
                    return 0.0
                
                # Factor 1: Confidence calibration
                confidence = float(prediction.confidence)
                
                # Factor 2: Response length (proxy for detail)
                response_length = 0
                if hasattr(prediction, 'insights'):
                    response_length += len(str(prediction.insights))
                if hasattr(prediction, 'recommendations'):
                    response_length += len(str(prediction.recommendations))
                
                length_score = min(1.0, response_length / 500)  # Normalize to 0-1
                
                # Factor 3: Domain keyword relevance
                domain = ground_truth.get('domain', 'business')
                domain_keywords = {
                    'business': ['revenue', 'cost', 'roi', 'market', 'strategy'],
                    'technical': ['system', 'performance', 'scalability', 'architecture'],
                    'academic': ['research', 'methodology', 'evidence', 'analysis']
                }
                
                keywords = domain_keywords.get(domain, [])
                full_text = f"{getattr(prediction, 'insights', '')} {getattr(prediction, 'recommendations', '')}"
                keyword_matches = sum(1 for kw in keywords if kw.lower() in full_text.lower())
                keyword_score = min(1.0, keyword_matches / 3)
                
                # Weighted combination
                final_score = (confidence * 0.4 + length_score * 0.3 + keyword_score * 0.3)
                return final_score
            
            # Simulate MIPRO optimization (in real implementation, would use actual DSPy)
            candidates = []
            for i in range(mipro_config["num_candidates"]):
                # Each candidate would be an optimized version of the signature
                candidate = {
                    "id": f"mipro_candidate_{i}",
                    "score": 0.5 + (i * 0.05),  # Simulated scores
                    "parameters": {
                        "temperature": 0.5 + (i * 0.1),
                        "instruction_variant": f"Instruction variant {i}"
                    },
                    "method": "mipro"
                }
                candidates.append(candidate)
            
            return {
                "status": "success",
                "method": "mipro",
                "candidates": candidates,
                "best_candidate": max(candidates, key=lambda x: x["score"]),
                "config": mipro_config
            }
            
        except Exception as e:
            logger.error(f"MIPRO optimization failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _evaluate_with_judge(self, candidates: List[Dict], training_data: List[Dict], criteria: Dict) -> List[Dict]:
        """Evaluate MIPRO candidates using LLM judge."""
        judge_results = []
        
        # Sample some training examples for judge evaluation
        sample_data = training_data[:3]  # Evaluate on first 3 examples
        
        for candidate in candidates:
            candidate_scores = []
            
            for example in sample_data:
                # Simulate prediction result for this candidate
                simulated_prediction = type('Prediction', (), {
                    'insights': f"Insight generated by {candidate['id']} for {example.get('domain', 'unknown')} domain",
                    'recommendations': f"Recommendations from {candidate['id']} with temperature {candidate['parameters'].get('temperature', 0.7)}",
                    'confidence': 0.6 + candidate["score"] * 0.3  # Correlate with MIPRO score
                })()
                
                # Get judge evaluation
                judge_result = await self.judge_framework.evaluate(
                    simulated_prediction, 
                    example, 
                    template="text_analysis"
                )
                
                if "error" not in judge_result:
                    candidate_scores.append(judge_result.get("overall_score", 0.0))
            
            # Average judge scores for this candidate
            avg_judge_score = sum(candidate_scores) / len(candidate_scores) if candidate_scores else 0.0
            
            judge_results.append({
                "candidate_id": candidate["id"],
                "judge_score": avg_judge_score,
                "individual_scores": candidate_scores,
                "method": "judge"
            })
        
        return judge_results
    
    async def _select_best_candidate(self, mipro_result: Dict, judge_results: List[Dict], config: Dict) -> Dict[str, Any]:
        """Select best candidate using hybrid scoring."""
        mipro_weight = config.get("mipro_weight", 0.6)
        judge_weight = config.get("judge_weight", 0.4)
        
        candidates = mipro_result.get("candidates", [])
        
        # Combine MIPRO and judge scores
        hybrid_candidates = []
        
        for candidate in candidates:
            # Find corresponding judge result
            judge_result = next((jr for jr in judge_results if jr["candidate_id"] == candidate["id"]), None)
            
            mipro_score = candidate["score"]
            judge_score = judge_result["judge_score"] if judge_result else 0.0
            
            # Weighted hybrid score
            hybrid_score = (mipro_score * mipro_weight) + (judge_score * judge_weight)
            
            hybrid_candidates.append({
                "id": candidate["id"],
                "mipro_score": mipro_score,
                "judge_score": judge_score,
                "hybrid_score": hybrid_score,
                "parameters": candidate["parameters"],
                "method": "hybrid"
            })
        
        # Select best hybrid candidate
        best_candidate = max(hybrid_candidates, key=lambda x: x["hybrid_score"])
        
        return {
            "status": "success",
            "method": "hybrid",
            "best_candidate": best_candidate,
            "all_candidates": hybrid_candidates,
            "selection_criteria": {
                "mipro_weight": mipro_weight,
                "judge_weight": judge_weight
            },
            "improvement_over_mipro": best_candidate["hybrid_score"] - best_candidate["mipro_score"]
        }
    
    async def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get history of all optimization runs."""
        return self.optimization_history
    
    async def analyze_optimization_patterns(self) -> Dict[str, Any]:
        """Analyze patterns across optimization runs."""
        if not self.optimization_history:
            return {"message": "No optimization history available"}
        
        # Analyze which approach tends to perform better
        mipro_wins = 0
        judge_adjustments = 0
        hybrid_improvements = 0
        
        for record in self.optimization_history:
            final_result = record["final_result"]
            if "improvement_over_mipro" in final_result:
                improvement = final_result["improvement_over_mipro"]
                if improvement > 0.05:  # Significant improvement
                    hybrid_improvements += 1
                elif improvement < -0.05:  # Judge made it worse
                    mipro_wins += 1
                else:  # Minimal change
                    judge_adjustments += 1
        
        total_runs = len(self.optimization_history)
        
        return {
            "total_optimizations": total_runs,
            "mipro_preferred": mipro_wins,
            "judge_improved": hybrid_improvements,
            "neutral_adjustments": judge_adjustments,
            "hybrid_effectiveness": hybrid_improvements / total_runs if total_runs > 0 else 0,
            "recommendation": "Use MIPRO-first approach" if mipro_wins > hybrid_improvements else "Hybrid approach showing value"
        }