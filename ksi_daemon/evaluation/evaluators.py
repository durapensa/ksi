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


class AllOfEvaluator(BaseEvaluator):
    """All sub-evaluators must pass (score >= threshold)."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        evaluators = config.get('evaluators', [])
        if not evaluators:
            return 1.0
        
        threshold = config.get('threshold', 0.7)  # Default threshold for "passing"
        passing_count = 0
        
        for eval_config in evaluators:
            eval_type = eval_config.get('type')
            if not eval_type or eval_type not in BUILTIN_EVALUATORS:
                logger.warning(f"Unknown evaluator type in all_of: {eval_type}")
                continue
                
            evaluator_class = BUILTIN_EVALUATORS[eval_type]
            evaluator = evaluator_class()
            score = await evaluator.evaluate(response, eval_config)
            
            if score >= threshold:
                passing_count += 1
        
        # Return 1.0 if all pass, 0.0 otherwise
        return 1.0 if passing_count == len(evaluators) else 0.0


class AnyOfEvaluator(BaseEvaluator):
    """At least one sub-evaluator must pass (score >= threshold)."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        evaluators = config.get('evaluators', [])
        if not evaluators:
            return 1.0
        
        threshold = config.get('threshold', 0.7)  # Default threshold for "passing"
        
        for eval_config in evaluators:
            eval_type = eval_config.get('type')
            if not eval_type or eval_type not in BUILTIN_EVALUATORS:
                logger.warning(f"Unknown evaluator type in any_of: {eval_type}")
                continue
                
            evaluator_class = BUILTIN_EVALUATORS[eval_type]
            evaluator = evaluator_class()
            score = await evaluator.evaluate(response, eval_config)
            
            if score >= threshold:
                return 1.0  # At least one passed
        
        return 0.0  # None passed


class ExactMatchEvaluator(BaseEvaluator):
    """Exact string match evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        expected = config.get('value', '')
        case_sensitive = config.get('case_sensitive', True)
        strip_whitespace = config.get('strip_whitespace', True)
        
        if strip_whitespace:
            response = response.strip()
            expected = expected.strip()
        
        if not case_sensitive:
            response = response.lower()
            expected = expected.lower()
        
        return 1.0 if response == expected else 0.0


class LengthRangeEvaluator(BaseEvaluator):
    """Character length range evaluator."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        min_length = config.get('min', 0)
        max_length = config.get('max', float('inf'))
        
        response_length = len(response)
        
        if response_length < min_length or response_length > max_length:
            return 0.0
        
        # Return a score based on how well it fits within the range
        # Perfect score if exactly in the middle of the range
        if max_length == float('inf'):
            return 1.0
        
        range_size = max_length - min_length
        if range_size == 0:
            return 1.0 if response_length == min_length else 0.0
        
        # Linear scoring: closer to middle = higher score
        middle = (min_length + max_length) / 2
        distance_from_middle = abs(response_length - middle)
        max_distance = range_size / 2
        
        score = 1.0 - (distance_from_middle / max_distance)
        return max(0.0, min(1.0, score))


class PipelineEvaluator(BaseEvaluator):
    """Sequential evaluation pipeline with extract, transform, and match steps."""
    
    async def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        steps = config.get('steps', [])
        if not steps:
            return 1.0
        
        # Context that flows through the pipeline
        context = {
            'response': response,
            'extracted': {},
            'transformed': {}
        }
        
        for step in steps:
            step_type = step.get('type')
            
            if step_type == 'extract':
                # Extract data using regex
                pattern = step.get('pattern', '')
                group = step.get('group', 0)
                save_as = step.get('as', 'extracted')
                
                try:
                    match = re.search(pattern, context['response'])
                    if match:
                        if group == 0:
                            context['extracted'][save_as] = match.group(0)
                        elif group <= len(match.groups()):
                            context['extracted'][save_as] = match.group(group)
                        else:
                            logger.warning(f"Group {group} not found in regex match")
                            return 0.0
                    else:
                        logger.debug(f"Pattern '{pattern}' not found in response")
                        return 0.0
                except re.error as e:
                    logger.error(f"Invalid regex pattern: {pattern} - {e}")
                    return 0.0
                    
            elif step_type == 'normalize':
                # Apply transformations
                input_key = step.get('input', 'extracted')
                output_key = step.get('output', 'normalized')
                operations = step.get('operations', [])
                
                # Get input value
                if input_key in context['extracted']:
                    value = context['extracted'][input_key]
                elif input_key in context['transformed']:
                    value = context['transformed'][input_key]
                else:
                    value = context['response']
                
                # Apply operations
                for op in operations:
                    if op == 'lowercase':
                        value = value.lower()
                    elif op == 'uppercase':
                        value = value.upper()
                    elif op == 'strip':
                        value = value.strip()
                    elif op == 'strip_punctuation':
                        import string
                        value = value.translate(str.maketrans('', '', string.punctuation))
                    elif op == 'strip_whitespace':
                        value = ''.join(value.split())
                    elif op == 'numbers_only':
                        value = ''.join(c for c in value if c.isdigit())
                    else:
                        logger.warning(f"Unknown normalization operation: {op}")
                
                context['transformed'][output_key] = value
                
            elif step_type == 'match':
                # Match against expected value
                input_key = step.get('input', 'normalized')
                expected = step.get('expected', '')
                method = step.get('method', 'exact')
                threshold = step.get('threshold', 0.8)
                
                # Get input value
                if input_key in context['transformed']:
                    value = context['transformed'][input_key]
                elif input_key in context['extracted']:
                    value = context['extracted'][input_key]
                else:
                    value = context['response']
                
                # Perform matching
                if method == 'exact':
                    return 1.0 if value == expected else 0.0
                elif method == 'fuzzy':
                    # Simple character-based similarity
                    from difflib import SequenceMatcher
                    similarity = SequenceMatcher(None, value, expected).ratio()
                    return 1.0 if similarity >= threshold else 0.0
                elif method == 'contains':
                    return 1.0 if expected in value else 0.0
                elif method == 'regex':
                    try:
                        return 1.0 if re.search(expected, value) else 0.0
                    except re.error:
                        logger.error(f"Invalid regex pattern in match: {expected}")
                        return 0.0
                else:
                    logger.warning(f"Unknown match method: {method}")
                    return 0.0
                    
            else:
                logger.warning(f"Unknown pipeline step type: {step_type}")
                
        # If we made it through all steps without a match step, consider it successful
        return 1.0


# Import LLM judge if available
try:
    from .llm_judge import LLMJudgeEvaluator
    llm_judge_available = True
except ImportError:
    llm_judge_available = False

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
    'all_of': AllOfEvaluator,
    'any_of': AnyOfEvaluator,
    'exact_match': ExactMatchEvaluator,
    'length_range': LengthRangeEvaluator,
    'pipeline': PipelineEvaluator,
}

# Add LLM judge if module is available
if llm_judge_available:
    BUILTIN_EVALUATORS['llm_judge'] = LLMJudgeEvaluator


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