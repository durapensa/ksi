"""LLM-as-Judge Framework Adapter for KSI Optimization."""

import logging
from typing import Dict, Any, Optional, List, Callable
import json

from ksi_daemon.event_system import get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("judge_framework")


class JudgeFramework:
    """LLM-as-Judge framework adapter for KSI optimization service."""
    
    def __init__(self):
        self.judge_models = ["claude-cli/sonnet", "claude-cli/opus"]
        self.evaluation_templates = self._initialize_templates()
    
    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get framework information."""
        return {
            "available": True,
            "description": "LLM-as-Judge evaluation framework for qualitative assessment",
            "version": "1.0.0",
            "capabilities": {
                "evaluation": ["qualitative scoring", "dimensional analysis", "detailed feedback"],
                "models": ["claude-cli/sonnet", "claude-cli/opus", "litellm/*"],
                "criteria": ["custom rubrics", "domain expertise", "multi-factor scoring"],
                "output": ["structured JSON", "detailed explanations", "improvement suggestions"]
            }
        }
    
    def _initialize_templates(self) -> Dict[str, str]:
        """Initialize evaluation prompt templates."""
        return {
            "text_analysis": """
You are an expert evaluator assessing text analysis quality. 

Evaluate the following text analysis on these criteria:

**INPUT:**
- Original Text: {original_text}
- Domain: {domain}

**OUTPUT TO EVALUATE:**
- Insights: {insights}
- Recommendations: {recommendations}
- Confidence: {confidence}

**EVALUATION CRITERIA:**
1. INSIGHT QUALITY (0.0-1.0): Depth, relevance, novel perspectives
2. RECOMMENDATION PRACTICALITY (0.0-1.0): Specificity, actionability, feasibility
3. CONFIDENCE CALIBRATION (0.0-1.0): Accuracy relative to actual quality

Return ONLY valid JSON in this format:
{{"insight_quality": X.X, "recommendation_practicality": X.X, "confidence_calibration": X.X, "overall_score": X.X, "explanation": "detailed explanation", "strengths": ["strength1", "strength2"], "weaknesses": ["weakness1", "weakness2"]}}
""",
            "generic": """
You are an expert evaluator. Assess the given output against the provided criteria.

**INPUT:** {input_data}
**OUTPUT:** {output_data}
**CRITERIA:** {criteria}

Provide scores and detailed feedback in JSON format.
"""
        }
    
    async def evaluate(self, prediction: Any, ground_truth: Dict[str, Any], template: str = "text_analysis") -> Dict[str, Any]:
        """Evaluate prediction using LLM judge."""
        router = get_router()
        
        # Prepare evaluation prompt
        template_str = self.evaluation_templates.get(template, self.evaluation_templates["generic"])
        
        if template == "text_analysis":
            prompt = template_str.format(
                original_text=ground_truth.get('text', ''),
                domain=ground_truth.get('domain', ''),
                insights=getattr(prediction, 'insights', ''),
                recommendations=getattr(prediction, 'recommendations', ''),
                confidence=getattr(prediction, 'confidence', 0.0)
            )
        else:
            prompt = template_str.format(
                input_data=json.dumps(ground_truth, indent=2),
                output_data=str(prediction),
                criteria=ground_truth.get('criteria', 'General quality assessment')
            )
        
        # Create judge agent for evaluation
        try:
            agent_result = await router.emit_first("agent:spawn", {
                "profile": "components/personas/analysts/insight_analyst",
                "prompt": prompt,
                "config": {
                    "model": "claude-cli/sonnet",
                    "temperature": 0.1,  # Low temperature for consistent evaluation
                    "max_tokens": 1000
                }
            })
            
            if "error" in agent_result:
                return {"error": f"Failed to spawn judge agent: {agent_result['error']}"}
            
            agent_id = agent_result["agent_id"]
            
            # Get evaluation response
            completion_result = await router.emit_first("completion:async", {
                "agent_id": agent_id,
                "prompt": "Please provide your evaluation in the requested JSON format.",
                "timeout": 60
            })
            
            # Cleanup agent
            await router.emit_first("agent:terminate", {"agent_id": agent_id})
            
            if "error" in completion_result:
                return {"error": f"Judge evaluation failed: {completion_result['error']}"}
            
            # Parse judge response
            response_text = completion_result.get("response", "{}")
            return self._parse_judge_response(response_text)
            
        except Exception as e:
            logger.error(f"Judge evaluation error: {e}")
            return {"error": str(e)}
    
    def _parse_judge_response(self, response: str) -> Dict[str, Any]:
        """Parse and validate judge response."""
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # Validate required fields
                if "overall_score" in result:
                    # Ensure score is in valid range
                    result["overall_score"] = max(0.0, min(1.0, float(result["overall_score"])))
                    return result
            
            # Fallback: sentiment-based scoring
            return self._fallback_scoring(response)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse judge JSON: {e}")
            return self._fallback_scoring(response)
    
    def _fallback_scoring(self, response: str) -> Dict[str, Any]:
        """Fallback scoring when JSON parsing fails."""
        response_lower = response.lower()
        
        # Simple sentiment analysis
        positive_words = ['excellent', 'good', 'strong', 'clear', 'effective', 'accurate']
        negative_words = ['poor', 'weak', 'unclear', 'ineffective', 'lacking', 'inaccurate']
        
        pos_count = sum(1 for word in positive_words if word in response_lower)
        neg_count = sum(1 for word in negative_words if word in response_lower)
        
        if pos_count > neg_count:
            score = 0.7
        elif neg_count > pos_count:
            score = 0.3
        else:
            score = 0.5
        
        return {
            "overall_score": score,
            "explanation": response,
            "parsing_method": "fallback_sentiment",
            "positive_signals": pos_count,
            "negative_signals": neg_count
        }

    async def batch_evaluate(self, predictions: List[Any], ground_truths: List[Dict[str, Any]], template: str = "text_analysis") -> List[Dict[str, Any]]:
        """Evaluate multiple predictions in batch."""
        results = []
        
        for pred, gt in zip(predictions, ground_truths):
            result = await self.evaluate(pred, gt, template)
            results.append(result)
        
        return results