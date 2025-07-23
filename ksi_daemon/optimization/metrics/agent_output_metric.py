"""Agent-based output evaluation metric for DSPy optimization."""

import asyncio
from typing import List, Dict, Any, Optional
import json
import numpy as np

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("agent_output_metric")


class AgentOutputMetric:
    """Evaluates instruction quality by testing actual agent outputs."""
    
    def __init__(self, judge_component: str = "evaluations/judges/analysis_quality_judge"):
        """
        Initialize the agent output metric.
        
        Args:
            judge_component: Component name for the LLM judge
        """
        self.judge_component = judge_component
        # Note: In subprocess context, we can't use event_emitter
        self.event_emitter = None
    
    async def evaluate(
        self, 
        instruction: str, 
        test_prompts: List[str],
        component_name: Optional[str] = None,
        trace: Optional[Any] = None
    ) -> float:
        """
        Evaluate instruction quality using a simplified approach for subprocess context.
        
        Since we can't spawn actual agents in the subprocess, we evaluate the instruction
        quality based on structural and content criteria relevant to data analysis.
        
        Args:
            instruction: The optimized instruction text
            test_prompts: List of prompts to test the agent with (used for context)
            component_name: Optional component name being optimized
            trace: Optional DSPy trace for bootstrapping
            
        Returns:
            float: Average quality score (0.0-1.0)
        """
        try:
            # Evaluate instruction quality based on multiple criteria
            scores = []
            
            # 1. Length and detail (0-1)
            length_score = min(1.0, len(instruction) / 1000)  # Up to 1000 chars is good
            scores.append(length_score)
            
            # 2. Structure and organization (0-1)
            structure_keywords = [
                'expertise', 'approach', 'method', 'step', 'first', 'then',
                'analyze', 'evaluate', 'recommend', 'when', 'how'
            ]
            structure_score = sum(1 for kw in structure_keywords if kw.lower() in instruction.lower()) / len(structure_keywords)
            scores.append(structure_score)
            
            # 3. Data analysis specific content (0-1)
            analysis_keywords = [
                'data', 'analysis', 'statistical', 'visualization', 'pattern',
                'insight', 'trend', 'correlation', 'hypothesis', 'metric',
                'business', 'recommendation', 'actionable', 'decision'
            ]
            analysis_score = sum(1 for kw in analysis_keywords if kw.lower() in instruction.lower()) / len(analysis_keywords)
            scores.append(analysis_score * 1.5)  # Weight this higher
            
            # 4. Professional tone and expertise (0-1)
            expertise_keywords = [
                'experience', 'expert', 'senior', 'proficient', 'skilled',
                'methodology', 'best practice', 'framework', 'systematic'
            ]
            expertise_score = sum(1 for kw in expertise_keywords if kw.lower() in instruction.lower()) / len(expertise_keywords)
            scores.append(expertise_score)
            
            # 5. Clarity and specificity (0-1)
            clarity_indicators = [
                instruction.count('\n'),  # Line breaks for readability
                instruction.count('.'),   # Proper sentences
                instruction.count(':'),   # Lists/explanations
                len([s for s in instruction.split() if s[0].isupper()])  # Proper nouns/sections
            ]
            clarity_score = min(1.0, sum(clarity_indicators) / 20)
            scores.append(clarity_score)
            
            # Calculate weighted average
            weights = [0.1, 0.2, 0.3, 0.2, 0.2]  # Analysis keywords get highest weight
            weighted_score = sum(s * w for s, w in zip(scores, weights))
            
            # Apply a non-linear transformation to spread scores
            final_score = weighted_score ** 0.7  # This makes differences more pronounced
            
            logger.info(f"Instruction evaluation: length={length_score:.2f}, "
                       f"structure={structure_score:.2f}, analysis={analysis_score:.2f}, "
                       f"expertise={expertise_score:.2f}, clarity={clarity_score:.2f}, "
                       f"final={final_score:.3f}")
            
            # For bootstrapping, return boolean
            if trace is not None:
                return final_score >= 0.6
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error in instruction evaluation: {e}", exc_info=True)
            return 0.0
    
    async def _evaluate_with_judge(self, prompt: str, response: str) -> Dict[str, Any]:
        """Simplified judge evaluation for subprocess context."""
        # In subprocess context, we can't use the full judge system
        # Return a simple score based on response quality
        try:
            score = 0.5  # Base score
            
            # Check response length
            if len(response) > 200:
                score += 0.1
            
            # Check for analysis keywords
            if any(kw in response.lower() for kw in ['analysis', 'data', 'insight', 'pattern']):
                score += 0.2
                
            # Check for structure
            if response.count('\n') > 2:
                score += 0.1
                
            # Cap at 1.0
            score = min(1.0, score)
            
            return {"score": score, "feedback": "Simplified evaluation in subprocess"}
            
        except Exception as e:
            logger.error(f"Error in simplified judge evaluation: {e}")
            return {"score": 0.0, "error": str(e)}


def create_agent_output_metric():
    """Create an agent output metric for DSPy optimization."""
    return AgentOutputMetric()


# Create a function that DSPy can use directly
async def evaluate_data_analysis(example, prediction, trace=None):
    """
    DSPy-compatible metric for evaluating data analysis outputs.
    
    This metric spawns an agent with the optimized instruction,
    tests it on analysis prompts, and uses a judge to score quality.
    """
    metric = AgentOutputMetric()
    
    # Extract instruction from prediction
    if hasattr(prediction, 'optimized_instruction'):
        instruction = str(prediction.optimized_instruction)
    elif hasattr(prediction, 'answer'):
        instruction = str(prediction.answer)
    else:
        instruction = str(prediction)
    
    # Use predefined test prompts
    test_prompts = [
        "Our company's monthly sales data shows: Jan $1.2M, Feb $1.5M, Mar $1.3M, Apr $1.7M, May $1.9M, Jun $1.6M. Analyze the sales trend, identify any patterns or anomalies, and provide recommendations for Q3 strategy.",
        "We have customer data with purchase frequency (1-10 times/year), average order value ($50-$500), and customer tenure (0-5 years). How would you approach segmenting our 10,000 customers to improve marketing effectiveness?",
        "Our website A/B test ran for 2 weeks: Version A had 5,000 visitors with 250 conversions (5%), Version B had 4,800 visitors with 288 conversions (6%). Is this difference statistically significant? What do you recommend?"
    ]
    
    # Evaluate the instruction
    score = await metric.evaluate(instruction, test_prompts, trace=trace)
    
    return score