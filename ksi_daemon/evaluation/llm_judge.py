#!/usr/bin/env python3
"""LLM-as-Judge implementation for KSI evaluation system."""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler
from .completion_utils import send_completion_and_wait
from .evaluators import BaseEvaluator

logger = get_bound_logger("llm_judge")


@dataclass
class JudgmentCriteria:
    """Criteria for LLM judge evaluation."""
    name: str
    description: str
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass 
class JudgmentResult:
    """Result from LLM judge evaluation."""
    criteria_scores: Dict[str, int]
    reasoning: Dict[str, str]
    overall_score: float
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    judge_model: str = "claude-cli/sonnet"


class LLMJudgeEvaluator(BaseEvaluator):
    """Evaluator that uses LLM-as-Judge pattern."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        """Evaluate response using LLM judge."""
        criteria = self._parse_criteria(config)
        judge_prompt = self._build_judge_prompt(response, criteria, config)
        
        result = await send_completion_and_wait(
            prompt=judge_prompt,
            model=config.get('judge_model', 'claude-cli/sonnet'),
            agent_config={'temperature': 0.1}  # Low temperature for consistency
        )
        
        if result.get('status') != 'completed':
            logger.error(f"Judge evaluation failed: {result.get('error')}")
            return 0.5
            
        try:
            judgment = self._parse_judgment(result.get('response', ''))
            return judgment.overall_score
        except Exception as e:
            logger.error(f"Failed to parse judgment: {e}")
            return 0.5
    
    def _parse_criteria(self, config: Dict[str, Any]) -> List[JudgmentCriteria]:
        """Parse evaluation criteria from config."""
        criteria_list = []
        for c in config.get('criteria', []):
            criteria_list.append(JudgmentCriteria(
                name=c['name'],
                description=c['description'],
                weight=c.get('weight', 1.0),
                scale_min=c.get('scale_min', 1),
                scale_max=c.get('scale_max', 5),
                examples=c.get('examples', [])
            ))
        return criteria_list
    
    def _build_judge_prompt(
        self, 
        response: str, 
        criteria: List[JudgmentCriteria],
        config: Dict[str, Any]
    ) -> str:
        """Build evaluation prompt for LLM judge using best practices."""
        
        # G-Eval style chain-of-thought approach
        prompt = """You are an expert evaluator. Your task is to evaluate the following response based on specific criteria.

## Response to Evaluate:
{response}

## Evaluation Criteria:
{criteria_text}

## Evaluation Process:
1. First, carefully read the response
2. For each criterion, think step-by-step about how well the response meets it
3. Provide specific examples from the response to support your evaluation
4. Assign a score based on the scale provided
5. Calculate an overall score based on weighted criteria

## Scoring Guidelines:
{scoring_guidelines}

## Chain of Thought Evaluation:
Let me evaluate this response step by step...

{cot_section}

## Final Evaluation:
Based on my analysis, here are my scores:

```json
{json_template}
```
"""
        
        # Build criteria text
        criteria_text = ""
        for i, criterion in enumerate(criteria, 1):
            criteria_text += f"\n{i}. **{criterion.name}** (weight: {criterion.weight})\n"
            criteria_text += f"   {criterion.description}\n"
            criteria_text += f"   Scale: {criterion.scale_min} (worst) to {criterion.scale_max} (best)\n"
            
            if criterion.examples:
                criteria_text += "   Examples:\n"
                for ex in criterion.examples[:2]:  # Limit examples
                    criteria_text += f"   - Score {ex['score']}: {ex['description']}\n"
        
        # Build scoring guidelines (few-shot examples if provided)
        scoring_guidelines = config.get('scoring_guidelines', 
            "Award points based on how well the response meets each criterion. "
            "Be objective and provide specific evidence for your scores."
        )
        
        # Build CoT section template
        cot_section = "### Step-by-step evaluation:\n"
        for criterion in criteria:
            cot_section += f"\n**{criterion.name}:**\n[Analyze how the response meets this criterion]\n"
        
        # Build JSON template
        json_template = {
            "criteria_scores": {c.name: f"[{c.scale_min}-{c.scale_max}]" for c in criteria},
            "reasoning": {c.name: "[brief explanation]" for c in criteria},
            "overall_score": "[0.0-1.0 normalized score]",
            "confidence": "[0.0-1.0 confidence in evaluation]"
        }
        
        return prompt.format(
            response=response,
            criteria_text=criteria_text,
            scoring_guidelines=scoring_guidelines,
            cot_section=cot_section,
            json_template=json.dumps(json_template, indent=2)
        )
    
    def _parse_judgment(self, judge_response: str) -> JudgmentResult:
        """Parse judgment from LLM response."""
        # Extract JSON from response
        if '```json' in judge_response:
            json_str = judge_response.split('```json')[1].split('```')[0].strip()
        else:
            # Try to find JSON-like structure
            import re
            json_match = re.search(r'\{[^{}]*\}', judge_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in judge response")
        
        judgment_data = json.loads(json_str)
        
        return JudgmentResult(
            criteria_scores=judgment_data.get('criteria_scores', {}),
            reasoning=judgment_data.get('reasoning', {}),
            overall_score=float(judgment_data.get('overall_score', 0.5)),
            confidence=float(judgment_data.get('confidence', 0.5))
        )


class PairwiseJudgeEvaluator:
    """Evaluator for comparing two responses."""
    
    async def compare(
        self,
        response_a: str,
        response_b: str,
        criteria: List[JudgmentCriteria],
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Compare two responses and return preference."""
        
        prompt = self._build_comparison_prompt(response_a, response_b, criteria)
        
        result = await send_completion_and_wait(
            prompt=prompt,
            model=config.get('judge_model', 'claude-cli/sonnet') if config else 'claude-cli/sonnet',
            agent_config={'temperature': 0.1}
        )
        
        if result.get('status') != 'completed':
            return {"error": "Judge comparison failed", "preference": "tie"}
        
        return self._parse_comparison(result.get('response', ''))
    
    def _build_comparison_prompt(
        self,
        response_a: str,
        response_b: str,
        criteria: List[JudgmentCriteria]
    ) -> str:
        """Build pairwise comparison prompt."""
        
        return f"""You are an expert evaluator comparing two responses.

## Response A:
{response_a}

## Response B:
{response_b}

## Comparison Criteria:
{self._format_criteria(criteria)}

## Task:
1. Compare how well each response meets each criterion
2. Identify specific strengths and weaknesses
3. Determine which response is better overall

## Analysis:
[Provide step-by-step comparison]

## Judgment:
```json
{{
  "preference": "A" or "B" or "tie",
  "confidence": 0.0-1.0,
  "criteria_preferences": {{
    "criterion_name": "A" or "B" or "tie",
    ...
  }},
  "reasoning": "explanation of overall preference"
}}
```
"""
    
    def _format_criteria(self, criteria: List[JudgmentCriteria]) -> str:
        """Format criteria for prompt."""
        formatted = ""
        for c in criteria:
            formatted += f"- **{c.name}**: {c.description}\n"
        return formatted
    
    def _parse_comparison(self, response: str) -> Dict[str, Any]:
        """Parse comparison result."""
        try:
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0].strip()
            else:
                raise ValueError("No JSON found in comparison response")
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse comparison: {e}")
            return {"preference": "tie", "error": str(e)}


