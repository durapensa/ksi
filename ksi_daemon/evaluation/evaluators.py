#!/usr/bin/env python3
"""Declarative evaluator system for KSI prompt evaluation."""

import re
from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("evaluators")


class BaseEvaluator(ABC):
    """Base interface for all evaluators."""
    
    @abstractmethod
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        """
        Evaluate a response.
        
        Args:
            response: The model's response text
            config: Evaluator configuration
            
        Returns:
            Score between 0.0 and 1.0
        """
        pass


class ContainsEvaluator(BaseEvaluator):
    """Single pattern match evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        pattern = config.get('value', '')
        case_sensitive = config.get('case_sensitive', False)
        
        if not case_sensitive:
            response = response.lower()
            pattern = pattern.lower()
            
        return 1.0 if pattern in response else 0.0


class ContainsAnyEvaluator(BaseEvaluator):
    """Any of multiple patterns evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        patterns = config.get('patterns', [])
        case_sensitive = config.get('case_sensitive', False)
        
        if not case_sensitive:
            response = response.lower()
            patterns = [p.lower() for p in patterns]
            
        for pattern in patterns:
            if pattern in response:
                return 1.0
        return 0.0


class ContainsAllEvaluator(BaseEvaluator):
    """All patterns must be present evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        patterns = config.get('patterns', [])
        case_sensitive = config.get('case_sensitive', False)
        
        if not patterns:
            return 1.0
            
        if not case_sensitive:
            response = response.lower()
            patterns = [p.lower() for p in patterns]
            
        found_count = sum(1 for pattern in patterns if pattern in response)
        return found_count / len(patterns)


class RegexEvaluator(BaseEvaluator):
    """Regular expression matching evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        pattern = config.get('value', '')
        flags = 0
        
        if not config.get('case_sensitive', False):
            flags |= re.IGNORECASE
            
        try:
            match = re.search(pattern, response, flags)
            return 1.0 if match else 0.0
        except re.error:
            logger.error(f"Invalid regex pattern: {pattern}")
            return 0.0


class WordCountEvaluator(BaseEvaluator):
    """Word count constraint evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        word_count = len(response.split())
        min_words = config.get('min', 0)
        max_words = config.get('max', float('inf'))
        
        if min_words <= word_count <= max_words:
            return 1.0
        return 0.0


class ExactWordCountEvaluator(BaseEvaluator):
    """Exact word count evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        word_count = len(response.split())
        expected_count = config.get('count', 0)
        
        return 1.0 if word_count == expected_count else 0.0


class SentenceCountEvaluator(BaseEvaluator):
    """Sentence count constraint evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        # Simple sentence splitting by common punctuation
        sentences = re.split(r'[.!?]+', response)
        sentence_count = len([s.strip() for s in sentences if s.strip()])
        
        min_sentences = config.get('min', 0)
        max_sentences = config.get('max', float('inf'))
        
        if min_sentences <= sentence_count <= max_sentences:
            return 1.0
        return 0.0


class NoContaminationEvaluator(BaseEvaluator):
    """Check for contamination indicators."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        # Default contamination patterns if not provided
        contamination_indicators = config.get('patterns', [
            "I cannot", "I can't", "I don't", "I won't",
            "As an AI", "I'm sorry", "I must not",
            "ethical", "harmful", "appropriate", "responsible AI"
        ])
        
        response_lower = response.lower()
        
        for indicator in contamination_indicators:
            if indicator.lower() in response_lower:
                return 0.0
        return 1.0


class FormatMatchEvaluator(BaseEvaluator):
    """Check if response matches expected format."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        format_type = config.get('format', 'list')
        
        if format_type == 'list':
            # Check for list indicators
            list_patterns = [r'\d+\.', r'\d+\)', r'^-\s', r'^•\s', r'^\*\s']
            for pattern in list_patterns:
                if re.search(pattern, response, re.MULTILINE):
                    return 1.0
            # Also check for comma-separated values
            if ',' in response and len(response.split(',')) > 1:
                return 1.0
            return 0.0
        
        return 0.0


class ContainsReasoningMarkersEvaluator(BaseEvaluator):
    """Check for reasoning indicators."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        markers = config.get('patterns', [
            "because", "therefore", "since", "however", 
            "but", "although", "thus", "hence", "so"
        ])
        
        response_lower = response.lower()
        found_count = sum(1 for marker in markers if marker.lower() in response_lower)
        
        # Score based on how many reasoning markers are found
        if found_count == 0:
            return 0.0
        elif found_count == 1:
            return 0.5
        else:
            return 1.0


