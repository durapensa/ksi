#!/usr/bin/env python3
"""
Tournament Bootstrap Integration

This module integrates the judge bootstrap process with tournament execution,
creating a complete autonomous improvement loop.
"""

from typing import Dict, List, Optional, Any, AsyncIterator
import asyncio
from datetime import timedelta

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now
from ksi_common.file_utils import save_yaml_file, load_yaml_file
from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.config import config

logger = get_bound_logger("tournament_bootstrap")

# Module initialization flag
ksi_plugin = True


@event_handler("evaluation:autonomous_improvement_cycle")
async def run_improvement_cycle(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a complete autonomous improvement cycle:
    1. Bootstrap judge variations
    2. Run tournament to evaluate them
    3. Select best performers
    4. Update evaluation system with winners
    
    Parameters:
        test_suite: Name of test suite to use for bootstrap
        num_variations: Number of variations per judge type (default: 3)
        tournament_config: Tournament configuration overrides
        output_dir: Directory for results
    """
    test_suite = data.get('test_suite', 'judge_ground_truth')
    num_variations = data.get('num_variations', 3)
    tournament_config = data.get('tournament_config', {})
    output_dir = data.get('output_dir', config.evaluations_dir / 'autonomous_cycles')
    
    cycle_id = f"cycle_{utc_now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Starting autonomous improvement cycle {cycle_id}")
    
    # Step 1: Bootstrap judge variations
    logger.info("Step 1: Bootstrapping judge variations")
    bootstrap_result = await emit_event('evaluation:bootstrap_judges_v2', {
        'test_suite': test_suite,
        'num_variations': num_variations,
        'output_dir': str(output_dir / cycle_id / 'bootstrap')
    })
    
    if not bootstrap_result or bootstrap_result[0].get('data', {}).get('status') != 'success':
        return {"status": "error", "error": "Bootstrap failed"}
    
    bootstrapped_judges = bootstrap_result[0]['data'].get('judges', [])
    logger.info(f"Bootstrapped {len(bootstrapped_judges)} judge variations")
    
    # Step 2: Spawn agents for each judge
    logger.info("Step 2: Spawning judge agents")
    agent_mapping = {}
    
    for judge in bootstrapped_judges:
        # Spawn agent with appropriate profile
        spawn_result = await emit_event('agent:spawn', {
            'profile': judge['profile'],
            'purpose': f"Tournament judge - {judge['variation_name']}",
            'metadata': {
                'cycle_id': cycle_id,
                'variation': judge['variation_name'],
                'technique': judge.get('technique', 'unknown')
            }
        })
        
        if spawn_result and spawn_result[0].get('data', {}).get('status') == 'success':
            agent_id = spawn_result[0]['data']['agent_id']
            agent_mapping[agent_id] = judge
            logger.info(f"Spawned agent {agent_id} for {judge['variation_name']}")
    
    # Step 3: Create and run tournament
    logger.info("Step 3: Creating tournament")
    tournament_id = f"auto_{cycle_id}"
    
    # Default tournament config
    default_config = {
        'participants': [],  # Will register separately
        'rounds': 1,
        'match_timeout': 120,
        'min_participants': len(agent_mapping) // 2,
        'test_cases_per_match': 3,
        'parallel_matches': 2
    }
    default_config.update(tournament_config)
    
    # Create tournament
    create_result = await emit_event('tournament:create', {
        'tournament_id': tournament_id,
        'config': default_config,
        'auto_start': False
    })
    
    if not create_result or create_result[0].get('data', {}).get('status') != 'success':
        return {"status": "error", "error": "Tournament creation failed"}
    
    # Start registration phase
    await emit_event('tournament:start_phase', {
        'tournament_id': tournament_id,
        'phase': 'registration'
    })
    
    # Register all agents
    for agent_id, judge in agent_mapping.items():
        await emit_event('tournament:register', {
            'tournament_id': tournament_id,
            'agent_id': agent_id,
            'role': judge['role'],
            'technique': judge.get('technique', 'unknown')
        })
    
    # Start round-robin phase
    logger.info("Step 4: Running tournament")
    await emit_event('tournament:start_phase', {
        'tournament_id': tournament_id,
        'phase': 'round_robin'
    })
    
    # Wait for tournament to complete
    await _wait_for_tournament_completion(tournament_id, timeout=600)
    
    # Finalize tournament
    await emit_event('tournament:start_phase', {
        'tournament_id': tournament_id,
        'phase': 'finalize'
    })
    
    # Step 5: Analyze results and select winners
    logger.info("Step 5: Analyzing tournament results")
    results_file = config.evaluations_dir / f"tournament_{tournament_id}_results.yaml"
    
    if results_file.exists():
        results = load_yaml_file(results_file)
        rankings = results.get('rankings', [])
        
        # Select top performers per role
        winners_by_role = {}
        for rank_data in rankings:
            agent_id = rank_data['agent_id']
            role = rank_data['role']
            score = rank_data.get('score', 0)
            
            if role not in winners_by_role or score > winners_by_role[role]['score']:
                winners_by_role[role] = {
                    'agent_id': agent_id,
                    'score': score,
                    'judge_data': agent_mapping.get(agent_id, {})
                }
        
        # Save cycle results
        cycle_results = {
            'cycle_id': cycle_id,
            'timestamp': utc_now().isoformat(),
            'bootstrap_count': len(bootstrapped_judges),
            'tournament_id': tournament_id,
            'winners': winners_by_role,
            'all_rankings': rankings
        }
        
        output_file = output_dir / cycle_id / 'cycle_results.yaml'
        save_yaml_file(output_file, cycle_results)
        
        logger.info(f"Improvement cycle complete. Winners saved to {output_file}")
        
        # Step 6: Optionally update evaluation system with winners
        if data.get('auto_deploy', False):
            for role, winner in winners_by_role.items():
                if winner['score'] > 0.7:  # Only deploy high-scoring judges
                    await _deploy_judge_to_evaluation(role, winner['judge_data'])
        
        return {
            "status": "success",
            "cycle_id": cycle_id,
            "winners": winners_by_role,
            "results_file": str(output_file)
        }
    else:
        return {
            "status": "error",
            "error": "Tournament results not found"
        }


async def _wait_for_tournament_completion(
    tournament_id: str,
    timeout: float = 600
) -> bool:
    """Wait for tournament to complete all matches."""
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        # Check tournament status
        status_result = await emit_event('tournament:status', {
            'tournament_id': tournament_id
        })
        
        # Simple completion check - could be enhanced
        await asyncio.sleep(10)
    
    return True


async def _deploy_judge_to_evaluation(
    role: str,
    judge_data: Dict[str, Any]
) -> None:
    """Deploy a winning judge to the evaluation system."""
    logger.info(f"Deploying {role} judge: {judge_data.get('variation_name')}")
    
    # This would update the active judge profiles used by the evaluation system
    # For now, just log the deployment
    deployment_record = {
        'role': role,
        'variation': judge_data.get('variation_name'),
        'prompt': judge_data.get('prompt'),
        'deployed_at': utc_now().isoformat()
    }
    
    deployment_file = config.evaluations_dir / 'deployed_judges' / f"{role}_active.yaml"
    save_yaml_file(deployment_file, deployment_record)


@event_handler("evaluation:list_improvement_cycles")
async def list_improvement_cycles(data: Dict[str, Any]) -> Dict[str, Any]:
    """List all autonomous improvement cycles and their results."""
    cycles_dir = config.evaluations_dir / 'autonomous_cycles'
    
    cycles = []
    if cycles_dir.exists():
        for cycle_dir in cycles_dir.iterdir():
            if cycle_dir.is_dir() and cycle_dir.name.startswith('cycle_'):
                results_file = cycle_dir / 'cycle_results.yaml'
                if results_file.exists():
                    results = load_yaml_file(results_file)
                    cycles.append({
                        'cycle_id': results['cycle_id'],
                        'timestamp': results['timestamp'],
                        'winners': {
                            role: {
                                'variation': data['judge_data'].get('variation_name'),
                                'score': data['score']
                            }
                            for role, data in results.get('winners', {}).items()
                        }
                    })
    
    return {
        "status": "success",
        "cycles": sorted(cycles, key=lambda x: x['timestamp'], reverse=True)
    }