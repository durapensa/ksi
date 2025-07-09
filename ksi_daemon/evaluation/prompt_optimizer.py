#!/usr/bin/env python3
"""LLM-based prompt optimization using evaluation feedback."""

from typing import Dict, Any, List
from dataclasses import dataclass
import json

from ksi_common.logging import get_bound_logger
from .completion_utils import send_completion_and_wait

logger = get_bound_logger("prompt_optimizer")


@dataclass
class PromptOptimizationRequest:
    """Request to optimize a failing prompt."""
    original_prompt: str
    expected_format: str
    actual_response: str
    evaluator_feedback: Dict[str, Any]
    successful_examples: List[Dict[str, str]] = None


class LLMPromptOptimizer:
    """Uses LLM to generate improved prompt variations based on failures."""
    
    async def generate_variations(
        self, 
        request: PromptOptimizationRequest,
        num_variations: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate improved prompt variations using LLM analysis."""
        
        optimization_prompt = self._build_optimization_prompt(request, num_variations)
        
        result = await send_completion_and_wait(
            prompt=optimization_prompt,
            model="claude-cli/sonnet",
            agent_config={'temperature': 0.7}  # Some creativity needed
        )
        
        if result.get('status') != 'completed':
            logger.error(f"Failed to generate variations: {result.get('error')}")
            return []
        
        try:
            # Parse LLM response
            response = result.get('response', '')
            # Extract JSON from response
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0].strip()
            else:
                json_str = response
                
            variations_data = json.loads(json_str)
            return variations_data.get('variations', [])
            
        except Exception as e:
            logger.error(f"Failed to parse variations: {e}")
            return []
    
    def _build_optimization_prompt(
        self, 
        request: PromptOptimizationRequest,
        num_variations: int
    ) -> str:
        """Build prompt for LLM to analyze failure and suggest improvements."""
        
        prompt = f"""You are a prompt engineering expert. Analyze this prompt failure and generate improved variations.

ORIGINAL PROMPT:
{request.original_prompt}

EXPECTED FORMAT:
{request.expected_format}

ACTUAL RESPONSE:
{request.actual_response}

EVALUATOR FEEDBACK:
{json.dumps(request.evaluator_feedback, indent=2)}
"""

        if request.successful_examples:
            prompt += "\n\nSUCCESSFUL PROMPT EXAMPLES:\n"
            for example in request.successful_examples[:3]:
                prompt += f"\nPrompt: {example['prompt']}\nResponse: {example['response']}\nTechniques: {example.get('techniques', [])}\n"

        prompt += f"""
Based on this analysis, generate {num_variations} improved prompt variations that will achieve the expected format.

For each variation:
1. Identify WHY the original failed
2. Apply a specific technique to fix it
3. Tag the technique used

Respond with JSON:
{{
  "failure_analysis": "why the original prompt failed",
  "variations": [
    {{
      "version": "descriptive_name",
      "prompt": "the improved prompt text",
      "hypothesis": "why this should work better",
      "techniques": ["technique1", "technique2"]
    }}
  ]
}}
"""
        return prompt


class EvolutionaryPromptOptimizer:
    """Evolutionary approach to prompt optimization."""
    
    def __init__(self):
        self.population_size = 20
        self.mutation_rate = 0.2
        self.crossover_rate = 0.7
        
    async def evolve_prompts(
        self,
        base_prompt: str,
        fitness_function,  # Async function that scores a prompt
        generations: int = 10
    ) -> List[Dict[str, Any]]:
        """Evolve prompts using genetic algorithm approach."""
        
        # Initialize population with variations
        population = await self._initialize_population(base_prompt)
        
        for generation in range(generations):
            # Evaluate fitness
            for individual in population:
                individual['fitness'] = await fitness_function(individual['prompt'])
            
            # Sort by fitness
            population.sort(key=lambda x: x['fitness'], reverse=True)
            
            # Select top performers
            survivors = population[:self.population_size // 2]
            
            # Generate new population
            new_population = survivors.copy()
            
            # Crossover
            while len(new_population) < self.population_size - 2:
                parent1 = survivors[0]  # Best performer
                parent2 = survivors[1 + (len(new_population) % (len(survivors) - 1))]
                child = await self._crossover(parent1, parent2)
                new_population.append(child)
            
            # Mutation
            for individual in new_population[len(survivors):]:
                if self.mutation_rate > 0.5:  # Random chance
                    individual = await self._mutate(individual)
            
            population = new_population
            
            logger.info(f"Generation {generation + 1}: Best fitness = {population[0]['fitness']}")
        
        return population[:5]  # Return top 5
    
    async def _initialize_population(self, base_prompt: str) -> List[Dict[str, Any]]:
        """Create initial population of prompt variations."""
        # This would use LLM to generate initial variations
        optimizer = LLMPromptOptimizer()
        request = PromptOptimizationRequest(
            original_prompt=base_prompt,
            expected_format="",
            actual_response="",
            evaluator_feedback={}
        )
        
        variations = await optimizer.generate_variations(request, self.population_size)
        return [{'prompt': v['prompt'], 'fitness': 0.0} for v in variations]
    
    async def _crossover(self, parent1: Dict, parent2: Dict) -> Dict[str, Any]:
        """Combine two successful prompts."""
        # Simplified: take first half of parent1, second half of parent2
        p1_words = parent1['prompt'].split()
        p2_words = parent2['prompt'].split()
        
        midpoint = len(p1_words) // 2
        child_prompt = ' '.join(p1_words[:midpoint] + p2_words[midpoint:])
        
        return {'prompt': child_prompt, 'fitness': 0.0}
    
    async def _mutate(self, individual: Dict) -> Dict[str, Any]:
        """Apply random mutation to prompt."""
        # This would use LLM to intelligently mutate
        # For now, simplified version
        mutations = [
            "IMPORTANT: ",
            "Please ensure that ",
            "Remember to ",
            " exactly as shown",
            " (this is critical)"
        ]
        
        import random
        mutation = random.choice(mutations)
        individual['prompt'] = mutation + individual['prompt']
        
        return individual


class ReinforcementLearningOptimizer:
    """RL-based approach using evaluation scores as rewards."""
    
    async def optimize_with_feedback_loop(
        self,
        initial_prompt: str,
        evaluator_config: Dict[str, Any],
        max_iterations: int = 20
    ) -> Dict[str, Any]:
        """Iteratively improve prompt using RL principles."""
        
        prompt_history = []
        current_prompt = initial_prompt
        best_score = 0.0
        best_prompt = initial_prompt
        
        for iteration in range(max_iterations):
            # Get current performance
            score = await self._evaluate_prompt(current_prompt, evaluator_config)
            
            prompt_history.append({
                'prompt': current_prompt,
                'score': score,
                'iteration': iteration
            })
            
            if score > best_score:
                best_score = score
                best_prompt = current_prompt
            
            # Check if we've reached target
            if score >= evaluator_config.get('target_score', 0.95):
                break
            
            # Generate next prompt based on history
            current_prompt = await self._generate_next_prompt(
                prompt_history,
                evaluator_config
            )
        
        return {
            'best_prompt': best_prompt,
            'best_score': best_score,
            'iterations': len(prompt_history),
            'history': prompt_history
        }
    
    async def _evaluate_prompt(
        self, 
        prompt: str, 
        evaluator_config: Dict[str, Any]
    ) -> float:
        """Evaluate prompt performance."""
        # This would run actual evaluation
        # Placeholder for now
        return 0.0
    
    async def _generate_next_prompt(
        self,
        history: List[Dict],
        evaluator_config: Dict[str, Any]
    ) -> str:
        """Generate next prompt based on learning from history."""
        
        # Build context from history
        context = "Learning from previous attempts:\n"
        for h in history[-3:]:  # Last 3 attempts
            context += f"\nPrompt: {h['prompt'][:100]}...\nScore: {h['score']}\n"
        
        optimization_prompt = f"""{context}

Based on the scores, generate an improved prompt that addresses the weaknesses of previous attempts.
Target: {evaluator_config.get('expected_format', 'High quality output')}

Respond with just the improved prompt, no explanation."""
        
        result = await send_completion_and_wait(
            prompt=optimization_prompt,
            model="claude-cli/sonnet",
            agent_config={'temperature': 0.3}
        )
        
        return result.get('response', history[-1]['prompt'])  # Fallback to last