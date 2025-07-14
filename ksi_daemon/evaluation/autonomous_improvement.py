#!/usr/bin/env python3
"""Autonomous evaluation improvement system with judge agents."""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
import yaml
from pathlib import Path

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now, timestamp_utc, filename_timestamp
from ksi_common.file_utils import save_yaml_file, load_yaml_file, ensure_directory
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler
from ksi_daemon.agent.agent_service import spawn_agent
from .prompt_iteration import PromptIterationEngine

logger = get_bound_logger("autonomous_improvement")


@dataclass
class ImprovementCycle:
    """Tracks a single improvement cycle."""
    cycle_id: str
    test_name: str
    original_prompt: str
    current_prompt: str
    iteration: int = 0
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    start_time: datetime = field(default_factory=utc_now)
    status: str = "active"  # active, converged, halted, completed


class AutonomousImprovementSystem:
    """Fully autonomous prompt improvement system using judge agents."""
    
    def __init__(self):
        self.cycles: Dict[str, ImprovementCycle] = {}
        self.constraints = self._load_constraints()
        self.judge_agents: Dict[str, str] = {}  # role -> agent_id
        self.iteration_engine = PromptIterationEngine()
        
    def _load_constraints(self) -> Dict[str, Any]:
        """Load constitutional constraints."""
        constraints_path = config.compositions_dir / "judge_constitutional_constraints.yaml"
        if constraints_path.exists():
            with open(constraints_path) as f:
                return yaml.safe_load(f)
        return {}
    
    async def start_improvement_cycle(
        self,
        test_name: str,
        test_config: Dict[str, Any],
        composition_name: str,
        human_breakpoints: List[str] = None
    ) -> str:
        """Start an autonomous improvement cycle."""
        cycle_id = f"{test_name}_{filename_timestamp()}"
        
        # Initialize cycle
        cycle = ImprovementCycle(
            cycle_id=cycle_id,
            test_name=test_name,
            original_prompt=test_config['prompt'],
            current_prompt=test_config['prompt']
        )
        self.cycles[cycle_id] = cycle
        
        # Spawn judge agents if not already running
        await self._ensure_judges_running()
        
        # Start improvement loop
        asyncio.create_task(
            self._run_improvement_loop(cycle, test_config, composition_name, human_breakpoints)
        )
        
        return cycle_id
    
    async def _ensure_judges_running(self):
        """Ensure all judge agents are spawned and ready."""
        judge_roles = ['evaluator_judge', 'analyst_judge', 'rewriter_judge', 'meta_judge']
        
        for role in judge_roles:
            if role not in self.judge_agents:
                # Spawn judge agent
                result = await spawn_agent({
                    'composition': role,
                    'composition_type': 'profile',
                    'name': f"{role}_agent"
                })
                
                if result['status'] == 'success':
                    self.judge_agents[role] = result['agent_id']
                    logger.info(f"Spawned {role}: {result['agent_id']}")
                else:
                    logger.error(f"Failed to spawn {role}: {result}")
    
    async def _run_improvement_loop(
        self,
        cycle: ImprovementCycle,
        test_config: Dict[str, Any],
        composition_name: str,
        human_breakpoints: List[str] = None
    ):
        """Run the autonomous improvement loop."""
        constraints = self.constraints.get('operational_limits', {})
        max_iterations = constraints.get('iteration_limit', {}).get('default', 10)
        improvement_threshold = constraints.get('improvement_threshold', {}).get('default', 0.05)
        
        best_score = 0.0
        consecutive_failures = 0
        
        while cycle.iteration < max_iterations and cycle.status == "active":
            cycle.iteration += 1
            logger.info(f"Cycle {cycle.cycle_id} iteration {cycle.iteration}")
            
            # Step 1: Evaluate current prompt
            eval_result = await self._evaluate_prompt(
                cycle.current_prompt,
                test_config,
                composition_name
            )
            
            current_score = eval_result['score']
            
            # Check for convergence
            if current_score >= test_config.get('success_threshold', 0.9):
                cycle.status = "converged"
                logger.info(f"Cycle {cycle.cycle_id} converged at score {current_score}")
                break
            
            # Check for improvement
            if current_score > best_score:
                improvement = current_score - best_score
                if improvement < improvement_threshold:
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                    best_score = current_score
            else:
                consecutive_failures += 1
            
            # Check divergence
            if consecutive_failures >= constraints.get('divergence_detection', {}).get('default', 3):
                cycle.status = "halted"
                reason = "Divergence detected - no improvement for multiple iterations"
                await self._trigger_human_review(cycle, reason)
                break
            
            # Step 2: Analyze failure
            analysis = await self._analyze_failure(
                cycle.current_prompt,
                eval_result,
                test_config
            )
            
            # Step 3: Check meta-judge circuit breakers
            if await self._check_circuit_breakers(cycle, analysis):
                cycle.status = "halted"
                break
            
            # Step 4: Generate improved prompt
            improved_prompt = await self._rewrite_prompt(
                cycle.current_prompt,
                analysis,
                cycle.improvements
            )
            
            # Step 5: Check human breakpoints
            if human_breakpoints and await self._should_trigger_breakpoint(
                cycle, improved_prompt, human_breakpoints
            ):
                await self._request_human_approval(cycle, improved_prompt)
                # Wait for approval (in real system, this would be async)
            
            # Update cycle
            cycle.improvements.append({
                'iteration': cycle.iteration,
                'prompt': improved_prompt,
                'score': current_score,
                'analysis': analysis,
                'timestamp': timestamp_utc()
            })
            cycle.current_prompt = improved_prompt
            
            # Update cost tracking
            cycle.total_cost += eval_result.get('cost', 0.0)
            
            # Check resource limits
            if cycle.total_cost > constraints.get('cost_budget', {}).get('default_usd', 10.0):
                cycle.status = "halted"
                await self._trigger_human_review(cycle, "Cost budget exceeded")
                break
        
        # Final evaluation
        if cycle.status == "active":
            cycle.status = "completed"
        
        await self._save_cycle_results(cycle)
    
    async def _evaluate_prompt(
        self,
        prompt: str,
        test_config: Dict[str, Any],
        composition_name: str
    ) -> Dict[str, Any]:
        """Use evaluator judge to score prompt."""
        evaluator_id = self.judge_agents.get('evaluator_judge')
        
        # Send evaluation request to judge
        eval_request = {
            'event': 'agent:message',
            'data': {
                'agent_id': evaluator_id,
                'message': f"""Evaluate this prompt's response:

Prompt: {prompt}
Expected criteria: {json.dumps(test_config.get('evaluators', []), indent=2)}

Run the evaluation and return scores."""
            }
        }
        
        # In real implementation, this would use proper agent messaging
        # For now, simulate evaluation
        return {
            'score': 0.7,  # Placeholder
            'details': {},
            'cost': 0.05
        }
    
    async def _analyze_failure(
        self,
        prompt: str,
        eval_result: Dict[str, Any],
        test_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use analyst judge to diagnose failure."""
        analyst_id = self.judge_agents.get('analyst_judge')
        
        analysis_request = {
            'prompt': prompt,
            'evaluation': eval_result,
            'expected': test_config.get('expected_format', ''),
            'criteria': test_config.get('evaluators', [])
        }
        
        # Simulate analysis
        return {
            'failure_type': 'format_mismatch',
            'root_cause': 'Missing explicit bracket instruction',
            'improvement_suggestions': [
                'Add explicit bracket formatting',
                'Provide examples',
                'Use step-by-step instructions'
            ]
        }
    
    async def _rewrite_prompt(
        self,
        current_prompt: str,
        analysis: Dict[str, Any],
        history: List[Dict[str, Any]]
    ) -> str:
        """Use rewriter judge to create improved prompt."""
        rewriter_id = self.judge_agents.get('rewriter_judge')
        
        rewrite_request = {
            'current_prompt': current_prompt,
            'analysis': analysis,
            'history': history[-3:] if history else []  # Last 3 attempts
        }
        
        # Simulate rewrite
        return current_prompt + "\nIMPORTANT: Include square brackets [ ] in your answer."
    
    async def _check_circuit_breakers(
        self,
        cycle: ImprovementCycle,
        analysis: Dict[str, Any]
    ) -> bool:
        """Meta-judge checks for circuit breaker conditions."""
        meta_judge_id = self.judge_agents.get('meta_judge')
        
        check_request = {
            'cycle': {
                'id': cycle.cycle_id,
                'iteration': cycle.iteration,
                'improvements': len(cycle.improvements),
                'cost': cycle.total_cost
            },
            'analysis': analysis,
            'constraints': self.constraints
        }
        
        # Check various circuit breaker conditions
        if cycle.iteration > 5 and not cycle.improvements:
            return True  # No improvements after many iterations
        
        if cycle.total_cost > 5.0:  # Half of budget as warning
            logger.warning(f"Cycle {cycle.cycle_id} approaching cost limit")
        
        return False
    
    async def _should_trigger_breakpoint(
        self,
        cycle: ImprovementCycle,
        new_prompt: str,
        breakpoints: List[str]
    ) -> bool:
        """Check if human breakpoint should be triggered."""
        # Check configured breakpoints
        if 'every_iteration' in breakpoints:
            return True
        
        if 'significant_change' in breakpoints:
            # Check semantic similarity
            # Simplified - in real system would use embeddings
            if len(new_prompt) > len(cycle.original_prompt) * 1.5:
                return True
        
        return False
    
    async def _trigger_human_review(self, cycle: ImprovementCycle, reason: str):
        """Trigger human review of cycle."""
        logger.info(f"Human review triggered for {cycle.cycle_id}: {reason}")
        
        # Save current state for human review
        review_data = {
            'cycle_id': cycle.cycle_id,
            'reason': reason,
            'current_state': {
                'iteration': cycle.iteration,
                'current_prompt': cycle.current_prompt,
                'improvements': cycle.improvements,
                'total_cost': cycle.total_cost
            },
            'timestamp': timestamp_utc()
        }
        
        review_path = config.evaluations_dir / f"human_review_{cycle.cycle_id}.yaml"
        save_yaml_file(review_path, review_data)
    
    async def _request_human_approval(self, cycle: ImprovementCycle, new_prompt: str):
        """Request human approval for prompt change."""
        # In real system, this would pause and wait for approval
        logger.info(f"Human approval requested for {cycle.cycle_id}")
    
    async def _save_cycle_results(self, cycle: ImprovementCycle):
        """Save complete cycle results."""
        results_path = config.evaluations_dir / f"autonomous_cycle_{cycle.cycle_id}.yaml"
        
        save_yaml_file(results_path, {
            'cycle_id': cycle.cycle_id,
            'test_name': cycle.test_name,
            'status': cycle.status,
            'iterations': cycle.iteration,
            'original_prompt': cycle.original_prompt,
            'final_prompt': cycle.current_prompt,
            'improvements': cycle.improvements,
            'total_cost': cycle.total_cost,
            'duration': (utc_now() - cycle.start_time).total_seconds()
        })


@event_handler("evaluation:autonomous_improve")
async def handle_autonomous_improve(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Start autonomous improvement for a test.
    
    Parameters:
        test_name: Name of test to improve
        test_file: Test configuration file
        composition_name: Composition to test with
        human_breakpoints: List of breakpoint conditions
        max_iterations: Override default iteration limit
    """
    data = event_format_linter(raw_data, dict)
    
    test_name = data.get('test_name')
    test_file = data.get('test_file')
    composition_name = data.get('composition_name', 'base-single-agent')
    human_breakpoints = data.get('human_breakpoints', [])
    
    if not test_name or not test_file:
        return error_response("test_name and test_file required", context)
    
    # Load test configuration
    test_path = Path(test_file)
    if not test_path.is_absolute():
        test_path = config.evaluations_dir / "test_suites" / test_file
    
    try:
        with open(test_path) as f:
            test_data = yaml.safe_load(f)
    except Exception as e:
        return error_response(f"Failed to load test file: {str(e)}", context)
    
    # Find specific test
    test_config = None
    for test in test_data.get('tests', []):
        if test['name'] == test_name:
            test_config = test
            break
    
    if not test_config:
        return error_response(f"Test {test_name} not found", context)
    
    # Start autonomous improvement
    try:
        system = AutonomousImprovementSystem()
        cycle_id = await system.start_improvement_cycle(
            test_name,
            test_config,
            composition_name,
            human_breakpoints
        )
        
        return event_response_builder({
            "cycle_id": cycle_id,
            "message": f"Started autonomous improvement cycle {cycle_id}"
        }, context)
    except Exception as e:
        return error_response(f"Failed to start improvement cycle: {str(e)}", context)


@event_handler("evaluation:cycle_status")
async def handle_cycle_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get status of an improvement cycle."""
    cycle_id = data.get('cycle_id')
    
    if not cycle_id:
        return {"status": "error", "error": "cycle_id required"}
    
    # In real implementation, would look up cycle status
    return {
        "status": "success",
        "cycle_status": "active",
        "iteration": 3,
        "current_score": 0.75
    }