@event_handler("evaluation:judge_prompt")
async def handle_judge_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate a prompt's response using LLM-as-Judge.
    
    Parameters:
        prompt: The prompt that was sent
        response: The response to evaluate
        criteria: List of evaluation criteria
        judge_model: Model to use as judge (default: claude-cli/sonnet)
    """
    prompt = data.get('prompt')
    response = data.get('response')
    criteria_data = data.get('criteria', [])
    
    if not response:
        return {"status": "error", "error": "response parameter required"}
    
    # Default criteria if none provided
    if not criteria_data:
        criteria_data = [
            {
                "name": "relevance",
                "description": "How well the response addresses the prompt",
                "weight": 1.0
            },
            {
                "name": "clarity", 
                "description": "How clear and well-structured the response is",
                "weight": 0.8
            },
            {
                "name": "completeness",
                "description": "How thoroughly the response covers the topic",
                "weight": 0.8
            }
        ]
    
    # Create evaluator config
    evaluator_config = {
        'type': 'llm_judge',
        'criteria': criteria_data,
        'judge_model': data.get('judge_model', 'claude-cli/sonnet'),
        'original_prompt': prompt
    }
    
    # Run evaluation
    evaluator = LLMJudgeEvaluator()
    score = await evaluator.evaluate(response, evaluator_config)
    
    # Get detailed judgment for analysis
    judge_prompt = evaluator._build_judge_prompt(
        response, 
        evaluator._parse_criteria(evaluator_config),
        evaluator_config
    )
    
    result = await send_completion_and_wait(
        prompt=judge_prompt,
        model=evaluator_config['judge_model'],
        agent_config={'temperature': 0.1}
    )
    
    if result.get('status') == 'completed':
        try:
            judgment = evaluator._parse_judgment(result.get('response', ''))
            return {
                "status": "success",
                "overall_score": judgment.overall_score,
                "criteria_scores": judgment.criteria_scores,
                "reasoning": judgment.reasoning,
                "confidence": judgment.confidence,
                "judge_model": evaluator_config['judge_model']
            }
        except Exception as e:
            logger.error(f"Failed to get detailed judgment: {e}")
    
    return {
        "status": "success",
        "overall_score": score,
        "error": "Could not extract detailed judgment"
    }


@event_handler("evaluation:judge_compare") 
async def handle_judge_compare(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two responses using LLM-as-Judge.
    
    Parameters:
        response_a: First response
        response_b: Second response  
        criteria: Comparison criteria
        judge_model: Model to use as judge
    """
    response_a = data.get('response_a')
    response_b = data.get('response_b')
    criteria_data = data.get('criteria', [])
    
    if not response_a or not response_b:
        return {"status": "error", "error": "response_a and response_b required"}
    
    # Parse criteria
    criteria = []
    for c in criteria_data:
        criteria.append(JudgmentCriteria(
            name=c['name'],
            description=c['description'],
            weight=c.get('weight', 1.0)
        ))
    
    # Default criteria if none provided
    if not criteria:
        criteria = [
            JudgmentCriteria("overall_quality", "Overall response quality", 1.0),
            JudgmentCriteria("accuracy", "Factual accuracy and correctness", 0.9),
            JudgmentCriteria("helpfulness", "How helpful the response is", 0.8)
        ]
    
    # Run comparison
    judge = PairwiseJudgeEvaluator()
    comparison = await judge.compare(
        response_a, 
        response_b, 
        criteria,
        {'judge_model': data.get('judge_model', 'claude-cli/sonnet')}
    )
    
    return {
        "status": "success",
        **comparison
    }