class WeightedEvaluator(BaseEvaluator):
    """Combine multiple evaluators with weights."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        evaluators = config.get('evaluators', [])
        total_weight = 0
        weighted_score = 0
        
        for evaluator_config in evaluators:
            evaluator_type = evaluator_config.get('type')
            weight = evaluator_config.get('weight', 1.0)
            
            evaluator = create_evaluator(evaluator_type)
            if evaluator:
                score = await evaluator.evaluate(response, evaluator_config)
                weighted_score += score * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_score / total_weight
        return 0.0


class SemanticEvaluator(BaseEvaluator):
    """Evaluate if response exhibits expected behaviors using LLM."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        from .completion_utils import send_completion_and_wait
        from ksi_common.config import config as ksi_config
        
        expected_behaviors = config.get('behaviors', [])
        if not expected_behaviors:
            return 1.0  # No behaviors to check = pass
        
        # Construct evaluation prompt
        behaviors_list = ', '.join(expected_behaviors)
        prompt = f"""Evaluate if the following response exhibits these behaviors: {behaviors_list}

Response to evaluate:
{response}

For each behavior, determine if it is clearly exhibited in the response.
Respond with ONLY a JSON object in this exact format:
{{
  "behaviors": {{
    "behavior_name": true/false,
    ...
  }},
  "score": 0.0-1.0
}}

The score should be the percentage of behaviors exhibited."""
        
        try:
            # Use completion system for evaluation
            result = await send_completion_and_wait(
                prompt,
                model=config.get('model', ksi_config.semantic_eval_default_model),
                agent_config={'temperature': 0.1}  # Low temperature for consistent evaluation
            )
            
            if result.get('status') != 'completed':
                logger.error(f"Semantic evaluation failed: {result.get('error')}")
                return 0.5  # Default middle score on error
            
            # Parse response
            import json
            response_text = result.get('response', '')
            
            # Strip markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            try:
                eval_result = json.loads(response_text)
                return float(eval_result.get('score', 0.5))
            except json.JSONDecodeError:
                logger.error(f"Failed to parse semantic evaluation response: {response_text}")
                return 0.5
                
        except Exception as e:
            logger.error(f"Semantic evaluation error: {e}")
            return 0.5


# Evaluator registry
BUILTIN_EVALUATORS = {
    'contains': ContainsEvaluator,
    'contains_any': ContainsAnyEvaluator,
    'contains_all': ContainsAllEvaluator,
    'regex': RegexEvaluator,
    'word_count': WordCountEvaluator,
    'exact_word_count': ExactWordCountEvaluator,
    'sentence_count': SentenceCountEvaluator,
    'no_contamination': NoContaminationEvaluator,
    'format_match': FormatMatchEvaluator,
    'contains_reasoning_markers': ContainsReasoningMarkersEvaluator,
    'weighted': WeightedEvaluator,
    'semantic': SemanticEvaluator,
}


def create_evaluator(evaluator_type: str) -> Optional[BaseEvaluator]:
    """Create an evaluator instance by type."""
    evaluator_class = BUILTIN_EVALUATORS.get(evaluator_type)
    if evaluator_class:
        return evaluator_class()
    
    logger.warning(f"Unknown evaluator type: {evaluator_type}")
    return None


async def evaluate_with_config(response: str, evaluator_configs: List[Dict[str, Any]], 
                              contamination_patterns: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Evaluate a response using multiple evaluator configurations.
    
    Returns:
        Dict with keys:
        - score: Overall weighted score (0.0 to 1.0)
        - details: Individual evaluator results
        - contaminated: Whether contamination was detected
        - contamination_severity: Highest severity found
    """
    total_weight = 0
    weighted_score = 0
    details = []
    
    # Check for contamination first if patterns provided
    contaminated = False
    contamination_severity = None
    
    if contamination_patterns:
        for pattern in contamination_patterns:
            pattern_type = pattern.get('pattern', 'contains')
            value = pattern.get('value', pattern.get('values', ''))
            severity = pattern.get('severity', 'medium')
            
            if pattern_type == 'regex':
                if re.search(value, response, re.IGNORECASE):
                    contaminated = True
                    contamination_severity = severity
                    break
            elif pattern_type == 'contains':
                if value.lower() in response.lower():
                    contaminated = True
                    contamination_severity = severity
                    break
            elif pattern_type == 'contains_any' and isinstance(value, list):
                if any(v.lower() in response.lower() for v in value):
                    contaminated = True
                    contamination_severity = severity
                    break
    
    # Evaluate each configured evaluator
    for evaluator_config in evaluator_configs:
        evaluator_type = evaluator_config.get('type')
        weight = evaluator_config.get('weight', 1.0)
        
        evaluator = create_evaluator(evaluator_type)
        if evaluator:
            score = await evaluator.evaluate(response, evaluator_config)
            weighted_score += score * weight
            total_weight += weight
            
            details.append({
                'type': evaluator_type,
                'score': score,
                'weight': weight,
                'config': evaluator_config
            })
    
    # Calculate final score
    if total_weight > 0:
        final_score = weighted_score / total_weight
    else:
        final_score = 0.0
    
    return {
        'score': final_score,
        'details': details,
        'contaminated': contaminated,
        'contamination_severity': contamination_severity
    }