#!/usr/bin/env python3
"""
Simple demonstration of the autonomous judge system working on the bracket formatting problem.
This shows how judges communicate and collaborate to improve a failing prompt.
"""

import asyncio
import json
import yaml
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("judge_demo")


class JudgeSystemDemo:
    """Demonstration of judge collaboration on bracket formatting problem."""
    
    def __init__(self):
        self.schemas_dir = config.evaluations_dir / "judge_schemas"
        self.results_dir = config.evaluations_dir / "judge_demo_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Load schemas so judges understand protocols
        self.schemas = self._load_schemas()
        
        # Track the improvement cycle
        self.cycle_data = {
            'original_prompt': "What is the capital of France? Format your answer as: The capital is [CITY].",
            'iterations': [],
            'start_time': datetime.utcnow()
        }
    
    def _load_schemas(self):
        """Load all judge communication schemas."""
        schemas = {}
        for schema_file in self.schemas_dir.glob("*.yaml"):
            with open(schema_file) as f:
                schema = yaml.safe_load(f)
                schemas[schema['name']] = schema
        return schemas
    
    async def run_demo(self):
        """Run a complete improvement cycle demonstration."""
        logger.info("Starting judge system demonstration")
        
        # Iteration 1: Initial evaluation
        logger.info("\n=== ITERATION 1: Initial Evaluation ===")
        eval_result = await self.simulate_evaluator_judge(
            self.cycle_data['original_prompt'],
            "The capital is Paris."  # Missing brackets
        )
        
        # Analyst reviews the failure
        logger.info("\n=== Analyst Judge Reviews Failure ===")
        analysis = await self.simulate_analyst_judge(eval_result)
        
        # Rewriter creates improved prompt
        logger.info("\n=== Rewriter Judge Creates Improvement ===")
        improved_prompt_v1 = await self.simulate_rewriter_judge(
            self.cycle_data['original_prompt'],
            analysis
        )
        
        # Adversarial tests the improvement
        logger.info("\n=== Adversarial Judge Tests Edge Cases ===")
        adversarial_results = await self.simulate_adversarial_judge(improved_prompt_v1)
        
        # Meta-judge reviews progress
        logger.info("\n=== Meta-Judge Reviews System State ===")
        meta_decision = await self.simulate_meta_judge({
            'iteration': 1,
            'cost_so_far': 0.15,
            'improvement': 0.0,
            'adversarial_findings': adversarial_results
        })
        
        # Store iteration results
        self.cycle_data['iterations'].append({
            'iteration': 1,
            'prompt': self.cycle_data['original_prompt'],
            'score': eval_result['evaluation_results']['overall_score'],
            'improved_prompt': improved_prompt_v1,
            'meta_decision': meta_decision['decision']['action']
        })
        
        if meta_decision['decision']['action'] == 'continue':
            # Iteration 2: Test improved prompt
            logger.info("\n=== ITERATION 2: Testing Improved Prompt ===")
            eval_result_v2 = await self.simulate_evaluator_judge(
                improved_prompt_v1,
                "The capital is [Paris]"  # With brackets!
            )
            
            self.cycle_data['iterations'].append({
                'iteration': 2,
                'prompt': improved_prompt_v1,
                'score': eval_result_v2['evaluation_results']['overall_score'],
                'meta_decision': 'success'
            })
        
        # Save demonstration results
        await self.save_demo_results()
        
    async def simulate_evaluator_judge(self, prompt, response):
        """Simulate evaluator judge scoring a response."""
        # Check if response has brackets
        has_brackets = '[' in response and ']' in response
        format_score = 1.0 if has_brackets else 0.0
        
        # Build message following schema
        message = {
            'metadata': {
                'sender_role': 'evaluator',
                'pipeline_stage': 'evaluation_complete',
                'urgency': 'high' if format_score == 0 else 'low',
                'timestamp': datetime.utcnow().isoformat(),
                'correlation_id': 'demo_001'
            },
            'evaluation_results': {
                'overall_score': format_score * 0.5 + 0.5,  # 50% weight on format
                'criteria_scores': {
                    'format_compliance': format_score,
                    'factual_accuracy': 1.0,
                    'clarity': 0.9
                },
                'failed_criteria': ['format_compliance'] if format_score == 0 else [],
                'success_threshold': 0.8
            },
            'context': {
                'original_prompt': prompt,
                'actual_response': response,
                'expected_patterns': {
                    'format': 'The capital is [CITY]',
                    'content': ['Paris']
                }
            },
            'analysis_hints': {
                'evaluator_hypothesis': 'Model ignored bracket formatting requirement' if format_score == 0 else 'Format correctly followed',
                'pattern_observations': [
                    'Content is correct (Paris)',
                    f'Brackets {"missing" if format_score == 0 else "present"}'
                ]
            }
        }
        
        logger.info(f"Evaluator: Score = {message['evaluation_results']['overall_score']}")
        logger.info(f"Evaluator: Failed criteria = {message['evaluation_results']['failed_criteria']}")
        
        return message
    
    async def simulate_analyst_judge(self, eval_message):
        """Simulate analyst judge diagnosing the failure."""
        # Analyze based on evaluation results
        failure_analysis = {
            'metadata': {
                'sender_role': 'analyst',
                'pipeline_stage': 'analysis_complete',
                'rewrite_urgency': 'high',
                'timestamp': datetime.utcnow().isoformat()
            },
            'failure_analysis': {
                'root_cause': 'Model ignoring bracket formatting despite clear instruction',
                'failure_category': 'format',
                'confidence': 0.95,
                'evidence': [
                    'Content accuracy: 100% (correctly identified Paris)',
                    'Format compliance: 0% (missing required brackets)',
                    'Pattern: Models often ignore single-line format instructions'
                ]
            },
            'improvement_recommendations': {
                'primary_strategy': {
                    'technique': 'explicit_example_driven',
                    'rationale': 'Concrete examples dramatically improve format compliance'
                },
                'alternative_strategies': [
                    {
                        'technique': 'step_by_step_breakdown',
                        'rationale': 'Forces model to consider each formatting element'
                    }
                ],
                'techniques_to_avoid': [
                    {
                        'technique': 'single_line_instruction',
                        'reason': 'Current approach - demonstrated 0% success'
                    }
                ]
            },
            'context_preservation': {
                'original_intent': 'Get capital city name formatted with brackets',
                'critical_elements': [
                    'Must ask for capital of France',
                    'Must require bracket formatting'
                ],
                'flexibility_areas': [
                    'Can add examples',
                    'Can restructure instructions'
                ]
            }
        }
        
        logger.info(f"Analyst: Root cause = {failure_analysis['failure_analysis']['root_cause']}")
        logger.info(f"Analyst: Recommended technique = {failure_analysis['improvement_recommendations']['primary_strategy']['technique']}")
        
        return failure_analysis
    
    async def simulate_rewriter_judge(self, original_prompt, analysis):
        """Simulate rewriter judge creating improved prompt."""
        technique = analysis['improvement_recommendations']['primary_strategy']['technique']
        
        if technique == 'explicit_example_driven':
            improved_prompt = """What is the capital of France?

Format your answer EXACTLY as shown in this example:
Example: The capital is [London]

Your answer should follow the same pattern with the correct city for France."""
        else:
            improved_prompt = original_prompt + "\nIMPORTANT: You must include square brackets [ ] around the city name."
        
        logger.info(f"Rewriter: Applied technique = {technique}")
        logger.info(f"Rewriter: New prompt = {improved_prompt[:100]}...")
        
        return improved_prompt
    
    async def simulate_adversarial_judge(self, prompt):
        """Simulate adversarial judge finding edge cases."""
        challenges = []
        
        # Test 1: Brackets in question
        if '[' in prompt and 'example' not in prompt.lower():
            challenges.append({
                'challenge': 'ambiguous_brackets',
                'severity': 'medium',
                'description': 'Multiple brackets could confuse which to replace'
            })
        
        # Test 2: Could be gamed
        if 'exactly' not in prompt.lower():
            challenges.append({
                'challenge': 'gaming_potential',
                'severity': 'low',
                'description': 'Could output extra text beyond format'
            })
        
        logger.info(f"Adversarial: Found {len(challenges)} potential issues")
        for challenge in challenges:
            logger.info(f"  - {challenge['challenge']} (severity: {challenge['severity']})")
        
        return challenges
    
    async def simulate_meta_judge(self, system_state):
        """Simulate meta-judge oversight decision."""
        decision = {
            'decision': {
                'action': 'continue',
                'authoritative': True
            },
            'circuit_breaker_triggered': False,
            'constraints_status': {
                'all_satisfied': True,
                'warnings': [],
                'violations': []
            },
            'reasoning': 'System operating within parameters, improvement likely'
        }
        
        # Check for issues
        if system_state['cost_so_far'] > 5.0:
            decision['decision']['action'] = 'pause'
            decision['constraints_status']['warnings'].append('Approaching cost limit')
        
        if system_state['iteration'] > 10 and system_state['improvement'] < 0.1:
            decision['decision']['action'] = 'halt'
            decision['reasoning'] = 'No significant improvement after many iterations'
        
        logger.info(f"Meta-Judge: Decision = {decision['decision']['action']}")
        logger.info(f"Meta-Judge: Reasoning = {decision['reasoning']}")
        
        return decision
    
    async def save_demo_results(self):
        """Save demonstration results."""
        results_file = self.results_dir / f"demo_run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.yaml"
        
        with open(results_file, 'w') as f:
            yaml.dump({
                'demo_type': 'bracket_formatting_improvement',
                'original_prompt': self.cycle_data['original_prompt'],
                'iterations': self.cycle_data['iterations'],
                'final_score': self.cycle_data['iterations'][-1]['score'] if self.cycle_data['iterations'] else 0,
                'duration_seconds': (datetime.utcnow() - self.cycle_data['start_time']).total_seconds()
            }, f)
        
        logger.info(f"\nDemo results saved to: {results_file}")
        
        # Print summary
        print("\n=== DEMONSTRATION SUMMARY ===")
        print(f"Original Score: {self.cycle_data['iterations'][0]['score']}")
        if len(self.cycle_data['iterations']) > 1:
            print(f"Final Score: {self.cycle_data['iterations'][-1]['score']}")
            print(f"Improvement: {self.cycle_data['iterations'][-1]['score'] - self.cycle_data['iterations'][0]['score']}")
        print(f"Iterations: {len(self.cycle_data['iterations'])}")


async def main():
    """Run the demonstration."""
    demo = JudgeSystemDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())