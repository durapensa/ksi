#!/usr/bin/env python3
"""Bootstrap protocol for creating high-quality judge agents - Version 2.
This version leverages existing KSI capabilities instead of requiring new features.
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
import yaml
from pathlib import Path

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, emit_event
from ksi_client import EventClient

logger = get_bound_logger("judge_bootstrap_v2")


@dataclass
class JudgeVariation:
    """A judge variation created using dynamic composition."""
    variation_id: str
    role: str  # evaluator, analyst, rewriter, meta
    base_profile: str
    technique: str
    technique_description: str
    composition_name: str  # Dynamic composition name
    agent_id: Optional[str] = None
    performance_scores: Dict[str, float] = field(default_factory=dict)
    test_results: List[Dict[str, Any]] = field(default_factory=list)


class JudgeBootstrapV2:
    """Bootstrap protocol using KSI's existing capabilities."""
    
    def __init__(self):
        self.variations: Dict[str, JudgeVariation] = {}
        self.bootstrap_dir = config.evaluations_dir / "judge_bootstrap"
        self.bootstrap_dir.mkdir(exist_ok=True)
        self.schemas_dir = config.evaluations_dir / "judge_schemas"
        
        # Message response schemas for structured communication
        self.response_schemas = self._load_response_schemas()
        
    def _load_response_schemas(self) -> Dict[str, Any]:
        """Load judge response schemas for structured messaging."""
        schemas = {}
        
        # Define response schemas for each judge type
        evaluator_response = {
            "type": "object",
            "required": ["action", "result"],
            "properties": {
                "action": {"const": "evaluation_complete"},
                "result": {
                    "type": "object",
                    "required": ["overall_score", "criteria_scores", "reasoning"],
                    "properties": {
                        "overall_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "criteria_scores": {"type": "object"},
                        "reasoning": {"type": "string"}
                    }
                }
            }
        }
        
        schemas['evaluator_response'] = evaluator_response
        
        # Save schemas to files for reference
        for name, schema in schemas.items():
            schema_file = self.schemas_dir / f"{name}_schema.yaml"
            with open(schema_file, 'w') as f:
                yaml.dump(schema, f)
        
        return schemas
    
    async def create_judge_variation(
        self,
        role: str,
        technique: str,
        technique_config: Dict[str, Any]
    ) -> JudgeVariation:
        """Create a judge variation using dynamic composition."""
        
        # Load base judge profile
        base_profile = f"{role}_judge"
        base_composition = await self._get_composition(base_profile)
        
        if not base_composition:
            raise ValueError(f"Base profile {base_profile} not found")
        
        # Create variation name
        variation_name = f"{role}_judge_{technique}"
        
        # Build dynamic composition with prompt variation
        dynamic_composition = {
            'name': variation_name,
            'type': 'profile',
            'extends': base_profile,
            'description': f"{role} judge with {technique} technique",
            'author': 'bootstrap_system',
            'metadata': {
                'bootstrap_variation': True,
                'technique': technique,
                'created': datetime.utcnow().isoformat()
            },
            'prompt': base_composition.get('prompt', '') + '\n\n' + technique_config['prompt_suffix']
        }
        
        # Copy other important fields from base
        for field in ['model', 'capabilities', 'tools']:
            if field in base_composition:
                dynamic_composition[field] = base_composition[field]
        
        # Create the dynamic composition
        result = await emit_event('composition:create', dynamic_composition)
        
        if result.get('status') != 'success':
            raise RuntimeError(f"Failed to create composition: {result}")
        
        # Create variation record
        variation = JudgeVariation(
            variation_id=f"{role}_{technique}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            role=role,
            base_profile=base_profile,
            technique=technique,
            technique_description=technique_config['description'],
            composition_name=variation_name
        )
        
        self.variations[variation.variation_id] = variation
        logger.info(f"Created judge variation: {variation_name}")
        
        return variation
    
    async def _get_composition(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a composition definition."""
        result = await emit_event('composition:get', {
            'name': name,
            'type': 'profile'
        })
        
        if result.get('status') == 'success':
            return result.get('composition')
        return None
    
    async def spawn_judge_variation(self, variation: JudgeVariation) -> str:
        """Spawn an agent for a judge variation."""
        
        # Spawn agent using the dynamic composition
        result = await emit_event('agent:spawn', {
            'composition': variation.composition_name,
            'composition_type': 'profile',
            'name': f"{variation.role}_bootstrap_{variation.technique}"
        })
        
        if result.get('status') != 'success':
            raise RuntimeError(f"Failed to spawn agent: {result}")
        
        agent_id = result['agent_id']
        variation.agent_id = agent_id
        
        logger.info(f"Spawned judge agent {agent_id} for variation {variation.variation_id}")
        return agent_id
    
    async def evaluate_with_ground_truth(
        self,
        variation: JudgeVariation,
        ground_truth_cases: List[Dict[str, Any]]
    ) -> float:
        """Evaluate a judge variation against ground truth using structured messaging."""
        
        if not variation.agent_id:
            await self.spawn_judge_variation(variation)
        
        total_score = 0.0
        case_count = 0
        
        for case in ground_truth_cases:
            if case['type'] != variation.role and case['type'] != 'general':
                continue
            
            # Send structured evaluation request
            message = {
                'action': f'{variation.role}_evaluate',
                'request_id': f"bootstrap_{case['id']}",
                'data': case['input'],
                'expected_schema': f'{variation.role}_response'
            }
            
            # Send message and await response
            response = await emit_event('agent:send_message', {
                'agent_id': variation.agent_id,
                'message': message
            })
            
            # Evaluate response against expected output
            score = self._score_response(response, case['expected_output'], case['rubric'])
            
            variation.test_results.append({
                'case_id': case['id'],
                'score': score,
                'response': response,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            total_score += score
            case_count += 1
        
        avg_score = total_score / case_count if case_count > 0 else 0.0
        variation.performance_scores['ground_truth'] = avg_score
        
        return avg_score
    
    def _score_response(
        self,
        response: Dict[str, Any],
        expected: Dict[str, Any],
        rubric: Dict[str, float]
    ) -> float:
        """Score a response against expected output using rubric."""
        
        total_score = 0.0
        total_weight = 0.0
        
        for criterion, weight in rubric.items():
            criterion_score = 0.0
            
            if criterion == 'format_compliance':
                # Check if response follows expected structure
                if self._check_response_structure(response, expected):
                    criterion_score = 1.0
                    
            elif criterion == 'accuracy':
                # Check if key values match
                if self._check_value_accuracy(response, expected):
                    criterion_score = 1.0
                    
            elif criterion == 'completeness':
                # Check if all expected fields are present
                if self._check_completeness(response, expected):
                    criterion_score = 1.0
            
            total_score += criterion_score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _check_response_structure(self, response: Dict, expected: Dict) -> bool:
        """Check if response follows expected structure."""
        # Simplified check - in real implementation would be more sophisticated
        return all(key in response for key in expected.keys())
    
    def _check_value_accuracy(self, response: Dict, expected: Dict) -> bool:
        """Check if values match expected."""
        # Check key values for accuracy
        for key, expected_value in expected.items():
            if key in response:
                if isinstance(expected_value, (int, float)):
                    # Numeric comparison with tolerance
                    if abs(response[key] - expected_value) > 0.1:
                        return False
                elif response[key] != expected_value:
                    return False
        return True
    
    def _check_completeness(self, response: Dict, expected: Dict) -> bool:
        """Check if response is complete."""
        return all(key in response for key in expected.keys())
    
    async def run_tournament_round(
        self,
        evaluator_variations: List[JudgeVariation],
        target_variations: List[JudgeVariation]
    ) -> Dict[str, Any]:
        """Run a tournament round where evaluators judge targets."""
        
        tournament_results = {
            'round_id': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
            'evaluations': []
        }
        
        for evaluator in evaluator_variations:
            if not evaluator.agent_id:
                await self.spawn_judge_variation(evaluator)
            
            for target in target_variations:
                if evaluator.variation_id == target.variation_id:
                    continue
                
                # Create evaluation task
                eval_task = {
                    'action': 'evaluate_peer',
                    'target_judge': {
                        'id': target.variation_id,
                        'role': target.role,
                        'technique': target.technique
                    },
                    'test_scenario': self._create_test_scenario(target.role)
                }
                
                # Send to evaluator
                response = await emit_event('agent:send_message', {
                    'agent_id': evaluator.agent_id,
                    'message': eval_task
                })
                
                tournament_results['evaluations'].append({
                    'evaluator': evaluator.variation_id,
                    'target': target.variation_id,
                    'response': response,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return tournament_results
    
    def _create_test_scenario(self, role: str) -> Dict[str, Any]:
        """Create a test scenario for a specific judge role."""
        scenarios = {
            'evaluator': {
                'prompt': 'What is 2+2?',
                'response': '4',
                'expected_evaluation': {'accuracy': 1.0, 'format': 0.5}
            },
            'analyst': {
                'failure': 'Missing format',
                'expected_analysis': {'root_cause': 'No format specified'}
            },
            'rewriter': {
                'prompt': 'Name a color',
                'issue': 'Too vague',
                'expected_improvement': 'Specify format and constraints'
            }
        }
        return scenarios.get(role, scenarios['evaluator'])
    
    async def select_best_variations(self) -> Dict[str, JudgeVariation]:
        """Select the best variation for each role based on performance."""
        best_by_role = {}
        
        # Group by role
        roles = {}
        for variation in self.variations.values():
            if variation.role not in roles:
                roles[variation.role] = []
            roles[variation.role].append(variation)
        
        # Select best for each role
        for role, variations in roles.items():
            # Sort by overall performance
            variations.sort(
                key=lambda v: sum(v.performance_scores.values()) / len(v.performance_scores) if v.performance_scores else 0,
                reverse=True
            )
            
            if variations:
                best_by_role[role] = variations[0]
                logger.info(f"Selected {variations[0].technique} technique for {role} role")
        
        return best_by_role
    
    async def save_bootstrap_results(self, selected_judges: Dict[str, JudgeVariation]):
        """Save bootstrap results and selected judge configurations."""
        
        # Save results
        results = {
            'bootstrap_run': datetime.utcnow().isoformat(),
            'variations_tested': len(self.variations),
            'selected_judges': {},
            'all_variations': []
        }
        
        # Selected judges
        for role, variation in selected_judges.items():
            results['selected_judges'][role] = {
                'variation_id': variation.variation_id,
                'technique': variation.technique,
                'composition_name': variation.composition_name,
                'performance_scores': variation.performance_scores,
                'agent_id': variation.agent_id
            }
            
            # Save the composition to disk for future use
            await emit_event('composition:save', {
                'name': variation.composition_name,
                'type': 'profile',
                'overwrite': True
            })
        
        # All variations for analysis
        for variation in self.variations.values():
            results['all_variations'].append({
                'variation_id': variation.variation_id,
                'role': variation.role,
                'technique': variation.technique,
                'scores': variation.performance_scores
            })
        
        # Save to file
        results_file = self.bootstrap_dir / f"bootstrap_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.yaml"
        with open(results_file, 'w') as f:
            yaml.dump(results, f)
        
        logger.info(f"Bootstrap results saved to {results_file}")
        return results


# Define judge variation techniques
JUDGE_TECHNIQUES = {
    'evaluator': [
        {
            'name': 'detailed_rubric',
            'description': 'Emphasizes detailed scoring rubrics',
            'prompt_suffix': """
When evaluating responses, always:
1. Break down evaluation into specific criteria
2. Assign individual scores to each criterion
3. Provide detailed reasoning for each score
4. Calculate weighted overall score
5. Include specific examples from the response"""
        },
        {
            'name': 'pattern_focused',
            'description': 'Focuses on pattern matching and format compliance',
            'prompt_suffix': """
Pay special attention to:
- Exact format compliance with specifications
- Pattern matching accuracy
- Structural consistency
- Missing or extra elements
Be precise about what patterns were expected vs found."""
        },
        {
            'name': 'holistic_quality',
            'description': 'Evaluates overall quality and effectiveness',
            'prompt_suffix': """
Consider the response holistically:
- Does it achieve the intended purpose?
- Is it clear and well-structured?
- Would a user find it helpful?
- What is the overall quality level?
Balance specific criteria with general effectiveness."""
        }
    ],
    'analyst': [
        {
            'name': 'root_cause_focus',
            'description': 'Deep root cause analysis',
            'prompt_suffix': """
When analyzing failures:
1. Identify the immediate symptom
2. Trace back to root causes
3. Consider multiple contributing factors
4. Distinguish correlation from causation
5. Provide evidence for your analysis"""
        },
        {
            'name': 'pattern_recognition',
            'description': 'Identifies failure patterns',
            'prompt_suffix': """
Look for patterns in failures:
- Common failure modes
- Systematic issues vs one-offs
- Category of failure (format, content, logic)
- Similar failures you've seen
- Predictable failure conditions"""
        }
    ],
    'rewriter': [
        {
            'name': 'incremental_improvement',
            'description': 'Makes minimal necessary changes',
            'prompt_suffix': """
When rewriting prompts:
- Make the smallest change that fixes the issue
- Preserve as much of the original as possible
- Focus on the specific problem identified
- Don't over-engineer the solution
- Maintain clarity and simplicity"""
        },
        {
            'name': 'comprehensive_restructure',
            'description': 'Willing to completely restructure',
            'prompt_suffix': """
When improving prompts:
- Consider complete restructuring if beneficial
- Use proven prompt engineering techniques
- Add examples, structure, and clarity
- Optimize for model understanding
- Create robust, foolproof instructions"""
        }
    ]
}


@event_handler("evaluation:bootstrap_judges_v2")
async def handle_bootstrap_judges_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run improved judge bootstrap protocol using KSI capabilities.
    
    Parameters:
        roles: List of judge roles to bootstrap
        techniques_per_role: Number of techniques to test per role
        run_tournament: Whether to run cross-evaluation tournament
        save_selected: Whether to save selected judges to disk
    """
    roles = data.get('roles', ['evaluator', 'analyst', 'rewriter'])
    techniques_per_role = data.get('techniques_per_role', 3)
    run_tournament = data.get('run_tournament', True)
    save_selected = data.get('save_selected', True)
    
    bootstrap = JudgeBootstrapV2()
    
    # Phase 1: Create variations using dynamic compositions
    logger.info("Phase 1: Creating judge variations")
    
    for role in roles:
        techniques = JUDGE_TECHNIQUES.get(role, [])[:techniques_per_role]
        
        for technique_config in techniques:
            try:
                variation = await bootstrap.create_judge_variation(
                    role,
                    technique_config['name'],
                    technique_config
                )
                logger.info(f"Created {role} variation: {technique_config['name']}")
            except Exception as e:
                logger.error(f"Failed to create variation: {e}")
    
    # Phase 2: Evaluate against ground truth
    logger.info("Phase 2: Evaluating against ground truth")
    
    # Load ground truth cases
    ground_truth_file = bootstrap.bootstrap_dir / "ground_truth_cases.yaml"
    if ground_truth_file.exists():
        with open(ground_truth_file) as f:
            ground_truth_data = yaml.safe_load(f)
            ground_truth_cases = ground_truth_data.get('cases', [])
    else:
        ground_truth_cases = []
        logger.warning("No ground truth cases found")
    
    # Evaluate each variation
    for variation in bootstrap.variations.values():
        try:
            score = await bootstrap.evaluate_with_ground_truth(variation, ground_truth_cases)
            logger.info(f"{variation.variation_id} ground truth score: {score:.2f}")
        except Exception as e:
            logger.error(f"Failed to evaluate {variation.variation_id}: {e}")
    
    # Phase 3: Tournament (if requested)
    if run_tournament and len(bootstrap.variations) > 1:
        logger.info("Phase 3: Running tournament")
        
        evaluator_vars = [v for v in bootstrap.variations.values() if v.role == 'evaluator']
        other_vars = [v for v in bootstrap.variations.values() if v.role != 'evaluator']
        
        if evaluator_vars and other_vars:
            tournament_results = await bootstrap.run_tournament_round(evaluator_vars, other_vars)
            logger.info(f"Tournament round complete: {len(tournament_results['evaluations'])} evaluations")
    
    # Phase 4: Select best and save
    logger.info("Phase 4: Selecting best variations")
    
    selected_judges = await bootstrap.select_best_variations()
    
    if save_selected:
        results = await bootstrap.save_bootstrap_results(selected_judges)
    
    return {
        "status": "success",
        "variations_tested": len(bootstrap.variations),
        "selected_judges": {
            role: {
                "technique": var.technique,
                "composition": var.composition_name,
                "score": sum(var.performance_scores.values()) / len(var.performance_scores) if var.performance_scores else 0
            }
            for role, var in selected_judges.items()
        }
    }